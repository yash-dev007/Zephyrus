"""Backup import must dedup memories against the importing user only.

import_data deduped incoming memories against memory_manager.load_all()
(every tenant\'s rows), so a memory whose text matched ANY other user\'s
memory was silently skipped - the importing user lost their own data. The
dedup must be scoped to the caller\'s own memories. The full multi-tenant
store is still saved back.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import routes.backup_routes as br


class _Req:
    def __init__(self, body):
        self._body = body
        self.state = SimpleNamespace(current_user="admin")

    async def json(self):
        return self._body


def _setup(monkeypatch, store, user="alice"):
    monkeypatch.setattr(br, "require_admin", lambda request: None)
    monkeypatch.setattr(br, "get_current_user", lambda request: user)

    mem = MagicMock()
    mem.load_all.return_value = list(store)
    saved = {}
    mem.save.side_effect = lambda entries: saved.__setitem__("entries", entries)

    skills = MagicMock()
    skills.load_all.return_value = []
    router = br.setup_backup_routes(mem, MagicMock(), skills)
    endpoint = None
    for r in router.routes:
        if r.path == "/api/import" and "POST" in getattr(r, "methods", set()):
            endpoint = r.endpoint
    assert endpoint is not None
    return endpoint, saved


def test_user_can_import_memory_matching_another_users_text(monkeypatch):
    # bob already has "buy milk"; alice imports her own "Buy Milk".
    endpoint, saved = _setup(monkeypatch, [{"text": "buy milk", "owner": "bob"}])
    body = {"memories": [{"text": "Buy Milk"}]}
    asyncio.run(endpoint(_Req(body)))
    texts_by_owner = {(e.get("owner"), e.get("text")) for e in saved["entries"]}
    assert ("alice", "Buy Milk") in texts_by_owner  # not dropped as a "duplicate"
    assert ("bob", "buy milk") in texts_by_owner     # other tenant preserved


def test_users_own_duplicate_is_still_skipped(monkeypatch):
    endpoint, saved = _setup(monkeypatch, [{"text": "buy milk", "owner": "alice"}])
    body = {"memories": [{"text": "Buy Milk"}]}
    asyncio.run(endpoint(_Req(body)))
    alice_milk = [e for e in saved["entries"]
                  if e.get("owner") == "alice" and e.get("text", "").lower() == "buy milk"]
    assert len(alice_milk) == 1  # the real duplicate is still deduped


def test_export_includes_research_key(monkeypatch):
    # Regression: /api/export 500 because asyncio was not imported.
    import json
    from routes.backup_routes import setup_backup_routes
    from unittest.mock import MagicMock
    monkeypatch.setattr(br, "require_admin", lambda request: None)
    mem = MagicMock()
    mem.load.return_value = []
    presets = MagicMock()
    presets.get_all.return_value = []
    skills = MagicMock()
    skills.load.return_value = []
    router = setup_backup_routes(mem, presets, skills)
    req = _Req({})
    resp = asyncio.run(router.routes[0].endpoint(req))  # first route is /api/export
    body = json.loads(resp.body)
    assert "research" in body
    assert body["research"] == []
