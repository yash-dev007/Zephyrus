"""Rewrite the selected reply without changing another row or saving private text."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.database as database
from core.models import ChatMessage, Session
import routes.chat_routes as routes


@pytest.fixture
def rewrite_case(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'rewrite.db'}")
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(database.Session(id="session", name="Chat", model="m", endpoint_url="url"))
        db.add_all([
            database.ChatMessage(id="first", session_id="session", role="assistant", content="First reply"),
            database.ChatMessage(id="last", session_id="session", role="assistant", content="Last reply"),
            database.ChatMessage(id="user", session_id="session", role="user", content="Question"),
        ])
        db.commit()
    session = Session(id="session", name="Chat", endpoint_url="url", model="m", history=[
        ChatMessage("assistant", "First reply", {"_db_id": "first"}),
        ChatMessage("assistant", "Last reply", {"_db_id": "last"}),
        ChatMessage("user", "Question", {"_db_id": "user"}),
    ])
    manager = SimpleNamespace(get_session=lambda sid: session, save_sessions=lambda: None)
    monkeypatch.setattr(routes, "SessionLocal", factory)
    monkeypatch.setattr(routes, "_verify_session_owner", lambda *a: None)
    monkeypatch.setattr(routes, "_enforce_chat_privileges", lambda *a: None)
    monkeypatch.setattr(routes, "resolve_session_auth", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "effective_user", lambda request: "alice")

    async def stream(*a, **kw):
        yield 'data: {"delta": "Rewritten"}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(routes, "stream_llm", stream)
    router = routes.setup_chat_routes(manager, None, None, None, None, None)
    endpoint = next(r.endpoint for r in router.routes if r.path == "/api/rewrite")

    def run(msg_id="first", original_text="First reply"):
        async def body():
            return {"session_id": "session", "msg_id": msg_id,
                    "original_text": original_text, "instruction": "Make it shorter"}

        async def consume():
            response = await endpoint(SimpleNamespace(json=body))
            return [chunk async for chunk in response.body_iterator]

        return asyncio.run(consume())

    def saved():
        with factory() as db:
            return {row.id: row.content for row in db.query(database.ChatMessage).all()}

    yield session, run, saved
    engine.dispose()


@pytest.mark.parametrize("as_dict", [False, True])
@pytest.mark.parametrize("msg_id", ["first", ""])
def test_rewrite_updates_only_selected_reply(rewrite_case, as_dict, msg_id):
    session, run, saved = rewrite_case
    if as_dict:
        session.history[0] = {"role": "assistant", "content": "First reply", "metadata": {"_db_id": "first"}}
    run(msg_id=msg_id)
    assert saved() == {"first": "Rewritten", "last": "Last reply", "user": "Question"}


@pytest.mark.parametrize("msg_id", ["missing", "user", ""])
def test_unmatched_reply_is_rejected_without_changing_history(rewrite_case, msg_id):
    session, run, saved = rewrite_case
    with pytest.raises(HTTPException) as exc:
        run(msg_id=msg_id, original_text="Not a saved reply")
    assert exc.value.status_code == 404
    assert saved()["last"] == "Last reply"
    assert session.history[1].content == "Last reply"


def test_ephemeral_reply_never_overwrites_persisted_reply(rewrite_case):
    session, run, saved = rewrite_case
    session.history.append(ChatMessage("assistant", "Private reply"))
    run(msg_id="", original_text="Private reply")
    assert session.history[-1].content == "Rewritten"
    assert saved()["last"] == "Last reply"


@pytest.mark.parametrize("error", [
    'event: error\ndata: {"error": "Disconnected"}\n\n',
    'data: {"error": "Disconnected"}\n\n',
])
def test_failed_rewrite_keeps_original(rewrite_case, monkeypatch, error):
    session, run, saved = rewrite_case

    async def failed_stream(*a, **kw):
        yield 'data: {"delta": "Incomplete"}\n\n'
        yield error
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(routes, "stream_llm", failed_stream)
    assert error in run()
    assert saved()["first"] == "First reply"
    assert session.history[0].content == "First reply"
