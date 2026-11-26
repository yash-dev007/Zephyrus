"""Regression: a tool-only reasoning model must still stream a final answer.

Some providers (e.g. deepseek-v4-flash on Sarvam) route every round's tokens
to ``reasoning_content`` + native tool calls and never emit user-visible
content. The agent loop then burns its whole round budget and the route
persists a bare "Done." — the user sees only a thinking indicator until the
turn ends. When the loop exhausts its rounds after doing effectful work, it
now runs one tool-free answer round and streams that summary live.
"""

import asyncio
import json

import src.agent_loop as al


# A native tool-call event with no assistant text, matching what a tool-only
# reasoning model emits every round.
_TOOL_CALL_EVENT = "data: " + json.dumps({
    "type": "tool_calls",
    "calls": [{"name": "bash", "arguments": json.dumps({"command": "echo hi"})}],
}) + "\n\n"


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


def _patch_common(monkeypatch):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_exec(block, *a, **k):
        return ("bash", {"output": "ok", "exit_code": 0})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)


def _run_loop(monkeypatch, *, max_rounds=2, final_text="Here is the summary."):
    calls = []

    async def _fake_stream(_candidates, messages, **kwargs):
        calls.append(kwargs)
        if kwargs.get("tools") is None:
            # Tool-free final-answer round.
            yield f'data: {json.dumps({"delta": final_text})}\n\n'
        else:
            # Every normal round is a native tool call with no assistant text.
            yield _TOOL_CALL_EVENT
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    # Use a known API host so the loop sends native tool schemas (tools=[...])
    # on normal rounds; the final-answer call is the one with tools=None.
    gen = al.stream_agent_loop(
        "https://api.openai.com/v1", "m",
        [{"role": "user", "content": "do a long multi-step task"}],
        max_rounds=max_rounds,
        relevant_tools={"bash"},
    )
    return _types(_collect(gen)), calls


def test_streams_final_answer_after_round_cap(monkeypatch):
    _patch_common(monkeypatch)
    events, calls = _run_loop(monkeypatch, max_rounds=2)

    # The cap still surfaces so the client can offer Continue.
    assert any(e.get("type") == "rounds_exhausted" for e in events), events

    # The tool-free answer round ran and its text streamed as a normal delta.
    assert any(c.get("tools") is None for c in calls), calls
    deltas = "".join(e.get("delta", "") for e in events if "delta" in e)
    assert "Here is the summary." in deltas, events


def test_no_final_answer_round_when_model_already_answered(monkeypatch):
    _patch_common(monkeypatch)

    async def _fake_stream(_candidates, messages, **kwargs):
        yield f'data: {json.dumps({"delta": "All done, here is your answer."})}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "https://api.openai.com/v1", "m",
        [{"role": "user", "content": "answer me"}],
        max_rounds=2,
        relevant_tools={"bash"},
    )
    events = _types(_collect(gen))

    assert not any(e.get("type") == "rounds_exhausted" for e in events), events
    assert any("All done" in e.get("delta", "") for e in events), events


def test_final_answer_falls_back_when_model_still_writes_nothing(monkeypatch):
    _patch_common(monkeypatch)

    async def _fake_stream(_candidates, messages, **kwargs):
        if kwargs.get("tools") is None:
            # Model still emits only reasoning, no visible content.
            yield f'data: {json.dumps({"delta": "thinking...", "thinking": True})}\n\n'
        else:
            yield _TOOL_CALL_EVENT
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "https://api.openai.com/v1", "m",
        [{"role": "user", "content": "do a long multi-step task"}],
        max_rounds=2,
        relevant_tools={"bash"},
    )
    events = _types(_collect(gen))

    deltas = "".join(e.get("delta", "") for e in events if "delta" in e)
    assert "couldn't produce a clean summary" in deltas, events
