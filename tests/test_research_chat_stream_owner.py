"""Owner-scoping behavior for research launched from the chat stream.

Replaces the old AST check ("start_research call must include owner=") with
executed behavior:

1. Driving the REAL ``chat_stream`` route with research enabled and
   asserting the mocked ``research_handler.start_research`` receives
   ``owner="alice"`` (PASSES — routes/chat_routes.py passes ``owner=_user``).
2. Cross-user poll isolation on the REAL research routes: status / result /
   stream / active as another user → 404 or exclusion; anonymous → 401.
3. Session-keyed isolation on the REAL ``ResearchHandler.get_status`` /
   ``get_sources``: asking for a session with no entry returns None instead
   of a neighboring user's data.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import routes.chat_routes as chat_routes
import routes.chat_helpers as chat_helpers_mod
import src.settings as settings_mod
from routes.research_routes import setup_research_routes
from src.research_handler import ResearchHandler


# ── Part 1: chat_stream passes owner to start_research (executed) ────

class _FakeSession:
    def __init__(self):
        self.id = "sess-research"
        self.model = "test-model"
        self.name = "Test"
        self.owner = "alice"
        self.endpoint_url = "https://llm.example.com/v1/chat/completions"
        self.headers = {}
        self.history = []

    def add_message(self, message):
        self.history.append(message)


class _FakeSessionManager:
    def get_session(self, session_id):
        return _FakeSession()

    def save_sessions(self):
        pass


class _EmptyDB:
    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def expunge(self, *a):
        pass


class _ZeroCountDB(_EmptyDB):
    def join(self, *a, **k):
        return self

    def count(self):
        return 0


def _ep(router, path, method="POST"):
    for route in router.routes:
        if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"{method} {path} route not registered")


class _AwaitableValue:
    """Minimal awaitable (avoids AsyncMock version quirks)."""

    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _coro():
            return self._value

        return _coro().__await__()


def _awaitable(value):
    return _AwaitableValue(value)


def test_chat_stream_start_research_receives_caller_owner(monkeypatch):
    """Research from the chat stream is attributed to the caller (PASSES)."""
    monkeypatch.setattr(chat_routes, "_verify_session_owner", lambda *a, **k: None)
    monkeypatch.setattr(chat_routes, "_clear_orphaned_session_endpoint", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "_recover_empty_session_model", lambda sess, sid, owner=None: False)
    monkeypatch.setattr(chat_routes, "resolve_session_auth", lambda sess, sid, owner=None: None)
    monkeypatch.setattr(chat_routes, "coerce_message_and_session",
                        lambda body, message, session, sm, allow_empty=False: (message or "hello", session or "sess-research"))
    monkeypatch.setattr(chat_routes, "_classify_tool_intent", lambda message: None)
    monkeypatch.setattr(chat_routes, "_is_contextual_web_followup", lambda message, sess: False)
    monkeypatch.setattr(chat_routes, "_ensure_current_request_is_latest_user", lambda messages, current: messages)
    monkeypatch.setattr(chat_routes, "_is_image_generation_session", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "get_session_mode", lambda sid: "chat")
    monkeypatch.setattr(chat_routes, "set_session_mode", lambda sid, mode: None)
    monkeypatch.setattr(chat_routes, "_owner_session_filter", lambda query, user: query)
    monkeypatch.setattr(chat_routes, "SessionLocal", lambda: _EmptyDB())
    monkeypatch.setattr(chat_routes, "_resolve_research_endpoint",
                        lambda sess: ("https://research.example.com", "research-model", {}))
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", lambda: _ZeroCountDB())
    monkeypatch.setattr(settings_mod, "get_setting", lambda key, default=None: default)

    async def fake_ctx(*args, **kwargs):
        return SimpleNamespace(
            messages=[{"role": "user", "content": "research this topic"}],
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
            user="alice",
            uprefs={},
        )

    monkeypatch.setattr(chat_routes, "build_chat_context", fake_ctx)

    research_handler = MagicMock()
    research_handler._get_session_json.return_value = {"raw_report": "prior findings"}
    research_handler.synthesize_query = MagicMock(return_value=_awaitable("focused query"))
    research_handler.get_status.return_value = {"status": "done"}
    research_handler.get_sources.return_value = []
    research_handler.get_raw_findings.return_value = []

    async def fake_form():
        return {"message": "research this topic", "session": "sess-research",
                "mode": "agent", "use_research": "true"}

    auth_manager = SimpleNamespace(get_privileges=lambda user: {"can_use_research": True})
    request = SimpleNamespace(
        headers={},
        state=SimpleNamespace(current_user="alice"),
        app=SimpleNamespace(state=SimpleNamespace(auth_manager=auth_manager)),
        form=fake_form,
    )

    router = chat_routes.setup_chat_routes(
        _FakeSessionManager(), MagicMock(), MagicMock(), MagicMock(),
        research_handler, MagicMock(),
    )
    endpoint = _ep(router, "/api/chat_stream")

    async def _run():
        resp = await endpoint(request)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(asyncio.wait_for(_run(), timeout=20))

    research_handler.start_research.assert_called_once()
    _, kwargs = research_handler.start_research.call_args
    assert kwargs.get("owner") == "alice"


def test_chat_stream_research_privilege_deny_suppresses_start(monkeypatch):
    """can_use_research=False on the stream path never starts research (PASSES).

    Companion to the /api/chat gap pinned (xfail) in test_chat_privilege_matrix.py.
    """
    monkeypatch.setattr(chat_routes, "_verify_session_owner", lambda *a, **k: None)
    monkeypatch.setattr(chat_routes, "_clear_orphaned_session_endpoint", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "_recover_empty_session_model", lambda sess, sid, owner=None: False)
    monkeypatch.setattr(chat_routes, "resolve_session_auth", lambda sess, sid, owner=None: None)
    monkeypatch.setattr(chat_routes, "coerce_message_and_session",
                        lambda body, message, session, sm, allow_empty=False: (message or "hello", session or "sess-r2"))
    monkeypatch.setattr(chat_routes, "_classify_tool_intent", lambda message: None)
    monkeypatch.setattr(chat_routes, "_is_contextual_web_followup", lambda message, sess: False)
    monkeypatch.setattr(chat_routes, "_ensure_current_request_is_latest_user", lambda messages, current: messages)
    monkeypatch.setattr(chat_routes, "_is_image_generation_session", lambda sess, owner=None: False)
    monkeypatch.setattr(chat_routes, "get_session_mode", lambda sid: "chat")
    monkeypatch.setattr(chat_routes, "set_session_mode", lambda sid, mode: None)
    monkeypatch.setattr(chat_routes, "_owner_session_filter", lambda query, user: query)
    monkeypatch.setattr(chat_routes, "SessionLocal", lambda: _EmptyDB())
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "effective_user", lambda request: "alice")
    monkeypatch.setattr(chat_helpers_mod, "SessionLocal", lambda: _ZeroCountDB())
    monkeypatch.setattr(settings_mod, "get_setting", lambda key, default=None: default)

    async def fake_ctx(*args, **kwargs):
        return SimpleNamespace(
            messages=[{"role": "user", "content": "hi"}],
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
            user="alice",
            uprefs={},
        )

    monkeypatch.setattr(chat_routes, "build_chat_context", fake_ctx)

    async def _empty_gen():
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(chat_routes, "stream_agent_loop", lambda *a, **k: _empty_gen())
    monkeypatch.setattr(chat_routes, "save_assistant_response", lambda *a, **k: "msg-1")
    monkeypatch.setattr(chat_routes, "run_post_response_tasks", lambda *a, **k: None)

    research_handler = MagicMock()

    async def fake_form():
        return {"message": "hi", "session": "sess-r2",
                "mode": "agent", "use_research": "true"}

    auth_manager = SimpleNamespace(get_privileges=lambda user: {"can_use_research": False})
    request = SimpleNamespace(
        headers={},
        state=SimpleNamespace(current_user="alice"),
        app=SimpleNamespace(state=SimpleNamespace(auth_manager=auth_manager)),
        form=fake_form,
    )

    router = chat_routes.setup_chat_routes(
        _FakeSessionManager(), MagicMock(), MagicMock(), MagicMock(),
        research_handler, MagicMock(),
    )
    endpoint = _ep(router, "/api/chat_stream")

    async def _run():
        resp = await endpoint(request)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(asyncio.wait_for(_run(), timeout=20))
    research_handler.start_research.assert_not_called()


# ── Part 2: cross-user poll isolation on the research routes ─────────

def _research_request(user):
    return SimpleNamespace(state=SimpleNamespace(current_user=user))


def _handler_with_bob_task():
    handler = MagicMock()
    handler._active_tasks = {
        "s-bob": {
            "status": "running",
            "progress": {"phase": "searching"},
            "query": "bob secret query",
            "started_at": 0.0,
            "owner": "bob",
        }
    }
    return handler


def test_research_status_cross_user_is_404():
    """Alice polling Bob's in-flight research → 404. PASSES."""
    router = setup_research_routes(_handler_with_bob_task())
    target = _ep(router, "/api/research/status/{session_id}", "GET")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(target(session_id="s-bob", request=_research_request("alice")))
    assert exc.value.status_code == 404


def test_research_result_cross_user_is_404():
    """Alice fetching Bob's result → 404 before get_sources runs. PASSES."""
    handler = _handler_with_bob_task()
    router = setup_research_routes(handler)
    target = _ep(router, "/api/research/result/{session_id}", "POST")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(target(session_id="s-bob", request=_research_request("alice")))
    assert exc.value.status_code == 404
    handler.get_sources.assert_not_called()


def test_research_stream_cross_user_is_404():
    """Alice subscribing to Bob's research SSE → 404. PASSES."""
    router = setup_research_routes(_handler_with_bob_task())
    target = _ep(router, "/api/research/stream/{session_id}", "GET")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(target(session_id="s-bob", request=_research_request("alice")))
    assert exc.value.status_code == 404


def test_research_active_hides_other_users_tasks():
    """The active-task list only contains the caller's runs. PASSES."""
    router = setup_research_routes(_handler_with_bob_task())
    target = _ep(router, "/api/research/active", "GET")
    out = asyncio.run(target(request=_research_request("alice")))
    assert out == {"active": []}


def test_research_status_anonymous_is_401():
    """No identity + auth enabled → 401 on poll endpoints. PASSES."""
    router = setup_research_routes(_handler_with_bob_task())
    target = _ep(router, "/api/research/status/{session_id}", "GET")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(target(session_id="s-bob", request=_research_request(None)))
    assert exc.value.status_code == 401


# ── Part 3: handler accessors are keyed by session ───────────────────

def test_handler_status_missing_session_returns_none_not_neighbor_data(monkeypatch, tmp_path):
    """get_status for an unknown session → None (Bob's entry never leaks). PASSES."""
    monkeypatch.setattr("src.research_handler.RESEARCH_DATA_DIR", tmp_path)
    fake_self = SimpleNamespace(_active_tasks={
        "s-bob": {"status": "running", "progress": {}, "query": "bob secret",
                  "started_at": 0.0, "owner": "bob"},
    })
    assert ResearchHandler.get_status(fake_self, "s-alice") is None


def test_handler_sources_missing_session_returns_none_not_neighbor_data(monkeypatch, tmp_path):
    """get_sources for an unknown session → None (Bob's sources never leak). PASSES."""
    monkeypatch.setattr("src.research_handler.RESEARCH_DATA_DIR", tmp_path)
    fake_self = SimpleNamespace(_active_tasks={
        "s-bob": {"status": "done", "sources": [{"url": "https://bob.example/secret"}],
                  "researcher": None, "owner": "bob"},
    })
    assert ResearchHandler.get_sources(fake_self, "s-alice") is None
    # Positive control: the accessor itself works — isolation is by key.
    assert ResearchHandler.get_sources(fake_self, "s-bob") == [
        {"url": "https://bob.example/secret"}
    ]
