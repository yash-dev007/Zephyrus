"""Failure recovery must preserve execution and authorization boundaries."""
import asyncio
import json

import pytest

import src.agent_loop as al
import src.teacher_escalation as teacher
from src.tool_execution import format_tool_result
from src.tool_policy import build_effective_tool_policy


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("error", [
    'event: error\ndata: {"error": "connection lost"}\n\n',
    'data: {"error": "connection lost"}\n\n',
])
def test_failed_generation_never_executes_collected_calls(monkeypatch, native, error):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10)
    executions = []
    takeovers = []

    async def execute(*args, **kwargs):
        executions.append(args)
        return "bash", {"output": "ran", "exit_code": 0}

    async def takeover(**kwargs):
        takeovers.append(kwargs)
        if False:
            yield ""

    async def stream(*args, **kwargs):
        payload = ({"type": "tool_calls", "calls": [
            {"id": "call_1", "name": "bash", "arguments": '{"command":"echo unsafe"}'}
        ]} if native else {"delta": "```bash\necho unsafe\n```"})
        yield "data: " + json.dumps(payload) + "\n\n"
        yield error
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "execute_tool_block", execute)
    monkeypatch.setattr(al, "stream_llm_with_fallback", stream)
    monkeypatch.setattr(teacher, "run_teacher_inline", takeover)

    async def run():
        return [chunk async for chunk in al.stream_agent_loop(
            "https://api.openai.com/v1", "gpt-4o",
            [{"role": "user", "content": "run echo unsafe"}],
            relevant_tools={"bash"}, max_rounds=1,
        )]

    chunks = asyncio.run(run())
    assert not executions
    assert not takeovers
    assert not any('"type": "tool_start"' in chunk for chunk in chunks)
    assert any("No tools from this round were executed" in chunk for chunk in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"


@pytest.mark.parametrize("payload", [
    {"stdout": "partial"}, {"output": "partial"}, {"content": "partial"},
    {"results": "partial"}, {"response": "partial"},
])
def test_partial_tool_output_does_not_hide_error(payload):
    formatted = format_tool_result("action", {**payload, "error": "timed out"})
    assert "partial" in formatted
    assert "timed out" in formatted


def test_generic_success_is_not_assumed_to_be_file_write():
    assert "Success" in format_tool_result("action", {"success": True})


@pytest.mark.parametrize("budget", [1, 2])
def test_outer_loop_handoff_preserves_policy_and_remaining_budget(monkeypatch, budget):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10)
    captured = []
    rounds = []
    policy = build_effective_tool_policy(disabled_tools={"bash"})

    async def stream(*args, **kwargs):
        rounds.append(True)
        payload = ({"type": "tool_calls", "calls": [{"id": "a", "name": "read_file",
                    "arguments": '{"path":"missing.txt"}'}]} if len(rounds) == 1
                   else {"delta": "The file was not found."})
        yield 'data: ' + json.dumps(payload) + '\n\n'
        yield 'data: [DONE]\n\n'

    async def execute(*args, **kwargs):
        return "read_file", {"error": "missing", "exit_code": 1}

    async def takeover(**kwargs):
        captured.append(kwargs)
        if False:
            yield ""

    monkeypatch.setattr(al, "stream_llm_with_fallback", stream)
    monkeypatch.setattr(al, "execute_tool_block", execute)
    monkeypatch.setattr(teacher, "run_teacher_inline", takeover)

    async def run():
        return [chunk async for chunk in al.stream_agent_loop(
            "https://api.openai.com/v1", "gpt-4o",
            [{"role": "user", "content": "read missing.txt"}],
            relevant_tools={"read_file"}, max_rounds=3, max_tool_calls=budget,
            tool_policy=policy, workspace="workspace", session_id="session",
        )]

    asyncio.run(run())
    if budget == 1:
        assert not captured
    else:
        assert len(captured) == 1
        assert captured[0]["max_tool_calls"] == 1
        assert captured[0]["max_rounds"] == 1
        assert captured[0]["tool_policy"] is policy
        assert "bash" in captured[0]["disabled_tools"]
        assert captured[0]["workspace"] == "workspace"
        assert captured[0]["session_id"] == "session"


@pytest.mark.parametrize("plan_mode", [False, True])
def test_teacher_inherits_constraints_and_cannot_save_disabled_skill(monkeypatch, plan_mode):
    settings = {"teacher_enabled": True, "teacher_model": "teacher"}
    monkeypatch.setattr("src.settings.get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr("src.ai_interaction._resolve_model", lambda *a, **k: ("url", "model", {}))
    monkeypatch.setattr(teacher, "evaluate_turn_regex", lambda events, reply: ("failure", "failed") if reply == "failed" else ("success", ""))
    policy = build_effective_tool_policy(disabled_tools={"bash", "manage_skills"})
    captured = []

    async def stream(**kwargs):
        captured.append(kwargs)
        yield 'data: {"delta": "resolved"}\n\n'
        yield "data: [DONE]\n\n"

    async def distill(*args, **kwargs):
        pytest.fail("disabled skill persistence must not start")

    monkeypatch.setattr(al, "stream_agent_loop", stream)
    monkeypatch.setattr(teacher, "_call_teacher", distill)

    async def run():
        return [chunk async for chunk in teacher.run_teacher_inline(
            student_endpoint_url="url", student_messages=[{"role": "user", "content": "help"}],
            student_tool_events=[], student_reply="failed", owner="alice",
            disabled_tools={"bash", "manage_skills"}, tool_policy=policy,
            plan_mode=plan_mode, workspace="workspace", session_id="session",
            max_rounds=2, max_tool_calls=3,
        )]

    asyncio.run(run())
    assert len(captured) == 1
    kwargs = captured[0]
    assert kwargs["disabled_tools"] == {"bash", "manage_skills"}
    assert kwargs["tool_policy"] is policy
    assert kwargs["plan_mode"] is plan_mode
    assert kwargs["workspace"] == "workspace"
    assert kwargs["session_id"] == "session"
    assert kwargs["owner"] == "alice"
    assert kwargs["max_rounds"] == 2
    assert kwargs["max_tool_calls"] == 3
