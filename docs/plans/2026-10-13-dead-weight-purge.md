# Dead-Weight Purge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove only provably-dead media, docs, and code from Zephyrus to reclaim ≥5M tracked bytes with zero test regressions.

**Architecture:** Read-only inventory first (JSON manifests), then reference-proof per file (grep + import graph + git log), then QUARANTINE-first deletes in small gated commits on a backup branch. Team E blocks any unsafe delete.

**Tech Stack:** git, du, md5sum, rg/grep, venv python (pytest 4623 tests), vulture, coverage.py, knip or rg, node --check, oxipng/cjpeg.

**Spec:** Subagent cleanup brief `ses_eca4674dfffevSFXUaYdkfQNJN` (2026-10-13) as corrected by live evidence below. All `Evidence:` lines were re-verified on `master @ b78c4dd`, clean tree, 1318 tracked files.

## Global Constraints

- Delete NOTHING without reference-proof (`grep` hits + import graph + `git log -1`) AND test-proof (fast lane green before AND after each commit).
- `venv/`, `.git/`, `.env`, `data/app.db`, `data/*.db` are HARD EXCLUDED from all analysis and all deletes.
- `data/`, `logs/`, `__pycache__/`, `node_modules/`, `.pytest_cache/` are local-hygiene only, NEVER part of the code PR.
- Disputed files go to `quarantine/<date>/` (gitignored, local only) for 1 sprint, never hard-deleted in this PR.
- No `git rm` before human approves `reports/purge-manifest.md`.
- Kill-switch: revert to tag `pre-purge-<sha>` on any red gate.

## Evidence Corrections (override subagent brief where it conflicts)

- `docs/Zephyrus-Logo.png` KEEP. Evidence: `README.md:1` embeds it (`<img src="docs/Zephyrus-Logo.png">`). `static/icons/Zephyrus-Logo.png` KEEP. Evidence: `static/index.html:618`, `static/login.html:298`, `static/sw.js:68`. Only `logs/*.png` copies are safe-delete (gitignored, never served). Triple-md5 `a9cbd1e2…` confirmed but the two tracked copies serve different consumers (GitHub vs served app).
- `static/icons/Zep_LOGO.png` (2.2M) KEEP. Evidence: `launcher.py:73` returns it (`os.path.join(base,'static','icons','Zep_LOGO.png')`). Deleting breaks launcher. Only `logs/Zep_LOGO.png` (same md5 `1dc7c1ec…`, gitignored) is safe-delete.
- `docs/Zephyrus-Chat.png` (1.6M) KEEP + compress. Evidence: `README.md:46` embeds it (`![Zephyrus UI preview](docs/Zephyrus-Chat.png)`).
- `README.md:43` lists 6 `docs/*.webm` (`chat, research, gallery, notes, compare, document`) that DO NOT EXIST (`ls docs/*.webm` → no such file). Fix README, do not chase deletes.
- All 8 `static/fonts/*.woff2` KEEP. Evidence: Inter ×3 referenced inline `static/index.html:61-63`; FiraCode ×3 + OpenDyslexic ×2 referenced `static/style.css:448-454,8207-8209`.
- `static/js/calendar/utils.js` KEEP. Evidence: imported `static/js/calendar.js:19`. `static/js/color/hex.js` KEEP. Evidence: imported `static/js/bgEffect.js:8`. `static/js/compare/` (10 files) and `static/js/editor/` (10+ files + `build/`) are NOT empty — verify imports, never blind-delete.
- `static/icons/ollama-mark-crop.png` + `sglang-mark.png` KEEP. Evidence: `static/js/cookbook.js:1099,1102` (mask + img). Only `ollama-mark.png` (7.4K) and `sglang-logo.png` (107K) have zero refs — sole icon delete candidates.
- `topo-dark.png` (1.9M) KEEP (`static/style.css:40800`, `static/login.html`). `topo-field.png` (667K) KEEP (`static/login.html`, `gan-harness/*.py`). All PWA icons KEEP (`static/manifest.json`, `static/sw.js:63-67`).
- `gan-harness/baseline/` (7.0M, 7 tracked files incl. `untracked-assets.tar.gz`) was unmentioned in brief — added to scope as investigate-first.
- Test lane: `venv/bin/python -m pytest` collects **4623** tests (not ~1000). `vulture` NOT installed — Task 4 installs it.
- `package.json` `@antithesishq/bombadil` KEEP. Evidence: `tests/bombadil-spec.ts:4-5` imports it.
- `docs/*.png|jpg` tracked: exactly 5 files (`Ultra-Dark…`, `Zephyrus Dark Topographic Dashboard`, `Zephyrus-Chat`, `Zephyrus-Logo`, `zephyrus.jpg`). Zero `*.mp4|mov|webm|mp3|wav` repo-wide (excluding `venv/.git/node_modules`) — verified.

## Review Focus

- Launcher boot path (`launcher.py` string-built icon path) breaks silently if an icon that looks unreferenced is deleted — expect `launcher.py` smoke to catch it.
- `cookbook.js` CSS-mask icon refs (`-webkit-mask:url(...)`) are invisible to import graphs — expect `rg` string search to catch what knip misses.
- `calendar.js` / `bgEffect.js` deep relative imports (`./calendar/utils.js`, `./color/hex.js`) look dead from the top level — expect collect-only + fast lane to catch it.
- `README.md` webm listing rots independently of `docs/` contents — expect link-check step to catch stale names.
- `gan-harness/baseline/untracked-assets.tar.gz` may be load-bearing for eval reproducibility — expect explicit KEEP-or-archive decision, never silent delete.

---

### Task 1: Safety baseline + backup branch

**Files:**
- Create: `reports/inventory-media.json`, `reports/inventory-docs.json`, `reports/inventory-py.json`, `reports/inventory-frontend.json`
- Modify: none (read-only task)
- Test: `venv/bin/python -m pytest --collect-only -q` (expect 4623)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: branch name + tag `pre-purge-<sha>` + before-metrics (consumed by Tasks 6–7 for delta report)

- [ ] **Step 1: Create backup branch + tag from clean tree**

Run: `git status --porcelain=v1` (Expected: empty) then `git checkout -b chore/dead-weight-purge-2026-10-13 && git tag pre-purge-$(git rev-parse --short HEAD) && git push origin chore/dead-weight-purge-2026-10-13 --dry-run`
Expected: clean tree, branch created, tag recorded (push real branch; tag local at minimum)

- [ ] **Step 2: Record before-metrics**

Run: `du -sh docs static static/icons static/js static/lib logs data gan-harness; git ls-files | wc -l; git count-objects -vH; venv/bin/python -m pytest --collect-only -q 2>&1 | tail -2`
Expected: docs 5.1M, static 18M, 1318 files, 4623 tests (save output to `reports/before-metrics.txt`)

- [ ] **Step 3: Emit read-only inventories (no deletes)**

Run: `git ls-files docs static gan-harness specs tests/*.md *.md | xargs ls -lh > reports/inventory-docs.txt; md5sum docs/*.png static/icons/*.png logs/*.png > reports/inventory-media.txt; find static/js/calendar static/js/color static/js/compare static/js/editor -type f > reports/inventory-frontend.txt`
Expected: 4 inventory files exist in `reports/` (untracked, gitignored later)

- [ ] **Step 4: Lock verification lane green**

Run: `venv/bin/python -m pytest tests/ -x -q --co -q 2>&1 | tail -2 && node --check static/app.js && echo LANE-OK`
Expected: `LANE-OK`, 4623 collected. Red = stop, do not proceed to Task 2.

- [ ] **Step 5: Commit inventories**

```bash
git add reports/before-metrics.txt reports/inventory-*.txt
git commit -m "chore(purge): phase 0 safety baseline + inventories"
```

### Task 2: Media purge (safe deletes only + quarantine candidates)

**Files:**
- Modify: `logs/` (local-only deletes, never committed), `reports/purge-manifest.md` (append media section)
- Delete (git-tracked, needs approval): `docs/Ultra-Dark Technical Topographic Map.png` (1.9M), `docs/Zephyrus Dark Topographic Dashboard.png` (1.5M) — ONLY if Step 2 confirms zero refs; `static/icons/ollama-mark.png`, `static/icons/sglang-logo.png` — ONLY if Step 3 confirms zero refs
- Test: `grep -rn` reference proofs + `venv/bin/python -m pytest tests/ -x -q -k "not slow"` fast lane

**Interfaces:**
- Consumes: before-metrics from Task 1
- Produces: media section of `reports/purge-manifest.md` with `KEEP | DELETE | QUARANTINE` + evidence per file (consumed by Task 6)

- [ ] **Step 1: Delete gitignored log-logo duplicates (local-only, unblocks 2.2M)**

Run: `rm -v logs/Zephyrus-Logo.png logs/Zep_LOGO.png && du -sh logs`
Expected: `logs/` drops ~2.2M, `git status --porcelain` shows NOTHING (files were ignored). If git shows deletions, STOP — assumption violated.

- [ ] **Step 2: Reference-proof the two oversized unlinked docs heroes**

Run: `grep -rn "Ultra-Dark Technical Topographic\|Zephyrus Dark Topographic Dashboard" README.md docs/ static/ app.py launcher.py 2>/dev/null; echo "EXIT:$?"`
Expected: EXIT:1 (zero hits) → mark both `DELETE` in manifest. Any hit → mark `KEEP + compress` instead. (`Zephyrus-Chat.png` and `Zephyrus-Logo.png` are pre-proven KEEP — do not re-litigate.)

- [ ] **Step 3: Reference-proof the two orphan icon candidates**

Run: `grep -rn "ollama-mark\.png\|sglang-logo\.png" --include="*.html" --include="*.js" --include="*.css" --include="*.json" --include="*.py" . 2>/dev/null | grep -v -E "venv/|node_modules/|.git/|data/"; echo "EXIT:$?"`
Expected: EXIT:1 (zero hits) → mark both `QUARANTINE` (not hard-delete: icons are cheap, launcher risk is not). Any hit → `KEEP`.

- [ ] **Step 4: Verify zero video/audio (close with evidence)**

Run: `find . -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" -o -iname "*.mp3" -o -iname "*.wav" | grep -v -E "venv/|.git/|node_modules/"; echo "EXIT:$?"`
Expected: EXIT:1 (zero hits) → log `no media hits` in manifest. (README webm names are fixed in Task 3.)

- [ ] **Step 5: Record media manifest section + run gate**

Run: append results to `reports/purge-manifest.md` (one line per file: path, size, status, evidence), then `venv/bin/python -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -2`
Expected: manifest section complete, fast lane green. No `git rm` yet — approval happens in Task 6.

### Task 3: Docs triage (fix links, archive history, investigate baseline)

**Files:**
- Modify: `README.md` (fix 6 dead webm names + verify `zephyrus.jpg` mention), `docs/setup.md` (only if it references deleted images)
- Create: `reports/purge-manifest.md` (append docs section)
- Move (needs approval): `gan-harness/feedback-*.md`, `gan-harness/generator-notes-*.md` → squash into `gan-harness/RESULTS.md` appendix or `quarantine/`
- Test: markdown link-check via `grep` + fast lane

**Interfaces:**
- Consumes: media manifest from Task 2 (which images survive)
- Produces: docs section of manifest + fixed README (consumed by Task 6 commit 2)

- [ ] **Step 1: Fix README dead webm listing**

Run: `grep -n "webm" README.md` (Expected: line 43 lists 6 names). Edit `README.md:43` to remove names that have no file in `docs/` or point at the surviving `docs/Zephyrus-Chat.png` preview.
Expected: `grep -rn "\.webm" README.md docs/setup.md` returns zero, or every named file exists on disk.

- [ ] **Step 2: Triage root + docs/ markdown (update, don't delete)**

Run: `grep -rn "docs/.*\.png\|docs/.*\.jpg" README.md docs/setup.md docs/*.md 2>/dev/null`
Expected: every referenced image exists on disk post-Task-2. Fix any dangling link in place. `README.md`, `ROADMAP.md`, `SECURITY.md`, `THREAT_MODEL.md`, `CONTRIBUTING.md`, `ACKNOWLEDGMENTS.md` are KEEP-always.

- [ ] **Step 3: Archive gan-harness history (squash, don't scatter)**

Run: `wc -c gan-harness/feedback-*.md gan-harness/generator-notes-*.md; du -sh gan-harness/baseline`
Expected: ~163K history + 7.0M baseline quantified. Decision logged: `spec.md`, `RESULTS.md`, `generator-prompt.md`, `evaluator-prompt.md`, `eval-rubric.md` = KEEP (harness contract); `feedback-*` + `generator-notes-*` = QUARANTINE-first (squash into `RESULTS.md` appendix in follow-up); `baseline/` + `*.py` helpers = investigate-first with Team C (check live imports before any move).

- [ ] **Step 4: Triage meta-docs (keep contracts, expiry-date plans)**

Run: `git ls-files specs/ tests/*.md static/js/MODULE_SUMMARY.md integrations/ companion/ | head -30`
Expected: manifest marks `SKILL.md`/`README.md` contract files KEEP; `tests/OVERSIZED_TEST_SPLIT_PLAN.md`, `tests/LAYOUT_INVENTORY.md` KEEP-with-expiry or DELETE-once-executed (explicit per-file line, no bulk delete).

- [ ] **Step 5: Run gate**

Run: `venv/bin/python -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -2`
Expected: green. Commit README fix separately in Task 6.

### Task 4: Backend dead-code snipe (analyse → confirm → quarantine)

**Files:**
- Create: `reports/dead-py-candidates.json`
- Modify: none until Task 6 (read-only analysis here)
- Test: `venv/bin/python -m pytest tests/ -x -q -k "not slow"` + `venv/bin/python -m compileall -q src routes core services scripts`

**Interfaces:**
- Consumes: docs/media manifest (what stays)
- Produces: `reports/dead-py-candidates.json` with confidence + `KEEP | QUARANTINE` per module (consumed by Task 6 commit 3). No `DELETE` verdicts in this task.

- [ ] **Step 1: Install + run static analysis (no deletes)**

Run: `venv/bin/pip install vulture coverage pip-check-reqs 2>&1 | tail -1; venv/bin/python -m vulture src/ routes/ core/ services/ scripts/ mcp_servers/ app.py launcher.py --min-confidence 80 > reports/vulture.txt; wc -l reports/vulture.txt`
Expected: `reports/vulture.txt` non-empty candidate list (or empty with reason logged — both are valid outputs).

- [ ] **Step 2: Coverage flag for 0%-covered modules**

Run: `venv/bin/python -m coverage run -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -2 && venv/bin/python -m coverage report --show-missing --skip-covered > reports/coverage.txt; head -30 reports/coverage.txt`
Expected: `reports/coverage.txt` exists; 0%-covered modules listed as QUARANTINE candidates (never DELETE on coverage alone).

- [ ] **Step 3: Manual false-positive kill (dynamic imports, CLI, tests)**

Run: for each candidate, `grep -rn "<module>" --include="*.py" app.py launcher.py routes/ core/ services/ scripts/ mcp_servers/ agent_tools/ tests/ 2>/dev/null | grep -v -E "venv/" | head -5` plus check `importlib`, `__import__`, route auto-registration strings, `scripts/zephyrus-*` entry points.
Expected: every candidate in `reports/dead-py-candidates.json` has `evidence: [grep hits, import graph, git log -1]`, `risk: HIGH|MEDIUM|LOW`, `verdict: KEEP|QUARANTINE`. Known attention: `src/tool_implementations.py`-era giants, `routes/email_routes.py`, `companion/`, `gan-harness/*.py` helpers. When in doubt → KEEP or QUARANTINE, never DELETE.

- [ ] **Step 4: Diff requirements vs actual imports**

Run: `venv/bin/python -m pip_check_reqs --help 2>&1 | head -3 || venv/bin/pip install pip-check-reqs; venv/bin/python -m pip_missing_reqs --help 2>&1 | head -3`
Expected: unused-pin list logged in manifest. No pin removed until full test pass (Task 6).

- [ ] **Step 5: Run gate**

Run: `venv/bin/python -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -2 && venv/bin/python -m compileall -q src routes core services scripts && echo PY-GATE-OK`
Expected: `PY-GATE-OK`.

### Task 5: Frontend + config dead-code (verify refs, quarantine, never blind-delete)

**Files:**
- Modify: `reports/purge-manifest.md` (append frontend section)
- Delete candidates (needs approval): `static/icons/ollama-mark.png`, `static/icons/sglang-logo.png` only; `static/lib/*.min.js` only if zero imports; empty-dir deletes FORBIDDEN (dirs are not empty — proven live)
- Test: `node --check static/js/*.js` + fast lane

**Interfaces:**
- Consumes: backend candidates from Task 4
- Produces: frontend section of manifest (consumed by Task 6 commit 4)

- [ ] **Step 1: Verify JS subdirs are live (no deletes)**

Run: `node --check static/js/calendar/utils.js && node --check static/js/color/hex.js && node --check static/js/calendar.js && node --check static/js/bgEffect.js && echo JS-LIVE-OK`
Expected: `JS-LIVE-OK` (imports proven in evidence block). Log `calendar/`, `color/`, `compare/`, `editor/` as KEEP — close the "empty dirs" claim as REFUTED.

- [ ] **Step 2: Audit static/js bundle (grep, not knip-first)**

Run: `for f in admin chat document cookbookServe documentLibrary chatRenderer; do echo -n "$f: "; grep -rln "$f" --include="*.html" --include="*.js" static/ | grep -v -E "static/js/$f" | head -3 | tr '\n' ' '; echo ""; done; du -sh static/js/* | sort -rh | head -10`
Expected: per-file consumer list in manifest (`document.js` 485K, `chat.js` 260K, `cookbook*.js` ×6 all have consumers or explicit QUARANTINE with reason — no bulk verdicts).

- [ ] **Step 3: Verify vendored static/lib before any prune**

Run: `grep -rln "docx\|mammoth\|xlsx\|html2pdf\|highlight" --include="*.js" --include="*.html" static/ | grep -v "static/lib/" | head -10`
Expected: each of the 5 `*.min.js` (3.3M) has a consumer (`document.js`/`cookbook*.js`) or a QUARANTINE line. No delete without a named consumer check.

- [ ] **Step 4: Config/scripts matrix (keep deploy paths)**

Run: `grep -rln "build-macos-app\|start-macos\|build-windows-portable\|launch-windows\|install-service\|docker-compose" docs/setup.md .github/ 2>/dev/null | head; grep -n "bombadil" tests/bombadil-spec.ts | head -3`
Expected: shell/Docker/CI files referenced in `docs/setup.md`/CI = KEEP; `bombadil` = KEEP (proven import). Unreferenced scripts = QUARANTINE, never silent-delete.

- [ ] **Step 5: Run gate**

Run: `for f in static/js/*.js; do node --check "$f" || echo "FAIL:$f"; done | grep FAIL; echo "NODE-CHECK-DONE"; venv/bin/python -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -2`
Expected: `NODE-CHECK-DONE` with zero FAIL lines + green fast lane.

### Task 6: Gated execution (4 small commits + quarantine sweep + report)

**Files:**
- Delete (approved only): manifest `SAFE-DELETE` group
- Move: `QUARANTINE` group → `quarantine/2026-10-13/` (gitignored, local only)
- Create: `reports/after-metrics.txt`
- Test: full fast lane per commit + boot smoke

**Interfaces:**
- Consumes: manifest sections from Tasks 2–5 + human approval of `reports/purge-manifest.md`
- Produces: 4 gated commits + before/after report (consumed by Task 7 gates)

- [ ] **Step 1: Human approves manifest (BLOCKING — no git rm before this)**

Run: `cat reports/purge-manifest.md`
Expected: human replies approve | modify | stop. `SAFE-DELETE` = dupe `logs/*.png` (local-only, already done), unlinked docs heroes (only if zero-ref proven), 2 orphan icons to QUARANTINE. Everything disputed = KEEP or QUARANTINE.

- [ ] **Step 2: Commit 1 (media) + Commit 2 (docs) with gates**

Run per commit: `venv/bin/python -m pytest tests/ -x -q -k "not slow" 2>&1 | tail -1 && venv/bin/python -m compileall -q src routes core && du -sh docs static | tee -a reports/after-metrics.txt`
Expected: green + size delta logged. Commit messages: `chore(purge): remove unlinked docs heroes` / `chore(purge): fix README dead webm links`.

- [ ] **Step 3: Commit 3 (backend quarantine) + Commit 4 (frontend quarantine) with gates**

Run per commit: same gate as Step 2 plus `for f in static/js/*.js; do node --check "$f" || exit 1; done`
Expected: green. Quarantine moves are local-only (`quarantine/` gitignored) — commits record manifest + shims, not the moved bytes.

- [ ] **Step 4: Boot smoke + before/after report**

Run: `venv/bin/python app.py --help 2>&1 | head -5; venv/bin/python launcher.py --help 2>&1 | head -5; git count-objects -vH; git ls-files | wc -l; du -sh docs static`
Expected: both `--help` exit 0, report shows ≥5M tracked-media reduction (or honest shortfall with reason) + zero test regressions. Target is a goal, not a gate — regressions are the gate.

### Task 7: Prevention gates (CI + gitignore + prune script)

**Files:**
- Create: `.github/workflows/cruft-guard.yml` (or append to existing CI), `scripts/prune-local.sh`
- Modify: `.gitignore` (add `quarantine/`, `reports/`, `*.db-journal`, tighten PNG allowlist)
- Test: CI dry-run + `bash -n scripts/prune-local.sh`

**Interfaces:**
- Consumes: after-metrics from Task 6
- Produces: merged prevention gates (final deliverable alongside the purge PR)

- [ ] **Step 1: CI guard (fail on new cruft)**

Run: add workflow with `git ls-files | grep -E "venv|__pycache__|\.pyc|\.db$" && exit 1`, PNG-size check (`find docs -name "*.png" -size +500k`), `vulture --min-confidence 90` allowlist.
Expected: workflow file exists; intentionally oversized fixture fails locally when tested.

- [ ] **Step 2: Harden .gitignore (already strong — tighten, don't rewrite)**

Run: append `quarantine/`, `reports/`, `*.db-journal`, `gan-harness/__pycache__/`; replace blanket `!docs/**/*.png` with named allowlist of the 5 surviving docs images.
Expected: `git check-ignore -v quarantine/x reports/y data/app.db logs/z.png` all match; `git ls-files docs/*.png` still shows exactly the surviving set.

- [ ] **Step 3: Local-prune script (never touches live state without prompt)**

Run: write `scripts/prune-local.sh` clearing `__pycache__/`, `.pytest_cache/`, `tests/__pycache__/` (21M), `data/cache/`, `logs/`; prompt before any `.db`/`.env`; `bash -n scripts/prune-local.sh && echo SYNTAX-OK`
Expected: `SYNTAX-OK`; dry-run lists bytes reclaimable without deleting.

- [ ] **Step 4: Final full-lane verification**

Run: `venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -2`
Expected: full suite green (4623 tests). PR description links before/after metrics + manifest + quarantine note (1-sprint hard-delete follow-up).

## Self-Review

1. **Spec coverage:** every brief requirement has a task — media (T2), docs (T3), backend (T4), frontend+config (T5), hygiene-local-only (T1 constraints + T7 script), single PR + gates (T6–T7). `gan-harness/baseline` 7.0M gap added (T3-Step 3). No gaps.
2. **Step scan:** each step is one action with a checkable `Expected:` — no TBDs, no bulk verdicts, no bodies the signature doesn't need.
3. **Type consistency:** manifest statuses fixed to `KEEP | DELETE | QUARANTINE`; `DELETE` only for zero-ref-proven + approved files; quarantine is local-only throughout.
4. **Review Focus:** 5 failure modes listed, each with the catching mechanism named (launcher smoke, rg string search, collect-only, link-check, explicit baseline decision).
5. **Proportion:** plan is shorter than the code it protects — decisions + evidence pointers, not transcripts. File bodies appear nowhere; only commands and expected outputs.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-13-dead-weight-purge.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end. Runs well with a mid-tier session model, since the plan carries the design.

For this plan I recommend **Subagent-driven**, because Tasks 2–5 touch disjoint surfaces (media, docs, backend, frontend) with HIGH-cost false positives (launcher icon, calendar/color imports, cookbook mask refs) that benefit from independent reviewers before any `git rm`. Does the plan capture what you want, and which approach should we use?
