from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.middleware import INTERNAL_TOOL_HEADER, INTERNAL_TOOL_TOKEN
from routes import harness_routes


def test_inventory_requires_admin_and_returns_only_display_fields(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    db_factory = MagicMock()
    db_factory.return_value.__enter__.return_value.query.return_value = [
        ("off", "Offline", False), ("custom", "Custom", True)
    ]
    monkeypatch.setattr(harness_routes, "SessionLocal", db_factory)
    monkeypatch.setattr(harness_routes, "get_setting", lambda key, default: True)
    manager = MagicMock()
    manager.get_all_statuses.return_value = {
        "builtin": {"name": "Builtin", "status": "connected", "auth_url": "private"},
    }
    app = FastAPI()
    app.include_router(harness_routes.setup_harness_routes(manager))
    with TestClient(app) as client:
        url = "/api/harness/runtime"
        assert client.get(url).status_code == 403
        manager.get_all_statuses.assert_not_called()
        result = client.get(url, headers={INTERNAL_TOOL_HEADER: INTERNAL_TOOL_TOKEN})
        assert result.status_code == 200
        assert result.json() == {
            "verifier_enabled": True,
            "servers": [{"name": "Builtin", "status": "connected"},
                        {"name": "Custom", "status": "disconnected"},
                        {"name": "Offline", "status": "disabled"}],
        }
