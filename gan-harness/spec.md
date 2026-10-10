# GAN Design Spec — Zephyrus Whole UI

Run date: 2026-10-08. Mode: design (no planner — this file *is* the spec).
Supersedes the 2026-10-06 theme-picker run; its `spec.md` / `eval-rubric.md` /
`RESULTS.md` content is preserved in git history at commit `916c571`.

## Brief (parsed)

> Run the GAN design harness against the **whole Zephyrus project UI**.

Operator decisions taken at parse time:

| Decision | Value | Source |
|---|---|---|
| Latitude | **Bold, inside the token system** | operator |
| Iteration scope | **Whole UI every iteration** | operator |
| `--max-iterations` | 10 | default |
| `--pass-threshold` | 7.5 weighted | default (design default) |

## What "whole UI" covers

Every surface reachable in the running app, not just the chat shell:

1. **Shell** — topbar/context pill, sidebar (nav groups, session lists, footer
   user + settings), main viewport, composer, scroll regions.
2. **Chat** — transcript, user/assistant bubbles, thinking-process disclosure,
   per-message action rows, code blocks + syntax highlighting, streaming states,
   empty/new-chat state, model picker, attachments.
3. **Overlays** — every modal, drawer, sheet, dropdown, tooltip, toast,
   context menu, command palette, confirm dialog.
4. **Workspaces** — Brain, Calendar, Compare, Cookbook, Deep Research, Gallery,
   Library/Documents, Notes, Tasks, Email (inbox + library + shared).
5. **Settings** — all tabs, appearance/text-layout controls, admin surfaces.
6. **Auth** — `static/login.html`, first-run setup.
7. **Responsive** — 1440px desktop **and** 375px mobile for every surface above.

## Latitude: bold, inside the token system

The Generator is expected to take creative leaps. The leaps are in **layout,
composition, information design, motion, density, hierarchy, and the values of
the existing tokens** — not in inventing a parallel styling system.

Green light:
- Editing token **values** in the `:root` block (`static/style.css`).
- New layout structures, grid/flex composition, responsive behaviour.
- New motion: transitions, transforms, staged reveals — via `--dur-*` / `--ease-out`.
- New depth staging using the existing surface ladder.
- Reworking information hierarchy, empty states, onboarding, affordances.

Hard red lines (from `CONTRIBUTING.md` — a PR breaking these is closed):

- **No new colour literals outside `:root`.** Every colour is a token.
- **No new spacing, radius, or font-size values.** `--space-1..10`,
  `--radius-sm/md/lg/full`, `--text-xs..3xl` only.
- **Depth from the surface ladder, not from a hairline.** Reaching for
  `border: 1px solid` to make something look raised is a defect.
- **Control edges use `--border-control`, never `--border`.** Inputs, selects,
  toggles, checkboxes, focusable wells.
- **Chrome is `--font-ui`, content is `--font-content`.** Never flip a
  code-rendering surface to the sans.
- **Shadows are two-layer** (`--shadow-sm/md/lg`). Never a single-layer shadow.
- **Motion tokens paired with the `prefers-reduced-motion` gate.** New animated
  surfaces must be reachable from that block in `static/style.css`.
- **No Unicode emoji anywhere in UI or code.** Inline SVG in the existing
  monochrome style, or plain text.
- **No parallel components.** Extend the existing widget; do not build a
  parallel one.
- **Palette rules:** danger/error never share a token with the accent; every text
  token clears 4.5:1 against the surface it actually renders on; adjacent
  `--hl-*` syntax tokens ≥30° apart in hue; decoration is never load-bearing.

## Functional invariants (a regression here fails the run regardless of looks)

- Chat send, streaming render, and abort still work.
- Sidebar navigation still reaches every workspace.
- Modals open, close, trap focus, and restore it.
- Settings + appearance prefs persist across reload (localStorage + `/api/prefs/*`).
- Auth path, API-token path, and `AUTH_ENABLED=false` path all still work.
- No new console errors; no 4xx/5xx asset regressions.
- `node --check` on every touched JS file.
- `./venv/bin/python -m pytest` — **the full suite must stay green.** This
  includes `tests/test_design_tokens_brutal.py`, which audits token resolution,
  contrast floors, reduced-motion, and responsiveness.
- `./venv/bin/python -m py_compile app.py routes/*.py src/*.py` if Python is touched.

## Harness mechanics (how the Evaluator sees the UI)

- Server: `127.0.0.1:7000`, booted by `/tmp/opencode/serve.sh` with
  `AUTH_ENABLED=false LOCALHOST_BYPASS=true`. Loopback only.
- Screenshot/interaction driver: `/tmp/opencode/pw/shot.mjs`, driven with a JSON
  plan. Actions: `goto click hover hoverAll wait waitFor scroll type press eval shot`.
  Writes PNGs plus a console log (pageerrors, failed requests, HTTP ≥400) and a
  per-step results JSON.
- **Appearance is pinned** to `{font: mono, density: comfortable, uiScale: 100}`
  via request interception on `/api/prefs/appearance`. The saved user pref in
  `data/` is `serif` @ 125%; without the pin every screenshot would render in
  Georgia and scores would not be comparable across iterations. User data is
  never mutated.
- Both viewports are mandatory evidence: **1440×900 and 375×812**.

## Working-tree safety

The tree had ~1,800 lines of uncommitted design work at run start (Ice/Arctic
redesign + in-progress topographic direction). A snapshot lives in
`gan-harness/baseline/` (`HEAD`, `worktree.patch`, `style.css`, `index.html`,
`login.html`, `untracked-assets.tar.gz`). Any iteration can be reverted from it.
The Generator must not delete or rewrite that in-progress direction.

## Definition of done

Weighted score ≥ 7.5 against `eval-rubric.md`, with the full pytest suite green
and screenshot evidence at both viewports. On plateau (no weighted gain for 3
consecutive iterations) the harness stops and flags for human review rather than
burning the remaining budget.