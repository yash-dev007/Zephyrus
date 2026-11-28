"""Prompt assembly must keep execution guidance and actual tool availability aligned."""

import pytest

from src import agent_loop as agent


@pytest.fixture(autouse=True)
def no_user_tool_overrides(monkeypatch):
    monkeypatch.setattr(agent, "get_builtin_overrides", lambda: {})


@pytest.mark.parametrize("compact", [False, True])
def test_execution_contract_is_shared_once_and_disabled_domains_are_omitted(compact):
    prompt = agent._assemble_prompt(
        {"python", "read_file", "manage_notes"},
        disabled_tools={"python", "read_file"},
        compact=compact,
    )
    assert prompt.count(agent._EXECUTION_RULES) == 1
    assert agent._DOMAIN_RULES["notes_calendar_tasks"] in prompt
    assert agent._DOMAIN_RULES["files"] not in prompt
    assert "```python" not in prompt
    assert "- `python`" not in prompt
    assert "manage_notes" in prompt


@pytest.mark.parametrize("compact", [False, True])
def test_workspace_prompt_includes_file_guidance_without_unrelated_domains(compact):
    prompt = agent._assemble_prompt({"read_file", "edit_file", "bash"}, compact=compact)
    assert agent._DOMAIN_RULES["files"] in prompt
    assert prompt.count(agent._EXECUTION_RULES) == 1
    if compact:
        assert "```bash" not in prompt
        assert "- `bash`" in prompt
    else:
        assert "```bash" in prompt
        assert "non-tool language tag" in prompt


@pytest.mark.parametrize("compact", [False, True])
def test_full_admin_fallback_does_not_advertise_disabled_tools(monkeypatch, compact):
    monkeypatch.setattr(agent, "get_setting", lambda _key, default=None: default)
    prompt, skill_index = agent._build_base_prompt(
        disabled_tools={"python"}, mcp_mgr=None, needs_admin=True,
        relevant_tools=None, compact=compact, suppress_skills=True,
    )
    assert skill_index == ""
    assert "```python" not in prompt
    assert "- `python`" not in prompt
    assert prompt.count(agent._EXECUTION_RULES) == 1
