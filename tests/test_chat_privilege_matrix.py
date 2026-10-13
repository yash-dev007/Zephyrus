"""Owner-isolation + privilege-gate behavior matrix for the chat API.

Drives the REAL route endpoints (POST /api/chat, POST /api/chat_stream,
/resume, /stop, /stream_status, /inject_context, /rewrite) and the REAL
``_verify_session_owner`` / ``_enforce_chat_privileges`` /
``_resolve_request_workspace`` helpers with stubbed collaborators.
Assertions are on outcomes (status codes, calls made or not made,
returned bodies) — never on source text.

TDD status: all tests PASS on current code except
``test_nonstream_research_privilege_suppresses_service_call``, which
FAILS (``/api/chat`` never consults ``can_use_research``) and is marked
xfail for Team A.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import routes.chat_routes as chat_routes
import routes.session_routes as session_routes
import routes.chat_helpers as chat_helpers_mod
import routes.research_routes as research_routes_mod  # noqa: F401 (documents research seam; unused)
from src.request_models import ChatRequest


# ── Shared fakes ─────────────────────────────────────────────────────

class _FakeSession:
    def __init__(self, model="test-model", name="Test", owner="alice"):
        self.id = "sess-x"
        self.model = model
        self.name = name
        self.owner = owner
        self.endpoint_url = "https://llm.example.com/v1/chat/completions"
        self.headers = {}
        self.history = []

    def add_message(self, message):
        self.history.append(message)


class _FakeSessionManager:
    def __init__(self, sess=None, ghosts=None):
        self._sess = sess or _FakeSession()
        self.sessions = dict(ghosts or {})
        self.get_session_calls = []
        self.saved = 0

    def get_session(self, session_id):
        self.get_session_calls.append(session_id)
        if session_id in self.sessions:
            return self.sessions[session_id]
        return self._sess

    def save_sessions(self):
        self.saved += 1


class _OwnerRowDB:
    """Fake for the owner lookup inside _verify_session_owner."""

    def __init__(self, row_owner="alice", has_row=True):
        self._row_owner = row_owner
        self._has_row = has_row

    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if not self._has_row:
            return None
        return SimpleNamespace(owner=self._row_owner)

    def close(self):
        pass


def _request(user="alice", *, token_owner=None):
    state = SimpleNamespace(current_user=user)
    if token_owner is not None:
        state.api_token = True
        state.api_token_owner = token_owner
    return SimpleNamespace(state=state)


def _authed_request(user, privs):
    auth_manager = SimpleNamespace(get_privileges=lambda u: dict(privs))
    req = _request(user)
    req.app = SimpleNamespace(state=SimpleNamespace(auth_manager=auth_manager))
    return req


def _light_router(sess=None, ghosts=None):
    """Router with stub managers; heavy collaborators left real (unreached
    by auth-gate tests, which fail before any LLM work)."""
    sm = _FakeSessionManager(sess, ghosts)
    router = chat_routes.setup_chat_routes(
        sm, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )
    return router, sm


def _ep(router, path, method="POST"):
    for route in router.routes:
        if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"{method} {path} route not registered")


def _form_request(user, fields, privs=None):
    async def fake_form():
        return dict(fields)

    req = _request(user) if privs is None else _authed_request(user, privs)
    req.headers = {}
    req.form = fake_form
    return req


# ── _verify_session_owner direct behavior ────────────────────────────

def test_verify_cross_user_session_returns_404(monkeypatch):
    """Bob posting into Alice's session → 404 (not 403: no existence leak). PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    with pytest.raises(HTTPException) as exc:
        session_routes._verify_session_owner(_request("bob"), "s-alice")
    assert exc.value.status_code == 404


def test_verify_unauthenticated_returns_401(monkeypatch):
    """No user + auth enabled → 401. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    with pytest.raises(HTTPException) as exc:
        session_routes._verify_session_owner(_request(None), "s-alice")
    assert exc.value.status_code == 401


def test_verify_legacy_null_owner_row_rejects_authenticated_user(monkeypatch):
    """Pre-ownership row (owner NULL) + logged-in user → 404 fail-closed. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB(None))
    with pytest.raises(HTTPException) as exc:
        session_routes._verify_session_owner(_request("alice"), "s-legacy")
    assert exc.value.status_code == 404


def test_verify_single_user_mode_ignores_stored_owner(monkeypatch):
    """AUTH_ENABLED=false + anonymous → owner-stamped rows still pass. PASSES."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    session_routes._verify_session_owner(_request(None), "s-alice")  # must not raise


def test_verify_owned_ghost_passes_with_session_manager(monkeypatch):
    """In-memory ghost owned by the caller passes once session_manager is
    supplied (Team A ghost-404 fix). PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB(has_row=False))
    ghost = SimpleNamespace(owner="alice")
    sm = SimpleNamespace(sessions={"sess-ghost": ghost})
    session_routes._verify_session_owner(_request("alice"), "sess-ghost", sm)  # must not raise


def test_verify_ghost_without_manager_is_404(monkeypatch):
    """No DB row + no session_manager → 404 fail-closed (documented). PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB(has_row=False))
    with pytest.raises(HTTPException) as exc:
        session_routes._verify_session_owner(_request("alice"), "sess-ghost")
    assert exc.value.status_code == 404


def test_verify_ghost_owned_by_other_user_is_404(monkeypatch):
    """Ghost owned by Bob is invisible to Alice. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB(has_row=False))
    sm = SimpleNamespace(sessions={"sess-ghost": SimpleNamespace(owner="bob")})
    with pytest.raises(HTTPException) as exc:
        session_routes._verify_session_owner(_request("alice"), "sess-ghost", sm)
    assert exc.value.status_code == 404


# ── Route-level cross-user 404 / unauth 401 ──────────────────────────

def test_chat_cross_user_post_is_404_without_touching_session(monkeypatch):
    """POST /api/chat into another user's session → 404, no session load. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, sm = _light_router()
    sm.get_session = MagicMock(side_effect=AssertionError("must not load session"))
    endpoint = _ep(router, "/api/chat")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request("bob"), ChatRequest(message="hi", session="s-alice")))
    assert exc.value.status_code == 404


def test_chat_unauthenticated_post_is_401(monkeypatch):
    """POST /api/chat with no identity → 401. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, _ = _light_router()
    endpoint = _ep(router, "/api/chat")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request(None), ChatRequest(message="hi", session="s-alice")))
    assert exc.value.status_code == 401


def test_chat_stream_cross_user_is_404(monkeypatch):
    """POST /api/chat_stream into another user's session → 404. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, _ = _light_router()
    endpoint = _ep(router, "/api/chat_stream")
    req = _form_request("bob", {"message": "hi", "session": "s-alice", "mode": "agent"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 404


def test_chat_stream_unauthenticated_is_401(monkeypatch):
    """POST /api/chat_stream with no identity → 401. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, _ = _light_router()
    endpoint = _ep(router, "/api/chat_stream")
    req = _form_request(None, {"message": "hi", "session": "s-alice", "mode": "agent"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("path,method,kwargs", [
    ("/api/chat/resume/{session_id}", "GET", {}),
    ("/api/chat/stop/{session_id}", "POST", {}),
    ("/api/chat/stream_status/{session_id}", "GET", {}),
    ("/api/inject_context/{session_id}", "POST", {"context": "extra facts"}),
])
def test_detached_run_and_inject_endpoints_reject_cross_user(monkeypatch, path, method, kwargs):
    """resume/stop/stream_status/inject → cross-user 404. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, _ = _light_router()
    endpoint = _ep(router, path, method)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request("bob"), "s-alice", **kwargs))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("path,method,kwargs", [
    ("/api/chat/resume/{session_id}", "GET", {}),
    ("/api/chat/stop/{session_id}", "POST", {}),
    ("/api/chat/stream_status/{session_id}", "GET", {}),
    ("/api/inject_context/{session_id}", "POST", {"context": "extra facts"}),
])
def test_detached_run_and_inject_endpoints_reject_anonymous(monkeypatch, path, method, kwargs):
    """resume/stop/stream_status/inject → anonymous 401. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    router, _ = _light_router()
    endpoint = _ep(router, path, method)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request(None), "s-alice", **kwargs))
    assert exc.value.status_code == 401


def test_rewrite_cross_user_is_404(monkeypatch):
    """POST /api/rewrite on another user's session → 404 before LLM. PASSES."""
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB("alice"))
    monkeypatch.setattr(chat_routes, "stream_llm", MagicMock(side_effect=AssertionError("no LLM on 404")))
    router, _ = _light_router()
    endpoint = _ep(router, "/api/rewrite")

    async def fake_json():
        return {"session_id": "s-alice", "original_text": "old", "instruction": "shorter"}

    req = _request("bob")
    req.json = fake_json
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 404


# ── allowed_models 403 + daily-cap 429 on POST /api/chat ─────────────

class _ZeroCountDB:
    def query(self, *a, **k):
        return self

    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def count(self):
        return 0

    def close(self):
        pass


def _drive_chat(monkeypatch, chat_request, *, privs, research_handler=None, llm_probe=None, cap_db=None):
    """Drive the REAL chat_endpoint with stubbed collaborators."""
    monkeypatch.setattr(chat_routes, "_verify_session_owner", lambda *a, **k: None)
    monkeypatch.setattr(chat_routes, "_clear_orphaned_session_endpoint", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "_recover_empty_session_model", lambda sess, sid, owner=None: False)
    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", lambda: (cap_db or _ZeroCountDB()))
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: "alice")

    llm_calls = []

    async def fake_llm(*args, **kwargs):
        llm_calls.append((args, kwargs))
        if llm_probe is not None:
            llm_probe.append((args, kwargs))
        return "<think>scratch</think>Real answer"

    monkeypatch.setattr(chat_routes, "llm_call_async", fake_llm)

    async def fake_memory(sess, message):
        return None

    async def fake_ctx(*args, **kwargs):
        return SimpleNamespace(
            messages=[{"role": "user", "content": "hi"}],
            preface=[],
            preset=SimpleNamespace(temperature=0.2, max_tokens=64, character_name=""),
            uprefs={},
            user="alice",
        )

    chat_handler = SimpleNamespace(handle_memory_command=fake_memory)
    monkeypatch.setattr(chat_routes, "build_chat_context", fake_ctx)
    monkeypatch.setattr(chat_routes, "run_post_response_tasks", lambda *a, **k: None)
    monkeypatch.setattr("core.database.update_session_last_accessed", lambda session: None)

    sm = _FakeSessionManager()
    router = chat_routes.setup_chat_routes(
        sm, chat_handler, MagicMock(), MagicMock(),
        research_handler or MagicMock(), MagicMock(),
    )
    endpoint = _ep(router, "/api/chat")
    return asyncio.run(endpoint(_authed_request("alice", privs), chat_request)), llm_calls, sm


def test_nonstream_allowed_models_403_before_llm(monkeypatch):
    """POST /api/chat with a non-allowlisted model → 403, LLM untouched. PASSES."""
    llm_probe = []
    with pytest.raises(HTTPException) as exc:
        _drive_chat(
            monkeypatch, ChatRequest(message="hi", session="s1"),
            privs={"allowed_models": ["allowed-model"], "max_messages_per_day": 0},
            llm_probe=llm_probe,
        )
    assert exc.value.status_code == 403
    assert llm_probe == []


def test_nonstream_daily_cap_429_before_llm(monkeypatch):
    """POST /api/chat at the daily cap → 429, LLM untouched. PASSES."""
    llm_probe = []
    with pytest.raises(HTTPException) as exc:
        _drive_chat(
            monkeypatch, ChatRequest(message="hi", session="s1"),
            privs={"allowed_models": [], "max_messages_per_day": 1},
            llm_probe=llm_probe,
            cap_db=_OverCapDB(),
        )
    assert exc.value.status_code == 429
    assert llm_probe == []


class _OverCapDB(_ZeroCountDB):
    def count(self):
        return 7


def test_nonstream_returns_cleaned_reply(monkeypatch):
    """POST /api/chat strips <think> scratchpad from the returned body. PASSES."""
    response, _, _ = _drive_chat(
        monkeypatch, ChatRequest(message="hi", session="s1"),
        privs={"allowed_models": [], "max_messages_per_day": 0},
    )
    assert response["response"] == "Real answer"
    assert "<think>" not in response["response"]


def test_daily_cap_db_error_fails_closed_not_silent(monkeypatch):
    """If the cap count query blows up, the gate must raise — never wave the
    request through. PASSES (raised as 500 today; Team A may map to 429/503)."""
    from routes.chat_helpers import _enforce_chat_privileges

    def _boom():
        raise ConnectionError("db unreachable")

    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", _boom)
    req = _authed_request("alice", {"allowed_models": [], "max_messages_per_day": 5})
    with pytest.raises(Exception):
        _enforce_chat_privileges(req, SimpleNamespace(model="m"))


@pytest.mark.xfail(
    reason="Team A: POST /api/chat never consults can_use_research, so a research-disabled user with use_research=true still burns research tokens",
    strict=True,
)
def test_nonstream_research_privilege_suppresses_service_call(monkeypatch):
    """use_research=true + can_use_research=False → no research call. FAILS today."""
    research_handler = MagicMock()
    with pytest.raises(HTTPException):
        _drive_chat(
            monkeypatch,
            ChatRequest(message="deep dive please", session="s1", use_research=True),
            privs={"can_use_research": False},
            research_handler=research_handler,
        )
    research_handler.call_research_service.assert_not_called()


# ── POST /api/rewrite privilege + input caps ─────────────────────────

def _drive_rewrite(monkeypatch, body, *, privs, row_owner="alice", user="alice"):
    monkeypatch.setattr(session_routes, "SessionLocal", lambda: _OwnerRowDB(row_owner))
    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: user)
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", lambda: _ZeroCountDB())
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: user)

    async def fake_json():
        return dict(body)

    req = _authed_request(user, privs)
    req.json = fake_json

    stream = MagicMock()

    async def _no_stream(*args, **kwargs):
        async def _gen():
            yield "data: [DONE]\n\n"

        return _gen()

    stream.side_effect = lambda *a, **k: _no_stream()
    monkeypatch.setattr(chat_routes, "stream_llm", stream)

    sm = _FakeSessionManager()
    router = chat_routes.setup_chat_routes(
        sm, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )
    endpoint = _ep(router, "/api/rewrite")
    return endpoint, req, stream


def test_rewrite_allowed_models_403_before_llm(monkeypatch):
    """Rewrite on a non-allowlisted model → 403, LLM untouched. PASSES."""
    endpoint, req, stream = _drive_rewrite(
        monkeypatch,
        {"session_id": "s1", "original_text": "old", "instruction": "shorter"},
        privs={"allowed_models": ["allowed-model"], "max_messages_per_day": 0},
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 403
    stream.assert_not_called()


def test_rewrite_caps_oversized_inputs(monkeypatch):
    """Unbounded rewrite inputs are rejected before any LLM work. PASSES."""
    endpoint, req, _ = _drive_rewrite(
        monkeypatch,
        {"session_id": "s1", "original_text": "x" * 20001, "instruction": "shorter"},
        privs={"allowed_models": [], "max_messages_per_day": 0},
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 400

    endpoint, req, _ = _drive_rewrite(
        monkeypatch,
        {"session_id": "s1", "original_text": "old", "instruction": "y" * 2001},
        privs={"allowed_models": [], "max_messages_per_day": 0},
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(req))
    assert exc.value.status_code == 400


# ── Workspace token-owner confinement ───────────────────────────────

def test_workspace_dropped_for_non_admin_user(monkeypatch, tmp_path):
    """A non-admin's posted workspace is dropped uniformly — no vetting, no
    rejected signal (otherwise existence-probing). PASSES."""
    monkeypatch.setattr(
        "src.tool_security.owner_is_admin_or_single_user", lambda owner: False,
    )
    workspace, rejected = chat_routes._resolve_request_workspace(_request("bob"), str(tmp_path))
    assert (workspace, rejected) == ("", "")


def test_workspace_vetted_for_admin(monkeypatch, tmp_path):
    """Admins get vet_workspace() + the rejected signal. PASSES."""
    monkeypatch.setattr(
        "src.tool_security.owner_is_admin_or_single_user", lambda owner: True,
    )
    workspace, rejected = chat_routes._resolve_request_workspace(_request("alice"), str(tmp_path))
    assert workspace == str(tmp_path)
    assert rejected == ""

    workspace, rejected = chat_routes._resolve_request_workspace(
        _request("alice"), "/nonexistent-workspace-xyz"
    )
    assert workspace == ""
    assert rejected == "/nonexistent-workspace-xyz"


def test_workspace_token_caller_confined_to_pseudo_user(monkeypatch, tmp_path):
    """A bearer-token caller is evaluated as its 'api' pseudo-user, NOT its
    token owner — the token owner grants no workspace rights. PASSES."""
    seen = []
    monkeypatch.setattr(
        "src.tool_security.owner_is_admin_or_single_user",
        lambda owner: seen.append(owner) or False,
    )
    req = _request("api", token_owner="alice")
    workspace, rejected = chat_routes._resolve_request_workspace(req, str(tmp_path))
    assert seen == ["api"]
    assert (workspace, rejected) == ("", "")


def test_workspace_allowed_in_single_user_mode(monkeypatch, tmp_path):
    """AUTH_ENABLED=false → local operator keeps workspace tools. PASSES."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    workspace, rejected = chat_routes._resolve_request_workspace(_request(None), str(tmp_path))
    assert workspace == str(tmp_path)
    assert rejected == ""
