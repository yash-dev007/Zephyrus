"""Read-only runtime inventory for the chat harness command."""
from fastapi import APIRouter, Request

from core.database import McpServer, SessionLocal
from core.middleware import require_admin
from src.mcp_manager import McpManager
from src.settings import get_setting


def setup_harness_routes(mcp_manager: McpManager) -> APIRouter:
    router = APIRouter(prefix="/api/harness", tags=["harness"])

    @router.get("/runtime")
    def runtime(request: Request):
        require_admin(request)
        servers = {
            sid: {"name": state.get("name") or sid, "status": state.get("status", "unknown")}
            for sid, state in mcp_manager.get_all_statuses().items()
        }
        with SessionLocal() as db:
            for sid, name, enabled in db.query(McpServer.id, McpServer.name, McpServer.is_enabled):
                row = servers.setdefault(sid, {"name": name or sid, "status": "disconnected"})
                if not enabled and row["status"] == "disconnected":
                    row["status"] = "disabled"
        return {
            "verifier_enabled": bool(get_setting("agent_verifier_subagent", False)),
            "servers": sorted(servers.values(), key=lambda row: row["name"]),
        }

    return router
