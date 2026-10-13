# Cleanup Tasks

## Task 0: Guardrails & baseline
**Description:** Worktree + branch + quarantine layout + MANIFEST v0 + baseline sizes.
**Acceptance criteria:**
- [x] On branch `cleanup/dead-weight-audit` at `b78c4dd`
- [ ] `.cleanup/quarantine/{docs,images,code,tests,gan-harness}/` exists
- [ ] `.cleanup/MANIFEST.json` v0 exists
- [ ] Baseline `du` + top-30 sizes recorded
**Verification:**
- [ ] `git status --porcelain` clean (worktree)
- [ ] `git worktree list` shows entry
**Dependencies:** None
**Files likely touched:** `tasks/plan.md`, `.cleanup/MANIFEST.json`
**Estimated scope:** Small

## Checkpoint: Baseline
- [x] Worktree clean, manifest v0 committed or staged

## Task 1: Asset reference graph
**Description:** Grep every image/icon reference; mark referenced vs orphan-candidate.
**Acceptance criteria:**
- [ ] Every file under `docs/*.{png,jpg}` + `static/icons/*` has referenced/orphan verdict
- [ ] README's two image links confirmed
- [ ] PWA icon set marked KEEP with referencing file:line
**Verification:**
- [ ] Grep output saved to `.cleanup/asset-refs.txt`
**Dependencies:** Task 0
**Files likely touched:** none (read-only)
**Estimated scope:** Small

## Task 2: Doc reference graph
**Description:** Inbound-link + staleness check for each `docs/*.md`.
**Acceptance criteria:**
- [ ] Each `docs/*.md` basename grep'd across README/Dockerfile/app.py/integrations/SKILL/static/index.html
- [ ] `git log --follow` touch-date per doc recorded
**Verification:**
- [ ] Output saved to `.cleanup/doc-refs.txt`
**Dependencies:** Task 0
**Files likely touched:** none (read-only)
**Estimated scope:** Small

## Task 3: Code entry-point map
**Description:** BFS import graph from app.py/launcher.py; reachability of scripts/mcp/companions/services.
**Acceptance criteria:**
- [ ] Reachable vs unreachable list for `scripts/*`, `mcp_servers/*`, `companion/*`, `services/hwfit/*`
- [ ] Empty `static/js/calendar,color,compare,editor,emailLibrary` dirs verdict
- [ ] `static/js/MODULE_SUMMARY.md` staleness verdict
**Verification:**
- [ ] Graph saved to `.cleanup/code-graph.txt`
**Dependencies:** Task 0
**Files likely touched:** none (read-only)
**Estimated scope:** Medium

## Task 4: Duplicate + size report
**Description:** md5 + tracked-size table + >5M sweep (video check).
**Acceptance criteria:**
- [ ] md5 for 3 proven duplicate sets confirmed in worktree
- [ ] `git ls-files | xargs du` top-30 recorded
- [ ] `find -size +5M` sweep for videos/binaries recorded
**Verification:**
- [ ] Output saved to `.cleanup/dupes.txt`
**Dependencies:** Task 0
**Files likely touched:** none (read-only)
**Estimated scope:** Small

## Checkpoint: Inventory
- [x] MANIFEST.json v1 complete (8 rows, 3.6M quarantined; evidence in .cleanup/*.txt)

## Task 5: Docs quarantine (depends: Task 2)
**Description:** `git mv` zero-ref docs to quarantine, one manifest row each.
**Acceptance criteria:**
- [ ] Only Task-2-proven zero-ref docs moved
- [ ] Manifest rows with bytes/md5/last-touch/reason
**Verification:**
- [ ] `python -m py_compile` on touched files; `git status --short` reviewed
**Dependencies:** Task 2
**Files likely touched:** `docs/*.md`, `.cleanup/MANIFEST.json`
**Estimated scope:** Small

## Task 6: Media dedupe (depends: Tasks 1,4)
**Description:** Keep canonical logo/topo, quarantine copies.
**Acceptance criteria:**
- [ ] One canonical kept per duplicate set, choice recorded with referencing evidence
- [ ] PWA/vendor icons untouched
**Verification:**
- [ ] `static/index.html` loads with no 404 for kept icons (manual or grep)
**Dependencies:** Tasks 1, 4
**Files likely touched:** `static/icons/*`, `docs/*.png`
**Estimated scope:** Small

## Task 7: Orphan images (depends: Task 1)
**Description:** Quarantine only Phase-1-proven zero-ref images.
**Acceptance criteria:**
- [ ] Zero moves without `referenced_by: []` evidence
**Verification:**
- [ ] Boot/static check passes after moves
**Dependencies:** Task 1
**Files likely touched:** `docs/*.png`, `static/icons/*`
**Estimated scope:** Small

## Task 8: Dead-code surgery (depends: Task 3)
**Description:** vulture/ruff/coverage candidates, manual confirm, smallest diffs first.
**Acceptance criteria:**
- [ ] Tool outputs saved, every removal has import-graph proof
- [ ] `legacy_*` paths untouched
**Verification:**
- [ ] Focused pytest + py_compile pass per increment
**Dependencies:** Task 3
**Files likely touched:** `src/*`, `routes/*`, `static/js/*`
**Estimated scope:** Medium

## Task 9: Caches + harness archive
**Description:** Local-only purge log; gan-harness archived as unit.
**Acceptance criteria:**
- [ ] No `git rm` of gitignored paths; harness never selectively deleted
**Verification:**
- [ ] `git status` shows only intended tracked moves
**Dependencies:** Tasks 1-4
**Files likely touched:** `.cleanup/*`
**Estimated scope:** Small

## Checkpoint: Complete
- [ ] Smoke `pytest tests/test_app.py tests/test_api_chat_security.py -q` passes (needs venv)
- [ ] Boot check passes
- [ ] PR `cleanup/dead-weight-audit -> master` with manifest + du before/after
