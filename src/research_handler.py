# src/research_handler.py
"""Handler for research service integration with expandable UI support.

Uses the IterResearch-style DeepResearcher (LLM-in-the-loop) as the primary
engine, falling back to the legacy ResearchOrchestrator or basic web search
if needed.

Includes a task registry so research survives page refreshes and can be cancelled.
"""
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict

from core.atomic_io import atomic_write_json
from src.research_utils import strip_thinking, is_low_quality
from src.constants import DEEP_RESEARCH_DIR

logger = logging.getLogger(__name__)

RESEARCH_DATA_DIR = Path(DEEP_RESEARCH_DIR)
_RESEARCH_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,128}$")

# Statuses after which a task entry is finished and its bulky payload is dead
# weight. "running" is the only live status.
_TERMINAL_STATUSES = ("done", "error", "cancelled")

# How long a finished entry keeps its full payload before being trimmed. Long
# enough that an in-flight SSE stream or a result-peek right after completion
# still reads from memory; short enough that a long-lived server does not
# accumulate every run's findings forever.
_FINISHED_ENTRY_TTL_SECONDS = 3600

# Ephemeral (incognito) runs are never persisted and are purged aggressively.
_EPHEMERAL_TTL_SECONDS = 300

# A successful endpoint probe is reused briefly so back-to-back jobs do not
# each pay a round-trip to the model before starting real work.
_PROBE_CACHE_TTL_SECONDS = 60


class ResearchConfigurationError(RuntimeError):
    """Fatal endpoint configuration error — do not mask with a search fallback."""



def _bounded_int(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, n))


def _format_probe_failure(model: str, exc: Exception) -> str:
    """Turn a failed research model probe into a user-facing message."""
    detail = getattr(exc, "detail", None)
    status = getattr(exc, "status_code", None)
    err = str(detail if detail is not None else exc).strip()

    if status in {401, 403} or "401" in err or "API key" in err or "Unauthorized" in err:
        return f"Model '{model}' requires an API key. Check your endpoint configuration."

    if status and err:
        return f"Model '{model}' probe failed: {err}"

    if err:
        return f"Cannot reach model '{model}' — {err}"

    return f"Cannot reach model '{model}' — check that the endpoint is running and accessible."


def _research_json_path(session_id: str) -> Optional[Path]:
    if not isinstance(session_id, str) or not _RESEARCH_SESSION_ID_RE.fullmatch(session_id):
        return None
    root = RESEARCH_DATA_DIR.resolve()
    path = (RESEARCH_DATA_DIR / f"{session_id}.json").resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _checkpoint_path(session_id: str) -> Optional[Path]:
    """Checkpoint files deliberately do NOT end in .json so Library/tool scans
    never mistake them for completed reports."""
    if not isinstance(session_id, str) or not _RESEARCH_SESSION_ID_RE.fullmatch(session_id):
        return None
    root = RESEARCH_DATA_DIR.resolve()
    path = (RESEARCH_DATA_DIR / f"{session_id}.checkpoint").resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _secure_chmod(path: Path) -> None:
    """Best-effort 0o600 on POSIX; Windows ACLs are left to the OS."""
    try:
        if os.name == "posix":
            os.chmod(path, 0o600)
    except OSError:
        pass



class ResearchHandler:
    """Handles research service operations with iterative deep research."""

    def __init__(self):
        self._active_tasks: Dict[str, dict] = {}
        self._probe_cache: Dict[tuple, float] = {}
        self._endpoint_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._reaper_task: Optional[asyncio.Task] = None
        self._last_retention_sweep = 0.0
        self._avg_duration_cache: tuple[float, Optional[float]] = (0.0, None)
        RESEARCH_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Shared concurrency / background maintenance
    # ------------------------------------------------------------------

    def _shared_semaphore(self, endpoint_id: str, limit: int) -> asyncio.Semaphore:
        """Return one extraction semaphore per endpoint for this process.

        Three parallel jobs pointed at the same local GPU used to create three
        independent semaphores, multiplying the configured concurrency by the
        number of jobs. Sharing the gate keeps aggregate load bounded.
        """
        key = str(endpoint_id or "default")
        limit = max(1, int(limit or 1))
        semaphore = self._endpoint_semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(limit)
            try:
                semaphore._zephyrus_limit = limit
            except Exception:
                pass
            self._endpoint_semaphores[key] = semaphore
            return semaphore
        if getattr(semaphore, "_zephyrus_limit", None) != limit:
            old = semaphore
            semaphore = asyncio.Semaphore(limit)
            try:
                semaphore._zephyrus_limit = limit
            except Exception:
                pass
            self._endpoint_semaphores[key] = semaphore
            old.release()
        return semaphore

    def _ensure_reaper(self) -> None:
        """Start a deterministic 60s background reaper exactly once."""
        if self._reaper_task is not None and not self._reaper_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _reap():
            while True:
                await asyncio.sleep(60)
                try:
                    self._release_finished_tasks()
                    self._purge_expired_ephemeral()
                    self._maybe_purge_retention()
                except Exception as exc:
                    logger.warning("Research reaper sweep failed: %s", exc)

        self._reaper_task = loop.create_task(_reap())

    def shutdown(self) -> None:
        """Cancel the background reaper task on application shutdown."""
        if self._reaper_task is not None and not self._reaper_task.done():
            self._reaper_task.cancel()
            self._reaper_task = None


    # ------------------------------------------------------------------
    # Query synthesis & planning
    # ------------------------------------------------------------------

    async def synthesize_query(
        self, sess, latest_message: str,
        llm_endpoint: str, llm_model: str, llm_headers: dict = None,
    ) -> str:
        """Synthesize the conversation into a single focused research query.

        Reads the session history and latest message to produce a clear,
        specific research question that captures the user's full intent.
        Falls back to the latest message if synthesis fails.
        """
        # Build conversation context from history
        history = getattr(sess, 'history', [])

        # A bare affirmation ("yes", "ok", "go ahead") is the user accepting the
        # clarifying-question round, NOT a research topic — researching the word
        # "yes" is the classic failure here. When synthesis can't run or fails,
        # fall back to the earliest substantive user message (the original ask)
        # rather than the literal follow-up.
        #
        # Match on an explicit affirmation/continuation phrase only (plus the
        # empty/punctuation-only case). We deliberately do NOT use a length
        # heuristic: a short answer like "UK", "C++", or "Rust" is a real topic
        # in a clarification flow and must be left untouched.
        _AFFIRMATIONS = {
            "yes", "y", "yeah", "yep", "yup", "sure", "sure thing", "ok", "okay",
            "k", "kk", "go", "go ahead", "go for it", "do it", "please",
            "yes please", "sounds good", "continue", "proceed", "lets go",
            "let's go", "yes go ahead",
        }

        def _normalize(text: str) -> str:
            return (text or "").strip().lower().strip("!.? ")

        def _fallback() -> str:
            normalized = _normalize(latest_message)
            if normalized and normalized not in _AFFIRMATIONS:
                return latest_message  # short or long, it's a real topic
            # Affirmation, or empty/punctuation-only: use the original ask.
            for m in history:
                c = (m.content or "").strip()
                if m.role == "user" and c and _normalize(c) not in _AFFIRMATIONS:
                    return c
            return latest_message

        if len(history) <= 1:
            return _fallback()  # No conversation to synthesize

        # Take last 6 messages max for context
        recent = history[-6:]
        convo = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:500]}"
            for m in recent if m.content
        )
        convo += f"\nUser: {latest_message}"

        try:
            from src.llm_core import llm_call_async

            response = await llm_call_async(
                url=llm_endpoint,
                model=llm_model,
                messages=[{"role": "user", "content":
                    "Read this conversation and write a single, specific research query that captures "
                    "what the user wants to know. Include all relevant context, constraints, and preferences "
                    "they mentioned. Output ONLY the research query — nothing else.\n\n"
                    f"Conversation:\n{convo}"
                }],
                temperature=0.1,
                max_tokens=200,
                headers=llm_headers,
                timeout=15,
                max_retries=1,
            )
            query = strip_thinking(response).strip().strip('"\'')
            if query and len(query) > 5:
                return query
        except Exception as e:
            logger.warning(f"Query synthesis failed: {e}")

        return _fallback()

    async def generate_plan(
        self, query: str, llm_endpoint: str, llm_model: str, llm_headers: dict = None,
    ) -> Optional[dict]:
        """Generate a research plan for user review before starting research."""
        try:
            from src.deep_research import RESEARCH_PLAN_PROMPT, current_date_context
            from src.llm_core import llm_call_async

            prompt = current_date_context() + RESEARCH_PLAN_PROMPT.format(question=query)
            response = await llm_call_async(
                url=llm_endpoint,
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
                headers=llm_headers,
                timeout=30,
                max_retries=1,
            )
            response = strip_thinking(response)

            # Try to parse structured plan
            import json as _json
            parsed = None
            try:
                # Try to extract JSON from response
                _clean = response.strip()
                if _clean.startswith("```"):
                    _clean = re.sub(r'^```(?:json)?\s*', '', _clean)
                    _clean = re.sub(r'\s*```$', '', _clean)
                import re as _re
                _match = _re.search(r'\{[\s\S]*\}', _clean)
                if _match:
                    parsed = _json.loads(_match.group())
            except Exception:
                pass

            return {
                "sub_questions": parsed.get("sub_questions", []) if parsed else [],
                "key_topics": parsed.get("key_topics", []) if parsed else [],
                "success_criteria": parsed.get("success_criteria", "") if parsed else "",
                "raw": response,
            }
        except Exception as e:
            logger.warning(f"Research plan generation failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Task registry — background research with persistence
    # ------------------------------------------------------------------

    def rename_owner(self, old_owner: str, new_owner: str) -> int:
        """Move in-flight research tasks from one owner key to another."""
        old_key = str(old_owner or "").strip().lower()
        new_key = str(new_owner or "").strip().lower()
        if not old_key or not new_key:
            return 0

        changed = 0
        for entry in list(self._active_tasks.values()):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("owner", "")).strip().lower() == old_key:
                entry["owner"] = new_key
                changed += 1
        return changed

    def cancel_owner_tasks(self, owner: str) -> int:
        """Cancel and drop every in-flight research task owned by ``owner``."""
        clean_owner = str(owner or "").strip()
        if not clean_owner:
            return 0
        owner_lower = clean_owner.lower()
        cancelled = 0
        for session_id, entry in list(self._active_tasks.items()):
            if not isinstance(entry, dict):
                continue
            entry_owner = str(entry.get("owner") or "").strip().lower()
            if entry_owner != owner_lower:
                continue
            if entry.get("status") == "running":
                try:
                    self.cancel_research(session_id)
                except Exception:
                    pass
            self._active_tasks.pop(session_id, None)
            self._delete_checkpoint(session_id)
            cancelled += 1
        return cancelled
    def delete_owner_files(self, owner: str) -> int:
        """Delete every disk report and checkpoint owned by ``owner``."""
        clean_owner = str(owner or "").strip()
        if not clean_owner:
            return 0
        owner_lower = clean_owner.lower()
        removed = 0
        if RESEARCH_DATA_DIR.exists():
            for path in RESEARCH_DATA_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if str(data.get("owner", "")).strip().lower() != owner_lower:
                    continue
                path.unlink(missing_ok=True)
                removed += 1
            for path in RESEARCH_DATA_DIR.glob("*.checkpoint"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    cp_owner = str(data.get("owner") or "").strip().lower()
                    if cp_owner != owner_lower:
                        continue
                    path.unlink(missing_ok=True)
                except Exception:
                    continue
        return removed
    def delete_owner_data(self, owner: str) -> int:
        """Cancel and delete every research artifact owned by ``owner``.
        Kept for backward compatibility. Delegates to
        :meth:`cancel_owner_tasks` and :meth:`delete_owner_files`.
        """
        self.cancel_owner_tasks(owner)
        return self.delete_owner_files(owner)

    def start_research(
        self,
        session_id: str,
        query: str,
        llm_endpoint: str,
        llm_model: str,
        max_time: int = 300,
        hard_timeout: int = None,
        llm_headers: dict = None,
        on_complete: callable = None,
        prior_report: str = "",
        prior_findings: list = None,
        prior_urls: set = None,
        max_rounds: int = 20,
        search_provider: str = None,
        category: str = None,
        extraction_timeout: int = None,
        extraction_concurrency: int = None,
        owner: str = "",
        ephemeral: bool = False,
        metadata: dict = None,
        endpoint_id: str = None,
    ) -> dict:
        """Start research as a background task. Returns task info dict.

        max_rounds is the safety cap; the AI's _should_stop decision (after
        min_rounds) terminates the loop earlier in normal operation.
        """
        if _research_json_path(session_id) is None:
            raise ValueError("Invalid research session_id")

        # Resolve the hard wall-clock timeout from settings when the caller
        # didn't pin one. Local / edge models routinely need more than the
        # old 600s default to finish a deep-research synthesis. A setting of
        # 0 disables the cap entirely (unlimited run); any other value is
        # bounded to [60, 86400] so a misconfigured settings.json can't
        # explode into a multi-day hang.
        if hard_timeout is None:
            from src.settings import get_setting
            try:
                raw_timeout = int(get_setting("research_run_timeout_seconds", 1800))
            except (TypeError, ValueError):
                raw_timeout = 1800
            if raw_timeout <= 0:
                hard_timeout = None  # 0 = no wall-clock cap (asyncio.wait_for timeout=None)
            else:
                hard_timeout = _bounded_int(
                    raw_timeout,
                    default=1800,
                    minimum=60,
                    maximum=86400,
                )
        if hard_timeout is not None and max_time:
            hard_timeout = max(hard_timeout, int(max_time) + 180)

        # Cancel any existing research for this session
        if session_id in self._active_tasks:
            existing = self._active_tasks[session_id]
            if existing.get("status") == "running":
                self.cancel_research(session_id)

        # Reclaim memory from long-finished runs before adding another one.
        try:
            self._release_finished_tasks()
        except Exception as prune_err:
            logger.warning(f"Failed to release finished research tasks: {prune_err}")
        self._ensure_reaper()
        self._maybe_purge_retention()

        entry = {
            "task": None,
            "researcher": None,
            "session_id": session_id,
            "query": query,
            "status": "running",
            "progress": {},
            "result": None,
            "started_at": time.time(),
            "completed_at": None,
            "category": category,
            "max_time": max_time,
            "max_rounds": max_rounds,
            "endpoint_id": endpoint_id or llm_endpoint,
            # SECURITY: track ownership so all reads / saves can filter by user.
            "owner": owner or "",
            "ephemeral": bool(ephemeral),
            "metadata": dict(metadata or {}),
            # Event-driven SSE wakeups: set on every progress update and on
            # terminal transitions. Routes wait on this with a 15s heartbeat.
            "progress_event": asyncio.Event(),
        }
        self._active_tasks[session_id] = entry

        def on_progress(event):
            entry["progress"] = event
            event_obj = entry.get("progress_event")
            if event_obj is not None:
                event_obj.set()

        def _mark_complete(status: str):
            entry["status"] = status
            entry["completed_at"] = time.time()
            event_obj = entry.get("progress_event")
            if event_obj is not None:
                event_obj.set()

        _completed = False

        def _guarded_complete(*args, **kwargs):
            nonlocal _completed
            if _completed:
                return
            _completed = True
            if on_complete:
                on_complete(*args, **kwargs)

        async def _run():
            # Hard wall-clock timeout — saves partial results if an LLM call hangs
            # hard_timeout passed from start_research()
            try:
                result = await asyncio.wait_for(
                    self.call_research_service(
                        query, llm_endpoint, llm_model,
                        max_time=max_time,
                        progress_callback=on_progress,
                        _task_entry=entry,
                        llm_headers=llm_headers,
                        prior_report=prior_report,
                        prior_findings=prior_findings,
                        prior_urls=prior_urls,
                        max_rounds=max_rounds,
                        search_provider=search_provider,
                        category=category,
                        extraction_timeout=extraction_timeout,
                        extraction_concurrency=extraction_concurrency,
                    ),
                    timeout=hard_timeout,
                )
                entry["result"] = result
                _mark_complete("done")
                self._save_result(session_id, entry)
                # Persist to DB via callback (ensures result survives even if SSE disconnected)
                try:
                    sources = entry.get("sources", [])
                    researcher = entry.get("researcher")
                    findings = self._extract_raw_findings(researcher.findings) if researcher and researcher.findings else []
                    _guarded_complete(session_id, result, sources, findings)
                except Exception as cb_err:
                    logger.error(f"on_complete callback failed: {cb_err}")
            except asyncio.TimeoutError:
                logger.error(f"Research hard timeout ({hard_timeout}s) for session {session_id}")
                entry["status"] = "error"
                _elapsed = time.time() - entry["started_at"]
                if self._salvage_partial(session_id, entry, _elapsed):
                    _mark_complete("done")
                    self._save_result(session_id, entry)
                    try:
                        _guarded_complete(
                            session_id, entry["result"],
                            entry.get("sources", []), entry.get("raw_findings", []),
                        )
                    except Exception as e:
                        logger.warning(f"on_complete callback failed in timeout branch: {e}")
                else:
                    entry["result"] = f"Research timed out after {hard_timeout}s. The model may be too slow for deep research."
                    _mark_complete("error")
                on_progress({"phase": "error", "message": f"Research timed out after {hard_timeout}s"})
            except asyncio.CancelledError:
                _mark_complete("cancelled")
                raise
            except Exception as e:
                logger.error(f"Background research failed: {e}", exc_info=True)
                # Preserve partial findings if available (mirrors timeout branch)
                _elapsed = time.time() - entry["started_at"]
                if self._salvage_partial(session_id, entry, _elapsed):
                    _mark_complete("done")
                    self._save_result(session_id, entry)
                    try:
                        _guarded_complete(
                            session_id, entry["result"],
                            entry.get("sources", []), entry.get("raw_findings", []),
                        )
                    except Exception as cb_err:
                        logger.warning(f"on_complete callback failed in error branch: {cb_err}")
                    on_progress({"phase": "warning", "message": f"Research finished with errors — partial results saved ({_elapsed:.0f}s elapsed)"})
                else:
                    entry["result"] = str(e)
                    _mark_complete("error")
                    on_progress({"phase": "error", "message": str(e)})

        task = asyncio.create_task(_run())
        entry["task"] = task
        return {
            "session_id": session_id,
            "status": "running",
            "query": query,
            "max_time": max_time,
            "max_rounds": max_rounds,
            "started_at": entry["started_at"],
            "task": task,
        }

    def _write_checkpoint(self, session_id: str, data: dict) -> None:
        if session_id not in self._active_tasks:
            return
        entry = self._active_tasks[session_id]
        if entry.get("ephemeral"):
            return
        path = _checkpoint_path(session_id)
        if path is None:
            return
        try:
            payload = dict(data or {})
            payload["session_id"] = session_id
            payload["query"] = entry.get("query", "")
            payload["owner"] = entry.get("owner", "")
            payload["updated_at"] = time.time()
            atomic_write_json(str(path), payload)
            _secure_chmod(path)
        except Exception as exc:
            logger.warning("Failed to write checkpoint for %s: %s", session_id, exc)

    def _load_checkpoint(self, session_id: str) -> Optional[dict]:
        path = _checkpoint_path(session_id)
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _delete_checkpoint(self, session_id: str) -> None:
        path = _checkpoint_path(session_id)
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                (path.parent / f"{session_id}.checkpoint.json").unlink(missing_ok=True)
            except Exception:
                pass

    def _salvage_partial(self, session_id: str, entry: dict, elapsed: float) -> bool:
        """Restore the best partial report from memory or the round checkpoint."""
        query = entry.get("query", "")
        researcher = entry.get("researcher")
        report = ""
        findings: list = []
        stats: dict = {}
        analyzed_urls: list = []

        if researcher is not None and getattr(researcher, "evolving_report", ""):
            report = researcher.evolving_report
            findings = list(getattr(researcher, "findings", []) or [])
            analyzed_urls = list(getattr(researcher, "analyzed_urls", []) or [])
            try:
                stats = researcher.get_stats()
            except Exception:
                stats = {}
        else:
            checkpoint = self._load_checkpoint(session_id)
            if checkpoint:
                report = str(checkpoint.get("evolving_report") or "")
                findings = list(checkpoint.get("findings") or [])
                analyzed_urls = list(checkpoint.get("analyzed_urls") or [])
                usage = checkpoint.get("usage") or {}
                prompt_tokens = sum(
                    (v or {}).get("prompt_tokens", 0) for v in usage.values()
                    if isinstance(v, dict)
                )
                completion_tokens = sum(
                    (v or {}).get("completion_tokens", 0) for v in usage.values()
                    if isinstance(v, dict)
                )
                stats = {
                    "Rounds": checkpoint.get("round", 0),
                    "Queries": (
                        checkpoint.get("queries_used")
                        if isinstance(checkpoint.get("queries_used"), int)
                        else len(checkpoint.get("queries_used") or [])
                    ),
                    "URLs": len(checkpoint.get("urls_fetched") or []),
                    "Tokens": prompt_tokens + completion_tokens,
                    "tokens": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "by_stage": usage,
                    },
                }

        if not report:
            return False

        entry["sources"] = self._extract_sources(findings)
        entry["raw_findings"] = self._extract_raw_findings(findings)
        entry["stats"] = stats
        entry["raw_report"] = strip_thinking(report)
        entry["result"] = self._format_research_report(
            query, report, stats, elapsed,
            findings=findings,
            analyzed_urls=analyzed_urls or None,
        )
        return True

    def get_status(self, session_id: str) -> Optional[dict]:
        """Get current research status for a session."""
        if session_id in self._active_tasks:
            entry = self._active_tasks[session_id]
            result = {
                "status": entry["status"],
                "progress": entry["progress"],
                "query": entry["query"],
                "started_at": entry["started_at"],
                "completed_at": entry.get("completed_at"),
                "max_time": entry.get("max_time"),
                "max_rounds": entry.get("max_rounds"),
                "ephemeral": bool(entry.get("ephemeral")),
            }
            # avg_duration is a historical figure over completed reports on
            # disk; get_avg_duration() globs and JSON-parses the whole research
            # dir, so compute it at most once per active stream (memoized on the
            # entry) instead of on every ~1s SSE poll. The disk branch below
            # never used it, so it no longer pays that cost at all.
            if "_avg_duration" not in entry:
                entry["_avg_duration"] = self.get_avg_duration()
            avg = entry["_avg_duration"]
            if avg is not None:
                result["avg_duration"] = round(avg, 1)
            return result
        # Check disk for completed research (skip consumed results)
        path = _research_json_path(session_id)
        if path is None:
            return None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("consumed"):
                    return None
                return {
                    "status": data.get("status", "done"),
                    "progress": {},
                    "query": data.get("query", ""),
                    "started_at": data.get("started_at", 0),
                    "completed_at": data.get("completed_at"),
                    "max_time": data.get("max_time"),
                    "max_rounds": data.get("max_rounds"),
                    "ephemeral": False,
                }
            except Exception:
                pass
        return None

    def _release_finished_tasks(self, ttl: int = _FINISHED_ENTRY_TTL_SECONDS) -> int:
        """Reclaim memory held by runs that finished long ago.

        A finished entry holds `researcher` (every finding extracted during the
        run, plus the evolving report), the formatted report string and the
        source list. None of that is read once the run is over. `_active_tasks`
        was otherwise append-only — `clear_result()` is the only thing that ever
        popped an entry, and only if the client actually consumed the result — so
        every research job started in this process pinned its full finding set
        for the lifetime of the server.

        Two cases, because persistence differs by outcome:

        * **Persisted** (`done`, written by `_save_result()`) → drop the entry
          entirely. Every accessor (`get_status`, `get_result`, `get_sources`,
          `get_raw_findings`) reads the memory copy *before* falling back to
          disk, so the entry has to be gone for the disk copy to be reachable.
          Blanking `entry["result"]` instead would make those accessors return
          `None` rather than fall through.
        * **Not persisted** (`error`, `cancelled` — `_save_result()` never runs
          for either) → keep the entry, because it is the only record of what
          happened, but drop `researcher`, which is the bulk of the footprint.

        Only entries past `ttl` are touched, so an in-flight SSE stream or a
        result-peek right after completion still reads from memory.

        Returns the number of entries released.
        """
        now = time.time()
        released = 0
        for session_id, entry in list(self._active_tasks.items()):
            if entry.get("status") not in _TERMINAL_STATUSES:
                continue
            finished_at = entry.get("completed_at") or entry.get("started_at") or 0
            effective_ttl = _EPHEMERAL_TTL_SECONDS if entry.get("ephemeral") else ttl
            if now - finished_at < effective_ttl:
                continue
            if entry.get("ephemeral"):
                self._delete_checkpoint(session_id)
                del self._active_tasks[session_id]
            else:
                path = _research_json_path(session_id)
                if path is not None and path.exists():
                    self._delete_checkpoint(session_id)
                    del self._active_tasks[session_id]
                elif now - finished_at >= (effective_ttl * 2):
                    # Fully evict unpersisted (error/cancelled) records after extended TTL
                    self._delete_checkpoint(session_id)
                    del self._active_tasks[session_id]
                else:
                    # Sole record of a failed/cancelled run — keep the summary text,
                    # drop the finding set.
                    entry.pop("researcher", None)
                    entry.pop("sources", None)
            released += 1
        if released:
            logger.info(f"Released {released} finished research task(s)")
        return released

    def _purge_expired_ephemeral(self) -> int:
        """Drop incognito results even if traffic never calls start_research again."""
        now = time.time()
        purged = 0
        for session_id, entry in list(self._active_tasks.items()):
            if not entry.get("ephemeral"):
                continue
            if entry.get("status") not in _TERMINAL_STATUSES:
                continue
            finished_at = entry.get("completed_at") or entry.get("started_at") or 0
            if now - finished_at >= _EPHEMERAL_TTL_SECONDS:
                self._delete_checkpoint(session_id)
                self._active_tasks.pop(session_id, None)
                purged += 1
        return purged

    def _maybe_purge_retention(self) -> int:
        """Delete reports older than ``research_retention_days`` (0 = keep)."""
        try:
            from src.settings import get_setting

            days = int(get_setting("research_retention_days", 0) or 0)
        except (TypeError, ValueError):
            days = 0
        if days <= 0:
            return 0
        now = time.time()
        # Retention is a maintenance task, not something every request should
        # pay for. Sweep at most once every six hours.
        if now - self._last_retention_sweep < 6 * 3600:
            return 0
        self._last_retention_sweep = now
        cutoff = now - days * 86400
        removed = 0
        if RESEARCH_DATA_DIR.exists():
            for path in RESEARCH_DATA_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    completed = float(data.get("completed_at") or data.get("started_at") or 0)
                    if completed and completed < cutoff:
                        path.unlink(missing_ok=True)
                        self._delete_checkpoint(path.stem)
                        removed += 1
                except Exception:
                    continue
        if removed:
            logger.info("Research retention purge removed %d report(s)", removed)
        return removed

    def cancel_research(self, session_id: str) -> bool:
        """Cancel running research for a session."""
        if session_id not in self._active_tasks:
            return False
        entry = self._active_tasks[session_id]
        if entry["status"] != "running":
            return False
        researcher = entry.get("researcher")
        if researcher:
            researcher.cancel()
        task = entry.get("task")
        if task and not task.done():
            task.cancel()
        entry["status"] = "cancelled"
        entry["completed_at"] = time.time()
        self._delete_checkpoint(session_id)
        event_obj = entry.get("progress_event")
        if event_obj is not None:
            event_obj.set()
        return True


    def get_result(self, session_id: str) -> Optional[str]:
        """Get the completed research result."""
        if session_id in self._active_tasks:
            entry = self._active_tasks[session_id]
            if entry["status"] in ("done", "error", "cancelled"):
                return entry.get("result")
        # Check disk (skip consumed results)
        path = _research_json_path(session_id)
        if path is None:
            return None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("consumed"):
                    return None
                return data.get("result")
            except Exception:
                pass
        return None

    def get_sources(self, session_id: str) -> Optional[list]:
        """Get deduplicated source list from research findings."""
        # Check in-memory first
        if session_id in self._active_tasks:
            entry = self._active_tasks[session_id]
            if entry.get("sources"):
                return entry["sources"]
            researcher = entry.get("researcher")
            if researcher and researcher.findings:
                return self._extract_sources(researcher.findings)
        # Check disk
        path = _research_json_path(session_id)
        if path is None:
            return None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("sources")
            except Exception:
                pass
        return None

    def get_raw_findings(self, session_id: str) -> Optional[list]:
        """Get raw per-source findings for display."""
        if session_id in self._active_tasks:
            entry = self._active_tasks[session_id]
            researcher = entry.get("researcher")
            if researcher and researcher.findings:
                return self._extract_raw_findings(researcher.findings)
        # Check disk
        path = _research_json_path(session_id)
        if path is None:
            return None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("raw_findings")
            except Exception as e:
                logger.warning(f"Failed to read raw findings for {session_id}: {e}")
        return None

    @staticmethod
    def _extract_sources(findings: list) -> list:
        """Extract deduplicated [{url, title}] from findings, filtering low-quality ones."""
        seen = set()
        sources = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            url = f.get("url", "")
            title = f.get("title", "") or url
            summary = f.get("summary", "") or f.get("evidence", "")
            if url and url not in seen and not is_low_quality(summary):
                seen.add(url)
                entry = {"url": url, "title": title}
                og_img = f.get("og_image", "")
                if og_img:
                    entry["image"] = og_img
                sources.append(entry)
        return sources

    @staticmethod
    def _extract_raw_findings(findings: list) -> list:
        """Extract [{url, title, summary}] for per-source findings display, filtering junk."""
        try:
            items = []
            for f in findings:
                if not isinstance(f, dict):
                    continue
                url = f.get("url", "")
                title = f.get("title", "") or "Untitled"
                summary = f.get("summary", "")
                evidence = f.get("evidence", "")
                content = summary if summary else (evidence[:2000] if evidence else "")
                if url and content and not is_low_quality(content):
                    items.append({"url": url, "title": title, "summary": content})
            return items
        except Exception as e:
            logger.warning(f"Failed to extract raw findings: {e}")
            return []

    def get_avg_duration(self) -> Optional[float]:
        """Compute average research duration from completed results on disk.

        The TTL cache keeps this off the hot SSE path; a full directory parse
        at most once a minute is acceptable without introducing a new store.
        """
        now = time.time()
        cached_at, cached_value = getattr(self, "_avg_duration_cache", (0.0, None))
        if cached_at and now - cached_at < 60:
            return cached_value
        durations = []
        try:
            for p in RESEARCH_DATA_DIR.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("status") == "done":
                        started = data.get("started_at", 0)
                        completed = data.get("completed_at", 0)
                        if started and completed and completed > started:
                            durations.append(completed - started)
                except Exception:
                    continue
        except Exception:
            pass
        value = (sum(durations) / len(durations)) if durations else None
        self._avg_duration_cache = (now, value)
        return value

    def clear_result(self, session_id: str):
        """Mark result as consumed so it won't be re-rendered on refresh.

        Keeps the JSON on disk so visual reports can be generated later, but
        purges incognito runs entirely from memory.
        """
        entry = self._active_tasks.get(session_id)
        if entry is not None and entry.get("ephemeral"):
            self._active_tasks.pop(session_id, None)
            self._delete_checkpoint(session_id)
            return
        self._active_tasks.pop(session_id, None)
        self._delete_checkpoint(session_id)
        path = _research_json_path(session_id)
        if path is None:
            return
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["consumed"] = True
                atomic_write_json(str(path), data)
                _secure_chmod(path)
            except Exception:
                pass

    def _save_result(self, session_id: str, entry: dict):
        """Persist completed research result to disk (atomically)."""
        try:
            path = _research_json_path(session_id)
            if path is None:
                logger.error("Refusing to save research result for invalid session_id: %r", session_id)
                return
            # Extract and cache sources + raw findings
            sources = list(entry.get("sources") or [])
            raw_findings = list(entry.get("raw_findings") or [])
            researcher = entry.get("researcher")
            if researcher and researcher.findings:
                sources = self._extract_sources(researcher.findings)
                raw_findings = self._extract_raw_findings(researcher.findings)
            entry["sources"] = sources
            entry["raw_findings"] = raw_findings
            entry.setdefault("completed_at", time.time())

            # Incognito runs never touch disk; the entry stays in memory until
            # consumed or evicted by the short ephemeral TTL.
            if entry.get("ephemeral"):
                self._delete_checkpoint(session_id)
                return

            data = {
                "query": entry["query"],
                "status": entry["status"],
                "result": entry["result"],
                "raw_report": entry.get("raw_report", ""),
                "sources": sources,
                "raw_findings": raw_findings,
                "stats": entry.get("stats"),
                "category": entry.get("category"),
                "started_at": entry["started_at"],
                "completed_at": entry.get("completed_at") or time.time(),
                "max_time": entry.get("max_time"),
                "max_rounds": entry.get("max_rounds"),
                "metadata": entry.get("metadata") or {},
                # SECURITY: stamp owner so route handlers can filter by user.
                "owner": entry.get("owner", ""),
            }
            atomic_write_json(str(path), data)
            _secure_chmod(path)
            self._delete_checkpoint(session_id)
            logger.info(f"Research result saved to {path}")
            try:
                from src.event_bus import fire_event
                fire_event("research_completed", entry.get("owner") or None)
            except Exception:
                logger.debug("research_completed event dispatch failed", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to save research result: {e}")

    def _get_session_json(self, session_id: str) -> Optional[dict]:
        """Load the saved research JSON for a session, if it exists."""
        path = _research_json_path(session_id)
        if path is None:
            return None
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def get_report_html(self, session_id: str) -> Optional[str]:
        """Generate the visual HTML report for a session (always fresh from JSON)."""
        entry = self._active_tasks.get(session_id)
        data = None
        if entry is not None and entry.get("ephemeral"):
            data = {
                "query": entry.get("query", ""),
                "raw_report": entry.get("raw_report") or entry.get("result", ""),
                "result": entry.get("result", ""),
                "sources": entry.get("sources", []),
                "stats": entry.get("stats"),
                "category": entry.get("category"),
                "hidden_images": entry.get("hidden_images") or [],
            }
        else:
            json_path = _research_json_path(session_id)
            if json_path is None:
                return None
            if not json_path.exists():
                logger.warning(f"No JSON found for visual report: {json_path}")
                return None
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error(f"Failed to read research JSON for {session_id}: {exc}")
                return None

        try:
            from src.visual_report import generate_visual_report

            report_md = data.get("raw_report") or data.get("result", "")
            html_content = generate_visual_report(
                question=data.get("query", ""),
                report_markdown=report_md,
                sources=data.get("sources"),
                stats=data.get("stats"),
                category=data.get("category"),
                session_id=session_id,
                hidden_images=data.get("hidden_images") or [],
            )
            logger.info(f"Visual report generated for {session_id}")
            return html_content
        except Exception as e:
            logger.error(f"Failed to generate visual report: {e}")
            return None

    def hide_image(self, session_id: str, image_url: str) -> bool:
        """Add image_url to the persisted hidden_images list for a research."""
        if not isinstance(image_url, str):
            return False
        clean_url = image_url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            return False
        image_url = clean_url

        entry = self._active_tasks.get(session_id)
        if entry is not None and entry.get("ephemeral"):
            hidden = entry.setdefault("hidden_images", [])
            if image_url not in hidden:
                hidden.append(image_url)
            return True
        path = _research_json_path(session_id)
        if path is None:
            return False
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            hidden = data.get("hidden_images") or []
            if image_url not in hidden:
                hidden.append(image_url)
                data["hidden_images"] = hidden
                atomic_write_json(str(path), data)
                _secure_chmod(path)
                logger.info(f"Hid image {image_url[:80]} for research {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to hide image: {e}")
            return False

    def unhide_all_images(self, session_id: str) -> bool:
        """Clear the hidden_images list for a research."""
        entry = self._active_tasks.get(session_id)
        if entry is not None and entry.get("ephemeral"):
            entry["hidden_images"] = []
            return True
        path = _research_json_path(session_id)
        if path is None:
            return False
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["hidden_images"] = []
            atomic_write_json(str(path), data)
            _secure_chmod(path)
            logger.info(f"Cleared hidden_images for research {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unhide images: {e}")
            return False

    @staticmethod
    async def _probe_endpoint(endpoint: str, model: str, headers: dict = None):
        """Quick probe to verify the LLM endpoint/model responds before research."""
        from src.llm_core import llm_call_async
        try:
            logger.info(f"Probing {model} at {endpoint} (has_auth={bool(headers and 'Authorization' in (headers or {}))})")
            await llm_call_async(
                url=endpoint,
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                temperature=0,
                max_tokens=5,
                headers=headers,
                timeout=15,
                max_retries=1,
            )
            logger.info(f"Endpoint probe OK: {model}")
        except Exception as e:
            logger.error(f"Probe failed for {model}: {e}")
            message = _format_probe_failure(model, e)
            status = getattr(e, "status_code", None)
            detail = str(getattr(e, "detail", e) or "")
            is_fatal = status in {401, 403, 404} or any(
                token in detail.lower()
                for token in ("api key", "unauthorized", "invalid model", "not found", "authentication")
            )
            if is_fatal:
                raise ResearchConfigurationError(message) from e
            raise RuntimeError(message) from e

    async def call_research_service(
        self,
        query: str,
        llm_endpoint: str,
        llm_model: str,
        max_time: int = 300,
        progress_callback=None,
        _task_entry: dict = None,
        llm_headers: dict = None,
        prior_report: str = "",
        prior_findings: list = None,
        prior_urls: set = None,
        max_rounds: int = 20,
        search_provider: str = None,
        category: str = None,
        extraction_timeout: int = None,
        extraction_concurrency: int = None,
    ) -> str:
        """
        Run iterative deep research using the LLM-in-the-loop DeepResearcher.

        Args:
            query: Research question
            llm_endpoint: LLM endpoint URL for chat completions
            llm_model: Model name/ID
            max_time: Maximum research time in seconds (default 5 minutes)
            _task_entry: Internal - registry entry to store researcher ref
            prior_report: Previous report to continue from.
            prior_findings: Previous findings to build on.
            prior_urls: URLs already visited (won't re-fetch).

        Returns:
            Formatted research report with expandable section and summary
        """
        is_continuation = bool(prior_report)
        logger.info(f"{'Continuing' if is_continuation else 'Starting'} IterResearch Deep Research")
        logger.info(f"Query: {query}")
        logger.info(f"LLM: {llm_endpoint} / {llm_model}")
        logger.info(f"Max time: {max_time}s")
        if is_continuation:
            logger.info(f"Prior: {len(prior_findings or [])} findings, {len(prior_urls or set())} URLs")

        # Probe the endpoint before committing to a long research run. Fatal
        # configuration errors (bad key / missing model) are surfaced directly;
        # a transient outage may still fall back to basic web search.
        if progress_callback:
            progress_callback({"phase": "probing", "model": llm_model})

        probe_key = (llm_endpoint, llm_model, hash(str(llm_headers or "")))
        probe_ok_at = self._probe_cache.get(probe_key)
        if not probe_ok_at or time.time() - probe_ok_at > _PROBE_CACHE_TTL_SECONDS:
            try:
                await self._probe_endpoint(llm_endpoint, llm_model, llm_headers)
                self._probe_cache[probe_key] = time.time()
            except ResearchConfigurationError as exc:
                logger.error("Fatal research model configuration error: %s", exc)
                if _task_entry is not None:
                    _task_entry["result"] = str(exc)
                    _task_entry["status"] = "error"
                if progress_callback:
                    progress_callback({"phase": "error", "message": str(exc)})
                raise
            except Exception as exc:
                logger.error(f"DeepResearcher probe failed: {exc}", exc_info=True)
                return await self._fallback_research(
                    query, llm_endpoint, llm_model, max_time, str(exc)
                )

        try:
            from src.deep_research import DeepResearcher

            from src.settings import get_setting
            _max_report_tokens = int(get_setting("research_max_tokens", 16384))
            _extraction_timeout = _bounded_int(
                extraction_timeout if extraction_timeout is not None else get_setting("research_extraction_timeout_seconds", 90),
                default=90,
                minimum=15,
                maximum=3600,
            )
            _extraction_concurrency = _bounded_int(
                extraction_concurrency if extraction_concurrency is not None else get_setting("research_extraction_concurrency", 3),
                default=3,
                minimum=1,
                maximum=12,
            )
            _planning_timeout = _bounded_int(
                get_setting("research_planning_timeout_seconds", _extraction_timeout),
                default=_extraction_timeout,
                minimum=15,
                maximum=3600,
            )
            _query_timeout = _bounded_int(
                get_setting("research_query_timeout_seconds", _extraction_timeout),
                default=_extraction_timeout,
                minimum=15,
                maximum=3600,
            )
            _min_rounds = _bounded_int(
                get_setting("research_min_rounds", 2),
                default=2,
                minimum=1,
                maximum=max_rounds,
            )
            _max_urls_per_round = _bounded_int(
                get_setting("research_max_urls_per_round", 8),
                default=8,
                minimum=1,
                maximum=64,
            )
            _final_reserve = _bounded_int(
                get_setting("research_final_report_reserve_seconds", 45),
                default=45,
                minimum=0,
                maximum=max(0, min(max_time // 4, max_time - 15)),
            )
            endpoint_id = (_task_entry or {}).get("endpoint_id") or llm_endpoint
            session_id = (_task_entry or {}).get("session_id")

            def _write_checkpoint(data: dict) -> None:
                if session_id:
                    self._write_checkpoint(session_id, data)

            researcher = DeepResearcher(
                llm_endpoint=llm_endpoint,
                llm_model=llm_model,
                llm_headers=llm_headers,
                max_rounds=max_rounds,
                min_rounds=min(max_rounds, _min_rounds),
                max_time=max_time,
                max_urls_per_round=_max_urls_per_round,
                max_report_tokens=_max_report_tokens,
                extraction_timeout=_extraction_timeout,
                planning_timeout=_planning_timeout,
                query_timeout=_query_timeout,
                extraction_concurrency=_extraction_concurrency,
                final_report_reserve_seconds=_final_reserve,
                progress_callback=progress_callback,
                search_provider=search_provider,
                category=category,
                endpoint_id=endpoint_id,
                shared_semaphore=self._shared_semaphore(endpoint_id, _extraction_concurrency),
                checkpoint_callback=_write_checkpoint,
            )
            if _task_entry is not None:
                _task_entry["researcher"] = researcher

            start_time = time.time()
            report = await researcher.research(
                query,
                prior_report=prior_report,
                prior_findings=prior_findings,
                prior_urls=prior_urls,
            )
            elapsed = time.time() - start_time

            stats = researcher.get_stats()
            logger.info("IterResearch completed successfully")
            for key, value in stats.items():
                logger.info(f"  {key}: {value}")

            # Store raw report and stats for visual report generation
            if _task_entry is not None:
                _task_entry["raw_report"] = strip_thinking(report)
                _task_entry["stats"] = stats
                _task_entry["sources"] = self._extract_sources(researcher.findings)
                _task_entry["raw_findings"] = self._extract_raw_findings(researcher.findings)

            return self._format_research_report(
                query, report, stats, elapsed,
                findings=researcher.findings,
                evolving_report=researcher.evolving_report,
                analyzed_urls=getattr(researcher, "analyzed_urls", None),
            )

        except Exception as e:
            logger.error(f"DeepResearcher failed: {e}", exc_info=True)
            return await self._fallback_research(query, llm_endpoint, llm_model, max_time, str(e))

    async def _fallback_research(
        self, query: str, llm_endpoint: str, llm_model: str,
        max_time: int, primary_error: str,
    ) -> str:
        """Fall back to basic web search when the research engine is unavailable."""
        return self._handle_research_failure(query, primary_error)

    def _format_research_report(
        self, query: str, full_report: str, stats: dict, elapsed: float,
        findings: Optional[list] = None, evolving_report: Optional[str] = None,
        analyzed_urls: Optional[list] = None,
    ) -> str:
        """Format research report with sources and expandable raw findings."""
        full_report = strip_thinking(full_report)
        summary_lines = [
            f"**Duration:** {elapsed:.1f}s",
            f"**Rounds:** {stats.get('Rounds', stats.get('Findings', '?'))}",
            f"**Queries:** {stats.get('Queries', stats.get('Searches', '?'))}",
            f"**URLs Analyzed:** {stats.get('URLs', '?')}",
        ]
        if stats.get("Tokens"):
            summary_lines.append(f"**Tokens:** {stats['Tokens']}")
        if stats.get("citations"):
            citations = stats["citations"]
            summary_lines.append(
                f"**Citations:** {citations.get('citations_verified', 0)} verified"
            )
        summary_text = " | ".join(summary_lines)

        # Keep the curated Sources section quality-filtered, while listing every
        # unique URL the run actually inspected so counts remain auditable.
        sources_section = ""
        analyzed_urls_section = ""
        url_items = analyzed_urls if analyzed_urls is not None else findings
        if findings or url_items:
            seen_urls = set()
            source_lines = []
            analyzed_seen = set()
            analyzed_lines = []
            for finding in findings or []:
                if not isinstance(finding, dict):
                    continue
                url = finding.get("url", "")
                title = finding.get("title", "") or url
                summary = finding.get("summary", "") or finding.get("evidence", "")
                if url and url not in seen_urls and not is_low_quality(summary):
                    seen_urls.add(url)
                    source_lines.append(f"- [{title}]({url})")
            for item in url_items or []:
                if not isinstance(item, dict):
                    continue
                url = item.get("url", "")
                title = item.get("title", "") or url
                if url and url not in analyzed_seen:
                    analyzed_seen.add(url)
                    analyzed_lines.append(f"{len(analyzed_lines) + 1}. [{title}]({url})")
            if source_lines:
                sources_section = "\n### Sources\n\n" + "\n".join(source_lines) + "\n"
            if analyzed_lines:
                analyzed_urls_section = "\n### Analyzed URLs\n\n" + "\n".join(analyzed_lines) + "\n"

        raw_findings_section = ""
        if findings:
            parts = []
            for i, finding in enumerate(findings, 1):
                if not isinstance(finding, dict):
                    continue
                url = finding.get("url", "")
                title = finding.get("title", "") or "Untitled"
                summary = finding.get("summary", "")
                evidence = finding.get("evidence", "")
                content = summary if summary else (evidence[:2000] if evidence else "(no content)")
                parts.append(f"**{i}. [{title}]({url})**\n\n{content}")
            raw_findings_section = "\n\n".join(parts)

        collected_section = ""
        if evolving_report or raw_findings_section:
            collected_section = "\n<details>\n<summary><strong>Raw collected findings ({} sources)</strong></summary>\n\n".format(
                len(findings) if findings else 0
            )
            if raw_findings_section:
                collected_section += raw_findings_section + "\n"
            collected_section += "\n</details>\n"

        return f"""---

## Research Summary

{summary_text}

---

{full_report}

{sources_section}
{analyzed_urls_section}
{collected_section}
---

**The AI has analyzed all research findings above. Ask me anything about: "{query}"**
"""

    def _format_error_response(self, error_msg: str, query: str) -> str:
        """Format error response in a user-friendly way."""
        return f"""## Research Engine Unavailable

**Query:** {query}

**Error:** {error_msg}

**Please check:**
1. LLM endpoint is reachable
2. SearXNG is running at the configured instance
3. Application logs for detailed error information

**Troubleshooting:**
- Test basic search: Try the web search toggle first
- Check search config: `/api/search/config`
- Review logs for initialization errors
"""

    def _handle_research_failure(self, query: str, error: str) -> str:
        """Handle research failure with fallback to basic search."""
        def _sanitize_md(s: str) -> str:
            return (
                str(s or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        safe_query = _sanitize_md(query)
        safe_error = _sanitize_md(error)

        try:
            logger.info("Attempting fallback to basic web search...")
            from src.search import comprehensive_web_search

            search_result = comprehensive_web_search(query)

            return f"""## Research Failed - Basic Search Fallback

**Query:** {safe_query}

**Error:** {safe_error}

**Note:** The deep research engine encountered an error. Here are basic search results instead:

---

### Basic Web Search Results

{search_result}

---

**To fix deep research:**
1. Check that your LLM endpoint and search provider are properly configured
2. Verify network connectivity
3. Review application logs for detailed error information

Try the web search toggle for simpler queries, or fix the research engine for comprehensive analysis.
"""

        except Exception as e2:
            logger.error(f"Fallback search also failed: {e2}", exc_info=True)
            safe_fallback_error = _sanitize_md(str(e2))
            return f"""## Complete Research Failure

**Primary Error:** {safe_error}
**Fallback Error:** {safe_fallback_error}

**Please check:**
1. Search provider configuration in Settings -> Search Settings
2. Network connectivity to search APIs
3. Application logs for detailed error information
4. That SearXNG is running (if using SearXNG)

**Debug Info:**
- Search config endpoint: `/api/search/config`
- Test basic search toggle with a simple query first
"""
