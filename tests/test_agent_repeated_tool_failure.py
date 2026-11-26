"""Regression: the repeated-tool-failure breaker stops a doomed retry loop.

An unwritable workspace (or any broken path/permission) makes the model retry
the same operation at a different path every round. The existing stall
detector only trips on IDENTICAL repeated calls, so it never fires. This
breaker keys on tool + normalized error (paths/numbers collapsed) and stops
after three identical failures, with a visible, actionable message.
"""

import asyncio
import json

import src.agent_loop as al


def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def _types(chunks):
    out = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                out.append(json.loads(c[6:]))
            except Exception:
                pass
    return out


def _tool_call(cmd):
    return "data: " + json.dumps({
        "type": "tool_calls",
        "calls": [{"name": "bash", "arguments": json.dumps({"command": cmd})}],
    }) + "\n\n"


def _patch_common(monkeypatch, exec_results):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    calls = {"n": 0}

    async def _fake_exec(block, *a, **k):
        idx = calls["n"]
        calls["n"] += 1
        result = exec_results[min(idx, len(exec_results) - 1)]
        return ("bash", result)

    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)


def _run_loop(monkeypatch, *, max_rounds, exec_results):
    _patch_common(monkeypatch, exec_results)
    round_no = {"n": 0}

    async def _fake_stream(_candidates, messages, **kwargs):
        round_no["n"] += 1
        # Distinct command each round so the stall detector (identical calls)
        # does not fire; only the repeated-failure breaker should trip.
        yield _tool_call(f"echo attempt {round_no['n']}")
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "https://api.openai.com/v1", "m",
        [{"role": "user", "content": "write the files"}],
        max_rounds=max_rounds,
        relevant_tools={"bash"},
    )
    return _types(_collect(gen))


def test_repeated_same_error_trips_breaker(monkeypatch):
    # Same failure at a different path each round: paths/numbers normalize to
    # one signature, so the third failure trips the breaker.
    events = _run_loop(
        monkeypatch,
        max_rounds=6,
        exec_results=[
            {"error": "No such file or directory: C:\\work\\index.html", "exit_code": 1}
        ] * 6,
    )

    guard = next(
        (e for e in events if e.get("type") == "loop_breaker_triggered"), None
    )
    assert guard is not None, events
    assert guard["reason"] == "repeated_tool_failure"

    deltas = "".join(e.get("delta", "") for e in events if "delta" in e)
    assert "Stopped after repeated tool failures" in deltas, events
    assert "writable workspace" in deltas, events


def test_success_resets_failure_streak(monkeypatch):
    # fail, fail, success, fail, fail — the success clears the streak, so the
    # breaker must not trip.
    events = _run_loop(
        monkeypatch,
        max_rounds=5,
        exec_results=[
            {"error": "No such file or directory: C:\\work\\a", "exit_code": 1},
            {"error": "No such file or directory: C:\\work\\b", "exit_code": 1},
            {"output": "ok", "exit_code": 0},
            {"error": "No such file or directory: C:\\work\\c", "exit_code": 1},
            {"error": "No such file or directory: C:\\work\\d", "exit_code": 1},
        ],
    )

    assert not any(
        e.get("type") == "loop_breaker_triggered"
        and e.get("reason") == "repeated_tool_failure"
        for e in events
    ), events


def test_policy_denials_do_not_count_as_environment_failures(monkeypatch):
    events = _run_loop(
        monkeypatch,
        max_rounds=4,
        exec_results=[{"blocked": True, "error": "Denied by policy", "exit_code": 1}],
    )
    assert not any(
        e.get("type") == "loop_breaker_triggered"
        and e.get("reason") == "repeated_tool_failure"
        for e in events
    )
