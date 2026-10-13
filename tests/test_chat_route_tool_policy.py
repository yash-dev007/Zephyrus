"""Route-level tool-policy behavior tests for POST /api/chat_stream.

The disabled-tools computation lives INLINE in ``chat_stream``
(routes/chat_routes.py:873-995) — there is no ``_build_disabled_tools``
helper to import. These tests therefore drive the REAL route endpoint
with stubbed collaborators and capture what it propagates to the
mocked ``stream_agent_loop``: ``disabled_tools`` / ``tool_policy`` /
``forced_tools`` / ``owner``.

TDD status: every test below PASSES on current code (the route logic is
already correct); they pin the behavior so Teams A/B cannot regress it.
Bugs that need prod fixes live in tests/test_chat_privilege_matrix.py
as ``xfail`` markers.

Two AST substring checks are kept as smoke only — they are not the
assertion core.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.tool_policy import WEB_TOOL_NAMES

import routes.chat_routes as chat_routes
import routes.session_routes as session_routes  # noqa: F401  (kept: ownership seam lives here)
import routes.chat_helpers as chat_helpers_mod
import src.settings as settings_mod


# ── Smoke guards (substring only; behavior is pinned below) ──────────

def test_allow_bash_reads_from_body_as_fallback_smoke():
    """chat_stream must read allow_bash from the JSON body, not just form_data."""
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    assert 'form_data.get("allow_bash") or (body or {}).get("allow_bash")' in source


def test_disabled_tools_respects_missing_vs_explicit_toggles_smoke():
    """Bash defers to privileges when unset; web is explicit per-turn opt-in."""
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    assert "allow_bash is not None" in source
    assert "web_search_enabled_for_turn(allow_web_search, use_web)" in source


# ── Harness: drive the real chat_stream endpoint ─────────────────────

class _FakeSession:
    def __init__(self, model="test-model", name="Test"):
        self.id = "sess-x"
        self.model = model
        self.name = name
        self.endpoint_url = "https://llm.example.com/v1/chat/completions"
        self.headers = {}
        self.history = []

    def add_message(self, message):
        self.history.append(message)


class _FakeSessionManager:
    def __init__(self, sess):
        self._sess = sess
        self.saved = 0

    def get_session(self, session_id):
        return self._sess

    def save_sessions(self):
        self.saved += 1


class _ChainQuery:
    """Chainable stand-in for the SQLAlchemy queries in the active-doc block."""

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _DocDB:
    def query(self, *args, **kwargs):
        return _ChainQuery()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def expunge(self, *args):
        pass


class _CountDB:
    """Fake for the daily-cap count query inside _enforce_chat_privileges."""

    def __init__(self, count):
        self._count = count

    def query(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return self._count

    def close(self):
        pass


def _make_ctx(user="alice"):
    return SimpleNamespace(
        messages=[{"role": "user", "content": "hello"}],
        preprocessed=SimpleNamespace(attachment_meta=None),
        auto_opened_docs=[],
        rag_sources=[],
        web_sources=None,
        used_memories=None,
        preset=SimpleNamespace(temperature=0.2, max_tokens=64, character_name=""),
        context_length=8000,
        context_trimmed=False,
        was_compacted=False,
        uploaded_files=[],
        user=user,
        uprefs={},
    )


def _route_endpoint(router, path, method="POST"):
    for route in router.routes:
        if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"{method} {path} route not registered")


def drive_chat_stream(
    monkeypatch,
    form_fields,
    *,
    json_body=None,
    privs=None,
    cap_count=0,
    session_id="sess-matrix",
    global_disabled=None,
):
    """Call the REAL chat_stream route; capture stream_agent_loop kwargs.

    Returns (captured_kwargs, fallback_kwargs, chunks).
    ``captured_kwargs`` is empty when the agent loop was not reached
    (e.g. can_use_agent=False downgrades to the direct-chat branch).
    """
    privs = {"allowed_models": [], "max_messages_per_day": 0} if privs is None else privs
    captured = {}
    fallback_captured = {}

    async def _empty_gen():
        yield "data: [DONE]\n\n"

    def fake_agent_loop(*args, **kwargs):
        captured.update(kwargs)
        return _empty_gen()

    def fake_fallback(*args, **kwargs):
        fallback_captured.update(kwargs)
        return _empty_gen()

    async def fake_build_ctx(*args, **kwargs):
        return _make_ctx()

    fields = dict(form_fields)
    fields.setdefault("message", "hello world")
    fields.setdefault("session", session_id)
    fields.setdefault("mode", "agent")
    headers = {} if json_body is None else {"content-type": "application/json"}

    async def fake_form():
        return dict(fields)

    async def fake_json():
        return json_body

    auth_manager = SimpleNamespace(get_privileges=lambda user: dict(privs))
    request = SimpleNamespace(
        headers=headers,
        state=SimpleNamespace(current_user="alice"),
        app=SimpleNamespace(state=SimpleNamespace(auth_manager=auth_manager)),
        form=fake_form,
        json=fake_json,
    )

    if global_disabled is None:
        monkeypatch.setattr(settings_mod, "get_setting", lambda key, default=None: default)
    else:
        table = {
            "disabled_tools": list(global_disabled),
            "agent_max_tool_calls": 0,
            "agent_max_rounds": 30,
        }
        monkeypatch.setattr(settings_mod, "get_setting", lambda key, default=None: table.get(key, default))

    monkeypatch.setattr(chat_routes, "_verify_session_owner", lambda request, sid, session_manager=None: None)
    monkeypatch.setattr(chat_routes, "_clear_orphaned_session_endpoint", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "_recover_empty_session_model", lambda sess, sid, owner=None: False)
    monkeypatch.setattr(chat_routes, "resolve_session_auth", lambda sess, sid, owner=None: None)
    monkeypatch.setattr(chat_routes, "coerce_message_and_session",
                        lambda body, message, session, sm, allow_empty=False: ((message or "hello"), (session or session_id)))
    monkeypatch.setattr(chat_routes, "build_chat_context", fake_build_ctx)
    monkeypatch.setattr(chat_routes, "_classify_tool_intent", lambda message: None)
    monkeypatch.setattr(chat_routes, "_is_contextual_web_followup", lambda message, sess: False)
    monkeypatch.setattr(chat_routes, "_ensure_current_request_is_latest_user", lambda messages, current: messages)
    monkeypatch.setattr(chat_routes, "_is_image_generation_session", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "get_session_mode", lambda sid: "chat")
    monkeypatch.setattr(chat_routes, "set_session_mode", lambda sid, mode: None)
    monkeypatch.setattr(chat_routes, "_owner_session_filter", lambda query, user: query)
    monkeypatch.setattr(chat_routes, "SessionLocal", lambda: _DocDB())
    monkeypatch.setattr(chat_routes, "stream_agent_loop", fake_agent_loop)
    monkeypatch.setattr(chat_routes, "stream_llm_with_fallback", fake_fallback)
    monkeypatch.setattr(chat_routes, "save_assistant_response", lambda *a, **k: "msg-1")
    monkeypatch.setattr(chat_routes, "run_post_response_tasks", lambda *a, **k: None)
    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", lambda: _CountDB(cap_count))
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: "alice")

    research_handler = MagicMock()
    research_handler.get_sources.return_value = None
    research_handler.get_raw_findings.return_value = None

    router = chat_routes.setup_chat_routes(
        _FakeSessionManager(_FakeSession()),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        research_handler,
        MagicMock(),
    )
    endpoint = _route_endpoint(router, "/api/chat_stream")

    async def _run():
        resp = await endpoint(request)
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
        return chunks

    chunks = asyncio.run(asyncio.wait_for(_run(), timeout=20))
    return captured, fallback_captured, chunks, research_handler


# ── Bash toggle matrix (issue #3229 + privilege fallback) ────────────

def test_bash_unset_defers_to_privilege_grant(monkeypatch):
    """allow_bash unset + can_use_bash=True → bash NOT disabled (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {}, privs={"can_use_bash": True}, session_id="sess-b1",
    )
    assert captured, "agent loop was not reached"
    assert "bash" not in captured["disabled_tools"]


def test_bash_explicit_true_enables_for_privileged_user(monkeypatch):
    """allow_bash=true + can_use_bash=True → bash enabled (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_bash": "true"},
        privs={"can_use_bash": True}, session_id="sess-b2",
    )
    assert "bash" not in captured["disabled_tools"]


def test_bash_explicit_false_disables_even_for_admin(monkeypatch):
    """allow_bash=false is a hard deny even with the privilege (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_bash": "false"},
        privs={"can_use_bash": True}, session_id="sess-b3",
    )
    assert "bash" in captured["disabled_tools"]


def test_bash_unset_privilege_deny_disables(monkeypatch):
    """allow_bash unset + can_use_bash=False → bash/python/file tools out (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {}, privs={"can_use_bash": False}, session_id="sess-b4",
    )
    for tool in ("bash", "python", "read_file", "write_file"):
        assert tool in captured["disabled_tools"]


def test_bash_explicit_true_overridden_by_privilege_deny(monkeypatch):
    """Privilege gate wins over allow_bash=true (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_bash": "true"},
        privs={"can_use_bash": False}, session_id="sess-b5",
    )
    assert "bash" in captured["disabled_tools"]


def test_json_body_allow_bash_true_enables_bash(monkeypatch):
    """JSON API caller {"allow_bash": true} with no form field → bash on (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {},
        json_body={"allow_bash": "true"},
        privs={"can_use_bash": True}, session_id="sess-b6",
    )
    assert "bash" not in captured["disabled_tools"]


def test_json_body_allow_bash_false_disables_bash(monkeypatch):
    """JSON API caller {"allow_bash": false} → bash off (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {},
        json_body={"allow_bash": "false"},
        privs={"can_use_bash": True}, session_id="sess-b7",
    )
    assert "bash" in captured["disabled_tools"]


# ── Web toggle matrix (explicit per-turn opt-in) ─────────────────────

def test_web_disabled_by_default_without_explicit_setting(monkeypatch):
    """No web flags → web_search/web_fetch disabled (PASSES)."""
    captured, _, _, _ = drive_chat_stream(monkeypatch, {}, session_id="sess-w1")
    assert "web_search" in captured["disabled_tools"]
    assert "web_fetch" in captured["disabled_tools"]
    assert captured["forced_tools"] is None


def test_web_agent_toggle_true_enables_and_forces(monkeypatch):
    """allow_web_search=true → web enabled AND forced visible (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_web_search": "true"}, session_id="sess-w2",
    )
    # NOTE: the route passes `disabled_tools=None` when the merged set is
    # empty (routes/chat_routes.py stream_agent_loop call site) — normalize.
    assert "web_search" not in (captured["disabled_tools"] or ())
    assert "web_fetch" not in (captured["disabled_tools"] or ())
    assert set(captured["forced_tools"]) == set(WEB_TOOL_NAMES)


def test_web_chat_presearch_use_web_true_enables(monkeypatch):
    """use_web=true (chat pre-search) is an explicit web setting (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"use_web": "true"}, session_id="sess-w3",
    )
    assert "web_search" not in (captured["disabled_tools"] or ())
    assert set(captured["forced_tools"]) == set(WEB_TOOL_NAMES)


def test_web_explicit_false_wins_over_use_web_true(monkeypatch):
    """allow_web_search=false hard-denies even with use_web=true (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_web_search": "false", "use_web": "true"},
        session_id="sess-w4",
    )
    assert "web_search" in captured["disabled_tools"]
    assert "web_fetch" in captured["disabled_tools"]


def test_global_disabled_web_wins_over_explicit_enable(monkeypatch):
    """Admin global disabled_tools still deny web; forced set documents the
    conflict (enforcement sees disabled). PASSES."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_web_search": "true"},
        global_disabled=["web_search", "web_fetch"], session_id="sess-w5",
    )
    assert "web_search" in captured["disabled_tools"]
    assert "web_fetch" in captured["disabled_tools"]
    # Forced-vs-disabled precedence: the explicit turn setting still forces
    # visibility, but the merged disabled set wins at enforcement time.
    assert set(captured["forced_tools"]) == set(WEB_TOOL_NAMES)


# ── Propagation: tool_policy / owner / identity ──────────────────────

def test_tool_policy_propagated_and_consistent(monkeypatch):
    """disabled_tools passed to the loop equals the policy's merged set, and
    the policy blocks what the set contains (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"allow_bash": "false"}, session_id="sess-p1",
    )
    policy = captured["tool_policy"]
    assert set(captured["disabled_tools"]) == set(policy.all_disabled_names())
    assert policy.blocks("bash")
    assert not policy.blocks("manage_notes")
    assert captured["owner"] == "alice"


def test_incognito_strips_memory_history_skill_tools(monkeypatch):
    """Incognito denies identity-linked tools (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"incognito": "true"}, session_id="sess-p2",
    )
    for tool in ("manage_memory", "search_chats", "manage_skills"):
        assert tool in captured["disabled_tools"]


def test_compare_mode_strips_pane_breaking_tools(monkeypatch):
    """compare_mode disables session/document-management tools (PASSES)."""
    captured, _, _, _ = drive_chat_stream(
        monkeypatch, {"compare_mode": "true"}, session_id="sess-p3",
    )
    for tool in ("create_document", "edit_document", "update_document",
                 "chat_with_model", "create_session", "manage_memory",
                 "generate_image", "ui_control"):
        assert tool in captured["disabled_tools"]


def test_can_use_agent_false_downgrades_to_direct_chat(monkeypatch):
    """can_use_agent=False never reaches the agent loop; the direct-chat
    branch runs instead (PASSES)."""
    captured, fallback, _, _ = drive_chat_stream(
        monkeypatch, {}, privs={"can_use_agent": False}, session_id="sess-p4",
    )
    assert captured == {}
    assert fallback, "expected fallback to the direct stream_llm path"


def test_can_use_research_false_suppresses_research(monkeypatch):
    """use_research=true + can_use_research=False → start_research never
    called (PASSES)."""
    captured, _, _, research_handler = drive_chat_stream(
        monkeypatch, {"use_research": "true"},
        privs={"can_use_research": False}, session_id="sess-p5",
    )
    assert captured, "agent loop was not reached"
    research_handler.start_research.assert_not_called()


# ── Privilege gates on the stream endpoint (mirror of /api/chat) ─────

def test_stream_allowed_models_403(monkeypatch):
    """Session model outside the allowlist → 403 before any LLM work (PASSES)."""
    import fastapi

    with pytest.raises(fastapi.HTTPException) as exc:
        drive_chat_stream(
            monkeypatch, {},
            privs={"allowed_models": ["allowed-model"], "max_messages_per_day": 0},
            session_id="sess-g1",
        )
    assert exc.value.status_code == 403


def test_stream_daily_cap_429(monkeypatch):
    """User at/over max_messages_per_day → 429 (PASSES)."""
    import fastapi

    with pytest.raises(fastapi.HTTPException) as exc:
        drive_chat_stream(
            monkeypatch, {},
            privs={"allowed_models": [], "max_messages_per_day": 1},
            cap_count=5,
            session_id="sess-g2",
        )
    assert exc.value.status_code == 429
