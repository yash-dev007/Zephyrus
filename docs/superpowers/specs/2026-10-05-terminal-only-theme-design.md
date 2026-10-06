# Terminal-Only Theme — Design Spec

**Date:** 2026-10-05
**Status:** Approved and implemented

## Goal

Remove the theme system. Make Terminal the only UI.

Zephyrus shipped with 16 theme presets, a custom-colour picker, a font/density/
background panel, a theme modal, a `/theme` slash command, a `zephyrus-theme`
CLI, and two AI actions that could create and switch themes at runtime. All of it
is gone. Terminal — the black background, green foreground, monospaced Fira Code
aesthetic — is now the app's only appearance, and it is defined statically in
CSS.

## Why there is no `data-theme`

The old system was never a set of alternative stylesheets. It was a
name → colours lookup table. Sixteen presets each mapped a theme name to a
dictionary of CSS variable values, and `applyColors()` wrote those variables
inline onto `document.documentElement` as inline style properties. The `data-theme`
attribute existed only so the runtime could remember which key of that table was
active — it was a lookup key, not a style hook. No stylesheet ever branched on it
except one leftover `:root.light` block.

So once there is exactly one theme, the indirection has no consumer: a name that
maps to one set of colours is not a theme system, it is a constant with extra
steps. Collapsing to one theme therefore means deleting the name → colours layer
entirely and promoting `:root` in `static/style.css` to be the definition rather
than a default that a runtime layer could overwrite.

## The nine approved decisions

1. **Full removal, with survivors extracted.** The theme system is deleted rather
   than switched off, and anything genuinely useful inside it is relocated rather
   than lost with it.
2. **Keep only the `perlin-flow` background effect.** Of the background patterns,
   only perlin-flow earns its runtime cost; the rest are deleted.
3. **Relocate Font / Density / Text size into Settings → Appearance.** These were
   never colours, so they do not go away with the palette — they become ordinary
   preferences in the settings panel.
4. **Delete frosted glass.** The translucent/blur layer is cut rather than
   restyled; the one remaining consumer (`#theme-opacity-wrap`) had to keep its
   class name for the drag guard described under Traps.
5. **Leave existing `user_prefs.json` theme keys untouched.** No migration and no
   scrubbing. Persisted theme keys from older installs are simply ignored, which
   is cheaper and less destructive than rewriting users' saved prefs.
6. **Login gets static dots.** The login page keeps its plain background; it does
   not inherit the animated effect.
7. **Bake the Terminal tokens into `:root` and delete `:root.light`.** The values
   the `terminal` preset used to write at runtime are declared verbatim in the
   `:root` block, and the dead light-mode block is removed.
8. **Define `--accent-primary: var(--red)`.** `--accent-primary` had exactly one
   writer — the deleted theme JS. Without an explicit definition the ~124
   `var(--accent-primary, var(--red))` call sites and the drag/snap guide lines in
   `windowDrag.js` / `modalSnap.js` silently fall back to a hardcoded blue.
9. **Delete the theme CLI, the theme modal, the `/theme` command, and the AI
   `set_theme` / `create_theme` actions.** All four are entrypoints into a system
   that no longer exists.

## Palette

Terminal, as declared in the `:root` block of `static/style.css`.

| Token | Value | |
|---|---|---|
| `--bg` | `#000000` | |
| `--fg` | `#00ff41` | |
| `--panel` | `#0a0a0a` | |
| `--border` | `#003b00` | |
| `--red` | `#00ff41` | |
| `--green` | `#50fa7b` | |
| `--warn` | `#f0ad4e` | |
| `--hl-bg` | `#000000` | |
| `--hl-fg` | `#00ff41` | |
| `--hl-keyword` | `#f0e675` | |
| `--hl-string` | `#eac886` | |
| `--hl-comment` | `#0f8a30` | **deviation** |
| `--hl-function` | `#79b3ec` | |
| `--hl-number` | `#e29c78` | |
| `--hl-builtin` | `#70dbdb` | |
| `--hl-variable` | `#33cca6` | |
| `--hl-params` | `#2efa62` | |
| `--code-bg` | `#0a0a0a` | **deviation** |
| `--accent-primary` | `var(--red)` | |
| `--accent-warm` | `#d19a66` | |
| `--color-error` | `#ff4444` | |
| `--color-error-light` | `#ff6666` | |
| `--color-success` | `#4caf50` | |
| `--color-warning` | `#f0ad4e` | |
| `--color-danger` | `#c0392b` | |
| `--color-recording` | `#ff3b30` | |
| `--color-recording-hover` | `#d63031` | |
| `--color-muted` | `#888` | |
| `--color-muted-alt` | `#6b7280` | |
| `--color-accent` | `#00aaff` | |
| `--color-agent-active` | `#00ff00` | |
| `--color-brand-blue` | `#3b82f6` | |
| `--color-blind-orange` | `#ff9800` | |
| `--color-save-green` | `var(--color-success)` | |
| `--color-link-hover` | `#66c7ff` | |
| `--color-subheader` | `#6b8a94` | |
| `--select-bg` | `var(--bg)` | |
| `--select-fg` | `var(--fg)` | |
| `--select-option-bg` | `color-mix(in srgb, var(--panel) 74%, var(--bg))` | |
| `--select-option-fg` | `var(--fg)` | |
| `--select-option-active-bg` | `color-mix(in srgb, var(--red) 24%, var(--panel))` | |

### The two deliberate deviations

Both are places where the mechanically derived value from the old `terminal`
preset was rejected on purpose. Everything else in the table is the preset's own
numbers, copied verbatim.

**`--hl-comment` → `#0f8a30`, not `#0d7327`.** The derived value measured 3.50:1
against the black background, which fails WCAG AA for body text. `#0f8a30`
measures 4.70:1 and passes. The margin is only 0.2, so the value must not be
darkened further without re-measuring.

**`--code-bg` → `#0a0a0a`, not `#000000`.** The derivation collapsed code-block
background to exactly `--bg`, which erased the visual lift that code blocks had
under the old default — blocks became indistinguishable from the page.
`#0a0a0a` is reused from `--panel` so the block still reads as a raised surface.

## What was extracted rather than deleted

Three things in the deleted code were load-bearing and were relocated instead of
going with it:

- **`makeDraggable`'s perlin-flow background → `static/js/bgEffect.js`.** The
  background effect was implemented inside the theme module's drag helper rather
  than where it belonged. It now lives in its own module, which
  `index.html` loads directly, and which self-terminates its draw loop when the
  body class it keys off is removed.
- **Font / Density / Text-size logic → `static/js/settings.js`.** These are now
  Settings → Appearance preferences. The early-apply head script in `index.html`
  still reads the same keys so there is no flash of unstyled text on load.
- **`makeDraggable` → inlined as direct `makeWindowDraggable` calls at six call
  sites.** It was a thin wrapper whose only additions over `makeWindowDraggable`
  were a `theme-modal` branch that was already unreachable and a dead
  `skipSelector` clause. With both gone the wrapper had no reason to exist, so
  the six callers now call `makeWindowDraggable` directly.

## Traps hit during implementation

These are the non-obvious things. Each one cost real time or produced a wrong
result the first time.

- **`.theme-io-btn` styles three non-theme buttons.** The class is named after
  the theme picker but is also applied to the Memory Import/Export buttons and the
  Skill import-from-URL button. Deleting the theme CSS took their styling with
  it. The class name had to stay.
- **`.theme-opacity-wrap` is load-bearing for the Settings Peek drag guard.**
  The Settings Peek feature still keys a drag guard off that selector, so the
  wrapper could not be deleted even though frosted glass was.
- **`:root.light` was dead code, but test-enforced.** No runtime path could
  activate it once the theme layer went away, but `test_select_dropdown_theme_css.py`
  asserted on it. The block was easy to remove and the test was the only thing
  holding it up.
- **Persisted `open_theme` keybinds render the literal string `undefined` as an
  icon.** Users who had bound a shortcut to the theme modal have that binding
  stored in their prefs. Without explicit pruning of the keybind, the Shortcuts
  tab would try to render an icon for a now-nonexistent action and print the
  string `undefined`. This needs active pruning, not passive tolerance.
- **`windowDrag.js` hardcodes `enableFullscreen = false`,** which makes the
  `theme-modal` branch inside it dead code. Confirmed rather than assumed.
- **`research/panel.js`'s pane is not `.modal`-wrapped.** Calling
  `closest('.modal')` on it returns the parent overlay, so passing the pane as the
  drag host would have orphaned the saved-window-size keybind — the size would be
  written under the overlay's key instead of the pane's.

## Preserved surface that looks theme-related but is not

Left alone deliberately. These match on "theme" and should not be "cleaned up"
by a later pass:

- **The Settings Peek feature.** Not part of the theme system; it happens to
  share the `.theme-opacity-wrap` hook described above.
- **`.theme-io-btn`.** A shared button class with three non-theme users. The name
  is historical; the style is still needed.
- **`src/visual_report.py`'s standalone palette.** A separate HTML-report
  generator with its own `prefers-color-scheme` light/dark handling. It renders a
  document, not the app, and has no relationship to `static/style.css`.
- **Mermaid's own `theme: 'dark'` parameter.** Mermaid is a third-party library
  with its own internal theme concept. Passing it is not app theming.