# Implementation Plan: Zephyrus Dead-Weight Cleanup

## Overview
Clean dead weight only (unnecessary docs, images/videos, dead code) on branch `cleanup/dead-weight-audit` (base `b78c4dd`) via quarantine-not-delete, with verification gates. Worktree: `/tmp/opencode/Zephyrus-cleanup`.

## Architecture Decisions
- Quarantine via `git mv` to `.cleanup/quarantine/<lane>/`, one MANIFEST.json row per move. No hard `git rm` until after one release cycle.
- 4 parallel recon lanes, orchestrator owns merges. Team-D (verifier) has veto.
- `venv/`, `node_modules/`, `data/`, `logs/` are gitignored: local purge only, never `git rm`.
- `legacy_*` migration code in `core/auth.py`, `core/database.py`, `app.py` is KEEP.

## Task List

### Phase 0: Guardrails & Baseline (done: worktree + branch)
- [x] Task 0: Worktree + branch `cleanup/dead-weight-audit` at `b78c4dd`

### Checkpoint: Baseline
- [ ] `git status` clean in worktree, MANIFEST.json v0 exists

### Phase 1: Reference Inventory (read-only, parallel)
- [ ] Task 1: Asset reference graph (images/icons/topo/logos)
- [ ] Task 2: Doc reference graph (docs/*.md inbound links + staleness)
- [ ] Task 3: Code entry-point map (app.py/launcher.py BFS, scripts/mcp/companions reachability)
- [ ] Task 4: Duplicate + size report (md5, git ls-files sizes, +5M sweep)

### Checkpoint: Inventory
- [ ] MANIFEST.json v1 complete, no moves yet, human review

### Phase 2: Docs Purge (depends: Task 2)
- [ ] Task 5: Quarantine zero-ref docs (4 candidates) via `git mv`

### Phase 3: Media (depends: Tasks 1,4)
- [ ] Task 6: Dedupe logos/topo (keep canonical, quarantine copies)
- [ ] Task 7: Quarantine proven orphans only

### Phase 4: Dead-Code (depends: Task 3)
- [ ] Task 8: vulture/ruff/coverage candidates + manual confirm, smallest diffs first

### Phase 5: Caches/Harness
- [ ] Task 9: Local-only cache purge log + gan-harness archive decision

### Checkpoint: Complete
- [ ] py_compile + smoke pytest + boot check pass
- [ ] `git diff --stat` + manifest totals reviewed, PR opened

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Live asset delete (PWA icons, static/lib) | High | Ref-graph gate + veto + quarantine + boot test |
| Linter false positives (dynamic imports, legacy-*) | High | Advisory only, manual import proof |
| User-data loss (data/*.db, logs/) | High | Explicit yes required, default document-only |
| Linked docs (setup.md, SKILL.md) | Med | Inbound-link check first |
| Test breakage (700 files) | Med | collect-only before/after + coverage delta |
| Harness history loss | Med | Archive as unit |

## Open Questions
- data/ user data to preserve? (default: preserve)
- Canonical logo: docs/ or static/icons/?
- gan-harness/baseline: archive or keep?
- May we purge logs/ + __pycache__ locally?
