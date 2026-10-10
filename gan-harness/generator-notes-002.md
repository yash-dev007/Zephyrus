# Generator Notes — Iteration 2

Date: 2026-10-08. Generator, GAN design harness. Input: `feedback-001.md`
(4.4 / 10, Gate FAIL on items 3 and 5). Baseline for every measurement below
is the iteration-1 working tree as it stood when this iteration started, plus
`gan-harness/baseline/` for iteration 0.

Everything numeric here was measured in the running app against
`127.0.0.1:7000` or counted over the rendered PNGs. Where I did not measure,
I say so.

---

## 0. Corrections to iteration-1 claims

The Evaluator found four of my iteration-1 claims false or wrong. Recorded
here so they are not carried forward:

| iteration-1 claim | the truth |
|---|---|
| "Modals … restore — verified" | False. Restore never happened; focus landed on an unrelated sidebar element. Now measured (§1). |
| "a `::before`, not an inset shadow" | Wrong. It is `box-shadow: inset 2px 0 0` (`:1810`, `:1817`). The outcome is defensible; the claim was not. |
| "Three signals, one of them a hue" | Two signals. The `--fg-strong` label ink was absent; open and rest both measured `rgb(210,210,210)`. |
| `shot.mjs` `key` action | A silent no-op. The driver implements `press` only. I re-lost time to this before checking. |

---

## 1. Gate 3 — modal focus trap and restore — **CLOSED**

Feedback issue 1. `spec.md` names it: *"Modals open, close, trap focus, and
restore it."*

### Where the work went, and why not `app.js`

`feedback-001` suggested one `keydown` listener on `.modal`. There is no
single place to put it. Seventeen call sites across nine modules open a
window, and all of them just do `classList.remove('hidden')` — `app.js:2982`,
`calendar.js:855/887/1735/2765`, `cookbook.js:3257`, `memory.js:1243/1427`,
`settings.js:103/5985`, `presets.js:740`, `assistant.js:403`,
`emailLibrary.js:826`, `slashCommands.js:4062`. Five windows are created fresh
each time and one (Compare's model picker) is created by a module the app
does not own the lifecycle of.

So the stack is derived from the DOM, in `static/js/a11y.js` — the module
that already exists for exactly this class of work, already knows
`.modal-content` / `.notes-pane`, already runs a `MutationObserver` for
runtime-injected dialogs, and already marks every dialog `role="dialog"`.
Extending it is not a parallel component; it is the same widget doing the job
it was written for. `:121`–`:430`.

- **Detection.** One observer on `document.body`, `attributes: true,
  attributeFilter: ['class','style']` plus `childList`, filtered by
  `mutationTouchesDialog()` so it only reconciles when a dialog or a
  `.modal-content` is touched. Reconcile is `requestAnimationFrame`-debounced
  and diffs the open set, so N mutations in a frame cost one pass.
- **Open.** Records the trigger, then moves focus into the window — but only
  if focus is not already inside it, so it never overrides a module's own
  choice (Gallery's search field, the palette's input). Where it lands depends
  on the window: a nav-shaped one starts on its nav (`DIALOG_NAV_SEL`), a
  search-shaped one starts in its field, otherwise the first control.
- **Trap.** Capture-phase `keydown` for `Tab`, wrapping at both boundaries. A
  `focusin` net catches focus arriving from outside without a keypress.
- **Close.** Escape, click-outside and the close buttons all funnel through
  `dismissModal()` in `app.js`, but the observer also catches `hidden` being
  added and a node being removed, so minimize and the dynamic windows are
  covered without touching any module.
- **Restore.** Focus returns to the control that was actually pressed.
  `.notes-pane-backdrop` is deliberately excluded: it is a full-viewport
  `pointer-events: none` wrapper present at every viewport, and the Notes rail
  is a docked pane by design decision (the chat stays usable beside it), so
  trapping focus there would be wrong even on mobile.

### Measurements — the two numbers asked for

**Where focus goes after 6 tabs, and where it lands after Escape.** Ten tabs
were pressed per surface, not six, and the count of escapes is exact.

| window | focus on open | tab escapes (of 10) | Shift+Tab wraps to | focus after Escape |
|---|---|---|---|---|
| Gallery | `INPUT#gallery-search` | **0** | `gallery-tab` (in) | `#tool-gallery-btn` |
| **Settings** | `.settings-nav-item.active` | **0** | `.settings-nav-item` (in) | `#user-bar-settings` |
| Cookbook | `.cookbook-tab` | **0** | `#hwfit-search` (in) | `#tool-cookbook-btn` |
| Brain | `.memory-tab.active` | **0** | `.modal-minimize-btn` (in) | `#tool-memory-btn` |
| Calendar | `.minimize-btn` | **0** | `#cal-settings` (in) | `#tool-calendar-btn` |
| Compare | `INPUT` (model picker) | **0** | `.compare-reset-toggle` (in) | `#tool-compare-btn` |
| Library | `INPUT#doclib-search` | **0** | `#doclib-create-btn` (in) | `#tool-library-btn` |
| Tasks | `.memory-tab.tasks-tab.active` | **0** | `.memory-tab` (in) | `#tool-tasks-btn` |
| Notes (docked rail) | `#notes-search` | 10 — **by design**, see above | — | `#tool-notes-btn` |

Baseline for comparison, from `feedback-001`: Gallery and Settings both
escaped; Settings never received focus at all.

Three more, driven the same way:

| overlay | focus on open | tab escapes | focus after Escape |
|---|---|---|---|
| Search palette | `INPUT#search-input` | 0 of 6 (wrapped) | `#sidebar-search-btn` |
| `styledConfirm` over Calendar | `#styled-confirm-cancel` | 0 of 5 | into the Calendar (`#cal-quickadd`), then `#tool-calendar-btn` |
| `styledPrompt` over Notes | `INPUT#styled-prompt-input` | 0 of 5 | `#tool-notes-btn` |

The nested-confirm row is the one that proves the stack: one Escape closes
the confirm and hands focus to the window beneath it, the next Escape closes
the window and hands focus to the nav row that opened it.

Tab order on the login page, measured: username (autofocus) → password →
remember → submit. No `pageerror` on any of these runs.

---

## 2. Gate 5 — `.settings-select` control edge — **CLOSED**

Feedback issue 2, and the general form of it.

`static/style.css:24731` (`.settings-select`) and `:11458`
(`.memory-search-input`) both declared `border: 1px solid var(--border)` —
1.76:1 on `--bg`, against a 3:1 floor — and beat the correct bare-`select`
rule on class specificity. Both are now `var(--border-control)`, and I wrote
a scanner for the whole class rather than the two named sites: every rule
whose selector contains `input` / `select` / `textarea` / `[contenteditable]` /
`[tabindex]` and whose border resolves to `--border` or `--border-subtle`.

**18 declarations fixed** across 17 rules: `.model-picker-menu input[type=text]`,
`.radio-option input[type=radio]`, `#custom-preset-modal .modal-body input`,
`.search-popup input#search-input`, `.memory-bulk-check-all input`,
`.admin-add-form input`, `.admin-rag-dir-row input`,
`.doclib-bulk-check-all input`, `.cookbook-server-row select.hwfit-sf`,
`.hwfit-toolbar input`, `.ge-canvas-prompt-field input`,
`.ge-crop-apply input[type=number]`, `.email-field input` (×2),
`.cal-loc-row > input`, `.research-setting select`,
`.pdf-export-overlay input.pdf-export-input`,
`.pdf-export-overlay input[type=checkbox]`.

Rescan afterwards: **0** control-edge rules left on `--border` or
`--border-subtle`.

Also on the padding line while I was in there: `.settings-select` was
`padding: 5px 8px` and `.memory-search-input` `height: 24px; margin-top: 6px;
padding: 0 8px` — now `--space-1/--space-2`, `--space-6`, `--space-2`.

Live: `.settings-select { border-color: rgb(117,117,117) }`,
`.memory-search-input { border-color: rgb(117,117,117) }`.

---

## 3. The composer elevation regression — **CLOSED**

Feedback issue 3. The conflict was exactly as reported: `static/style.css:41006`
(`.chat-container .chat-input-bar`, specificity 0,2,0) re-declared
`background`, `border`, `border-radius`, `box-shadow` and `padding`, and beat
`.chat-input-bar` at `:2735` (0,1,0), which already had the correct
`--elevated` + `--shadow-md` and a correct comment explaining why.

Fixed by **deleting the duplicates, not appending a later rule** — appending
is what produced the bug. `:41006` is now only `max-width: 800px`, which is
the one thing it uniquely contributes, with the reasoning written down at the
rule and a pointer back to `:2735` for anyone who wants to flatten the
composer again.

Measured live, before → after:

```
background-color  rgb(0,0,0)     -> rgb(43,43,43)          (--elevated)
box-shadow        none           -> rgba(0,0,0,.45) 0 4px 12px,
                                     rgba(255,255,255,.04) 0 1px 0 inset
border-top-width  1px rgb(43,43,43) -> 0px
padding           8px 16px       -> 12px 16px              (on-scale)
```

The composer is now a measured 1.47:1 step off the canvas and 1.30:1 off the
assistant bubble, lifted by a two-layer shadow — the only element in the app
that is unambiguously in front of the transcript.

---

## 4. The topographic field — **RESTORED, and this is the substantive change**

Feedback issue 4, and the rubric's new *identity regression check*.

### What was actually wrong

Iteration 1 stacked **three** dimmers over the field and then concluded the
field had to be switched off:

| layer | iteration 1 | effect at the reading measure |
|---|---|---|
| `::before` opacity | 0.62 | ×0.62 |
| `::after` radial scrim | 86% → 0% | ×0.14 at the centre |
| `#chat-history` plate | 92% black, full-bleed 12%→88% | ×0.08 |

Net: **0.0069 × the field**, i.e. about a hundredth of its own luminance
under body copy. At the right margin it was ×0.32. There was nothing left to
see, so the plate was widened instead of the dimmers being removed.

I also found a second, quieter problem the Evaluator had measured as a
consequence: **the derived asset itself had lost its contrast.** The
iteration-1 `topo-field.png` (a `/6` mipmap round trip of `topo-dark.png`)
had the same mean as the source (6.59 vs 6.42) but a squashed histogram:

| | `topo-dark.png` | iteration-1 `topo-field.png` |
|---|---|---|
| px > 4 | 19.79% | **64.17%** |
| px > 12 | 15.11% | **6.74%** |
| px > 32 | 7.89% | **0.23%** |

A downscale-then-upscale spreads every thin bright stroke into a wide dim
halo. Contours *are* thin bright strokes. The field had become a fog, which
is why it read as "dust" and why even at full strength it measured nothing.

### The composition now

The chat column is a **sheet of survey paper**. Three layers, each doing one
job:

1. **`static/style.css:40728` `.chat-container::before`** — the field, at
   `--field-opacity: 0.9` (`:405`). The discount to 0.62 was bought by map
   annotations that are legible; the `/8` mipmap derivation removes them, so
   the discount is no longer needed. Legibility is the plate's job, and a
   plate is a better instrument for it than dimming the whole substrate.
2. **`:40758` `.chat-container::after`** — the sheet edge, and nothing else.
   Two short linear ramps (90° over 7%, 180° over 5%) for the only two edges
   the eye actually sees: the rail on the left and the viewport on top. The
   iteration-1 radial scrim dimmed by distance from the centre, which is
   precisely the opposite of the rule (strongest where nothing is read); it
   also cost the top-left corner ~76% and measured as no terrain at all.
3. **`:40818` `.chat-container > #chat-history`** — the reading plate, as
   `background-color` with **`background-clip: content-box`**.

`background-clip: content-box` is the whole trick and it is what makes the
plate self-sizing: the clip area is the scroll container's *content box*,
which **is** the reading measure — `.msg` is capped at 85% of it and both
bubble alignments sit inside it. So the plate never needs a magic number; it
tracks the layout. At 1440 it spans x 460–1248 while the prose spans 468–1240,
and the layout's own padding becomes the terrain's margins: 164px on the left,
176px on the right.

Two consequences I did not expect and had to work around:

- **`backdrop-filter` had to go.** It applies to the element's whole area, not
  to the painted background, so `blur(10px)` blurred the gutters too. The
  terrain would only ever have been legible as "there is something there",
  never as contours.
- **`background-repeat` defaults to `repeat`.** My first attempt was
  `background-origin: content-box` + a solid gradient; the 788px gradient
  *tiled* across the 1128px border box and covered both gutters in flat 92%
  black. The field was rendering correctly and being painted over — which is
  exactly the failure the Evaluator measured on iteration 1, reproduced by my
  own first fix. A clipped background-**colour** has no tile to get wrong.
  `:40818` documents both traps.

The hero state keeps its exemption (`:40825`) — no plate, field as subject —
because that is the one surface where the terrain is the point.

### The asset

`static/icons/topo-field.png`, regenerated: `/8` LANCZOS down → bicubic up →
1.2px blur → **histogram match onto `topo-dark.png`'s own luminance CDF**
(smoothed 9-tap LUT so it does not posterise) → compact-component glyph
suppression → 0.7px blur.

The histogram match is the step that matters: it puts back the tonal
distribution the mipmap flattened without repainting a single pixel, so
contours return to the level the source artwork had.

| asset | px > 4 | px > 12 | px > 24 | px > 32 |
|---|---|---|---|---|
| `topo-dark.png` (source) | 19.79% | 15.11% | 10.86% | 7.89% |
| iteration-1 `topo-field.png` | 64.17% | 6.74% | 0.43% | 0.23% |
| **`topo-field.png` now** | 51.42% | 27.10% | 8.18% | 2.41% |

### Measured coverage — before and after

Same script, same regions, same instrument, over the rendered PNGs. The
threshold that reproduces the Evaluator's own numbers (baseline 11.7% →
iteration 1 0.4%) is `max(channel) > 12`, so that is the headline column;
the others are there so the number cannot be accused of threshold-shopping.

Region right of the reading column, `(1150,200)–(1430,700)` = 140,000 px:

| | >0 | >4 | **>12** | >24 | mean lum |
|---|---|---|---|---|---|
| iteration 0 (`base0/d-chat.png`) | 39.61% | 27.92% | **11.81%** | 2.16% | 4.40 |
| iteration 1 (`iter1/d/d01-shell-chat.png`) | 19.83% | 11.42% | **0.40%** | 0.32% | 1.67 |
| **iteration 2** | 59.23% | 44.85% | **18.87%** | 3.63% | 6.98 |

Region top-left, `(300,60)–(440,180)` = 16,800 px:

| | >4 | **>12** | mean lum |
|---|---|---|---|
| iteration 0 | 24.29% | **14.64%** | 3.75 |
| iteration 1 | 0.10% | **0.00%** | 0.44 |
| **iteration 2** | 60.45% | **23.62%** | 7.63 |

Pure gutter right of the plate, `(1250,80)–(1424,760)` (my own region, not
the Evaluator's, to isolate the terrain):

| | **>12** | mean lum |
|---|---|---|
| iteration 1 | **0.00%** | 0.15 |
| **iteration 2** | **26.63%** | 8.04 |

So: **0.40% → 18.87%** on the Evaluator's own metric, against a 5% target and
an iteration-0 baseline of 11.81%. Not "the field came back"; the field is
*stronger than it was before the legibility fix*, because the fog is gone and
the two global dimmers are gone.

Measurement method, so it can be repeated: `/tmp/opencode/pw/topo-measure.mjs`
loads the app with appearance pinned, injects a four-turn transcript built
with the same DOM shape `chatRenderer.js` produces, waits 1.2s, screenshots at
1440×900; `/tmp/opencode/pixcount.py` counts over the PNG. The fixture is a
measurement harness in `/tmp`, not a source change.

### Legibility did not pay for it

Measured on the **brightest pixel in glyph-free inter-paragraph gaps inside
the reading measure** — gaps located from the DOM (`getBoundingClientRect()`
between sibling `<p>` boxes), so no glyph can be in them:

```
worst pixel  rgb(0,0,0)  lum 0.00000
contrast vs --fg        #d2d2d2  13.89:1     (WCAG AA floor 4.5:1)
contrast vs --fg-strong #f1f1f1  18.59:1
```

And the theoretical bound, since the plate is 92% opaque: even directly over
the field's brightest pixel (source max 113), the surface under the prose is
sRGB ~9, which measures ~13:1 against `--fg`. Iteration 1 measured 12.94:1 at
the same statistic. The prose pays nothing.

### Mobile

At 375px the content box *is* the viewport, so the plate covers the transcript
edge to edge. That is the correct outcome, not a fallback — a 12% dissolve at
375px is 45px, wide enough to push a bubble off the plate, which is the
defect the plate exists to remove. The terrain still reads on a phone in the
two places there is room: the top-bar band above the transcript and the gap
between the transcript and the composer. `scrollWidth === innerWidth === 375`,
no horizontal overflow.

### Login

`static/login.html` had a full-viewport radial scrim at `opacity: 0.6` over
the same fogged asset. Now one soft pool behind the card at 88/52/0 (`:76`) at
`opacity: 1`, and the field's restored contrast carries the page. The two dead
`--plate-blur` / `--plate-feather` declarations in its `:root` mirror are gone
— nothing on that page read them.

---

## 5. Remaining feedback items

| # | Item | Status |
|---|---|---|
| 5 | **Compare: four selected-state vocabularies** | Closed. `:7972` — one treatment for all five toggles: `opacity: 1`, `color: var(--fg-strong)`, `border-color: var(--accent-ink)`, `background: color-mix(in srgb, var(--accent-ink) 10%, transparent)`. `#e0a050` and `#5b8def` deleted, and `.compare-parallel-toggle` no longer paints itself orange unconditionally. Verified in `d06-compare.png`. |
| 7 | **Five window widths** | Closed. The `:41579` rule was already unconditional; three inline `style="width:…"` attributes were beating it. Cookbook → `var(--window-w-wide)`, Library → `var(--window-w)`, Email → `var(--window-w)`, Compare's model picker → `var(--window-w)`. Measured after: **760 or 1080, two widths, both tokens**, title bars 40px everywhere. Centres: 860 for all of them except Calendar at 744 — and that is not a fourth axis. `#calendar-modal` measures `left: 48px; width: 1392px` because Calendar hides the sidebar, so `--sidebar-w` is 0 and `--icon-rail-w` is 48; it centres on the chat area *as it currently is*. Cookbook and Compare were missing from the chat-area centring list and are now in it. |
| 8 | **Sub-11px text** | Partly closed. Runtime count of elements under 11px: **0** on the shell and Settings, 1 on Gallery, 3 on Brain, 2 on Tasks (iteration 1: 4 live). `.memory-count` was already `--text-xs` at source; the sub-11px values are coming from per-module overrides I did not chase. |
| 8 | **Off-scale radii** | Improved, not finished. `.export-dl-btn`, `.modal-minimize-btn`, `.section-header-btn`, `.list-item-plus-btn`, `.modal-close`, `.minimize-btn` 4px→`--radius-sm`; `.cal-nav`, `.cal-view-toggle` 5px→`--radius-sm`; `.scroll-nav-btn`, `.gallery-chip` →`--radius-full`; `.msg-action-btn` 4px→`--radius-sm` and `padding: 2px 6px`→`--space-1/--space-2`. `.send-btn` was the only control at an arbitrary font-size (13.3333px, a 10pt inheritance) and now declares `--font-ui` / `--text-base`. **Runtime off-scale radii per surface: 4** (iteration 1: 33–46). The remaining four are `.section-collapse-btn` 4px, `.overflow-menu` 10px and the two `.mode-toggle-btn` 10px corner pairs. |
| 10 | **Checkbox inside the username field** | Closed. `static/login.html` — the `.remember-toggle` was `position: absolute` inside the *username* `.pw-wrapper`, measuring x 840–856 / y 264–280 inside an input at x 572–868 / y 250–293. It is now its own row below the password field (`:215`, `:318`) with a visible `Remember me` label. It also carried `display: flex !important`, which meant `setMode()`'s attempt to hide it in setup and signup modes had never worked. Tab order verified. |
| 11 | **`Download from:☁HuggingFace`** | Closed. `static/js/cookbook.js` — the inline SVG had `margin-right: 1px` and no whitespace before the label, so the glyph touched the word. Now `margin-right: var(--space-1)` and a real space. `margin-top: 6px` → `var(--space-2)`. The `En… ?` / `Quant ?` / `Context ?` truncations are still there — deferred, see below. |
| 12 | **`NOT YET WIRED` comments** | Closed. All five stale "NOT YET WIRED" markers in `:root` corrected to describe what is actually wired and why, including the explicit list of the shadow values that are deliberately *not* elevation. A stale "NOT YET WIRED" next to a live token invites the next contributor to bypass the tokens. |
| 12 | **Raw green glow** | Closed. `rgba(0, 255, 0, 0.3)` → `0 0 var(--space-3) color-mix(in srgb, var(--color-agent-active) 30%, transparent)` at both sites. It also carries pure green, which the palette reserves for added/success, and an agent that is merely running is neither. |
| 1 | **Colour literals** | Partly closed. Live hex outside `:root` **212 → 199**, `rgba()` **175 → 62** (both counting only live declarations: comments and `var(--token, #fallback)` excluded). Closed on interactive affordances: `.send-btn.newchat-mode` `#2a2a2a` → `--elevated`, `.censored-item:hover` literal green → `color-mix(--success 8%)`, the PDF-view checkbox `#444`/`#111` → `--surface-4`/`--bg`. **Deferred:** `#4ade80` (21) and `#f44` (15) are spread too wide for a blind substitution and each needs a token decision; `#fff` (43) / `#000` (40) are the syntax theme; `#e5a33a` (11), `#b48a4a` (9), `#98c379` (7), `#d19a66` (7) are per-language highlight palettes. `#f00` at `:39714` is a **data** gradient (an RGB channel visualisation) and is legitimately a literal. |
| 6 | **Glyph residue in the field** | Improved, not eliminated. See below. |
| 9, 11, 12 (other) | Drawer scrim, clipped rows, empty states | Deferred. See below. |

### Feedback issue 6 — the dust, honestly

The `/8` derivation plus the histogram match put the contour lines back at
their source level and the annotation residue is much less prominent than it
was. It is **not gone**. I targeted it three ways and report what each did:

- *Highlight knee at 36* — collapsed the whole field (`>24` fell from 11.12%
  to 0.36%). My estimate of the contour level was wrong; the contours live in
  24–48, not below 36. Rejected.
- *High-pass subtraction* (image minus a blurred copy, radius 16) — turned the
  field into vertical striping. Rejected.
- *Local-density attenuation* — contour lines are locally dense too, so this
  cost `>24` 11.12% → 8.18%. Rejected.

What did land is component targeting: connected components of the matched
image above 48 that are **compact** (fill ratio > 0.55, bbox < 900px) are
glyph blocks; components that are large and stringy (fill 0.19–0.45) are
contour crossings and dense terrain and are left alone. 164 glyph blocks were
soft-masked down by 78% with a 5px feather. Residue is now a faint highlight
rather than a hard white rectangle, and `--field-opacity` no longer has to pay
for it.

**Remaining:** a handful of faint 3–4px highlights are still visible on the
login and in the chat gutters at 2× crop. The honest next step is not another
filter — it is to re-derive from the source with a mask painted over the ~30
known annotation locations, which is an artwork edit and not a design one.
I did not have the budget and did not want to half-paint it.

---

## 6. Checks run, with real output

```
$ ./venv/bin/python -m pytest
=========== 4620 passed, 3 skipped, 76 warnings in 167.05s (0:02:47) ===========
```

Identical counts to iteration 1 (4620 / 3) — no test was added, removed or
weakened. Run four times during the iteration. One run *did* fail
(`test_design_tokens_brutal.py::test_tail_shadows_are_two_layer_tokens_or_none`)
because my own explanatory comment in `style.css` literally spelled
``box-shadow: none``, which that test's regex reads as a declaration. I
reworded the comment. **I did not touch the test.**

```
$ node --check   → OK on all 11 touched JS files:
  static/app.js  static/js/a11y.js  static/js/chatRenderer.js
  static/js/models.js  static/js/spinner.js  static/js/tourHints.js
  static/sw.js  static/js/documentLibrary.js  static/js/emailLibrary.js
  static/js/cookbook.js  static/js/compare/selector.js
$ ./venv/bin/python -m py_compile app.py routes/*.py src/*.py  → OK
```

### Computed evidence, live, at 1440×900

```
.chat-input-bar    background-color rgb(43,43,43)
                   box-shadow rgba(0,0,0,.45) 0 4px 12px, rgba(255,255,255,.04) 0 1px 0 inset
                   border-top-width 0px      padding 12px 16px
.settings-select   border-color rgb(117,117,117)   border-radius 6px   padding 4px 8px
.memory-search-input  border-color rgb(117,117,117)  height 30px
#chat-history      background-clip content-box    backdrop-filter none
.chat-container::before  opacity 0.9   url(/static/icons/topo-field.png)
overflow           scrollWidth 1440 === innerWidth 1440
```

Window geometry, measured `getBoundingClientRect()` at 1440×900:

```
calendar  760 @ cx 744   gallery   1080 @ cx 860   cookbook 1080 @ cx 860
compare   760 @ cx 860   brain      760 @ cx 860   library   760 @ cx 860
tasks     760 @ cx 860   settings  1080 @ cx 860   title bars 40px throughout
```

### Console log — `/tmp/opencode/shots/gen2/console.log`

Full run at both viewports (13 driver steps each). **0 `pageerror`. 0 asset
HTTP ≥400. 0 × 5xx.** The set is identical to the Evaluator's iteration-1
triaged list:

- benign, expected: `403 /api/auth/integrations` ×3, `403 /api/auth/users`,
  `401 /api/auth/2fa/status` — correct refusals under `AUTH_ENABLED=false`
- benign: `[warning] TTS: not available` — no TTS binary in the container
- benign: `ERR_ABORTED` on `/api/diagnostics/logs` — aborted on navigation
- **not scored, identical to the baseline report:** two
  `Executing inline script violates … 'script-src 'self' 'nonce-…''` errors.
  They fire **only** in the run that loads `/static/login.html` as a raw
  static file. That page carries a literal `nonce="{{CSP_NONCE}}"` which is
  only substituted on the real `/login` route, and that route 302s away with
  auth disabled. It is an artefact of the access method, not of this change.

### Screenshots

`/tmp/opencode/shots/gen2/` — 1440×900: `d01-shell-chat` (welcome),
`d02-transcript`, `d03-gallery`, `d04-calendar`, `d05-cookbook`,
`d06-compare`, `d07-brain`, `d08-library`, `d09-tasks`, `d10-settings`,
`d11-login`, `d12-login-focus`. 375×812: `m01-chat`, `m02-transcript`,
`m03-drawer`, `m04-tasks`, `m05-gallery`, `m06-settings`. Field assets and
the before/after crops under `topo/`. Every one was opened and read back with
the image tool, not inferred from the DOM.

Both 1440×900 and 375×812, for the shell/chat, an overlay (Settings, Compare
picker), six workspaces, Settings and the login, per `spec.md`'s evidence
requirement.

---

## 7. Deliberately deferred

| Item | Why |
|---|---|
| **Issue 6 — glyph dust** | Three filters tried and rejected on measurement (§5). The correct fix is an artwork mask, not a filter. |
| **Off-scale padding/gap (~1,200 sites)** | Root cause (the missing `--space-5/6/7/9/10` steps) was closed in iteration 1; what is left is mostly 1–2px optical nudges. Rewriting them blind makes it worse, and the penalty for the cluster is already capped. I did the named classes only. |
| **`#4ade80` ×21, `#f44` ×15, `#fff` ×43, `#000` ×40, the highlight palettes** | Each needs a token decision, not a substitution. `#fff` → `--accent-ink` would move 255 → 241 and re-tint the whole syntax theme; `#000` → `--bg` is safe but 40 of them is a blind sweep. Reported as backlog, per the rubric's rule 3. |
| **Issue 9 — mobile drawer has no scrim** | Real (measured: `elementsFromPoint` topmost is `#chat-history`), but it is a per-viewport styling question with its own evidence requirement at 375px, and I had already spent the iteration on the two Gate items and the identity. |
| **Issue 9 — `Tasks` behind the base plate at 375px** | Confirmed real in `m03-drawer.png`. Needs a scroll-shadow or `padding-bottom` on `.sidebar-inner`; a two-line change I would rather do with a screenshot at both viewports than rush. |
| **Issue 11 — `En… ?` / `Quant ?` / `Context ?`** | Still truncated. Fixing it means finding the truncation in `cookbook.js` and choosing real label text — an information decision per field, not a styling one. The icon collision on the same screen *was* mechanical, so I did that half. |
| **Empty states** (Cookbook's ~400px under a 12px spinner, Calendar's ~130px, Brain's void, Gallery/Library italic copy) | Unchanged from iteration 1's deferral. Four modules, four information designs; better done one at a time than four rushed. |
| **`--accent` is monochrome, not the documented ice-blue** | Still needs the maintainer's call, same as iteration 1. Changing the hue now would re-tint every surface whose evidence I have just gathered. |
| **Scroll affordances on clipped rows** (Tasks "Email Tags", Settings header) | Per-module; deferred as in iteration 1. |

---

## 8. What I would do next

1. **Re-derive `topo-field.png` with a painted mask** over the ~30 known
   annotation locations in the source artwork. The tonal pipeline is done and
   correct; this is the last 1% of the identity.
2. **The drawer scrim + the `Tasks` scroll affordance**, together — both are
   mobile, both need 375px evidence, and both are the reason a workspace reads
   as absent from the nav on a phone.
3. **The four empty states**, one at a time, each with a real primary action
   instead of a caption in a void. This is where Design Quality goes next; the
   shell now has a focal point (the mark tile), a substrate (the survey sheet),
   a frame (the base plate) and real elevation (the composer).
4. **Promote the syntax and highlight palettes into `:root` as named tokens**,
   one decision at a time, starting with `#fff` → a `--text-on-accent` token so
   the sweep is value-preserving rather than a 255 → 241 re-tint.
5. **Add the measurements to the loop permanently.** Five lines of
   `getBoundingClientRect()` assert per window, and the pixel-count script,
   both belong in `gan-harness/` rather than in `/tmp`. Three of this
   iteration's findings — the composer's specificity conflict, the plate's
   `background-repeat` tiling, the asset's crushed histogram — were invisible
   to reading the CSS and only appeared when measured.