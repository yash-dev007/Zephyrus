import asyncio
from contextlib import asynccontextmanager
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.mcp_manager import _format_mcp_connection_error, McpManager


def test_custom_stdio_uses_only_explicit_environment(tmp_path, monkeypatch):
    server = tmp_path / "server.py"
    server.write_text(
        'import os\n'
        'from mcp.server.fastmcp import FastMCP\n'
        'server = FastMCP("fixture")\n'
        '@server.tool()\n'
        'def inspect_environment() -> str:\n'
        '    return os.environ["USERNAME"] + ":" + str("HOST_ONLY_SECRET" in os.environ)\n'
        'server.run()\n', encoding="utf-8",
    )
    monkeypatch.setenv("HOST_ONLY_SECRET", "private")
    manager = McpManager()
    env = {"USERNAME": "test-user", "ACCOUNT_TOKEN": "private-token"}

    async def exercise():
        try:
            assert await asyncio.create_task(manager.connect_server(
                "custom", "Custom", "stdio", sys.executable, [str(server)], env
            ))
            assert manager.get_server_status("custom")["identity"] == "test-user"
            reply = await manager.call_tool("mcp__custom__inspect_environment", {})
            assert reply["exit_code"] == 0
            assert reply["stdout"] == "test-user:False"
        finally:
            await manager.disconnect_server("custom")
        assert manager.get_server_status("custom")["status"] == "disconnected"

    asyncio.run(asyncio.wait_for(exercise(), 30))


def test_playwright_mcp_connection_error_includes_install_hint():
    msg = _format_mcp_connection_error(
        "Browser (Playwright)",
        "npx",
        ["-y", "@playwright/mcp@latest", "--headless"],
        RuntimeError("package not found"),
    )

    assert "package not found" in msg
    assert "Browser MCP could not start" in msg
    assert "npx -y @playwright/mcp@latest --version" in msg
    assert "restart Zephyrus" in msg


def test_generic_mcp_connection_error_preserves_original_error():
    msg = _format_mcp_connection_error(
        "Custom MCP",
        "python",
        ["server.py"],
        RuntimeError("boom"),
    )

    assert msg == "boom"


def test_shutdown_during_stdio_handshake_reaps_subprocess(tmp_path, monkeypatch):
    import mcp
    from mcp.client import stdio

    # The child waits for EOF without replying to MCP initialize.
    script = tmp_path / "pending.py"
    script.write_text("import sys\nsys.stdin.buffer.read()\n", encoding="utf-8")
    entered = asyncio.Event()
    closed = asyncio.Event()
    original_transport = stdio.stdio_client
    original_initialize = mcp.ClientSession.initialize

    @asynccontextmanager
    async def transport(params):
        owner = asyncio.current_task()
        try:
            async with original_transport(params) as streams:
                yield streams
        finally:
            assert asyncio.current_task() is owner
            closed.set()

    async def initialize(session):
        entered.set()
        return await original_initialize(session)

    monkeypatch.setattr(stdio, "stdio_client", transport)
    monkeypatch.setattr(mcp.ClientSession, "initialize", initialize)

    async def exercise():
        manager = McpManager()
        pending = asyncio.create_task(manager.connect_server("pending", "Pending", "stdio", sys.executable, [str(script)]))
        await entered.wait()
        await manager.disconnect_all()
        assert await pending is False
        assert closed.is_set()
        assert manager.get_all_statuses() == {}

    asyncio.run(asyncio.wait_for(exercise(), 20))


def test_http_session_and_transport_close_in_opening_task(monkeypatch):
    import mcp
    from mcp.client import streamable_http
    from src import mcp_oauth

    order = []

    @asynccontextmanager
    async def transport(url, auth):
        owner = asyncio.current_task()
        yield None, None, None
        assert asyncio.current_task() is owner
        order.append("transport")

    @asynccontextmanager
    async def session(*streams):
        owner = asyncio.current_task()
        client = AsyncMock()
        client.list_tools.return_value = SimpleNamespace(tools=[])
        yield client
        assert asyncio.current_task() is owner
        order.append("session")

    monkeypatch.setattr(streamable_http, "streamablehttp_client", transport)
    monkeypatch.setattr(mcp_oauth, "build_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr(mcp, "ClientSession", session)

    async def exercise():
        manager = McpManager()
        assert await asyncio.create_task(manager.connect_server("srv", "Server", "http", url="http://fixture"))
        await manager.disconnect_all()
        assert order == ["session", "transport"]

    asyncio.run(exercise())
