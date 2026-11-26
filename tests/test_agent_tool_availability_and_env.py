"""Regressions from the "Simple DeepSeek AI Website" session.

Four defects made the agent refuse to edit files it had just written:

1. A follow-up turn ("improve it", "too plain, needs wow") was classified
   low-signal, and the low-signal branch handed the model only the READ-ONLY
   half of the files domain. write_file/bash vanished, so the agent truthfully
   reported "no write access".
2. The bash subprocess ran with HOME=<data dir>, so `~/Desktop/x` resolved to
   <data>/Desktop/x and every `ls ~/...` check said "No such file or
   directory" while the files existed.
3. `ui_control get_toggles` returned a canned sentence instead of state.
4. Document/UI tool events carried `exit_code: None`, unlike file tools.
"""
import asyncio
import os

from src.agent_loop import (
    _DOMAIN_TOOL_MAP,
    _tool_event_exit_code,
    _with_workspace_file_tools,
)
from src.tool_execution import _AGENT_WORKDIR, _agent_subproc_env


# ── 1. workspace turns keep the write/shell tools ─────────────────────────

def test_workspace_turn_keeps_write_and_shell_tools():
    read_only = {"read_file", "grep", "glob", "ls", "get_workspace", "ask_user"}
    tools = _with_workspace_file_tools(read_only, "/home/yash/Desktop")
    assert {"write_file", "edit_file", "bash", "python"} <= tools
    # The read-only tools the caller selected are still there.
    assert read_only <= tools


def test_workspace_union_is_the_whole_files_domain():
    tools = _with_workspace_file_tools(set(), "/tmp/project")
    assert tools == set(_DOMAIN_TOOL_MAP["files"])


def test_no_workspace_leaves_selection_untouched():
    read_only = {"read_file", "grep"}
    assert _with_workspace_file_tools(read_only, None) == read_only
    assert _with_workspace_file_tools(read_only, "") == read_only


def test_unset_selection_stays_unset():
    # None means "send every schema"; a workspace must not turn that into a
    # narrow files-only list.
    assert _with_workspace_file_tools(None, "/tmp/project") is None


# ── 2. HOME is the real home, caches stay on the data volume ──────────────

def test_subprocess_home_is_the_real_home():
    env = _agent_subproc_env()
    assert env["HOME"] == os.environ.get("HOME") or env["HOME"] == _AGENT_WORKDIR
    assert env["HOME"] != _AGENT_WORKDIR or not os.environ.get("HOME")


def test_subprocess_caches_stay_on_the_data_volume():
    env = _agent_subproc_env()
    assert env["XDG_CACHE_HOME"].startswith(_AGENT_WORKDIR)
    assert env["PIP_CACHE_DIR"].startswith(_AGENT_WORKDIR)
    assert env["HF_HOME"].startswith(_AGENT_WORKDIR)


# ── 3. get_toggles reports real flags, not a canned sentence ──────────────

def test_get_toggles_returns_feature_flags():
    from src.ai_interaction import do_ui_control

    r = asyncio.run(do_ui_control("get_toggles"))
    assert "error" not in r
    flags = r.get("feature_flags")
    assert isinstance(flags, dict) and flags
    assert all(isinstance(v, bool) for v in flags.values())
    # The old answer claimed the state lived only in localStorage.
    assert "localStorage" not in r.get("results", "")


# ── 4. every tool event carries a 0/1 exit code ───────────────────────────

def test_exit_code_defaults_to_zero_for_document_tools():
    assert _tool_event_exit_code({"action": "create", "doc_id": "x"}) == 0


def test_exit_code_is_one_when_the_result_is_an_error():
    assert _tool_event_exit_code({"error": "boom"}) == 1


def test_explicit_exit_code_is_preserved():
    assert _tool_event_exit_code({"exit_code": 2}) == 2
    assert _tool_event_exit_code({"exit_code": 0, "error": "ignored"}) == 0


# ── 5. sessions.headers is encrypted at rest ──────────────────────────────

def test_session_headers_are_encrypted_at_rest():
    from core.database import EncryptedJSON

    col = EncryptedJSON()
    value = {"Authorization": "Bearer sk-test"}
    stored = col.process_bind_param(value, None)
    assert stored.startswith("enc:")
    assert "sk-test" not in stored
    assert col.process_result_value(stored, None) == value


def test_legacy_plaintext_headers_still_load():
    from core.database import EncryptedJSON

    col = EncryptedJSON()
    assert col.process_result_value('{"Authorization": "Bearer old"}', None) == {
        "Authorization": "Bearer old"
    }
    assert col.process_result_value(None, None) is None
