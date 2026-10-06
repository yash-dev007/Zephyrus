# Ice / Arctic Redesign — Design Spec

**Date:** 2026-10-06
**Status:** Approved and implemented

## Goal

Replace the green Terminal palette with a black "Ice / Arctic" terminal look.
Pure black surfaces, neutral grey-blue text, a single ice-blue accent, and no
green anywhere in the chrome or the body text.

Zephyrus has exactly one UI, which [the previous spec made static and
non-negotiable](2026-10-05-terminal-only-theme-design.md). That spec fixed *how
many* themes there are; it never claimed the surviving palette was correct. An
audit of the `:root` block in `static/style.css` found that the green palette
was not merely a matter of taste — it was rendering error states as successes,
inverting diff highlighting, and producing text that failed WCAG AA in 93
places. This redesign replaces the values in `:root` and nothing else. The
single-theme decision stands.

## Why the old palette had to go

Terminal's `--fg` was `#00ff41`: HSV hue 135.3°, saturation 1.00, value 1.00.
That is not a lot of information. It says "this text is terminal output" and
nothing else.

The rest of the palette did not help, because it sat on the same hue. `--border`
was `#003b00`, hue 120°, saturation 1.00. The scrollbar and the active-nav tint
were drawn from the same green. And the accent *role* — the one thing that was
supposed to mean "this is interactive" — was filled by `--red`, which was also
`#00ff41`, because `--accent` was referenced everywhere and defined nowhere.
Body text, borders, scrollbar and accent therefore all lived within about 15°
of hue at full saturation.

| Old token | Value | Hue | Sat |
|---|---|---|---|
| `--fg` | `#00ff41` | 135.3° | 1.00 |
| `--hl-fg` | `#00ff41` | 135.3° | 1.00 |
| `--red` (the accent role) | `#00ff41` | 135.3° | 1.00 |
| `--border` | `#003b00` | 120.0° | 1.00 |
| `--color-accent` | `#00aaff` | 200.0° | 1.00 |

Two consequences. There was **no chromatic rest**: every saturated pixel on
screen was the same green, so the eye had nothing to rest on and nothing to
land on. And there was **no typographic hierarchy**: `--fg-strong`, `--fg-muted`
and `--fg-subtle` did not exist, because a single token cannot express four
levels of emphasis. Headings, body text and metadata were all the same colour at
the same weight.

The audit also compared `--fg` against what terminals actually ship. `#00ff41`
has an OKLab chroma of 0.278 — roughly 50× the chroma of a typical real
terminal default foreground, which is a near-neutral light grey. Terminal did
not look like other terminals. It looked like a phosphor.

Ice / Arctic keeps the substrate and the type discipline and drops the chroma.
`--fg` lands at `#c9d4dc`: same lightness as `#00ff41` (OKLab L 0.864 vs
0.869), one-seventeenth the chroma, hue rotated out of the green band entirely.
The accent keeps enough chroma to be an accent (C 0.101) and nothing more.

## The correctness bugs the audit found

These are the stronger argument for the change. A palette that reads as dated is
a preference; a palette where the delete button is green is a defect.

**`--red` held green, so every danger selector rendered green.** `--red` was the
deprecated alias for the accent, and the accent was `#00ff41`. Roughly 129
selectors whose names contain `danger`, `error` or `delete` were therefore
painted in the success hue. Python tracebacks in `.code-runner-error` were
green. Destructive buttons were green. A user reading a failed command could not
distinguish it from a successful one by colour at all.

**The highlighted diff was inverted.** Deletions took the green and additions
took a tan. Diff highlighting is one of the few places in the app where colour
carries meaning that the user cannot infer from context, and it was pointing the
wrong way.

**`--accent` was referenced 718 times and defined nowhere.** A `var(--accent)`
with no fallback and no definition is invalid at computed-value time, so those
declarations rendered nothing. `mark.doc-find-mark` — find-in-document — was
painting black text on a transparent background: 1.0:1, i.e. invisible. The
same gap left completed task-list checkboxes with no fill and the calendar "+"
with no disc behind it. Everything else that read it fell back to `var(--red)`,
which is why the "accent" was green.

**93 text sites failed WCAG AA.** The pattern was
`color: color-mix(in srgb, var(--fg) 60%, transparent)` — already marginal
against `#00ff41` because the mix halves the alpha, and then stacked with an
`opacity` on the same element, which multiplies again. Two dimming mechanisms
compounding, on a foreground colour that was already the only thing on screen.

**The unchecked toggle was invisible.** Its knob sat on its track at 1.00:1.
Because the knob is drawn and nothing else is, the control looked checked when
unchecked, and the state could not be read at all.

Every one of these is downstream of the same root cause: a single saturated hue
forced into roles it cannot carry, with tokens renamed but never re-pointed.

## The palette

As declared in the `:root` block of `static/style.css`. Contrast is WCAG
relative-luminance against `--bg` (`#000000`); re-measure before changing any
value.

### Surfaces and text

| Token | Value | On `--bg` | |
|---|---|---|---|
| `--bg` | `#000000` | — | pure black substrate |
| `--panel` | `#141c23` | 1.22:1 | Terminal's `#0a0a0a` was 1.06:1, i.e. no perceptible surface; real terminals land 1.26–1.31:1 |
| `--panel-2` | `#1a2229` | 1.30:1 | second tier for nested surfaces (card in card, composer in modal) |
| `--fg` | `#c9d4dc` | 13.93:1 | body text |
| `--fg-strong` | `#eaf2f8` | 18.55:1 | headings, emphasis |
| `--fg-muted` | `#9aa5ad` | 8.36:1 | secondary text, labels |
| `--fg-subtle` | `#7d8890` | 5.80:1 | the floor for muted text |

### Status and accent

| Token | Value | On `--bg` | |
|---|---|---|---|
| `--accent` | `#7cc4f5` | 11.07:1 | the primary accent: selection, focus, primary actions |
| `--danger` | `#ff5f56` | 7.02:1 | errors, destructive actions, deletions |
| `--success` | `#3ddc84` | 11.77:1 | the only green in the palette; additions and success |
| `--warn` | `#fbbf24` | 12.58:1 | warnings |

### Deprecated aliases

| Token | Value | |
|---|---|---|
| `--red` | `var(--danger)` | historical name, retained because 1,171 rules still read it |
| `--green` | `var(--success)` | retained because it is only ever read for added/success semantics |

New rules use `--danger` and `--success`.

### Code and syntax

| Token | Value | On `--hl-bg` | Hue |
|---|---|---|---|
| `--code-bg` | `#1a2229` | — | reuses the `--panel-2` tier; Terminal collapsed this to `--bg` |
| `--hl-bg` | `var(--code-bg)` | — | |
| `--hl-fg` | `var(--fg)` | 10.68:1 | unhighlighted code is body text, not a hue of its own |
| `--hl-keyword` | `#efafff` | 9.39:1 | 288.0° |
| `--hl-string` | `#d0c871` | 9.34:1 | 54.9° |
| `--hl-number` | `#e78f69` | 6.54:1 | 18.1° |
| `--hl-function` | `#a3a1ec` | 6.80:1 | 241.6° |
| `--hl-builtin` | `#f088bc` | 6.86:1 | 330.0° |
| `--hl-variable` | `#92c272` | 7.80:1 | 96.0° |
| `--hl-params` | `#74aa7f` | 5.98:1 | 132.2° |
| `--hl-comment` | `#659189` | 4.57:1 | 169.1° |
| `--hl-punct` | `#68757e` | 3.40:1 | 204.5° |

## The seven rules

These are the constraints the palette is built to satisfy. A future palette that
breaks one of them reintroduces a bug the redesign already fixed.

1. **Danger and error never share a token with the accent.** Red means red.
   Never put the accent value in `--red` or `--danger`, and never read a
   danger-intent selector from a token that is also the accent. This is the rule
   whose violation produced ~129 green error selectors.
2. **Every text token clears 4.5:1 (WCAG AA) against the surface it actually
   renders on** — `--bg`, `--panel` or `--panel-2`, not just `--bg`. A token
   that passes on black and fails on a card is a token that will fail somewhere
   in the app. Measure it; do not eyeball it.
3. **`--border` clears 3:1 (WCAG 1.4.11) for control edges.** It is the only
   affordance inputs, table cells and bubbles have, so it has to carry that job
   on its own.
4. **Adjacent `--hl-*` tokens sit at least 30° apart in hue** (and at least
   0.08 OKLab delta E). Nine of the ten syntax tokens clear this pairwise in
   declaration order; the tightest adjacent pair is `--hl-variable` /
   `--hl-params` at 36.2° / 0.085. The single exception is `--hl-punct`, which
   deliberately holds `--hl-fg`'s hue and separates by lightness instead
   (3.40:1 against `--hl-fg`'s 10.68:1), because punctuation is neutral structure
   and should not outrank comments the way the old `.hljs-operator` rule did.
5. **Decoration is never load-bearing for legibility.** An unchecked toggle
   knob, a spinner arc, a find-in-document highlight, a scrollbar thumb — each
   has to be visible against its own background without help from anything
   else. If removing a colour would remove information, the colour is not
   decoration.
6. **Dim text with the ramp, not with alpha.** Use `--fg-muted` or
   `--fg-subtle` instead of `color-mix(in srgb, var(--fg) N%, transparent)`, and
   never stack an `opacity` on an already-mixed colour. Alpha multiplies, so two
   dimming mechanisms compound into a third, unintended contrast ratio.
7. **A hue carries meaning only where it is defined.** One accent hue for
   interaction (selection, focus, primary action), red/green/amber for status
   only, and a separate ramp for syntax. If a rule needs a colour that no
   category owns, the rule is asking for a new token — not a new literal.

## Preserved on purpose

**Pure black substrate.** `--bg` stays `#000000`. It is the one decision from
Terminal that was right, and it is also the substrate every contrast figure in
this spec is measured against.

**Monospace Fira Code throughout.** This is load-bearing, not nostalgic. A
uniform advance width makes generated prose structurally harder to confuse with
your own input: an LLM response and a keystroke do not have different letterforms
to tell them apart, so the boundary has to come from something else — the bubble
background, the role label, the weight. Changing the primary UI font would
remove one of the few remaining signals about who wrote a given line.

**The single-accent discipline.** Terminal had exactly one accent role too. The
redesign did not add accents; it gave the one accent an honest colour and stopped
it doubling as the danger colour.

**The token architecture itself.** This is why the redesign was a `:root` edit
and not a sweep. Component rules read tokens rather than naming colours in the
property, so the file had 2,800+ token call sites at audit time and 5,469
`var(--…)` reads today; the literals that remain are `var(--token, #literal)`
fallback tails plus the `@media print` block. Every one of the six bugs above was
fixed by changing a value in `:root`, with no component edit except where the
*meaning* of a token changed.

**The `--red` deprecated-alias strategy.** `--red` now resolves to `--danger`
rather than being renamed. Renaming it would have been the tidier diff and would
also have turned 1,171 rules red simultaneously, including every rule that reads
it for a non-danger reason — the active-nav tint, focus rings, the select
highlight. Aliasing keeps the blast radius at zero and leaves a grep-able marker
(`var(--red)`) for the migration. It is a deliberate staging decision, not a
cleanup shortcut.

## Known follow-ups

Left in place deliberately. Each one is measured and documented rather than
silently tolerated.

- **`--fg-subtle` is 4.44:1 on `--panel-2`**, just under the 4.5:1 AA bar. It
  clears comfortably on `--bg` (5.80:1) and on `--panel` (4.75:1). It is used
  only for text that is deliberately subordinate, but any future use of it on a
  nested surface needs re-measuring first.
- **`--border` clears 3:1 on `--bg` (3.12:1) but not on the raised surfaces** —
  2.55:1 on `--panel` and 2.39:1 on `--panel-2`. Controls that render on a
  panel rely on the accent focus ring for their edge, so any such control needs
  a focus state that reads without hover.
- **`--accent` is still undefined in some component-local chains.** Rules such as
  `var(--accent, var(--red))` now fall back to `--danger`, because the fallback
  tail still names the deprecated alias. `--accent` itself is defined in `:root`
  and those chains resolve correctly, but the fallbacks should be rewritten to
  drop the `--red` step.
- **The animated background falls back to `--fg` for its particle colour**, so
  the particles are now neutral grey rather than tinted. It reads correctly but
  it was never an intentional choice, and a dedicated low-alpha token would make
  the effect tunable independently of body text.
