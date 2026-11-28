import asyncio
from unittest.mock import AsyncMock

from src.agent_loop import _build_actions_snapshot, _run_verifier_subagent


def test_snapshot_keeps_latest_repair_and_its_exit_status():
    events = [{"tool": "bash", "command": "old", "output": "a" * 5000}] * 20
    events += [{"tool": "bash", "command": "check", "output": "missing", "exit_code": 1}]
    evidence = _build_actions_snapshot(events)
    assert len(evidence) <= 8000
    assert evidence.endswith("[bash] check (exit 1)\n-> missing")


def test_only_the_final_verdict_triggers_remediation(monkeypatch):
    llm = AsyncMock(side_effect=["quoted VERIFICATION: FAIL: hypothetical\nundecided",
                                 "Reasoning\nVERIFICATION: FAIL: missing output; wrong value"])
    monkeypatch.setattr("src.llm_core.llm_call_async", llm)
    options = {"endpoint_url": "local", "model": "test", "headers": {}}
    assert asyncio.run(_run_verifier_subagent("task", "test evidence", **options)) == []
    assert asyncio.run(_run_verifier_subagent("task", "test evidence", **options)) == ["missing output", "wrong value"]
    system, evidence = llm.await_args.kwargs["messages"]
    assert "test evidence" not in system["content"]
    assert evidence["role"] == "user" and "test evidence" in evidence["content"]
