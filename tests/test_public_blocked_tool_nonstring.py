"""Regression: is_public_blocked_tool must fail CLOSED on a non-string tool name.

The `if not tool_name` guard only handled falsy values; a truthy non-string
(e.g. 5 or a list) reached `tool_name.startswith("mcp__")` and raised
AttributeError/TypeError. Because this is a public-execution security gate, a
malformed (non-string) identifier must be treated as BLOCKED, not silently
allowed. None/empty mean there is no tool to gate.
"""
import pytest
from src.tool_security import is_public_blocked_tool


def test_malformed_non_string_name_is_blocked():
    # Fail closed: a non-string identifier cannot be validated, so block it.
    assert is_public_blocked_tool(5) is True
    assert is_public_blocked_tool(["bash"]) is True
    assert is_public_blocked_tool({"x": 1}) is True


def test_none_or_empty_is_not_gated():
    assert is_public_blocked_tool(None) is False
    assert is_public_blocked_tool("") is False


def test_real_tool_names_still_classified():
    assert is_public_blocked_tool("mcp__whatever") is True


def test_cookbook_inspection_tools_blocked_for_public_users():
    cookbook_tools = [
        "list_served_models",
        "tail_serve_output",
        "list_downloads",
        "list_cached_models",
        "list_serve_presets",
        "list_cookbook_servers",
        "adopt_served_model",
    ]
    for t in cookbook_tools:
        assert is_public_blocked_tool(t) is True, f"{t} must be blocked for public/non-admin users"

    from src.tool_execution import _ADMIN_TOOLS
    for t in cookbook_tools:
        assert t in _ADMIN_TOOLS, f"{t} must be in _ADMIN_TOOLS"


@pytest.mark.asyncio
async def test_cookbook_tools_blocked_at_execution_for_non_admin(monkeypatch):
    import src.tool_execution as te
    from src.agent_tools import ToolBlock

    monkeypatch.setattr(te, "_owner_is_admin", lambda owner: False)

    for tool in ("list_served_models", "tail_serve_output"):
        desc, result = await te.execute_tool_block(
            ToolBlock(tool, "{}"),
            owner="regular_user",
        )
        assert result.get("exit_code") == 1
        assert "admin" in result.get("error", "").lower() or "restricted" in result.get("error", "").lower()


