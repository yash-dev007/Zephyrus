
# Contributing to Zephyrus


Thanks for helping. The project is moving quickly, so the best contributions are focused, easy to review, and easy to test.

## Branch model

Zephyrus has two branches:

- **`dev`** — where all PRs land. Things can be in flux here; the merge button gets used freely.
- **`main`** — what users run. Curated and tested by the maintainer. Fast-forwarded to a stable `dev` commit at each release.

**Open your PR against `dev`, not `main`.** The GitHub "base" dropdown defaults to `dev`. If you opened a PR against `main` by accident, click "Edit" on the PR and change the base — no rebase needed.

End-users cloning the repo will land on `dev` by default. To run the curated/stable version: `git checkout main` after clone.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Prefer one bug fix or feature per pull request.
- Avoid broad rewrites, formatting-only changes, or moving many files unless the issue is specifically about structure.
- If you want to work on a large feature, open an issue first and describe the approach.

## Setup

Docker is the recommended path for normal testing:

```bash
git clone https://github.com/pewdiepie-archdaemon/zephyrus.git
cd zephyrus
cp .env.example .env
docker compose up -d --build
```

Manual development uses Python 3.11+:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

Windows is not actively tested. Docker on Linux or a Linux/macOS manual install is the safer path for now.

## Running Checks

Run the smallest relevant checks for your change:

```bash
python -m pytest
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/<file-you-changed>.js
```

For Docker-related changes:

```bash
docker compose config
docker compose up -d --build
docker compose logs --tail=120 zephyrus
```

Mention what you ran in the pull request description. If you could not run a check, say so.

## Pull Requests

Good pull requests usually include:

- A short explanation of the bug or feature.
- The files or areas changed.
- Manual test steps or automated test results from running the actual app, not just the test suite.
- Screenshots or short recordings for UI changes.
- Links to related issues, for example `Fixes #123`.

Please keep PRs small. Large PRs that mix unrelated cleanup, formatting, refactors, and behavior changes are much harder to review.

> **Auto-generated PRs.** If you are running an LLM agent (Devin, Cursor, OpenHands, Claude Code, etc.) against this repo: please open an issue describing the problem first instead of opening a PR directly. Bulk agent-generated PRs that don't match the project's visual style or contribution format will be closed without review, even when the underlying fix is correct.

## Style and visual changes

Zephyrus has an intentional visual style. PRs that ignore it will be closed without merge, no matter how correct the underlying code is.

Before submitting any change that affects what the app looks like — buttons, icons, fonts, colors, spacing, layout, CSS, HTML, SVG, or any `static/js/` module that draws to the DOM — please:

1. **Run the app locally** and view the change in a browser. Type-checks and unit tests are not enough.
2. **Attach a screenshot or short clip** of the change in the running app, at a desktop width **and at a 375px mobile viewport**. This applies to token-level changes too — editing a value in `:root` changes the whole app, so it needs the same evidence a new button does.
3. **Match the existing visual language.** Specifically:
   - Reuse existing CSS variables (`--accent`, `--danger`, `--fg`, `--bg`, `--surface-*`, `--text-*`, `--space-*`, `--radius-*`, `--shadow-*`, `--border-control`, …). Do not introduce new colour values, font sizes, spacing units, or radii.
   - Reuse existing button, input, card, and border classes. Don't invent parallel styling for similar widgets.
   - **No Unicode emoji in UI or code.** Use inline SVG (matching the monochrome icon style already in `static/index.html`) or plain text.
   - Zephyrus has ONE theme, **Ice / Arctic** — pure black surfaces, cool grey-blue text, one ice-blue accent, green reserved for "added / success". It is defined by the CSS variables in the `:root` block of `static/style.css`. There is no theme-switching mechanism, so make colour changes by editing those tokens. The palette and the reasoning behind it are in `docs/superpowers/specs/2026-10-06-ice-arctic-redesign-design.md`; the type, spacing, radius, elevation and motion scales are in `docs/superpowers/specs/2026-10-07-design-system-foundation-design.md`.
   - `--red` is a **deprecated alias for `--danger`**, kept only because older rules still read it. New rules must use `--danger`. `--green` is likewise an alias for `--success` and is only correct in added/success semantics.
   - The design system answers to these rules. A PR that breaks one will be sent back:
     - **Depth comes from the surface ladder, not from a hairline.** `--bg` → `--surface-1` → `--surface-2` → `--surface-3` → `--surface-4` → `--elevated` is the whole elevation model; each step is measured lighter than the one below. Reach for the next rung instead of adding `border: 1px solid`. A border is for separating things the ladder cannot — a divider inside one surface, or a card edge against a neighbour at the same level. If you find yourself adding a border to make a thing look raised, the fix is a ladder step.
     - **A control edge uses `--border-control`, never `--border`.** When the boundary *is* the affordance — an input, a select, a toggle track, a checkbox, a focusable well — the edge has to clear 3:1 (WCAG 1.4.11) against the lightest surface it can land on. `--border-control` is the only weight validated for that: 4.56:1 on `--bg` down to 3.10:1 on `--elevated`, and 3.10:1 is the worst case. `--border` is deliberately *below* 3:1 (1.20–1.76:1 across the ladder) because it is a divider, not a control boundary, and making every divider clear 3:1 would draw a grid over the whole app. Do not "fix" `--border` to clear 3:1 — use `--border-control` for the control instead.
     - **Text sizes come from the `--text-*` scale.** Eight steps (`--text-xs` 11 → `--text-3xl` 34) replace what used to be ~27 off-grid values. Do not introduce a size that is not a step. Below 11px is for decorative glyphs only — a drag grip, a status dot, a keycap — never readable text.
     - **Chrome is `--font-ui`, content is `--font-content`.** Navigation, buttons, labels and panel chrome take the proportional sans. The chat transcript, code, diffs, logs, paths, ids, hex and keycaps take `Fira Code`. Do not flip a code-rendering surface to the sans: monospace is what preserves the indentation of generated output and makes a long streamed response scannable. `--font-family` is runtime-owned (written by the user's font preference in `static/js/settings.js`) and both tokens derive from it, so a user's pick still wins.
     - **Spacing and radius come from their scales.** `--space-1` … `--space-10` on a 4px grid; `--radius-sm/md/lg/full`. An ad-hoc `padding: 13px` is the drift the scales exist to stop.
     - **A shadow pairs the dark drop with the light inset.** All three of `--shadow-sm/md/lg` are two-layer: a `rgba(0,0,0,·)` drop plus a 1px `inset 0 1px 0 rgba(255,255,255,·)` edge. The inset is load-bearing, not decorative — on a pure-black canvas a dark shadow is invisible where it falls, so a lone drop gives a floating panel no visible top boundary at all. Never write a single-layer `box-shadow`.
     - **Motion uses `--ease-out` and `--dur-fast/base/slow`, and is paired with the `prefers-reduced-motion` gate.** Every consumer of those tokens must be reachable from a `prefers-reduced-motion: reduce` block that zeroes the duration and keeps the end state. The consolidated gate for the shell and component primitives lives in `static/style.css`; if you add a new animated surface, add it there too.
     - **The palette answers to these rules.** A PR that breaks one of these will be sent back:
       - **Danger and error never share a token with the accent.** The old palette put green in `--red`, so ~129 selectors named `danger|error|delete` rendered green, including Python tracebacks and destructive buttons.
       - **Every text token clears 4.5:1 (WCAG AA) against the surface it actually renders on** — any rung of the ladder, not just `--bg`. Measure it; do not eyeball it. `--fg-subtle` is the floor at 4.67:1 on `--elevated`, its worst case.
       - **Adjacent `--hl-*` syntax tokens sit at least 30° apart in hue** (and ≥0.08 OKLab delta E), or the highlighting reads as emphasis rather than structure.
       - **Decoration is never load-bearing for legibility.** An unchecked toggle knob, a spinner arc, or a find-in-document highlight has to be visible on its own.
4. **Don't add parallel components.** If a similar widget already exists in the app, extend it instead of writing a new one.

If you are unsure whether a change is "visual," it is. Default to attaching a screenshot.

## Code conventions

Don't hardcode values that the project already exposes through a constant or a helper. Hardcoded literals drift out of sync, break on non-default deployments, and reintroduce bugs we've already fixed.

- **Filesystem paths:** never build writable paths from `Path(__file__)...` into the source tree, hardcode `/app/...`, or use a relative `"data/..."` string. Every persisted file and directory has a named constant in `src/constants.py` (for example `AUTH_FILE`, `USER_PREFS_FILE`, `SETTINGS_FILE`, `TTS_CACHE_DIR`, `CHROMA_DIR`). Import and use that named constant; do not re-derive the path locally with `os.path.join(DATA_DIR, "x.json")` or `DATA_DIR / "x.json"`. `DATA_DIR` is the single place that reads `ZEPHYRUS_DATA_DIR`, so use it directly only for dynamic paths that have no fixed name (for example per-owner files). If a data file or directory has no constant yet, add one to `src/constants.py`. The source tree is read-only in Docker and `/app/...` does not exist on native runs; guard directory creation so an unwritable path degrades gracefully instead of crashing at import.
- **Internal API / loopback URLs:** don't hardcode `http://localhost:7000`. Use `internal_api_base()` from `src.constants` (it honors `ZEPHYRUS_INTERNAL_BASE` / `APP_PORT`).
- **Ports, limits, model lists, and similar:** reuse the existing constant if one exists; if it doesn't and the value is used in more than one place, add a constant rather than copying the literal.

If you need a value that has no constant or helper yet, add it to `src/constants.py` (the single source of truth for paths and config; `core/constants.py` only re-exports it for backward compatibility) and import it, rather than repeating a literal across files.

**Commits:** use [Conventional Commits](https://www.conventionalcommits.org), `type(scope): summary` (e.g. `fix(search): ...`, `feat(notes): ...`, `docs(contributing): ...`). Common types: `fix`, `feat`, `refactor`, `docs`, `test`, `chore`, `ci`. Keep the subject short and imperative; put the "why" in the body when it isn't obvious.

## Issue Reports

For bugs, include:

- Install method: Docker, manual Python, WSL, etc.
- OS, browser, and device if relevant.
- Exact steps to reproduce.
- Expected behavior and actual behavior.
- Logs, screenshots, or terminal output.

For model-serving issues, include:

- Backend: Ollama, vLLM, SGLang, llama.cpp, LM Studio, etc.
- Model name.
- GPU/CPU and operating system.
- Cookbook task logs or server logs.

Issues with only "help", "does not work", or a screenshot without context may be closed as not actionable.

## Security

Do not post secrets, API keys, private logs, personal documents, or public IPs in issues or pull requests.

For security reports, follow [SECURITY.md](SECURITY.md).

