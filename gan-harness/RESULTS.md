# GAN Design Harness — Results (Zephyrus Theme Selection)

> **Superseded.** The theme-selection feature these results describe was removed entirely. The app now has a single theme whose palette was later redesigned from the original green Terminal look to **Ice / Arctic**. See `docs/superpowers/specs/2026-10-05-terminal-only-theme-design.md` (why the runtime theme layer is gone) and `docs/superpowers/specs/2026-10-06-ice-arctic-redesign-design.md` (the palette and its rules).

Parsed invocation:
- `brief` = "Improve design quality of Zephyrus frontend + theme selection feature"
- `--max-iterations 10` (default 10, used 3 before plateau)
- `--pass-threshold 9.0` (default 7.5, raised per "at least 9 score")
- Mode: design (skip planner, Generator + Evaluator only)
- Weights: Design 0.35, Originality 0.30, Craft 0.25, Functionality 0.10

## Loop
- Iter 0 baseline: 4.33 FAIL (D4.5 O3.5 C4.0 F7.0)
- Iter 1 (rich previews, search/counts/empty, motion/a11y, token fixes): 7.11 FAIL (D7.2 O6.8 C7.0 F8.0)
- Iter 2 (single preview language, sibling delete, search fix, harmony copy, empty CTA, thumb parity, reduced-motion): 7.95 FAIL (D8.0 O7.5 C8.0 F9.0)
- Iter 3 (chrome bar, code lines, accent gradient+glow, group roles, inset focus, scope filter, reduced-motion guard): 7.9 FAIL (D8.0 O7.5 C8.0 F8.5) — plateau

Per harness anti-pattern #3: stop after 3-iteration plateau, flag for human review. No live Playwright/screenshot run in this env (code-only), so Functionality capped and "award" bar unproven.

## What changed (files)
- `static/index.html`: browse hierarchy (search, counts, aria-live no-results, empty-state icon+CTA), group roles, harmony hex inherits Fira Code
- `static/js/theme.js`: button swatches with chrome preview, sibling delete, aria-pressed, filter both grids + reapply, harmony click-to-copy, empty CTA, reduced-motion canvas guard
- `static/style.css`: 96px grid, chrome/code/accent preview, 160ms cubic-bezier, focus-visible, inset harmony focus, thumb parity, token-only colors, reduced-motion block

## Checks
- `node --check static/js/theme.js` OK
- `./venv/bin/python -m pytest test_select_dropdown_theme_css + test_hex_to_rgb_js + test_compare_js` — 10 passed
- `py_compile app.py routes/*.py src/*.py` clean

## To reach 9.0
Needs live browser pass: screenshots (both tabs + mobile sheet), keyboard-only walkthrough, custom save/delete #8 edge, harmony apply, peek restore, zero console errors + one novel delight (pattern-aware glow / live mini-chat / ripple+toast+tab slide). Current honest score: ~7.9-8.0, not 9.0.
