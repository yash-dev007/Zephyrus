"""Incognito turns must stay out of the database, and the inline memory
command must not swallow ordinary sentences."""

import tempfile

import core.models as models
from core.models import ChatMessage, Session


class _Mgr:
    def __init__(self):
        self.persisted = []

    def _persist_message(self, session_id, message):
        self.persisted.append((session_id, message))


def test_incognito_session_skips_persistence(monkeypatch):
    mgr = _Mgr()
    monkeypatch.setattr(models, "_SESSION_MANAGER_INSTANCE", mgr)

    sess = Session(id="s1", name="Nobody", endpoint_url="", model="m", incognito=True)
    sess.add_message(ChatMessage("user", "secret"))
    assert mgr.persisted == []
    assert len(sess.history) == 1

    sess.incognito = False
    sess.add_message(ChatMessage("user", "public"))
    assert len(mgr.persisted) == 1


def test_manager_add_message_cannot_bypass_incognito(monkeypatch):
    from core.session_manager import SessionManager
    import core.session_manager as session_manager

    session = Session(id="s1", name="Nobody", endpoint_url="", model="m", incognito=True)
    manager = SessionManager.__new__(SessionManager)
    manager.sessions = {session.id: session}
    monkeypatch.setattr(manager, "get_session", lambda sid: session)

    def no_database():
        raise AssertionError("Incognito message opened a database connection")

    monkeypatch.setattr(session_manager, "SessionLocal", no_database)
    manager.add_message(session.id, ChatMessage("user", "secret"))
    assert session.history[-1].content == "secret"


def test_memory_command_requires_separator():
    from src.memory import MemoryManager

    with tempfile.TemporaryDirectory() as d:
        mm = MemoryManager(d)
        assert mm.process_inline_memory_command("remember: buy milk") == (True, "buy milk")
        assert mm.process_inline_memory_command("remember - buy milk") == (True, "buy milk")
        assert mm.process_inline_memory_command("Save the file as report.txt") == (False, "")
        assert mm.process_inline_memory_command("save -5 dollars") == (False, "")


def test_memory_command_keeps_other_owners_entries(tmp_path, monkeypatch):
    """save() replaces the whole file, so the write must start from load_all()."""
    import asyncio

    import src.database as database
    from core.models import Session
    from src.chat_handler import ChatHandler
    from src.memory import MemoryManager

    monkeypatch.setattr(database, "update_session_last_accessed", lambda *a, **k: None, raising=False)

    mm = MemoryManager(str(tmp_path))
    mm.save([{"id": "a", "text": "alice fact", "owner": "alice",
              "timestamp": 0, "source": "user", "category": "fact"}])

    class _SM:
        def save_sessions(self):
            pass

    handler = ChatHandler(_SM(), mm, None, None, None, None)
    sess = Session(id="s", name="c", endpoint_url="", model="m", owner="bob")
    asyncio.run(handler.handle_memory_command(sess, "remember: bob fact", owner="bob"))

    assert {e["text"] for e in mm.load_all()} == {"alice fact", "bob fact"}


def test_incognito_memory_command_is_not_persisted(tmp_path):
    import asyncio

    from core.models import Session
    from src.chat_handler import ChatHandler
    from src.memory import MemoryManager

    mm = MemoryManager(str(tmp_path))

    class _SM:
        def save_sessions(self):
            pass

    handler = ChatHandler(_SM(), mm, None, None, None, None)
    sess = Session(id="s", name="Nobody", endpoint_url="", model="m", incognito=True)
    reply = asyncio.run(handler.handle_memory_command(sess, "remember: secret", owner="bob"))

    assert reply == "Incognito mode: memory is not saved."
    assert mm.load_all() == []
    assert [(msg.role, msg.content) for msg in sess.history] == [
        ("user", "remember: secret"), ("assistant", reply),
    ]
    assert all(not (msg.metadata or {}).get("_db_id") for msg in sess.history)
