# Deep Research — Developer Guide

Written for a developer who has **no prior context** on this feature. It assumes
you can read Python and JavaScript but knows nothing about Zephyrus's research
code.

Every line number below was verified against the current `dev` tree. If one is
stale, trust the code over the number and open a PR to fix the doc.

---

## 1. What this feature actually is

The user types a question, Zephyrus runs an **LLM-driven iterative search loop**
in the background, and produces a long markdown report with citations.

It is not a single search call. The defining characteristic is the loop:

```
plan → generate queries → search → fetch pages → extract findings
     → synthesize → ask the LLM "do I have enough?" → repeat or stop
```

The LLM is in the loop at every arrow, not just at the end. That is the whole
design, and most of the complexity in this feature exists to make that loop
survive partial failure.

There are **three ways in**, and they do not behave identically:

| Entry point | Where | Nature |
|---|---|---|
| **Side panel** | `POST /api/research/start` + `GET /api/research/stream/{id}` | Background job, streams progress over SSE. The primary path. |
| **Chat bubble** | `POST /api/chat_stream` with research enabled | Background job, progress piggy-backed on the chat stream. No longer reachable from the UI (see §11). |
| **Agent tool** | LLM calls the `trigger_research` tool | Loops back over HTTP to `POST /api/research/start`. The agent's entry. |

---

## 2. File map — read these in this order

```
src/deep_research.py            929 L  the engine: DeepResearcher class + every prompt
src/research_handler.py        1060 L  LIVE handler: task registry, persistence, job lifecycle
routes/research/research_routes.py  783 L  all 15 HTTP routes
src/research_utils.py            63 L  strip_thinking / is_low_quality
src/constants.py                            DEEP_RESEARCH_DIR (the only path you need)
src/settings.py                91-109 L  research_* defaults

static/js/research/panel.js    1261 L  the side panel: form, job cards, sections
static/js/research/jobs.js      382 L  job state machine + REST/SSE transport
static/js/researchSynapse.js    225 L  animated SVG progress graph
static/style.css             ~38805+   research CSS (see §12 before touching it)
```

### The single most important fact in this document

**`src/research_handler.py` is live. `services/research/research_handler.py`
is dead.**

Both files define a class called `ResearchHandler`, both are ~500-1000 lines,
and they have diverged badly. The application imports the `src/` one:

```
src/app_initializer.py:22   from src.research_handler import ResearchHandler
src/app_initializer.py:88   research_handler = ResearchHandler()
```

Nothing in `app.py`, `routes/`, or `src/` imports the `services/` one. Only
`services/research/__init__.py` and two test files do.

**If you edit `services/research/research_handler.py`, you have changed nothing.**

They differ in ways that matter:

| Behaviour | `src/` (live) | `services/` (dead) |
|---|---|---|
| `start_research` params | 17 | 5 |
| Path confinement | `_research_json_path()` — validated + traversal-checked | raw `f"{session_id}.json"` — **traversal risk** |
| Owner stamping | yes | no |
| Hard wall-clock timeout | yes | no |
| Endpoint probe | yes | no |
| `consumed` flag | yes | no — `clear_result` deletes the file |
| `max_rounds` | caller-supplied (default 20) | hardcoded `8` |
| `research_max_tokens` | 16384 | 8192 |

The `services/` copy is also the only place a **report feature exists that the
live path lost**: `tests/test_research_handler_analyzed_urls.py` asserts the
`_format_research_report()` output contains an `### Sources` section and an
`### Analyzed URLs` section. The live signature takes no `findings` /
`analyzed_urls` kwargs and emits neither. So that test passes only against dead
code.

**Do not "fix" this by deleting or shimming `services/`** — that would delete a
feature and break two tests. It needs a maintainer decision (port the report
sections forward, or retire the feature deliberately). It is flagged in §11.

---

## 3. The panel execution path, end to end

Follow this when debugging a run. Every arrow is a real function you can set a
breakpoint in.

```
[browser] Start button
  → panel.js:542  _handleStart()
      → jobs.js:272  _launchJob(job)
          → POST /api/research/start
                │
[server]         ▼
  routes/research/research_routes.py:492  research_start()
      :496  require_privilege(request, "can_use_research")
      :511  session_id = "rp-" + 12 hex chars
      :520  _owned_enabled_endpoint(...) / resolve_endpoint("research")
      :563  research_handler.start_research(...)
                │
              src/research_handler.py:250  start_research()
      :463   _release_finished_tasks()        ← reclaims finished runs (§5)
      :419   asyncio.create_task(_run())      ← the job is a bare asyncio.Task
                │
              src/research_handler.py:804  call_research_service()
      :856   await _probe_endpoint(...)       ← inside the try
      :886   researcher = DeepResearcher(...)
      :906   report = await researcher.research(...)
                │
              src/deep_research.py:252  DeepResearcher.research()
      :274   _create_plan()          ── LLM
      :282   _classify_category()    ── LLM  (skipped if category given)
      :291   for round in 1..max_rounds:
      :301       _emit(phase="searching")
      :304       _generate_queries() ── LLM
      :314       _search_and_extract()
      :343           _synthesize() ── LLM
      :347           _should_stop() ── LLM  → break?
      :369   _final_report()         ── LLM
                │
              ┌─────────────────────────────────────────────┐
[server]       │ _save_result() writes                      │
              │ data/deep_research/<session_id>.json        │
              │ + fire_event("research_completed", owner)   │
              └─────────────────────────────────────────────┘
                │
[browser]      ▼
  jobs.js:302  _connectStream(job)
      EventSource(/api/research/stream/{id})
      → onmessage → progress dict replaces job.progress
      → d.final   → _finishJob() → _fetchResult()
                        → POST /api/research/result-peek/{id}
```

---

## 4. Inside the loop — what each phase emits

`DeepResearcher._emit()` (`src/deep_research.py:788`) is the single source of
progress. It calls the `progress_callback` closure that `start_research`
installed (`src/research_handler.py:326`), which does one thing:

```python
def on_progress(event):
    entry["progress"] = event     # wholesale replace, not merge
```

So `entry["progress"]` is always the **latest** event, never a history. There is
no queue, no `Event`, no `Condition` anywhere in this feature.

The `phase` values the frontend knows how to render
(`jobs.js:244` `formatPhase()`):

| `phase` | Meaning | Extra keys |
|---|---|---|
| `probing` | checking the model answers | `model` |
| `planning` | writing the research strategy | — |
| `searching` | about to hit the search provider | `round`, `queries`, `query_preview`, `total_sources` |
| `reading` | fetching + extracting a page | `round`, `new_sources`, `total_sources`, `total_findings`, `url`, `title` |
| `analyzing` | synthesizing findings into prose | `round`, `total_sources`, `total_findings` |
| `writing` | final report | `total_sources`, `total_findings` |
| `warning` | degraded but continuing | `message` |
| `error` | giving up this round | `message` |

Adding a phase means: emit it in `deep_research.py`, **and** add a row to
`formatPhase()` in `jobs.js:244`. Miss the second and the user sees the raw
phase string.

---

## 5. Job lifecycle and the in-memory registry

The job is **an `asyncio.Task` in a plain dict**, keyed by session id:

```
src/research_handler.py:80    self._active_tasks: Dict[str, dict] = {}
src/research_handler.py:419   task = asyncio.create_task(_run())
```

States: `running → done | error | cancelled`.

`_release_finished_tasks()` (`src/research_handler.py:463`) reclaims entries
past a 1-hour TTL. Its rule is subtle and worth knowing before you touch it:

- **Persisted** (`done`) → the entry is **deleted**, because all four accessors
  (`get_status`, `get_result`, `get_sources`, `get_raw_findings`) read memory
  *before* falling back to disk. Delete the entry and the disk copy answers.
  Blank out `entry["result"]` instead and they return `None` — they do **not**
  fall through. This is the trap: it type-checks, passes review, and only
  shows up as a 404 on an old report hours later.
- **Not persisted** (`error`, `cancelled`) → entry kept, `researcher` dropped.
  `_save_result()` never runs for these outcomes, so the entry is the *only*
  record of what went wrong.

### Cancellation is double-layered

`cancel_research()` (`src/research_handler.py:511`):

1. `researcher.cancel()` sets a flag → cooperative break at the top of the next
   round (`deep_research.py:245`, checked at `:293`)
2. `task.cancel()` → hard `CancelledError` at the next await

A cancelled run **saves nothing** — no partial-result salvage, unlike timeout and
error, which both try to keep whatever was gathered.

### Persistence

`data/deep_research/<session_id>.json`, written by `_save_result()`
(`src/research_handler.py:665`). Fields:

```
query, status, result, raw_report, sources[], raw_findings[],
stats{}, category, started_at, completed_at, owner
— added later — consumed, hidden_images[], archived
```

`consumed` matters: `clear_result()` sets it instead of deleting the file (so
the visual report keeps working), and `get_status()` then returns `None` for
that id. **This means `POST /api/research/result/{id}` is destructive and can
only succeed once.** The panel uses `result-peek` (non-destructive); the chat
path uses the destructive one. Don't mix them up.

---

## 6. HTTP API

All in `routes/research/research_routes.py`, all inside
`setup_research_routes()` at `:209`.

| Method | Path | Handler | Notes |
|---|---|---|---|
| POST | `/api/research/start` | `:492` | The only way to launch. Needs `can_use_research`. |
| GET | `/api/research/stream/{id}` | `:579` | SSE, 1.5 s poll-and-diff |
| GET | `/api/research/active` | `:259` | Adopt jobs started elsewhere |
| GET | `/api/research/status/{id}` | `:278` | |
| POST | `/api/research/cancel/{id}` | `:289` | |
| POST | `/api/research/result/{id}` | `:298` | **Destructive** — marks consumed |
| POST | `/api/research/result-peek/{id}` | `:613` | Non-destructive read |
| GET | `/api/research/library` | `:366` | Paginated, sortable, searchable |
| GET | `/api/research/detail/{id}` | `:421` | Whole JSON verbatim |
| GET | `/api/research/report/{id}` | `:323` | Server-rendered HTML, new tab |
| POST | `/api/research/spinoff/{id}` | `:635` | Creates a chat session to discuss it |
| POST | `/api/research/{id}/archive` | `:437` | |
| DELETE | `/api/research/{id}` | `:455` | Unlinks the JSON |
| POST | `/api/research/{id}/hide-image` | `:343` | |
| POST | `/api/research/{id}/unhide-images` | `:355` | |
| — | `/api/research/tasks` | — | **Does not exist.** Was advertised to the agent until the fix in §11. |

Request body (`ResearchStartRequest`, `:480`):

```
query                 (required)
max_rounds            0-20, 0 = "Auto" → internally 20
search_provider       override for this run
endpoint_id           pick a specific endpoint
model                 override the endpoint's model
max_time              60-1800, default 300
extraction_timeout    15-3600
extraction_concurrency 1-12
category              skip LLM category classification
```

### Auth and ownership

Every route calls `_require_user`, and most also verify ownership. Research
results carry an `owner` field stamped at start; a mismatch reads as **404, not
403**, deliberately, so the existence of another user's report isn't leaked.

`require_privilege(request, "can_use_research")` gates the start route only.

---

## 7. SSE, and why it is poll-and-diff

The panel stream (`routes/research/research_routes.py:579`) does **not** push from the producer.
It polls:

```python
while True:
    status = research_handler.get_status(session_id)   # every 1.5s
    if progress != last_progress:
        yield f"data: {...progress, 'status': status}"  # only on CHANGE
    if status != "running":
        yield terminal_frame; return
    await asyncio.sleep(1.5)
```

Consequences you must respect:

- Only the **latest** progress dict exists. You cannot replay history.
- Add a key to the progress dict and it propagates. Change the dict's identity
  and it propagates. There is no ordering guarantee beyond arrival.
- Terminal frame is `{"status": ..., "final": true}` plus `error` (≤500 chars)
  only when the status is `error`.

Client side (`jobs.js:302`): native `EventSource`. On `es.onerror` it closes
and falls back to explicit `GET /status` polling after 3 s
(`jobs.js:333` `_pollFallback`) — the browser's own reconnect is deliberately
bypassed.

The chat path uses a different mechanism entirely: progress is emitted as
`{"type": "research_progress"}` frames inside the normal chat SSE, on a 1 s poll,
with `: heartbeat N` comments interleaved to defeat proxy buffering
(`routes/chat_routes.py:1131-1150`).

---

## 8. Configuration

`src/settings.py:91-109`, overridable per user for the first two:

| Key | Default |
|---|---|
| `research_endpoint_id` / `research_model` | `""` |
| `research_search_provider` | `""` (falls back to `search_provider`) |
| `research_max_tokens` | 16384 |
| `research_extraction_timeout_seconds` | 90 |
| `research_planning_timeout_seconds` | 90 |
| `research_query_timeout_seconds` | 90 |
| `research_extraction_concurrency` | 3 |
| `research_run_timeout_seconds` | 1800 |

**The Settings-drawer controls in `index.html:1137-1353` are not read by the
panel.** The panel's `POST` body never sends `max_time`,
`extraction_timeout`, or `extraction_concurrency` — those are resolved
server-side from user settings. Editing the drawer changes the settings file,
not the request.

Paths: always import `DEEP_RESEARCH_DIR` from `src.constants` (`:47`). Never
build `os.path.join(DATA_DIR, "deep_research")` yourself.

Env: `ZEPHYRUS_DATA_DIR`, `SEARXNG_INSTANCE`, `SEARXNG_GENERAL_ENGINES`,
`LLM_CONNECT_TIMEOUT`, `ZEPHYRUS_LOCAL_MODEL_GATE`, `ZEPHYRUS_INTERNAL_BASE`,
`APP_PORT`, `ZEPHYRUS_INTERNAL_TOKEN`.

Dead config, safe to ignore: `RESEARCH_LLM_ENDPOINT` (in `.env.example` and all
three compose files, read by nothing) and `src/config.py:78-82`
(`research_service_url`, `research_timeout`).

---

## 9. Search providers

Registered in `services/search/providers.py:19`:
`searxng`, `brave`, `duckduckgo`, `google_pse`, `tavily`, `serper`, `disabled`.

Selection order (`deep_research.py:567-571`):
per-run override → `research_search_provider` → `search_provider` (default
`searxng`) → then `_build_provider_chain()` appends the user's
`search_fallback_chain` (default `["duckduckgo"]`).

`"disabled"` makes every query return `[]`, and the run dies with the
"Search unavailable" message (§11).

### Known bypass worth knowing

`deep_research.py:582` calls `_call_provider` **directly** instead of going
through `searxng_search_results`. That means research skips the shared disk
search cache, the 2-attempt retry loop, query analytics, and result re-ranking.
It also hardcodes `count=10`, ignoring `search_result_count`. Within one run,
`self.queries_used` is the only defense against re-issuing the same query.

Not fixed — it's a behavioral change to shared search code, not a defect in the
research path. Flagged in §11.

---

## 10. Frontend architecture

Three modules, one state owner.

```
panel.js   owns the DOM, the form, and the card rendering
jobs.js    owns _jobs[] — the single source of truth for job state
researchSynapse.js  the animated SVG, shared by panel and chat
```

`jobs.js:5` `let _jobs = []` is the truth. `getJobs()` hands out the **live
array**, not a copy. `panel.js:665 _renderJobs()` wipes and rebuilds the entire
job list on **every** notification — which fires on each SSE tick *and* each
1 s elapsed-timer tick. So the panel tears down and re-creates every button
listener roughly once per second per running job. The only thing deliberately
preserved across that churn is the SVG synapse, re-parented from `_jobSynapses`
at `panel.js:966`.

Consequence: **do not store per-card state in the DOM.** Put it in the job
object. `data-job-id` on the card is the only stable handle.

`jobs.js:35 init()` runs at app boot, before the panel is ever opened — so jobs
exist and stream whether or not the modal is visible. `panel.js:216` shows a
completion badge only `if (!_open)`.

### Module import rule (do not break this)

Every import of a given module must use an **identical specifier**. A `?v=`
query makes a different URL and the browser instantiates the module **twice**,
with two independent copies of module-scope state. `static/app.js:35` carries a
comment about this because `cookbook.js` already shipped with the bug.

It bit research too: `app.js` imported `panel.js?v=...` while
`chatRenderer.js` and `chatStream.js` imported the bare path, so agent-started
research was adopted into a second `_jobs` array whose `_renderCb` was `null` —
invisible jobs plus duplicate `EventSource` connections. Now fixed (§11). The
research files are **not** in the `sw.js` precache list, and `sw.js:120-122` is
network-first for `/static` JS, so `?v=` bought nothing anyway.

---

## 11. Bugs found and fixed

All verified: 4595 tests pass, and the two remaining failures are pre-existing
on a clean tree (`test_docs_no_orphan_images`,
`test_new_chat_model_preference`).

| # | Bug | Impact | Fix |
|---|---|---|---|
| 1 | `?v=` suffix on research imports vs. bare specifiers elsewhere | Agent-started research silently invisible; duplicate `EventSource` connections; the `#research-<id>` link opened an uninitialized panel instance | Removed the suffixes; extended the guard comment at `app.js:35` |
| 2 | `_active_tasks` was append-only — only `clear_result()` ever popped | Unbounded memory: every run's full finding set pinned for server lifetime | `_release_finished_tasks()` at `src/research_handler.py:463`, TTL 1 h, called from `start_research` |
| 3 | `await self._probe_endpoint(...)` sat **outside** the `try` | A dead model or bad key raised past `call_research_service`, bypassing the fallback chain — a plain web-search fallback that needs no LLM could still have answered | Moved inside the `try` at `src/research_handler.py:856` |
| 4 | `"...not allowed to can use research."` | Doubled word in a user-facing 403 | `routes/research/research_routes.py:505` |
| 5 | `/api/research/tasks` advertised in the agent system prompt | Route doesn't exist; agent would call a 404 | Removed from `src/agent_loop.py:558` |
| 6 | `openPanel()` set `_open = true` before the `#chat-container` guard | Panel marked open with no DOM; `isOpen()` lied and later `toggle()`/`close()` short-circuited | Guard now returns before setting the flag (`panel.js:236`) |
| 7 | `n + (n === 1 ? ' research' : ' research')` | Dead ternary — both branches identical, and `0` rendered `"0 research"` with no space | `panel.js:194` |

### Found, deliberately **not** fixed

These need a product decision, not a patch. Each is a trap for whoever picks
them up.

- **`services/research/` duplicate** (§2). Converting it to a `sys.modules`
  shim — the repo's own established pattern, see `routes/research_routes.py:13`
  — would delete the `### Analyzed URLs` / curated `### Sources` report
  features and break `tests/test_research_handler_analyzed_urls.py` and
  `tests/test_services_research_low_quality_sources.py`. Decide: port the
  report sections into `src/`, or retire them on purpose.
- **Search cache bypass** (§9). Fixing it changes shared search behaviour for
  every consumer.
- **`_active_streams` gates background jobs during research.** A research turn
  keeps the foreground gate busy for its whole duration
  (`src/interactive_gate.py:134`), so unrelated background tasks stall.
- **Multi-worker uvicorn is unsafe.** `_active_tasks` is process-local, so
  `/stream/{id}` can hit a worker holding no entry while the job runs elsewhere.
- **Inline chat research mode is vestigial but live.** `#research-toggle` cannot
  be switched on from the UI (`index.html:710`), yet ~250 lines of `chat.js` are
  still wired to it, including `checkPendingResearch` (`chat.js:4686`) which
  fires a `GET /status` on every session switch. It is reachable only if the
  agent emits `ui_control: toggle {toggle_name: 'research'}`.
- **`#overflow-research-btn` does not exist in `index.html`** but is referenced
  8 times. All reads are null-guarded, so it is inert dead code, not a bug.
- **`get_avg_duration()` globs and JSON-parses the whole research directory**,
  memoized per active entry but not for disk-only reads.

---

## 12. Running and debugging it

```bash
# The checks CONTRIBUTING asks for
python -m pytest -k research -q
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/research/panel.js
node --check static/js/research/jobs.js
```

Then run the app and drive it in a browser — CONTRIBUTING requires screenshots at
desktop width **and** a 375 px viewport for anything visual.

Useful reads:

- `GET /api/research/active` — is the server even aware of the job?
- `GET /api/research/status/{id}` — status + the latest progress dict
- `GET /api/research/detail/{id}` — the whole persisted JSON
- `data/deep_research/*.json` — same thing on disk
- `scripts/zephyrus-research list|show|search|delete` — read-only CLI over disk

Logs carry the useful signal: `Round N: extracted M findings`,
`consecutive empty`, `Search appears to be down`,
`Released N finished research task(s)`.

`scripts/zephyrus-research` maps the CLI's `--status complete` to the stored
`"done"`, so the two vocabularies differ.

### Adding a progress phase

1. Emit it: `self._emit(phase="yourphase", ...)` in `deep_research.py`
2. Render it: add a row to `formatPhase()` in `jobs.js:244`
3. Add test coverage in `tests/` — there are 217 research tests already

### Changing the panel's look

Read `CONTRIBUTING.md`'s design-system rules first. The existing research CSS
predates some of them: it leans on `1px solid var(--border)` where the current
rule is to step the surface ladder, uses raw durations (`0.15s`, `1.1s`) instead
of `--dur-*`, uses literal radii instead of `--radius-*`, and never uses
`--border-control` for control edges — which the current rule says is mandatory
for anything focusable, including the query textarea and the four `<select>`s.
Category colours are hardcoded hexes at `style.css:39121`, not tokens. Matching
the surrounding style is required for merge.