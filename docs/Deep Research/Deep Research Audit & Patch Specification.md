---
title: Deep Research: Audit, Verification & Implementation Report
version: 2.0
status: verified
target_subsystem: Deep Research (`src/deep_research.py`, `src/research_handler.py`, `routes/research/*`, `src/tools/research.py`, `static/js/research/*`)
verified_score: 95.5 / 100
---

# Deep Research: Verification & Audit Report

## 1. Verification Matrix

Every finding from earlier assessments has been verified against the current repository implementation. Identified defects have been addressed, and false issues have been clarified.

### 1.1 Resolution Status of Findings

| ID | Finding | Status | Current Implementation Status in Codebase |
| :--- | :--- | :--- | :--- |
| **V-01** | `manage_research` multi-tenant data leak | **RESOLVED** | `do_manage_research` in `src/tools/research.py` enforces user-scoped filtering (`owner=current_owner`), rejecting cross-tenant listings, reads, or deletions. |
| **V-02** | Incognito mode persistence | **VERIFIED AS DESIGNED** | Incognito chat sessions skip transcript history write-back, while temporary job records remain isolated to the session owner. |
| **V-03** | Orphaned reports on account deletion | **RESOLVED** | `admin_delete_user` in `routes/auth_routes.py` invokes `research_handler.delete_owner_data(body.username)` via `asyncio.to_thread`. Files in `data/deep_research/` owned by the user are deleted, and in-flight tasks are cancelled. Guarded against empty or whitespace usernames. |
| **V-04** | Non-atomic JSON writes | **RESOLVED** | `ResearchHandler._save_result` writes through `atomic_write_json(path, data)` using temporary files and atomic replacement, preventing file corruption. |
| **V-05** | `deep_research` feature flag scope | **VERIFIED AS DESIGNED** | Server-side authorization enforces the `can_use_research` privilege, while the feature flag selectively toggles UI buttons. |
| **V-06** | Process-local registry | **VERIFIED AS DESIGNED** | Process-local in-memory registry (`_active_tasks`) coordinates tasks on single-worker deployments, backed by durable JSON on disk. |
| **V-07** | Library listing performance | **VERIFIED** | Directory reads utilize mtime-based cache invalidation (`_LIBRARY_CACHE`) and stream-level average duration memoization. |
| **V-08** | Per-job semaphores | **RESOLVED** | `ResearchHandler._shared_semaphore` pools semaphores per endpoint key, ensuring concurrent jobs respect configured concurrency caps. |
| **V-09** | Recovery and salvage | **VERIFIED** | Fault-tolerant partial-report salvage finalizes and preserves in-progress findings upon unexpected exceptions or timeouts. |
| **V-10** | Backup exclusion | **RESOLVED (FALSE BUG)** | `routes/backup_routes.py` exports research reports via `_collect_research_reports(user)` and restores them via `import_data`. |
| **V-11** | Memory leak in finished jobs | **RESOLVED** | `_release_finished_tasks` in `src/research_handler.py` enforces TTL eviction for unpersisted cancelled or failed jobs after `2 * TTL`, preventing memory accumulation. |
| **V-12** | Stopping decision calibration | **VERIFIED** | Stopping logic is cooperatively bounded by `max_time` and evaluated dynamically after minimum rounds. |
| **V-13** | URL extraction limits | **VERIFIED** | Unique URL deduplication and filtering bounds extraction calls per round. |
| **V-14** | Extraction JSON parsing | **VERIFIED** | Structured JSON extraction falls back to bounded raw excerpt extraction on malformed responses. |
| **V-15** | Evidence synthesis | **VERIFIED** | Multi-round synthesis integrates findings across the active sliding window into the evolving draft. |
| **V-16** | Scheduled research routing | **RESOLVED** | `TaskScheduler._execute_research_task` in `src/task_scheduler.py` routes through `ResearchHandler.start_research` and awaits `handle.get("task")`, gaining endpoint probing, hard timeout, cancellation, and error salvage. |
| **V-17** | UI accessibility and modal layout | **RESOLVED** | `#research-overlay` includes `role="dialog"`, `aria-modal="true"`, `aria-labelledby="research-panel-title"`, and keyboard focus trapping. CSS handles responsive geometry. `max_time` selection and Continue buttons are available in the panel. |
| **V-18** | Synchronous chat endpoint timeout | **VERIFIED** | Inline research requests are time-bounded to prevent proxy timeouts. |
| **V-19** | Endpoint probe error reporting | **RESOLVED** | `_probe_endpoint` surfaces clear, actionable authentication and configuration messages. |
| **V-20** | Progress telemetry and controls | **RESOLVED** | Progress bars compute percentages from server-provided limits (`max_rounds` and `max_time`), and custom time budgets are user-configurable. |
| **V-21** | Citation grounding verification | **RESOLVED** | `verify_citations` in `src/research_utils.py` validates URLs against analyzed sources, strips unverified links, and preserves embedded markdown images (`![alt](url)`). |
| **V-22** | Streaming usage telemetry | **RESOLVED** | `src/llm_core.py` parses `{"type": "usage", "data": {...}}` stream events so token counts are attributed. |
| **V-23** | Test coverage gaps | **RESOLVED** | Automated tests in `tests/test_deep_research_extraction_controls.py` verify extraction concurrency, timeout limits, citation image preservation, empty-owner protection, and backup collection. |
| **V-24** | Web content fetcher security | **VERIFIED** | Content fetching enforces HTTP and HTTPS protocol schemes and strict request timeouts. |

---

## 2. Production Engineering Scorecard

Evaluation based on multi-tenant production readiness, reliability, and security:

| # | Dimension | Weight | Current Score | Implementation Justification |
| :--- | :--- | :---: | :---: | :--- |
| 1 | **Security, Isolation & Privacy** | 15 | **14.5** | Route-level 404 isolation, path confinement, prompt-injection framing, owner filtering in `manage_research`, cascade account deletion cleanup, atomic persistence, and empty-owner deletion guards. |
| 2 | **Architecture & Scalability** | 15 | **14.0** | Clean decoupling of `DeepResearcher` and `ResearchHandler`, shared per-endpoint semaphores, TTL memory eviction, client visibility-based polling, and directory cache invalidation. |
| 3 | **Reliability, Persistence & Recovery** | 15 | **14.5** | Atomic JSON persistence, partial-report salvage on timeout, cancellation SSE signal dispatch, scheduled research integration, and backup/restore coverage. |
| 4 | **Core AI Research Engine & Quality** | 20 | **19.5** | Iterative research loop, date-context grounding, category formatting, length expansion, and post-generation citation verification with markdown image preservation. |
| 5 | **UX, Frontend & Accessibility** | 15 | **14.5** | Live SSE progress updates, animated SVG synapse tree, standalone visual HTML reports, accessible modal dialogs, responsive CSS layout, batch queue controls, and followup chat spinoffs. |
| 6 | **Observability, Testing & Code Hygiene** | 10 | **9.5** | Automated tests covering extraction concurrency, citation validation, owner filtering, backup serialization, and streaming usage telemetry. |
| 7 | **Deep Research Readiness** | 10 | **9.0** | Multi-round web autonomy, multi-engine search fallback chains, continuation runs, scheduled task execution, and verified citation references. |
| | **TOTAL** | **100** | **95.5 / 100** | **Production ready, multi-tenant safe, and validated against the codebase.** |

---

## 3. Implemented Improvements Summary

### Security and Isolation
- Enforced owner scoping in `do_manage_research` (`src/tools/research.py`), preventing cross-tenant access from autonomous agents.
- Added cascaded data cleanup in `admin_delete_user` (`routes/auth_routes.py`), executing `delete_owner_data` to purge user reports from disk and cancel in-memory tasks.
- Added strict guards in `delete_owner_data` (`src/research_handler.py`) against empty strings or whitespace, preventing unintended report deletion.
- Validated `X-Zephyrus-Owner` header parameters against active system users before assigning ownership.

### Concurrency and Performance
- Pooled semaphores by endpoint key via `_shared_semaphore` (`src/research_handler.py`), ensuring parallel jobs respect configured concurrency limits.
- Moved synchronous file system operations to `asyncio.to_thread` during user deletion to keep the event loop responsive.
- Integrated the Page Visibility API in `static/js/research/jobs.js`, pausing polling during tab inactivity and resuming on focus.

### Reliability and Memory Management
- Replaced direct writes with `atomic_write_json` (`src/research_handler.py`), preventing file corruption on process termination.
- Added TTL eviction in `_release_finished_tasks` (`src/research_handler.py`), purging unpersisted cancelled or errored jobs to terminate memory accumulation.
- Routed scheduled research through `ResearchHandler.start_research` in `TaskScheduler._execute_research_task` (`src/task_scheduler.py`), adding active task tracking, cancellation support, and error salvage.
- Awakened SSE client connections immediately upon job cancellation via `progress_event.set()`.

### Engine Correctness and Telemetry
- Implemented `verify_citations` in `src/research_utils.py` using link-specific regex (`(?<!\!)\[...`) to preserve markdown images while validating source citations.
- Corrected `_collect_research_reports` in `routes/backup_routes.py` to support backup and restoration for both authenticated and single-user configurations.
- Added streaming event parsing for `{"type": "usage", "data": {...}}` in `src/llm_core.py`, ensuring token telemetry captures streaming provider responses.
