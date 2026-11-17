"""Research-domain tool implementations.

Extracted from tool_implementations.py as part of slice 1 (#4082/#4071).

Holds the ``manage_research`` (library CRUD) and ``trigger_research`` (live job)
tools. ``src.tool_implementations`` re-exports these for backward compatibility.

``_internal_headers`` and ``_INTERNAL_BASE`` still live in
``tool_implementations.py`` and are imported function-locally to avoid circular
imports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.constants import DEEP_RESEARCH_DIR
from src.tools._common import _parse_tool_args

logger = logging.getLogger(__name__)

_VALID_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_READ_ACTIONS = frozenset({"read", "open", "view", "get"})
_MAX_OUTPUT_CHARS = 16_000
_MAX_SOURCES = 30
_MAX_LIST_ITEMS = 50
_MAX_ERROR_SNIPPET = 200
_HTTP_TIMEOUT_SECONDS = 30.0


def _ok(output: str, **extra: Any) -> Dict[str, Any]:
    return {"output": output, "exit_code": 0, **extra}


def _err(message: str) -> Dict[str, Any]:
    return {"error": message, "exit_code": 1}


def _sanitize_md_label(text: str) -> str:
    """Keep clickable markdown anchor labels single-line and bracket-safe."""
    return text.replace("\r", " ").replace("\n", " ").replace("[", "(").replace("]", ")").strip()


def _parse_timestamp(value: Any) -> float:
    """Normalize numeric or ISO-8601 timestamps into a sortable float."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return 0.0
        try:
            return float(raw)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _load_research_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load research file %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("Unexpected JSON root type in %s: %s", path, type(data).__name__)
        return None
    return data


def _resolve_research_path(data_dir: Path, rid: str) -> Optional[Path]:
    """Resolve <data_dir>/<rid>.json safely inside data_dir."""
    if not _VALID_ID_RE.fullmatch(rid):
        return None
    base = data_dir.resolve()
    candidate = (base / f"{rid}.json").resolve()
    if not candidate.is_relative_to(base):
        return None
    return candidate


def _format_source_line(source: Any) -> Optional[str]:
    if isinstance(source, str):
        url = source.strip()
        return f"- {url}" if url else None
    if isinstance(source, dict):
        url = str(source.get("url") or "").strip()
        title = str(source.get("title") or url).strip()
        if not title and not url:
            return None
        return f"- {title}: {url}" if url else f"- {title}"
    return None


def _read_research_sync(data_dir: Path, rid: str) -> Dict[str, Any]:
    path = _resolve_research_path(data_dir, rid)
    if path is None:
        return _err("Invalid research id.")
    if not path.exists():
        return _err(f"Research '{rid}' not found.")

    record = _load_research_json(path)
    if record is None:
        return _err(f"Research '{rid}' could not be read or contains invalid JSON.")

    title = str(record.get("query") or "(untitled)")
    summary = str(
        record.get("result")
        or record.get("raw_report")
        or record.get("summary")
        or record.get("report")
        or "(no report body)"
    )
    out = f"# {title}\n\n{summary}"

    raw_sources = record.get("sources")
    if isinstance(raw_sources, list):
        source_lines = [
            line for line in (_format_source_line(s) for s in raw_sources[:_MAX_SOURCES]) if line
        ]
        if source_lines:
            out += "\n\nSources:\n" + "\n".join(source_lines)

    if len(out) > _MAX_OUTPUT_CHARS:
        suffix = "\n\n... (truncated)"
        out = out[: _MAX_OUTPUT_CHARS - len(suffix)] + suffix

    return _ok(out)


def _delete_research_sync(data_dir: Path, rid: str) -> Dict[str, Any]:
    path = _resolve_research_path(data_dir, rid)
    if path is None:
        return _err("Invalid research id.")
    if not path.exists():
        return _err(f"Research '{rid}' not found.")

    try:
        path.unlink()
    except OSError as exc:
        logger.warning("Failed to delete research file %s: %s", path, exc)
        return _err(f"Failed to delete research '{rid}'.")
    return _ok(f"Deleted research '{rid}'.")


def _list_research_sync(data_dir: Path, search: str) -> Dict[str, Any]:
    items: List[Tuple[float, str, str, int]] = []
    if data_dir.exists():
        for path in data_dir.glob("*.json"):
            record = _load_research_json(path)
            if record is None:
                continue
            query = str(record.get("query") or "")
            if search and search not in query.lower():
                continue
            sources = record.get("sources")
            source_count = len(sources) if isinstance(sources, list) else 0
            completed_at = _parse_timestamp(record.get("completed_at"))
            items.append((completed_at, path.stem, query, source_count))

    items.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not items:
        hint = f" (search: {search})" if search else ""
        return _ok(f"No research found in the library.{hint}")

    rows = "\n".join(
        f"- [{_sanitize_md_label(query) or '(untitled)'}](#research-{sid}) — {count} sources"
        for _, sid, query, count in items[:_MAX_LIST_ITEMS]
    )
    noun = "item" if len(items) == 1 else "items"
    return _ok(f"Research library ({len(items)} {noun}):\n{rows}")


def _parse_optional_args(content: str) -> Optional[Dict[str, Any]]:
    raw = (content or "").strip()
    if not raw or not raw.startswith("{"):
        return {}
    try:
        parsed = _parse_tool_args(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def do_manage_research(content: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """List, read/open, or delete saved deep-research results from the Library.

    Args (JSON): ``{"action": "list|read|delete", "id": "<id>", "search": "..."}``.
    Research is stored as ``data/deep_research/<id>.json`` (query, summary, sources).
    """
    # TODO: Enforce per-owner isolation if DEEP_RESEARCH_DIR becomes multi-tenant.
    _ = owner

    args = _parse_optional_args(content)
    if args is None:
        return _err("Invalid JSON arguments.")

    action = str(args.get("action") or "list").strip().lower()
    rid = str(args.get("id") or args.get("session_id") or args.get("research_id") or "").strip()
    data_dir = Path(DEEP_RESEARCH_DIR)

    if rid and not _VALID_ID_RE.fullmatch(rid):
        return _err("Invalid research id.")

    if action in _READ_ACTIONS:
        if not rid:
            return _err("Provide the research id (from action='list').")
        return await asyncio.to_thread(_read_research_sync, data_dir, rid)

    if action == "delete":
        if not rid:
            return _err("Provide the research id to delete (from action='list').")
        return await asyncio.to_thread(_delete_research_sync, data_dir, rid)

    if action == "list":
        search = str(args.get("search") or "").strip().lower()
        return await asyncio.to_thread(_list_research_sync, data_dir, search)

    return _err(f"Unknown action '{action}'. Expected 'list', 'read', or 'delete'.")


async def do_trigger_research(content: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """Start a live deep-research job that appears in the Deep Research sidebar.

    Hits ``/api/research/start`` (the same path the sidebar's 'Research' button uses)
    so the session is discoverable and streamable there.
    """
    # Shared constants still live in the facade; keep function-local to avoid circular import.
    from src.tool_implementations import _INTERNAL_BASE, _internal_headers

    try:
        args = _parse_tool_args(content)
    except ValueError:
        return _err("Invalid JSON arguments.")
    if not isinstance(args, dict):
        return _err("Arguments must be a JSON object.")

    topic = str(args.get("topic") or args.get("query") or "").strip()
    if not topic:
        return _err("topic (or query) is required.")

    payload: Dict[str, Any] = {"query": topic}
    for key in ("max_rounds", "max_time"):
        val = args.get(key)
        if val is not None:
            if isinstance(val, bool):
                return _err(f"{key} must be a positive integer.")
            try:
                parsed_int = int(val)
            except (ValueError, TypeError):
                return _err(f"{key} must be a positive integer.")
            if parsed_int <= 0:
                return _err(f"{key} must be a positive integer.")
            payload[key] = parsed_int

    for key in ("category", "search_provider"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            payload[key] = val.strip()

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{_INTERNAL_BASE}/api/research/start",
                json=payload,
                headers=_internal_headers(owner),
            )
    except httpx.TimeoutException:
        return _err("Research service timed out while starting the job.")
    except httpx.RequestError as exc:
        logger.warning("Research start request failed: %s", exc)
        return _err("Could not reach the research service.")

    if resp.status_code >= 400:
        return _err(f"research/start returned HTTP {resp.status_code}: {resp.text[:_MAX_ERROR_SNIPPET]}")

    try:
        data = resp.json()
    except ValueError:
        return _err("Research service returned invalid JSON.")
    if not isinstance(data, dict):
        return _err("Research service returned an unexpected response shape.")

    sid = str(data.get("session_id") or "?")
    anchor = f"[{_sanitize_md_label(topic)}](#research-{sid})"
    return _ok(
        f"Deep research started: {anchor}. "
        "Click to open the Deep Research sidebar and watch progress / read the report.",
        session_id=sid,
        anchor=anchor,
        ui_event="research_started",
        research_session_id=sid,
    )