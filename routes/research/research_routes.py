"""Research background task routes — /api/research/*."""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from core.atomic_io import atomic_write_json
from core.middleware import INTERNAL_TOOL_USER
from src.endpoint_resolver import resolve_endpoint
from src.auth_helpers import _auth_disabled, get_current_user
from core.auth import RESERVED_USERNAMES
from src.constants import DEEP_RESEARCH_DIR
from src.settings import is_feature_enabled

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9-]{1,128}$")

# Lightweight metadata cache for the Library: keyed by (data_dir_str, mtime)
# so a report write invalidates it without parsing every JSON file.
_LIBRARY_CACHE: dict = {"key": None, "records": []}



def _validate_session_id(session_id: str) -> str:
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise HTTPException(400, "Invalid session ID format")
    return session_id


def _research_storage_root() -> Path:
    return Path(DEEP_RESEARCH_DIR).resolve()


def _find_research_path(session_id: str) -> Path | None:
    """Find a persisted research file without deriving its path from input."""
    expected_name = f"{_validate_session_id(session_id)}.json"
    root = _research_storage_root()
    for stored_path in root.glob("*.json"):
        if stored_path.name != expected_name:
            continue
        resolved = stored_path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return None
        if not resolved.is_file():
            return None
        return resolved
    return None


def _require_research_path(session_id: str) -> Path:
    path = _find_research_path(session_id)
    if path is None:
        raise HTTPException(404, "Research not found")
    return path


def _find_owned_research_path(session_id: str, user: str) -> Path | None:
    path = _find_research_path(session_id)
    if path is None:
        return None
    try:
        owner = json.loads(path.read_text(encoding="utf-8")).get("owner")
    except Exception:
        return None
    if owner != user:
        return None
    return path


logger = logging.getLogger(__name__)

# Model-name substrings that are NOT chat/generation models — research must
# never pick these as its model. An OpenAI-style endpoint often lists
# `text-embedding-ada-002` etc. first in its model list, which is why research
# was failing with "Cannot reach model 'text-embedding-ada-002'".
_NON_CHAT_MODEL = (
    "text-embedding", "embedding", "tts-", "whisper", "dall-e",
    "moderation", "rerank", "reranker", "clip", "stable-diffusion",
)

_RESEARCH_IMAGE_BLOCKLIST = {
    "cdn.shopify.com/s/files/1/0179/4388/7926/files/icon.png",
}


def _is_research_icon_or_logo_url(url: str) -> bool:
    path = url.lower().split("?")[0]
    return any(token in path for token in (
        "/logo", "logo_", "-logo", "favicon", "apple-touch-icon",
        "sprite", "icon-", "_icon", "/icons/", "badge",
    ))


def _research_thumbnail(data: dict) -> str:
    """Pick the same first visible image the visual report uses as hero."""
    hidden = set(data.get("hidden_images") or [])
    seen = set()

    def usable(image: str) -> bool:
        image = str(image or "").strip()
        if not image or image in seen or image in hidden:
            return False
        if not image.startswith("https://"):
            return False
        if image.endswith((".svg", ".ico", ".gif")):
            return False
        if any(blocked in image for blocked in _RESEARCH_IMAGE_BLOCKLIST):
            return False
        if _is_research_icon_or_logo_url(image):
            return False
        return True

    for source in data.get("sources") or []:
        if not isinstance(source, dict):
            continue
        image = str(source.get("image") or source.get("og_image") or "").strip()
        if usable(image):
            seen.add(image)
            return image
    for finding in data.get("raw_findings") or data.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        image = str(finding.get("image") or finding.get("og_image") or "").strip()
        if usable(image):
            seen.add(image)
            return image
    return ""


METADATA_KEYS = (
    "id", "owner", "query", "category", "source_count", "status",
    "duration", "rounds", "tokens", "started_at", "completed_at",
    "archived", "thumbnail", "sources", "stats", "hidden_images",
)


def _load_library_records(data_dir: Path) -> list[dict]:
    """Parse research JSON files, reusing cached records until files change.
    Only metadata fields are cached; full report bodies stay on disk.
    Keyed on (dir_path, file_count, max_mtime) so in-place edits (e.g. image hide)
    properly invalidate the cache.
    """
    try:
        entries = [p for p in data_dir.glob("*.json") if p.is_file()]
        file_count = len(entries)
        max_mtime = max((p.stat().st_mtime for p in entries), default=0.0)
    except OSError:
        return []
    key = (str(data_dir), file_count, max_mtime)
    if _LIBRARY_CACHE.get("key") == key:
        return _LIBRARY_CACHE.get("records") or []
    records = []
    for path in entries:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            stats = data.get("stats") or {}
            sources = data.get("sources") or []
            record = {
                "id": data.get("id") or path.stem,
                "owner": data.get("owner"),
                "query": data.get("query", ""),
                "category": data.get("category") or "",
                "source_count": len(sources) if isinstance(sources, list) else int(data.get("source_count") or 0),
                "status": data.get("status", "done"),
                "duration": stats.get("Duration", "") if stats else str(data.get("duration") or ""),
                "rounds": stats.get("Rounds", "") if stats else str(data.get("rounds") or ""),
                "tokens": stats.get("Tokens", 0) if stats else int(data.get("tokens") or 0),
                "started_at": data.get("started_at", 0),
                "completed_at": data.get("completed_at", 0),
                "archived": bool(data.get("archived")),
                "thumbnail": _research_thumbnail(data),
                "sources": sources,
                "stats": stats,
                "hidden_images": data.get("hidden_images") or [],
                "_path": path,
            }
            records.append(record)
        except Exception:
            continue
    _LIBRARY_CACHE["key"] = key
    _LIBRARY_CACHE["records"] = records
    return records


def _first_chat_model(models) -> str:
    """First model that isn't an embedding/tts/etc. — falls back to models[0]."""
    for m in (models or []):
        if not any(p in str(m).lower() for p in _NON_CHAT_MODEL):
            return m
    return (models[0] if models else "")


def _resolve_research_endpoint(sess, owner: Optional[str] = None) -> tuple:
    """Return (endpoint_url, model, headers) for Deep Research, checking admin overrides."""
    owner = owner or getattr(sess, "owner", None) or None
    url, model, headers = resolve_endpoint(
        "research",
        fallback_url=sess.endpoint_url,
        fallback_model=sess.model,
        fallback_headers=sess.headers,
        owner=owner,
    )
    return url, model, headers


def _owned_enabled_endpoint(db, owner, endpoint_id=None):
    """An enabled ModelEndpoint VISIBLE to `owner` (their own rows + legacy
    null-owner "shared" rows), optionally narrowed to a specific endpoint_id;
    None if nothing visible matches.

    Owner-scoped on purpose. ModelEndpoint is per-user (core/database.py: non-null
    owner = private, "the model picker only shows the endpoint to that user") and
    holds a decrypted `api_key`. /api/research/start feeds the resolved row's
    api_key + base_url into research_handler.start_research(llm_endpoint=,
    llm_headers=), so an UNSCOPED lookup — by the caller-supplied endpoint_id, or
    via the bare first-enabled fallback — would let a research-privileged user
    spend ANOTHER user's API key/quota and reach whatever internal base_url they
    configured. Mirrors webhook_routes._first_enabled_endpoint and
    session_routes._owned_endpoint. A null/empty owner is a no-op (single-user /
    legacy mode).
    """
    from src.database import ModelEndpoint
    from src.auth_helpers import owner_filter
    q = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)  # noqa: E712
    if endpoint_id:
        q = q.filter(ModelEndpoint.id == endpoint_id)
    return owner_filter(q, ModelEndpoint, owner).first()


def _resolve_endpoint_runtime(ep, owner=None, model: Optional[str] = None):
    """Resolve a ModelEndpoint row into (chat_url, model, headers).

    Mirrors endpoint_resolver.resolve_endpoint's provider-auth handling for
    panel-selected research endpoints. ChatGPT Subscription endpoints keep
    OAuth tokens in ProviderAuthSession, so ep.api_key is intentionally empty.
    """
    from src.endpoint_resolver import (
        build_chat_url,
        build_headers,
        resolve_endpoint_runtime as resolve_model_endpoint_runtime,
    )

    try:
        base, api_key = resolve_model_endpoint_runtime(ep, owner=owner)
    except Exception as e:
        logger.warning("Could not resolve endpoint credentials for research: %s", e)
        return None

    ep_model = (model or "").strip()
    if not ep_model:
        try:
            models = json.loads(ep.cached_models) if ep.cached_models else []
            if models:
                ep_model = _first_chat_model(models)
        except Exception:
            pass
    if not ep_model:
        return None
    return build_chat_url(base), ep_model, build_headers(api_key, base)


def setup_research_routes(research_handler, session_manager=None) -> APIRouter:
    router = APIRouter(tags=["research"])

    def _require_user(request: Request) -> str:
        """All research endpoints require an authenticated user."""
        user = get_current_user(request)
        if not user:
            if _auth_disabled():
                return ""
            raise HTTPException(401, "Not authenticated")
        return user

    def _require_research_enabled(request: Request) -> str:
        """Server-side kill switch + privilege gate for every launch path."""
        from src.auth_helpers import require_privilege
        user = require_privilege(request, "can_use_research")
        if not is_feature_enabled("deep_research"):
            raise HTTPException(403, "Deep research is disabled by the administrator.")
        return user

    def _owns_in_memory(session_id: str, user: str) -> bool:
        """Ownership check for an in-flight (in-memory) research task.
        Falls back to the on-disk JSON if the task has already finished."""
        entry = research_handler._active_tasks.get(session_id)
        if entry is not None:
            return entry.get("owner", "") == user
        # Task no longer in memory — check the persisted JSON.
        try:
            return _find_owned_research_path(session_id, user) is not None
        except HTTPException:
            return False

    def _require_owned_or_active_research_path(session_id: str, user: str) -> Path | None:
        """Validate ownership once and return the completed on-disk path.

        Active running research has no completed disk path yet. Completed
        tasks can remain in _active_tasks after persistence, so prefer their
        owned disk path when available. Completed disk lookups still reuse the
        path after the ownership gate.
        """
        entry = research_handler._active_tasks.get(session_id)
        if entry is not None:
            if entry.get("owner", "") != user:
                raise HTTPException(404, "No research found for this session")
            if entry.get("status") != "running":
                path = _find_owned_research_path(session_id, user)
                if path is not None:
                    return path
            return None

        path = _find_owned_research_path(session_id, user)
        if path is None:
            raise HTTPException(404, "No research found for this session")
        return path

    @router.get("/api/research/active")
    async def research_active(request: Request):
        """List all currently active (running) research tasks."""
        user = _require_user(request)
        active = []
        for sid, entry in research_handler._active_tasks.items():
            # SECURITY: only show this user's running tasks.
            if entry.get("owner", "") != user:
                continue
            if entry.get("status") == "running":
                active.append({
                    "session_id": sid,
                    "query": entry.get("query", ""),
                    "status": "running",
                    "progress": entry.get("progress", {}),
                    "started_at": entry.get("started_at", 0),
                    "max_time": entry.get("max_time"),
                    "max_rounds": entry.get("max_rounds"),
                    "ephemeral": bool(entry.get("ephemeral")),
                })
        return {"active": active}

    @router.get("/api/research/status/{session_id}")
    async def research_status(session_id: str, request: Request):
        user = _require_user(request)
        _validate_session_id(session_id)
        if not _owns_in_memory(session_id, user):
            return {"status": "idle", "active": False}
        status = research_handler.get_status(session_id)
        if status is None:
            return {"status": "idle", "active": False}
        return status

    @router.post("/api/research/cancel/{session_id}")
    async def research_cancel(session_id: str, request: Request):
        user = _require_user(request)
        _validate_session_id(session_id)
        if not _owns_in_memory(session_id, user):
            raise HTTPException(404, "No research found for this session")
        cancelled = research_handler.cancel_research(session_id)
        return {"cancelled": cancelled}

    @router.post("/api/research/result/{session_id}")
    async def research_result(session_id: str, request: Request):
        user = _require_user(request)
        _validate_session_id(session_id)
        if not _owns_in_memory(session_id, user):
            raise HTTPException(404, "No research result available")
        result = research_handler.get_result(session_id)
        if result is None:
            raise HTTPException(404, "No research result available")
        sources = research_handler.get_sources(session_id) or []
        raw_findings = research_handler.get_raw_findings(session_id) or []
        research_handler.clear_result(session_id)
        return {"result": result, "sources": sources, "raw_findings": raw_findings}

    def _assert_owns_research(session_id: str, user: str) -> Optional[Path]:
        """404-not-403 ownership gate for a research session.

        Returns the on-disk path for completed reports, or ``None`` for an
        owned in-memory (incognito / still-running) entry.
        """
        entry = research_handler._active_tasks.get(session_id)
        if entry is not None:
            if entry.get("owner", "") == user:
                return None
            raise HTTPException(404, "Research not found")
        path = _require_research_path(session_id)
        try:
            owner = json.loads(path.read_text(encoding="utf-8")).get("owner")
        except Exception:
            raise HTTPException(404, "Research not found")
        if owner != user:
            raise HTTPException(404, "Research not found")
        return path

    @router.get("/api/research/report/{session_id}")
    async def research_report(session_id: str, request: Request):
        """Serve the visual HTML report for a completed research session."""
        user = _require_user(request)
        _validate_session_id(session_id)
        _assert_owns_research(session_id, user)
        logger.info(f"Visual report requested for session {session_id}")
        try:
            html_content = research_handler.get_report_html(session_id)
        except Exception as e:
            logger.error(f"Visual report generation error: {e}", exc_info=True)
            raise HTTPException(500, f"Report generation failed: {e}")
        if html_content is None:
            logger.warning(f"No report data found for session {session_id}")
            raise HTTPException(404, "No visual report available for this session")
        return HTMLResponse(content=html_content)

    class HideImageRequest(BaseModel):
        url: str

    @router.post("/api/research/{session_id}/hide-image")
    async def research_hide_image(session_id: str, body: HideImageRequest, request: Request):
        """Mark an image URL as hidden for this research's visual report.
        Persisted to the research JSON so subsequent /report renders skip it."""
        user = _require_user(request)
        _validate_session_id(session_id)
        _assert_owns_research(session_id, user)
        ok = research_handler.hide_image(session_id, body.url)
        if not ok:
            raise HTTPException(404, "Research not found")
        return {"ok": True}

    @router.post("/api/research/{session_id}/unhide-images")
    async def research_unhide_images(session_id: str, request: Request):
        """Clear the hidden-images list for a research session."""
        user = _require_user(request)
        _validate_session_id(session_id)
        _assert_owns_research(session_id, user)
        ok = research_handler.unhide_all_images(session_id)
        if not ok:
            raise HTTPException(404, "Research not found")
        return {"ok": True}

    @router.get("/api/research/library")
    async def research_library(
        request: Request,
        search: Optional[str] = Query(None),
        sort: str = Query("recent"),
        limit: int = Query(50),
        archived: bool = Query(False),
    ):
        user = _require_user(request)
        """List all completed research for the Library panel."""
        try:
            research_handler._maybe_purge_retention()
        except Exception:
            pass
        data_dir = Path(DEEP_RESEARCH_DIR)
        items = []
        for d in _load_library_records(data_dir):
            try:
                # SECURITY: only show research belonging to this user. Legacy
                # JSONs without an `owner` field are hidden — auth was the only
                # gate before, so every user saw every other user's reports.
                if d.get("owner") != user:
                    continue
                # Archived view shows ONLY archived reports; default hides them.
                if bool(d.get("archived")) != archived:
                    continue
                query = d.get("query", "")
                if search and search.lower() not in query.lower():
                    continue
                sources = d.get("sources", [])
                p = d.get("_path")
                stats = d.get("stats") or {}
                thumbnail = d.get("thumbnail")
                if thumbnail is None:
                    thumbnail = _research_thumbnail(d)
                items.append({
                    "id": p.stem if p else d.get("id", ""),
                    "query": query,
                    "category": d.get("category") or "",
                    "source_count": len(sources) if isinstance(sources, list) else int(d.get("source_count") or 0),
                    "status": d.get("status", "done"),
                    "duration": stats.get("Duration", "") if stats else str(d.get("duration") or ""),
                    "rounds": stats.get("Rounds", "") if stats else str(d.get("rounds") or ""),
                    "tokens": stats.get("Tokens", 0) if stats else int(d.get("tokens") or 0),
                    "started_at": d.get("started_at", 0),
                    "completed_at": d.get("completed_at", 0),
                    "archived": bool(d.get("archived")),
                    "thumbnail": thumbnail,
                })
            except Exception:
                continue

        def _sort_ts(x: dict) -> float:
            val = x.get("completed_at")
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return float(val)
            if isinstance(val, str) and val.strip():
                try:
                    return float(val.strip())
                except ValueError:
                    pass
            return 0.0

        # Sort. "most-messages" is kept as an alias for old clients.
        if sort == "recent":
            items.sort(key=_sort_ts, reverse=True)
        elif sort == "oldest":
            items.sort(key=_sort_ts)
        elif sort in ("most-sources", "most-messages"):
            items.sort(key=lambda x: x["source_count"], reverse=True)
        elif sort == "alpha":
            items.sort(key=lambda x: str(x.get("query") or "").lower())

        return {"research": items[:limit], "total": len(items)}

    @router.get("/api/research/detail/{session_id}")
    async def research_detail(session_id: str, request: Request):
        """Return the full JSON for a single research result — sources,
        summary, stats — used by the Library preview panel."""
        user = _require_user(request)
        _validate_session_id(session_id)
        path = _require_research_path(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise HTTPException(500, f"Failed to read research: {e}")
        # SECURITY: 404 (not 403) so we don't leak that the report exists.
        if data.get("owner") != user:
            raise HTTPException(404, "Research not found")
        return data

    @router.post("/api/research/{session_id}/archive")
    async def research_archive(session_id: str, request: Request, archived: bool = Query(True)):
        """Soft-archive / restore a research report (sets `archived` in its JSON)."""
        user = _require_user(request)
        _validate_session_id(session_id)
        path = _require_research_path(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("owner") != user:
                raise HTTPException(404, "Research not found")
            data["archived"] = bool(archived)
            atomic_write_json(str(path), data)
            _LIBRARY_CACHE["key"] = None
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Failed to update research: {e}")
        return {"ok": True, "id": session_id, "archived": bool(archived)}

    @router.delete("/api/research/{session_id}")
    async def research_delete(session_id: str, request: Request):
        """Delete a research result from disk and active state."""
        user = _require_user(request)
        _validate_session_id(session_id)

        # Cancel and clean active task if present
        active_entry = research_handler._active_tasks.get(session_id)
        if active_entry is not None:
            if active_entry.get("owner", "") != user:
                raise HTTPException(404, "Research not found")
            try:
                research_handler.cancel_research(session_id)
            except Exception:
                pass
            research_handler._active_tasks.pop(session_id, None)

        research_handler._delete_checkpoint(session_id)

        json_path = _find_research_path(session_id)
        deleted = False
        if json_path is not None and json_path.exists():
            # SECURITY: verify ownership before letting the caller delete it.
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if data.get("owner") != user:
                    raise HTTPException(404, "Research not found")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(404, "Research not found")
            json_path.unlink()
            deleted = True
            _LIBRARY_CACHE["key"] = None
        return {"deleted": deleted or active_entry is not None}

    # ------------------------------------------------------------------
    # Panel endpoints — launch research without a chat session
    # ------------------------------------------------------------------

    class ResearchStartRequest(BaseModel):
        query: str
        # max_rounds=0 means "Auto" — let the AI decide when to stop, capped at 20.
        max_rounds: int = Field(default=0, ge=0, le=20)
        search_provider: Optional[str] = None
        endpoint_id: Optional[str] = None
        model: Optional[str] = None
        max_time: int = Field(default=300, ge=60, le=1800)
        extraction_timeout: Optional[int] = Field(default=None, ge=15, le=3600)
        extraction_concurrency: Optional[int] = Field(default=None, ge=1, le=12)
        category: Optional[str] = None
        continue_from_session_id: Optional[str] = None

    @router.post("/api/research/start")
    async def research_start(body: ResearchStartRequest, request: Request):
        """Launch a research job from the dedicated panel."""
        user = _require_research_enabled(request)
        if user == INTERNAL_TOOL_USER:
            tool_owner = (request.headers.get("X-Zephyrus-Owner") or "").strip()
            if tool_owner and tool_owner not in RESERVED_USERNAMES:
                auth_mgr = getattr(request.app.state, "auth_manager", None)
                if auth_mgr is not None and getattr(auth_mgr, "is_configured", False):
                    if tool_owner in getattr(auth_mgr, "users", {}):
                        try:
                            privs = auth_mgr.get_privileges(tool_owner) or {}
                            if not privs.get("can_use_research", True):
                                raise HTTPException(403, "Your account is not allowed to use research.")
                            user = tool_owner
                        except HTTPException:
                            raise
                        except Exception:
                            pass
        session_id = f"rp-{uuid.uuid4().hex[:12]}"

        if body.endpoint_id:
            from src.database import SessionLocal
            db = SessionLocal()
            try:
                # Owner-scoped: never resolve another user's private endpoint
                # (and its decrypted api_key / internal base_url). A scoped miss
                # reads as 404 so the endpoint's existence isn't revealed.
                ep = _owned_enabled_endpoint(db, user, body.endpoint_id)
                if not ep:
                    raise HTTPException(404, "Endpoint not found or disabled")
                resolved = _resolve_endpoint_runtime(ep, owner=user, model=body.model)
                if not resolved:
                    raise HTTPException(400, "Endpoint is not configured with a usable model.")
                ep_url, ep_model, ep_headers = resolved
            finally:
                db.close()
        else:
            ep_url, ep_model, ep_headers = resolve_endpoint("research", owner=user)
            if not ep_url:
                ep_url, ep_model, ep_headers = resolve_endpoint("utility", owner=user)
            # When neither research nor utility is configured, use the user's
            # configured DEFAULT model (default_endpoint_id/default_model) rather
            # than arbitrarily grabbing the first enabled endpoint's first model
            # (which surfaced gpt-3.5). "Default" should mean the default model.
            if not ep_url:
                ep_url, ep_model, ep_headers = resolve_endpoint("default", owner=user)
            if not ep_url:
                ep_url, ep_model, ep_headers = resolve_endpoint("chat", owner=user)
            if not ep_url:
                from src.database import SessionLocal
                db = SessionLocal()
                try:
                    # Owner-scoped first-enabled fallback: the caller's own rows
                    # + legacy null-owner shared rows only — never borrow another
                    # user's private endpoint/api_key. Same fix as the
                    # /api/v1/chat fallback (webhook_routes._first_enabled_endpoint).
                    ep = _owned_enabled_endpoint(db, user)
                    if ep:
                        resolved = _resolve_endpoint_runtime(ep, owner=user)
                        if resolved:
                            ep_url, ep_model, ep_headers = resolved
                finally:
                    db.close()
            if not ep_url:
                raise HTTPException(400, "No endpoints configured. Add one in Settings first.")
            if body.model:
                ep_model = body.model

        # max_rounds=0 → "Auto", let AI decide; pass 20 as the safety cap.
        effective_max_rounds = body.max_rounds if body.max_rounds > 0 else 20

        prior_report = ""
        prior_findings = None
        prior_urls = None
        if body.continue_from_session_id:
            prior_id = _validate_session_id(body.continue_from_session_id)
            prior_path = _find_owned_research_path(prior_id, user)
            prior_data = None
            if prior_path is not None:
                try:
                    prior_data = json.loads(prior_path.read_text(encoding="utf-8"))
                except Exception:
                    prior_data = None
            if prior_data is None:
                prior_entry = research_handler._active_tasks.get(prior_id)
                if prior_entry is not None and prior_entry.get("owner", "") == user:
                    prior_data = prior_entry
            if prior_data is None:
                raise HTTPException(404, "Research not found")
            prior_report = prior_data.get("raw_report") or prior_data.get("result") or ""
            prior_findings = prior_data.get("raw_findings") or prior_data.get("findings")
            prior_urls = {
                source.get("url", "")
                for source in (prior_data.get("sources") or [])
                if isinstance(source, dict) and source.get("url")
            } or None
            if not prior_report:
                raise HTTPException(400, "Research has no report to continue from")

        handle = research_handler.start_research(
            session_id=session_id,
            query=body.query,
            llm_endpoint=ep_url,
            llm_model=ep_model,
            max_time=body.max_time,
            llm_headers=ep_headers,
            prior_report=prior_report,
            prior_findings=prior_findings,
            prior_urls=prior_urls,
            max_rounds=effective_max_rounds,
            search_provider=body.search_provider or None,
            category=body.category or None,
            extraction_timeout=body.extraction_timeout,
            extraction_concurrency=body.extraction_concurrency,
            owner=user,
            endpoint_id=body.endpoint_id,
        )
        started_at = handle.get("started_at") if isinstance(handle, dict) else time.time()
        return {
            "session_id": session_id,
            "status": "running",
            "query": body.query,
            "max_rounds": effective_max_rounds,
            "max_time": body.max_time,
            "started_at": started_at,
            "continued_from": body.continue_from_session_id,
        }

    @router.get("/api/research/stream/{session_id}")
    async def research_stream(session_id: str, request: Request):
        """SSE stream of research progress events."""
        user = _require_user(request)
        _validate_session_id(session_id)
        if not _owns_in_memory(session_id, user):
            raise HTTPException(404, "No research found for this session")
        async def _generate():
            last_progress = None
            while True:
                event_obj = None
                entry = research_handler._active_tasks.get(session_id)
                if isinstance(entry, dict):
                    event_obj = entry.get("progress_event")
                if event_obj is not None:
                    event_obj.clear()

                status = research_handler.get_status(session_id)
                if status is None:
                    yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                    return
                st = status.get("status", "")
                progress = status.get("progress", {})
                if progress != last_progress:
                    last_progress = progress
                    yield f"data: {json.dumps({**progress, 'status': st})}\n\n"
                if st != "running":
                    final = {'status': st, 'final': True}
                    task = research_handler._active_tasks.get(session_id, {})
                    if st == "error" and task.get("result"):
                        final['error'] = str(task["result"])[:500]
                    yield f"data: {json.dumps(final)}\n\n"
                    return

                # Event-driven wakeup: a progress update or terminal transition
                # sets the entry event, so the next event is delivered in
                # milliseconds. The 15s timeout is a keepalive, not a poll.
                if event_obj is not None:
                    try:
                        await asyncio.wait_for(event_obj.wait(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                else:
                    await asyncio.sleep(1.5)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/api/research/result-peek/{session_id}")
    async def research_result_peek(session_id: str, request: Request):
        """Get research result without clearing it (for panel use)."""
        user = _require_user(request)
        _validate_session_id(session_id)
        owned_disk_path = _require_owned_or_active_research_path(session_id, user)
        result = research_handler.get_result(session_id)
        if result is None:
            p = owned_disk_path
            if p is not None:
                d = json.loads(p.read_text(encoding="utf-8"))
                return {
                    "result": d.get("result", ""),
                    "sources": d.get("sources", []),
                    "raw_findings": d.get("raw_findings", []),
                    "category": d.get("category") or "",
                }
            raise HTTPException(404, "No research result available")
        sources = research_handler.get_sources(session_id) or []
        raw_findings = research_handler.get_raw_findings(session_id) or []
        return {"result": result, "sources": sources, "raw_findings": raw_findings, "category": ""}

    @router.post("/api/research/spinoff/{session_id}")
    async def research_spinoff(session_id: str, request: Request):
        """Create a new chat session pre-seeded with this research as context.

        Reads the persisted research result + sources for `session_id`, creates
        a fresh session (inheriting endpoint/model/headers from the source
        session if available, otherwise from the resolved chat endpoint), and
        injects a single system message containing the report and sources so
        the user can ask follow-up questions in a clean conversation.
        """
        user = _require_user(request)
        _validate_session_id(session_id)
        # SECURITY: gate on ownership before reading the persisted research —
        # otherwise any authenticated user could spin off (and thereby read)
        # another user's report by guessing its session ID. Mirrors every other
        # endpoint in this file (see result_peek above).
        owned_disk_path = _require_owned_or_active_research_path(session_id, user)
        if session_manager is None:
            raise HTTPException(500, "session_manager not configured")

        # Load research data — prefer in-memory result, fall back to disk
        result = research_handler.get_result(session_id)
        sources = research_handler.get_sources(session_id) or []
        query = ""

        path = owned_disk_path
        if path is not None:
            try:
                disk = json.loads(path.read_text(encoding="utf-8"))
                if not result:
                    result = disk.get("result")
                if not sources:
                    sources = disk.get("sources", []) or []
                query = disk.get("query", "") or ""
            except Exception as e:
                logger.warning(f"Could not read research JSON for spinoff: {e}")

        if not result:
            raise HTTPException(404, "No research result available for this session")

        # Inherit endpoint/model/headers from the source session when possible.
        # For panel-launched research (rp-* IDs), there is no chat session, so
        # fall back through the same chain as /api/research/start: research →
        # utility → first enabled endpoint in the DB.
        ep_url, ep_model, ep_headers = "", "", {}
        try:
            src_sess = session_manager.get_session(session_id)
            ep_url = src_sess.endpoint_url or ""
            ep_model = src_sess.model or ""
            ep_headers = dict(src_sess.headers or {})
        except KeyError:
            pass

        def _merge(r_url, r_model, r_headers):
            nonlocal ep_url, ep_model, ep_headers
            if not ep_url and r_url:
                ep_url = r_url
            if not ep_model and r_model:
                ep_model = r_model
            if not ep_headers and r_headers:
                ep_headers = dict(r_headers)

        if not ep_url or not ep_model:
            _merge(*resolve_endpoint("chat", owner=user))
        if not ep_url or not ep_model:
            _merge(*resolve_endpoint("research", owner=user))
        if not ep_url or not ep_model:
            _merge(*resolve_endpoint("utility", owner=user))
        if not ep_url or not ep_model:
            # Last resort: this user's enabled endpoint, plus legacy shared rows.
            from src.database import SessionLocal
            from src.endpoint_resolver import normalize_base, build_chat_url, build_headers
            db = SessionLocal()
            try:
                ep = _owned_enabled_endpoint(db, user)
                if ep:
                    base = normalize_base(ep.base_url)
                    fallback_url = build_chat_url(base)
                    fallback_headers = build_headers(ep.api_key, base)
                    fallback_model = ""
                    if ep.cached_models:
                        try:
                            models = json.loads(ep.cached_models)
                            if models:
                                fallback_model = _first_chat_model(models)
                        except Exception:
                            pass
                    _merge(fallback_url, fallback_model, fallback_headers)
            finally:
                db.close()

        if not ep_url or not ep_model:
            raise HTTPException(400, "No endpoint configured — add one in Settings first")

        # Create new session
        new_sid = str(uuid.uuid4())

        title_query = (query or "research").strip()
        if len(title_query) > 60:
            title_query = title_query[:57] + "…"
        new_name = f"Follow-up: {title_query}"

        new_sess = session_manager.create_session(
            session_id=new_sid,
            name=new_name,
            endpoint_url=ep_url,
            model=ep_model,
            rag=False,
            owner=user,
        )
        if ep_headers:
            new_sess.headers = ep_headers
            session_manager.save_sessions()
        try:
            from src.event_bus import fire_event
            fire_event("session_created", user)
        except Exception:
            logger.debug("session_created event dispatch failed", exc_info=True)

        # Build the priming system message — report only, no sources injected.
        # The user can open the visual report for source details; keeping sources
        # out of the chat context saves tokens and avoids the AI fabricating
        # citations.
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        primer = (
            f"[Research context — {date_str}]\n\n"
            f"The user previously ran a deep research investigation. Use the "
            f"report below as your primary knowledge base when answering "
            f"follow-up questions. If the user asks something not covered, "
            f"say so plainly rather than guessing.\n\n"
            f"=== ORIGINAL QUERY ===\n{query or '(not recorded)'}\n\n"
            f"=== REPORT ===\n{result}"
        )

        from core.models import ChatMessage
        new_sess.add_message(ChatMessage(
            role="system",
            content=primer,
            metadata={"research_spinoff_from": session_id},
        ))
        session_manager.save_sessions()

        return {
            "session_id": new_sid,
            "name": new_name,
            "source_count": len(sources),
        }

    return router
