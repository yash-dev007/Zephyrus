# Design System Foundation — Design Spec

**Date:** 2026-10-07
**Status:** Approved and implemented

## Goal

Give the single Ice / Arctic UI a foundation it can be extended from.

[The palette spec](2026-10-06-ice-arctic-redesign-design.md) fixed *colour*: which
hues exist, what they mean, and whether the contrast clears AA. It deliberately
did not touch the values that were already hardcoded in component rules — 1,392
`font-size` declarations, ~719 hairline borders, and eleven competing radii were
all still there when it landed. A correct palette rendered through an ad-hoc
scale is a correct palette at seven different type sizes.

This spec replaces those ad-hoc values with scales, and it replaces the flat
two-step surface model with a real elevation ladder so borders stop doing the
work hierarchy should be doing. Nothing about the app's structure, colour meaning,
or single-theme decision changes. `--bg` stays `#000000`. Green stays reserved
for added/success.

## Why the previous state had to change

The numbers are not a style preference. Each one is a mechanism by which the UI
became hard to change correctly.

| Measured at the start of this pass | Count | What it costs |
|---|---|---|
| `font-size` declarations | 1,416 | — |
| …spread over distinct `px` values | 27 | 6.5, 8.5, 9.75, 10.2, 10.5, 11.5, 12.5, 23, 28… most of them 1–3px off a neighbour |
| …at 9px or 10px | 336 | 24% of all text in the app, below any legibility floor and below the oldest supported browser zoom |
| `border: 1px solid` declarations | 719 | — |
| …shorthand `border: 1px solid` | 544 | the majority carried no other property, so the border *was* the component |
| distinct `border-radius` values | 17 (incl. `50%`, `999px`) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, plus the two non-`px` forms |
| `padding`/`margin`/`gap` values off the 4px grid | 22 | 1, 2, 3, 5, 6.9, 7, 8.5, 9, 10, 11, 13, 14, 17, 18, 22, 30, 38, 52, 58, 60 |

Three consequences.

**There was no base size, so nothing lined up.** With 27 sizes and no step
between them, two labels that were both supposed to be "secondary" could be 12px
and 13px with no reason. A component could not say "this is one step down from
the row label" because there was no row label. Every size was a local decision
that had to be re-decided everywhere.

**Depth was drawn rather than lit.** The old surface model was two steps —
`--panel` and `--panel-2` — and everything below them was `--bg`. A card on
`--bg` had no luminance difference to show, so the only way to make it read as a
card was `border: 1px solid`, and then another card needed a *different* border
to look different, and 719 of them did. A hairline on pure black reads as a drawn
outline: it tells you where the edge is, not that the surface is above you.

**Two surfaces cannot carry five levels of nesting.** The composer sits on the
transcript; a card sits in a modal; a popover sits in a popover. With two steps
below `--bg`, the fourth nested surface had no rung to take, so it either
re-used an existing one and became ambiguous, or invented a `color-mix` literal
and became a fifteenth surface nobody could reason about.

## The tokens

All declared in the `:root` block of `static/style.css`. Re-measure before
changing any value — the contrast figures quoted here are WCAG relative-luminance
against the surface named in each comment, computed, not estimated.

### Surface ladder

Elevation by luminance. Each step is measured lighter than the one below it.

| Token | Value | On `--bg` | Role |
|---|---|---|---|
| `--bg` | `#000000` | 1.00:1 | app canvas |
| `--surface-1` | `#0a0c0f` | 1.07:1 | sidebar, icon rail |
| `--surface-2` | `#111418` | 1.14:1 | cards, message bubbles |
| `--surface-3` | `#171b21` | 1.22:1 | hover, raised card |
| `--surface-4` | `#1e232b` | 1.33:1 | popovers, dropdowns, input wells |
| `--elevated` | `#252b34` | 1.47:1 | modals, composer, drag surfaces |

Steps stay between 1.07 and 1.47. Below ~1.06 the step is imperceptible — the
Terminal palette's `#0a0a0a` sat at 1.06:1, which is why it had no perceptible
surface at all. Above ~1.5 the surfaces stop reading as the same material. The
adjacent step ratios are 1.06, 1.07, 1.07, 1.10, 1.11: each rung is a visible
lift, and none of them is a jump.

`--panel` and `--panel-2` remain defined at their measured legacy values and are
still read by a shrinking set of call sites. They are superseded, not deleted:
`--panel` had ~199 code call sites, and remapping those by semantic role is a
judgement call per selector, not a token edit.

### Type scale

| Token | Value | Role |
|---|---|---|
| `--text-xs` | 11px | badges, keycaps, the smallest labels |
| `--text-sm` | 12px | secondary UI text, timestamps |
| `--text-base` | 13px | default UI body — buttons, nav rows, inputs |
| `--text-md` | 14px | chat prose, table cells |
| `--text-lg` | 16px | section titles |
| `--text-xl` | 20px | page titles |
| `--text-2xl` | 26px | the one display size |
| `--text-3xl` | 34px | hero numerals |

Replaces 27 off-grid values. Tracking collapses from 13 competing
`letter-spacing` values to `--tracking-normal` (0) and `--tracking-wide` (0.06em),
because only uppercase micro-labels take a non-zero value and they all want the
same one.

### Spacing, radius, elevation, motion

| Scale | Tokens |
|---|---|
| Spacing (4px grid) | `--space-1` 4 · `-2` 8 · `-3` 12 · `-4` 16 · `-5` 20 · `-6` 24 · `-8` 32 · `-10` 40 |
| Radius | `--radius-sm` 6 · `-md` 8 · `-lg` 12 · `-full` 999px |
| Elevation | `--shadow-sm` · `-md` · `-lg`, each two-layer |
| Motion | `--ease-out` `cubic-bezier(.22,.61,.36,1)` · `--dur-fast` 120ms · `--dur-base` 180ms · `--dur-slow` 280ms |

`--space-5` and `--space-6` exist because they were already in heavy use and fold
cleanly onto the grid. There is no 6px step because nothing on the ladder should
need a half-grid gap. `--radius-full` absorbs the pill and avatar-dot cases that
`999px` and `50%` were both being used for.

## The border decision

This is the decision the rest of the change follows from, and it is the one worth
arguing about.

WCAG 1.4.11 (Non-text Contrast) requires 3:1 for "the visual information required
to identify user interface components and states." That is a requirement about
**affordances**: the input you can click, the checkbox you can tick, the track
that tells you a switch exists. It is not a requirement about dividers, because a
divider carries no information you would otherwise miss.

Before this pass, one token had to be both. `--border` was `#525d66`, and it was
the only edge the app had. So it had to clear 3:1 for control affordances. It did
— on pure black, where it measured 3.12:1.

Then the surface ladder moved inputs off the canvas. An input now sits on
`--surface-4`; a toggle track inside a modal sits on `--elevated`. A value tuned
on pure black no longer describes the surface it lands on:

| Against | `--bg` | `--surface-1` | `--surface-2` | `--surface-3` | `--surface-4` | `--elevated` |
|---|---|---|---|---|---|---|
| old `--border` `#525d66` | **3.12** | 2.91 | 2.74 | 2.56 | 2.34 | 2.11 |

It clears 3:1 on one of six rungs and fails on five. Every input on a raised
surface was below the bar, and the failure was invisible in review because the
one place anyone checked — pure black — passed.

The obvious fix is to lighten `--border` until it clears 3:1 on `--elevated`. That
value would be roughly `#697782`, and here is what it costs: measured against
`--bg` it is 4.56:1, against `--surface-1` 4.25:1. A divider is, by definition, a
low-contrast line that separates two things of the same weight. At 4.5:1 on the
darkest surface, every divider in the app becomes a drawn outline again — the
exact failure the surface ladder exists to fix — and the eye reads the rules
before the content. WCAG 1.4.11 does not ask for that; the app would be paying a
contrast tax to satisfy a requirement it was never subject to.

So there are two weights, and the point of each is to be *out of range* for the
other's job:

| Token | Value | Across the ladder | What it is for |
|---|---|---|---|
| `--border` | `#2f3841` | 1.20–1.76:1 | dividers inside one surface; card edges against a neighbour at the same level. Deliberately below 3:1. |
| `--border-subtle` | `#242c34` | 1.01–1.48:1 | internal separators between rows of the same component |
| `--border-control` | `#697782` | 3.10–4.56:1 | anything whose boundary *is* the affordance: inputs, selects, toggle tracks, checkboxes, focusable wells |

`--border-control` is the only weight validated against 1.4.11, and it is
validated against the *lightest* surface it can land on, not against `--bg` —
4.56 / 4.25 / 4.01 / 3.75 / 3.43 / **3.10**:1 from `--bg` up to `--elevated`.
3.10:1 is the worst case and it clears.

`--border` keeps its name and roughly its value, so its several hundred existing
call sites keep working unchanged and the blast radius is zero. The control
affordances were re-pointed to `--border-control` in the component phase that
followed.

The practical rule for a contributor is one sentence: **if removing the edge would
make the control harder to identify, it is `--border-control`; if it would only
make the layout harder to parse, it is `--border`.** That is the whole 1.4.11
question, and it is answerable without a contrast table.

## Elevation: why the shadow has two layers

`--shadow-sm`, `-md` and `-lg` are each a pair:

```css
--shadow-md: 0 4px 12px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04);
```

The dark drop does the separation. The 1px light inset does something the drop
cannot, and on this palette it is not decoration.

`rgba(0,0,0,·)` on `#000000` is invisible. It has always been invisible. A shadow
that falls on the canvas adds no pixels — the canvas is already the darkest thing
on screen — so a lone drop shadow on a pure-black background produces a floating
panel with no visible top boundary at all. It reads as the background having got
slightly darker above the element, which is the opposite of an elevation cue.

The inset is a `rgba(255,255,255,·)` edge at 1px scale, and it is what actually
draws the top of the surface. That is the whole reason it is there: the faint
white line says *lit from above*, and lighting is how the eye reads height. On a
light theme the equivalent cue comes free from the drop shadow, which is why
`box-shadow: 0 1px 2px rgba(0,0,0,.1)` is a complete elevation on white and is
invisible on black.

Both layers are the same two-pixel budget, so the change costs nothing visually
where the drop was already working. A single-layer `box-shadow` in a new rule is
a bug: on this canvas it silently loses half its job.

## The typography split

Fira Code is not being removed. It is being *scoped*.

**Kept on `--font-content`:** the chat transcript, code and code blocks, diffs,
logs and tool output, paths, ids, hex and keycaps, and inputs. The reason is
structural, not aesthetic — monospace preserves the whitespace and indentation
structure of generated output, and it makes a long streamed response scannable
because you are reading aligned columns rather than a ragged wall of proportional
text. It also keeps the app's transcript visually distinct from the chrome
around it, which is a signal that survives at a glance.

**Moved to `--font-ui`:** navigation, buttons, labels, and panel chrome. Proportional
text is measurably more scannable at 11–13px, because word-shape recognition beats
reading character cells, and every one of those surfaces is exactly that size.
Putting 13px labels in monospace is paying the readability cost for nothing —
there is no code structure to preserve in a button label.

The split is what makes the product read as an application rather than a shell.
Before it, everything was monospace at the same size, which is a coherent choice
for a terminal emulator and a poor one for a settings panel.

`--font-family` is **not** redefined in `:root`. It has no definition in the
stylesheet at all — it is written at runtime by the font preference
(`static/js/settings.js`, `static/index.html:30`) onto the document element and
read at `body`. Defining it in `:root` would repurpose a runtime-owned property
into a stylesheet-owned one and silently break the user's pick. Instead, `body`
derives both tokens from it:

```css
--font-ui: var(--font-family, var(--font-sans));
--font-content: var(--font-family, var(--font-mono));
```

With no pick, `--font-ui` falls back to the proportional sans and `--font-content`
falls back to Fira Code. With a pick, both resolve to the user's stack, exactly as
the pre-existing `body` rule already did. The user still wins; the split is the
default, not an override.

## Judgement calls made during implementation

Five places where the rule and the specific component disagreed, and the rule
lost. Each is recorded because the next contributor will hit it again.

**Sub-11px decorative glyphs stayed small.** Thirteen rules remain below
`--text-xs`: `.note-cl-grip`, `.search-fb-grip`, `.item-drag-handle`,
`.cal-dot-more`, `.hwfit-fit-dot`, `.hwfit-dl-dot`, `.gallery-aitag-mark`,
`.doc-fontsize-levels i`, the note draw size/shape badges, the `.ge-topbar`
attribute selector, and one `.ge-transform-spin button`. Every one is a drag grip,
a status dot, a spinner face, or a superscript badge — a glyph, not prose. Raising
them to 11px would make a 14px grip box overflow its hit target and would make the
spinner arc visibly lumpy. The rule that survives is the narrower one: sub-11px is
for decoration, never for readable text.

**Density overrides stayed in `rem`.** `:root.density-compact` sets a 13px root and
`density-spacious` a 16px one, then moves a handful of things with `rem`. Those
handfuls kept `rem` because density only changes the root `font-size` — a `px`
value is unreachable by the density setting by construction. The
`.list-item span` catch-all is the clearest case: session titles arrive as a bare
`<span>`, so that rule is the only thing sizing them, and at `rem` the Density
control reaches them. Its comment records the same reasoning. Everywhere else the
scales won.

**Calendar year cells were checked in a browser, not assumed.** `.cal-year-cell` is
a 7-column grid of single digits with a 14px `min-height`, and it is the tightest
legible case in the app. Reading the CSS alone cannot tell you whether 11px digits
in a 14px row clip, collide, or read as noise; the grid was rendered and looked at.
The outcome is that they sit on `--text-xs` and stay quiet.

**The document font-size ladder is deliberately off-scale.** `.doc-font-m` is 13px,
`.doc-font-l` is 15px, and the email rich-body equivalents are 15px/17px — none of
them a `--text-*` step. That is right: a document editor simulates a document, and
a document's type size is a property of the document, not of the app's chrome. The
same reasoning keeps the calendar hero clock at 56px/44px and the gallery album
placeholder at 40px rather than at `--text-3xl`. The scale governs app text; a
few surfaces legitimately size their own content.

**`--text-3xl` was added above `--text-2xl` for the calendar hero clock.** At 26px
the 56px clock had no step to reach for and was being set from a literal, and the
album placeholder lost over half its height at 26px. Rather than widen
`--text-2xl` (which is doing real work as the one display size), the scale gained
a rung above it. This is the one place the type scale was extended instead of
folded.

## What changed in the shell

The elevation model had to prove itself on the surfaces users touch most, so it was
applied there first.

**The sidebar and icon rail are `--surface-1` planes with no hairline.** The sidebar
used to carry two competing rules — `border-right: 1px solid var(--border)` and then
a full `border: 1px solid color-mix(--fg 11%)`, the later one winning — so the pane
was separated by a drawn outline at 3.12:1. The rail did the same. Both now sit on
`--surface-1` at 1.07:1 with no edge rule; the luminance does the separating.

**Rows have nothing at rest.** A `.list-item` has no border and no resting fill. It
gains `--surface-2` on hover, and the selected row gains `--surface-3` plus a 2px
`--accent` left indicator — the pattern from Linear and Vercel: nothing, one step on
hover, two plus an accent rule when selected. The old hover painted an 8% accent wash
and a `border-color` that `.list-item`'s own `border: none` discarded, so all that
survived was a barely-there blue tint.

**Section labels are quiet.** Uppercase `--text-xs` in `--fg-subtle` at
`--tracking-wide`. At 6.41:1 on the `--surface-1` sidebar that is a clear step below
the row labels underneath, so the label recedes instead of competing. `.section`
itself is `border: none; background: none; box-shadow: none` — it is a heading, not
a box.

**AI bubbles are `--surface-2` with no border** and lift to `--surface-3` on hover,
so the message you are reading separates from the rest of the thread. The user
bubble is a 6% `--accent` wash over `--surface-3` rather than a saturated fill —
"yours", but the same material. **The composer is the one element in the app that is
unambiguously in front of the transcript**, so it is the one that gets real
elevation: `--elevated` at 1.47:1 with `--shadow-md`, and an inset `--surface-4`
input well so the typing area sits in a recess instead of floating on the face. Its
old `1px` hairline is gone.

## Preserved on purpose

**Pure black substrate.** `--bg` stays `#000000`. Every contrast figure in this spec
is measured against it, and it is what makes the inset-edge argument above necessary
in the first place.

**The single-theme decision.** No theme system, no `data-theme`, no presets. All of
this is expressed as `:root` custom properties that can be edited in one place.

**Fira Code as the content face.** Scoped, not retired. See the split above.

**The token architecture.** This is why the change was a `:root` edit plus a
judgement pass rather than a rewrite: component rules read tokens rather than naming
values, so most of the work was moving call sites onto existing names.

**Reduced-motion as a first-class gate.** The consolidated
`prefers-reduced-motion: reduce` block zeroes duration and keeps the end state — the
selected-row accent rule, the checked toggle, the composer's elevation, the active
rail state all stay exactly where they are, so nothing becomes harder to see
because motion is off.

## Known follow-ups

Left in place deliberately. Each is measured and documented rather than silently
tolerated.

- **`--task-paused-badge` reads an undefined `--orange`.** Four rules in the tasks
  and cookbook area use `var(--orange, #ffb86c)` and `var(--orange, #ff9800)`, but
  `--orange` is defined nowhere in `:root`. They render the hardcoded fallback, which
  is an off-palette orange in both cases. It needs either a `--warn`-derived token
  (`.cookbook-task-stopping` is genuinely a warning state) or a re-point to an
  existing one. Do not add a new orange to the palette to fix it.
- **A Tailwind hex set sits outside the palette in `.email-tag-*`.** The category
  chips carry raw Tailwind values — `#60a5fa`, `#4ade80`, `#facc15`, `#fb923c`,
  `#a78bfa`, `#94a3b8`, `#f472b6`, `#f87171`, `#f0ad4e`, `#38bdf8`, `#ec4899` — as
  both a `rgba(…, 0.22)` background and a solid text colour. Eleven colours that are
  not in the palette, and none of them measured against the surface they land on.
  `.email-tag-urgent` is the exception: it already resolves through `--danger`.
- **`--fg-subtle` is 4.67:1 on the lightest surface.** It clears AA, but with almost
  no headroom — `--elevated` is its worst case, and it is 6.88:1 on `--bg`. Any new
  use of it on a raised surface needs re-measuring before it ships.
- **Two toggle-track families are split.** `.toggle-slider` and `.admin-slider` use
  `--border-control` (4.56:1 on `--bg`, correct for 1.4.11). The older `.toggle .slider`
  and `.vis-switch` still paint their track with `var(--border)` at 1.76:1, and the
  comment above `.toggle .slider` still quotes the old `#525d66` figure of 3.12:1.
  Both families should be on `--border-control`; the inline comments need updating
  with them.
- **Several scale tokens have no consumers yet.** `--border-subtle`, `--shadow-sm`,
  `--text-3xl`, `--space-5`, `--space-6`, `--space-8`, `--space-10` and
  `--tracking-normal` are defined and currently unread. That is deliberate — a scale
  is allowed to have rungs nothing needs yet — but it means the ladder is not
  complete, and the remaining off-scale literals (17 `border-radius` values, 691
  hairline borders, the sub-11px glyphs above) are the migration work still
  outstanding.