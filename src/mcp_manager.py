"""
mcp_manager.py

Manages connections to MCP (Model Context Protocol) tool servers.
Each server exposes tools that are made available to the agent loop.
"""

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
import json
import logging
import os
import re
from itertools import islice
from typing import Any, Dict, List, Optional, Set, Tuple

from src.runtime_paths import get_app_root

logger = logging.getLogger(__name__)

def _format_mcp_connection_error(name: str, command: str = "", args: Optional[List[str]] = None, error: Exception = None) -> str:
    """Return a user-actionable MCP connection error message."""
    args = args or []
    raw_error = str(error) if error else "Unknown error"
    command_line = " ".join([command or "", *args]).strip()
    lower_command = command_line.lower()

    if "@playwright/mcp" in lower_command:
        return (
            f"{raw_error}\n\n"
            "Browser MCP could not start. On fresh installs, cache the Playwright MCP package once before connecting:\n\n"
            "npx -y @playwright/mcp@latest --version\n\n"
            "Then restart Zephyrus and reconnect the Browser MCP server."
        )

    return raw_error


# Caps for rendering untrusted MCP tool schemas into the agent prompt (issue #2660).
# MCP servers are third-party/user-added, so field names and parameter counts are
# untrusted input — bound them so an odd or hostile schema cannot distort the prompt.
_MCP_PARAM_MAX = 12   # max params rendered per tool
_MCP_TOKEN_MAX = 40   # max chars per rendered name / type token
_MCP_HINT_MAX = 300   # total-length backstop for the whole hint


def _sanitize_schema_token(value: Any, limit: int = _MCP_TOKEN_MAX) -> str:
    """Make an untrusted JSON-Schema token safe to splice into the prompt.

    Replaces control chars / newlines with a space, collapses whitespace, and
    length-caps the result, so a weird field name or type cannot inject newlines
    or run on. Normal short identifiers pass through unchanged.
    """
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _format_mcp_params(input_schema: Any) -> str:
    """Render an MCP tool's JSON-Schema inputs as a compact prompt hint.

    Without this the agent only sees a tool's name + description and has to
    guess its arguments (issue #2509). Produces e.g.
    ` Args (JSON): {"path": string (required), "limit": integer}` — names,
    coarse types, and required-ness, kept short so it stays prompt-friendly.
    Returns "" when there are no parameters.

    MCP servers are third-party, so names/types are sanitized and the parameter
    count + total length are capped (issue #2660); normal schemas are unaffected.
    """
    if not isinstance(input_schema, dict):
        return ""
    props = input_schema.get("properties")
    if not isinstance(props, dict) or not props:
        return ""
    required_fields = input_schema.get("required")
    required = {key for key in required_fields if isinstance(key, str)} if isinstance(required_fields, list) else set()
    parts = []
    for pname, pinfo in islice(props.items(), _MCP_PARAM_MAX):
        pinfo = pinfo if isinstance(pinfo, dict) else {}
        ptype = pinfo.get("type") or "any"
        if isinstance(ptype, list):
            ptype = "|".join(str(x) for x in ptype)
        tag = f'"{_sanitize_schema_token(pname)}": {_sanitize_schema_token(ptype)}'
        if pname in required:
            tag += " (required)"
        parts.append(tag)
    extra = len(props) - len(parts)
    if extra > 0:
        parts.append(f"…+{extra} more")
    hint = " Args (JSON): {" + ", ".join(parts) + "}"
    if len(hint) > _MCP_HINT_MAX:
        hint = hint[:_MCP_HINT_MAX - 1].rstrip() + "…"
    return hint


# Tool-name prefixes that denote a read-only/inspection operation. Used to
# classify MCP tools for plan mode when the server provides no readOnlyHint.
# These are PREFIXES, not whole words (matched via str.startswith below), so a
# stem like "summar" intentionally covers "summarise"/"summarize"/"summary".
_MCP_READONLY_VERBS = (
    "list", "get", "read", "search", "fetch", "query", "find", "describe",
    "show", "view", "lookup", "count", "status", "info", "inspect", "summar",
)


def mcp_tool_is_readonly(tool: Dict) -> bool:
    """Classify an MCP tool as safe (non-mutating) for plan mode.

    Prefer the server's own annotations (readOnlyHint / destructiveHint). When
    absent, fall back to a tool-name verb heuristic, and FAIL CLOSED (treat as
    write) for anything that doesn't clearly read — plan mode must not run a
    write tool just because its intent is ambiguous.
    """
    ann = tool.get("annotations")
    # annotations may be a dict or a pydantic model
    read_hint = None
    destructive = None
    if ann is not None:
        if isinstance(ann, dict):
            read_hint = ann.get("readOnlyHint")
            destructive = ann.get("destructiveHint")
        else:
            read_hint = getattr(ann, "readOnlyHint", None)
            destructive = getattr(ann, "destructiveHint", None)
    if read_hint is False or destructive is True:
        return False
    if read_hint is True:
        return True
    # No usable hint — heuristic on the tool name's leading verb.
    name = (tool.get("name") or "").lower()
    return name.startswith(_MCP_READONLY_VERBS)


def _discovered_tools(result) -> List[Dict]:
    """Keep tool policy metadata consistent across all MCP transports."""
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": getattr(tool, "inputSchema", {}),
            "annotations": getattr(tool, "annotations", None),
        }
        for tool in result.tools
    ]


@dataclass
class _ConnectionLifetime:
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task = field(init=False)


class McpManager:
    """Manages MCP server connections and tool routing."""

    def __init__(self):
        # server_id -> connection state
        self._connections: Dict[str, Dict[str, Any]] = {}
        # server_id -> list of tool schemas
        self._tools: Dict[str, List[Dict]] = {}
        # server_id -> MCP ClientSession
        self._sessions: Dict[str, Any] = {}
        self._lifetimes: Dict[str, _ConnectionLifetime] = {}
        self._generation = 0

    async def connect_server(
        self, server_id: str, name: str, transport: str,
        command: Optional[str] = None, args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None, url: Optional[str] = None,
    ) -> bool:
        """Wait for discovery. HTTP authorization can continue in the background."""
        lifetime = self._lifetimes.get(server_id)
        if lifetime and lifetime.stop.is_set():
            return False
        starting = lifetime is None or lifetime.task.done()
        if starting:
            lifetime = _ConnectionLifetime()
            self._lifetimes[server_id] = lifetime
            self._connections[server_id] = {"status": "connecting", "name": name, "transport": transport}
            lifetime.task = asyncio.create_task(self._serve_connection(
                lifetime, server_id, name, transport, command, args or [], env or {}, url,
            ))
        try:
            await asyncio.wait_for(lifetime.ready.wait(), timeout=8.0 if transport == "http" else None)
        except asyncio.TimeoutError:
            # The OAuth redirect callback publishes needs_auth and the login URL.
            # A slow discovery without a redirect is still connecting.
            return False
        except asyncio.CancelledError:
            if starting and self._lifetimes.get(server_id) is lifetime:
                await self.disconnect_server(server_id)
            raise
        return (self._lifetimes.get(server_id) is lifetime and not lifetime.stop.is_set()
                and self.get_server_status(server_id)["status"] == "connected")

    async def _serve_connection(self, lifetime, server_id, name, transport, command, args, env, url):
        """One task owns the SDK transport and session from entry through exit."""
        try:
            from mcp import ClientSession
            async with AsyncExitStack() as stack:
                if transport == "stdio":
                    from mcp import StdioServerParameters
                    from mcp.client.stdio import stdio_client
                    params = StdioServerParameters(command=command, args=args, env=env or None)
                    streams = await stack.enter_async_context(stdio_client(params))
                elif transport == "sse":
                    from mcp.client.sse import sse_client
                    streams = await stack.enter_async_context(sse_client(url))
                elif transport == "http":
                    from mcp.client.streamable_http import streamablehttp_client
                    from src.mcp_oauth import build_provider, clear_auth_url

                    def on_redirect(auth_url):
                        self._connections[server_id].update(status="needs_auth", auth_url=auth_url)

                    provider = build_provider(server_id, url, on_redirect=on_redirect)
                    streams = await stack.enter_async_context(streamablehttp_client(url, auth=provider))
                else:
                    raise ValueError(f"Unknown MCP transport: {transport}")

                session = await stack.enter_async_context(ClientSession(*streams[:2]))
                await session.initialize()
                tools = _discovered_tools(await session.list_tools())
                state = {"status": "connected", "name": name, "transport": transport, "tool_count": len(tools)}
                if transport == "stdio" and not self.is_builtin(server_id):
                    state["identity"] = ", ".join(
                        v for k, v in env.items()
                        if k.lower() in {"email_address", "account", "username"} and isinstance(v, str)
                    )
                if transport == "http":
                    clear_auth_url(server_id)
                self._sessions[server_id] = session
                self._tools[server_id] = tools
                self._connections[server_id] = state
                self._generation += 1
                logger.info("MCP server connected: %s (%s) - %d tools via %s", name, server_id, len(tools), transport)
                lifetime.ready.set()
                await lifetime.stop.wait()
        except Exception as exc:
            error = _format_mcp_connection_error(name, command or "", args, exc)
            logger.warning("MCP connection %s (%s) failed: %s", name, server_id, exc)
            self._connections[server_id] = {"status": "error", "error": error, "name": name}
        finally:
            self._tools.pop(server_id, None)
            self._sessions.pop(server_id, None)
            if self._connections.get(server_id, {}).get("status") == "connected":
                self._connections.pop(server_id, None)
            self._generation += 1
            lifetime.ready.set()

    async def disconnect_server(self, server_id: str):
        lifetime = self._lifetimes.get(server_id)
        if lifetime:
            if not lifetime.stop.is_set():
                lifetime.stop.set()
                if not lifetime.ready.is_set():
                    lifetime.task.cancel()
            await asyncio.gather(lifetime.task, return_exceptions=True)
            # A task cancelled before its first instruction never ran its finally.
            lifetime.ready.set()
            if self._lifetimes.get(server_id) is not lifetime:
                return
            self._lifetimes.pop(server_id)
        from src.mcp_oauth import clear_auth_url
        clear_auth_url(server_id)
        self._connections.pop(server_id, None)
        self._sessions.pop(server_id, None)
        self._tools.pop(server_id, None)
        self._generation += 1

    async def disconnect_all(self):
        """Drain pending handshakes as well as established sessions."""
        for server_id in list(self._lifetimes.keys() | self._sessions.keys()):
            await self.disconnect_server(server_id)

    async def connect_all_enabled(self):
        """Connect to all enabled MCP servers from the database."""
        from src.database import McpServer, SessionLocal

        db = SessionLocal()
        try:
            servers = db.query(McpServer).filter(McpServer.is_enabled == True).all()
            for srv in servers:
                # Retire the old built-in registration on existing installs.
                if srv.id == "email":
                    db.delete(srv)
                    db.commit()
                    continue
                args = json.loads(srv.args) if srv.args else []
                env = json.loads(srv.env) if srv.env else {}
                await self.connect_server(
                    server_id=srv.id,
                    name=srv.name,
                    transport=srv.transport,
                    command=srv.command,
                    args=args,
                    env=env,
                    url=srv.url,
                )
        finally:
            db.close()

    async def call_tool(self, qualified_name: str, arguments: Dict) -> Dict:
        """Call an MCP tool by its qualified name (mcp__{server_id}__{tool_name}).

        Returns a result dict compatible with agent_tools format.
        """
        parts = qualified_name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            return {"error": f"Invalid MCP tool name: {qualified_name}", "exit_code": 1}

        server_id = parts[1]
        tool_name = parts[2]

        session = self._sessions.get(server_id)
        if not session:
            return {"error": f"MCP server not connected: {server_id}", "exit_code": 1}

        try:
            result = await self._do_call(session, tool_name, arguments)
        except Exception as e:
            # Auto-reconnect for builtin servers whose subprocess may have died
            if self.is_builtin(server_id):
                logger.warning(f"MCP call failed for {qualified_name}, attempting reconnect: {e}")
                reconnected = await self._reconnect_builtin(server_id)
                if reconnected:
                    session = self._sessions.get(server_id)
                    if session:
                        try:
                            result = await self._do_call(session, tool_name, arguments)
                        except Exception as e2:
                            logger.error(f"MCP tool call failed after reconnect: {qualified_name}: {e2}")
                            return {"error": str(e2), "exit_code": 1}
                    else:
                        return {"error": f"Reconnected but no session for {server_id}", "exit_code": 1}
                else:
                    logger.error(f"MCP reconnect failed for {server_id}")
                    return {"error": f"MCP server crashed and reconnect failed: {server_id}", "exit_code": 1}
            else:
                logger.error(f"MCP tool call failed: {qualified_name}: {e}")
                return {"error": str(e), "exit_code": 1}

        return result

    async def _do_call(self, session, tool_name: str, arguments: Dict) -> Dict:
        """Execute a single MCP tool call and return result dict."""
        result = await session.call_tool(tool_name, arguments)
        output_parts = []
        images = []
        for content in result.content:
            if hasattr(content, 'text'):
                output_parts.append(content.text)
            elif getattr(content, 'type', '') == 'image' and hasattr(content, 'data'):
                # Image content (e.g. Playwright screenshots)
                mime = getattr(content, 'mimeType', 'image/png')
                images.append({"data": content.data, "mimeType": mime})
                output_parts.append(f"[Screenshot captured ({mime})]")
            elif hasattr(content, 'data'):
                output_parts.append(str(content.data))

        output = "\n".join(output_parts)
        is_error = getattr(result, 'isError', False)

        result_dict = {
            "stdout": output if not is_error else "",
            "stderr": output if is_error else "",
            "exit_code": 1 if is_error else 0,
        }
        if images:
            result_dict["images"] = images
        return result_dict

    async def _reconnect_builtin(self, server_id: str) -> bool:
        """Tear down and reconnect a crashed builtin MCP server."""
        import sys
        from src.builtin_mcp import _BUILTIN_SERVERS, builtin_python_env

        if server_id not in _BUILTIN_SERVERS:
            return False

        script_rel, name = _BUILTIN_SERVERS[server_id]
        base_dir = get_app_root()
        script_path = os.path.join(base_dir, script_rel)

        # Clean up old connection
        await self.disconnect_server(server_id)

        try:
            ok = await self.connect_server(
                server_id=server_id,
                name=name,
                transport="stdio",
                command=sys.executable,
                args=[script_path],
                env=builtin_python_env(base_dir),
            )
            if ok:
                logger.info(f"Reconnected builtin MCP server: {name}")
            return ok
        except Exception as e:
            logger.error(f"Failed to reconnect builtin MCP server {name}: {e}")
            return False

    def get_all_openai_schemas(self, disabled_map: Optional[Dict[str, set]] = None) -> List[Dict]:
        """Return all MCP tools in OpenAI function-calling format.

        Tool names are namespaced as mcp__{server_id}__{tool_name}.
        disabled_map: optional {server_id: set_of_disabled_tool_names} to filter out.
        """
        schemas = []
        for server_id, tools in self._tools.items():
            # Skip builtin Python servers — they use the code-block tool format
            # But include NPX-based builtins (like browser) which need function calling
            if self.is_builtin(server_id) and server_id != "builtin_browser":
                continue
            conn = self._connections.get(server_id, {})
            server_name = conn.get("name", server_id)
            disabled = (disabled_map or {}).get(server_id, set())

            identity = conn.get("identity", "")
            label = f"{server_name} ({identity})" if identity else server_name

            for tool in tools:
                if tool["name"] in disabled:
                    continue
                qualified = f"mcp__{server_id}__{tool['name']}"
                schema = {
                    "type": "function",
                    "function": {
                        "name": qualified,
                        "description": f"[MCP:{label}] {tool['description']}",
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
                schemas.append(schema)

        return schemas

    def get_all_tools(self, disabled_map: Optional[Dict[str, set]] = None) -> List[Dict]:
        """Return a flat list of all discovered tools with server info."""
        result = []
        for server_id, tools in self._tools.items():
            conn = self._connections.get(server_id, {})
            disabled = (disabled_map or {}).get(server_id, set())
            for tool in tools:
                result.append({
                    "server_id": server_id,
                    "server_name": conn.get("name", server_id),
                    "name": tool["name"],
                    "qualified_name": f"mcp__{server_id}__{tool['name']}",
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("input_schema") or {},
                    "is_disabled": tool["name"] in disabled,
                })
        return result

    def plan_mode_blocked_mcp(self) -> Tuple[Dict[str, Set[str]], Set[str]]:
        """Plan mode: block every MCP tool that isn't clearly read-only.

        Returns (disabled_map, qualified_names):
          - disabled_map: {server_id: {tool_name, ...}} to hide write tools from
            the prompt/schemas (merged into the existing mcp_disabled_map).
          - qualified_names: {"mcp__<server>__<tool>", ...} for runtime rejection
            in execute_tool_block (which matches the qualified name).
        """
        disabled_map: Dict[str, Set[str]] = {}
        qualified: Set[str] = set()
        for server_id, tools in self._tools.items():
            for tool in tools:
                if not mcp_tool_is_readonly(tool):
                    disabled_map.setdefault(server_id, set()).add(tool["name"])
                    qualified.add(f"mcp__{server_id}__{tool['name']}")
        return disabled_map, qualified

    def is_builtin(self, server_id: str) -> bool:
        """Check if a server is a built-in (auto-registered) server."""
        return server_id.startswith("builtin_") or server_id in {
            "image_gen",
            "memory",
            "rag",
        }

    def get_server_status(self, server_id: str) -> Dict:
        """Get connection status for a server."""
        return self._connections.get(server_id, {"status": "disconnected"})

    def get_all_statuses(self) -> Dict[str, Dict]:
        """Get connection statuses for all servers."""
        return dict(self._connections)

    _cached_prompt_desc = None
    _cached_prompt_desc_key = None

    def get_tool_descriptions_for_prompt(self, disabled_map: Optional[Dict[str, set]] = None) -> str:
        """Generate text describing MCP tools for the agent system prompt. Cached."""
        cache_key = (
            frozenset((k, frozenset(v)) for k, v in (disabled_map or {}).items()),
            len(self._tools),
            self._generation,
        )
        if self._cached_prompt_desc is not None and self._cached_prompt_desc_key == cache_key:
            return self._cached_prompt_desc
        tools = self.get_all_tools(disabled_map)
        if not tools:
            return ""

        lines = ["\n\nYou also have access to external MCP tool servers. These tools are called via native function calling:"]
        by_server = {}
        for t in tools:
            # Skip builtin Python servers — they're already in the agent prompt
            # But include NPX-based builtins (like browser) which aren't hardcoded
            if self.is_builtin(t["server_id"]) and t["server_id"] != "builtin_browser":
                continue
            if t.get("is_disabled"):
                continue
            sn = t["server_name"]
            if sn not in by_server:
                by_server[sn] = []
            by_server[sn].append(t)

        if not by_server:
            return ""

        for server_name, server_tools in by_server.items():
            # Include identity (e.g. email address) if available
            sid = server_tools[0]["server_id"] if server_tools else ""
            identity = self._connections.get(sid, {}).get("identity", "")
            label = f"{server_name} ({identity})" if identity else server_name
            lines.append(f"\n**{label}:**")
            for t in server_tools:
                # Truncate long descriptions
                desc = t['description'][:120] + '...' if len(t['description']) > 120 else t['description']
                # Include the tool's declared inputs so the model calls it with
                # real argument names instead of guessing from the description
                # alone (issue #2509).
                args_hint = _format_mcp_params(t.get("input_schema"))
                lines.append(f"  - {t['qualified_name']}: {desc}{args_hint}")

        result = "\n".join(lines)
        self._cached_prompt_desc = result
        self._cached_prompt_desc_key = cache_key
        return result
