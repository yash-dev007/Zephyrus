# GAN Design Spec — Zephyrus Frontend + Theme Selection

> **Superseded.** The theme-selection feature described below was removed entirely. The app now has a single theme whose palette was later redesigned from the original green Terminal look to **Ice / Arctic**. See `docs/superpowers/specs/2026-10-05-terminal-only-theme-design.md` (why the runtime theme layer is gone) and `docs/superpowers/specs/2026-10-06-ice-arctic-redesign-design.md` (the palette and its rules).

## Brief (parsed)
Improve design quality of the existing Zephyrus frontend, with special focus on the theme selection feature, to reach a weighted score >= 9.0.

## Scope
- Primary surface: `#theme-popup` modal in `static/index.html` (459-669):
  - Tabs: Themes / Customize (`#theme-tabs`)
  - Browse: Default Themes grid `#themeGrid`, Your Themes `#themeUserGrid` + `#themeUserCard`
  - Customize: Colors `.theme-custom`, More Colors `#themeAdvanced`, Harmony generator `#theme-harmony-card`, Font & Layout, Save/Share, Reset, Peek toggle `#theme-opacity-wrap`
- Secondary: overall frontend cohesion that theme affects — chat bubbles, sidebar (`--sidebar-bg`, `--brand-color`), input area, code blocks (`--hl-*`), controls, scrollbars, background patterns, frosted glass.
- Logic: `static/js/theme.js` (THEMES, applyColors, applyFontDensity, applyBgPattern, initThemeUI). Do not break persistence (localStorage `zephyrus-theme`, `zephyrus-custom-themes` + `/api/prefs/theme` sync).

## Constraints (from CONTRIBUTING.md — must obey)
- Reuse existing CSS variables (`--bg`, `--fg`, `--panel`, `--border`, `--red`, etc). Do not introduce new color literals for theming.
- Reuse existing button, input, card, border classes. No parallel styling systems.
- No Unicode emoji in UI or code. Use inline SVG monochrome icons matching `static/index.html`.
- Monospaced `Fira Code` for primary UI text. Don't override.
- Dark theme is default; light work via existing theme system, not hard-coded.
- Don't hardcode paths/ports. Use `src/constants.py` if touching Python (not needed here).
- Run app locally + screenshot for visual changes. Mention checks in summary.

## Visual Excellence Goals (Generator PRIMARY goal)
> A stunning half-finished app beats a functional ugly one. Push for creative leaps — unusual layouts, custom animations, distinctive color work — while preserving all existing functionality.

Specific directions:
1. Theme swatches: evolve from flat 4-dot strips to rich mini-previews (browser-chrome mock: sidebar+chat+bubble dots) with hover lift, active ring using `--red` at 33% mix, smooth 160ms cubic-bezier, keyboard focus-visible.
2. Browse tab: section hierarchy (`Default Themes` / `Your Themes`), search/filter input reusing `.theme-fd-select` style, empty-state for custom, count badges.
3. Customize tab: grouped cards with consistent 8px rhythm, zone-highlight on hover (already via `initThemeZoneHighlight` — polish it), reset buttons only visible when `.changed`.
4. Harmony generator + Save/Share + Font/Layout: tighten spacing, align rows, unify `.theme-io-btn`, `.harmony-generate-btn`, `#theme-save-go`.
5. Micro-interactions: swatch select ripple/check, tab switch fade/slide, peek toggle eye animation, range slider thumb polish, toast on save.
6. Accessibility: focus rings, aria-pressed/selected on swatches, contrast-safe text via `color-mix(in srgb, var(--fg) ...)`, reduced-motion media query.
7. Responsive: modal `max-height: min(85vh, 600px)`, `.theme-grid` auto-fill minmax, mobile full-sheet rules preserved (see style.css 6930-6951, 7120-7138).
8. Craft details: consistent border-radius, 1px `var(--border)`, no layout shift on tab switch, no global `*` margin reset.

## Functional Invariants (must not regress)
- 16 presets render + click applies + persists.
- Custom themes max 8, save/delete/sync, overwrite guard for built-ins.
- Font/density/text-size/frosted/pattern/intensity/size/effect-color all apply live.
- Advanced overrides tracking (old-default vs new-default logic) preserved.
- Peek toggle only on Customize, restores on tab switch.
- `node --check static/js/theme.js`, `python -m py_compile`, `pytest` relevant tests pass.

## Config (parsed from user invocation)
- `--max-iterations 10` (default 10)
- `--pass-threshold 9.0` (default 7.5, raised per "give me at least 9 score")
- Mode: design (skip planner, generator + evaluator only)
- Weights: Design 0.35, Originality 0.30, Craft 0.25, Functionality 0.10
