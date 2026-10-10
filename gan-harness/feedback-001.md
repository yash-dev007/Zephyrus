# Feedback — Iteration 1

Evaluator: adversarial review of the working tree as rendered. Adversary to
`generator-notes-001.md`, whose claims were re-derived independently.
Date: 2026-10-08. Mode: design. Screenshots: `/tmp/opencode/shots/iter1/`.

---

## 1. Verdict

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Design Quality | **5.6** | 0.35 | 1.960 |
| Originality | **5.2** | 0.30 | 1.560 |
| Craft | **1.0** *(floored — see arithmetic note)* | 0.25 | 0.250 |
| Functionality | **5.8** | 0.10 | 0.580 |
| | | **1.00** | **4.350 → 4.4** |

**Weighted total: 4.4 / 10. Threshold 7.5. → FAIL**

**Gate: FAIL** (items 3 and 5). Any single gate failure fails the iteration
regardless of the weighted score, so iteration 1 fails twice over — the same two
items that failed at baseline, for *different, and in one case newly-identified,
reasons* (§3, and Delta below).

### Penalties applied

| Penalty | Applied | Where |
|---|---|---|
| Raw hex/rgb outside `:root` (max −3) | **−3.0** | 220 hex + 69 `rgba()` outside `:root` (`static/style.css`); largest clusters `#fff` 49, `#000` 62, `#4ade80` 15, `#f00` 14, `#e0a050`/`#5b8def` on live Compare controls |
| Off-scale spacing / radius / font-size (max −2) | **−2.0** | runtime: 33–46 off-scale radii per surface, 132–317 off-scale paddings, 12–98 off-scale gaps, 1–14 off-scale font-sizes (see §3 table) |
| Border used to fake elevation (max −2) | **−1.0** | two clusters: `static/style.css:41006` (composer: `--bg` + `--border-subtle` + `box-shadow: none`, which silently cancels the correct rule 6,700 lines earlier at `:2735`); `static/style.css:41532` (nine `.modal-content` selectors given `--surface-2` **and** `1px solid var(--border-subtle)` **and** `--shadow-lg`, directly under a comment saying the hairline is not needed) |
| Animation with no reduced-motion counterpart | not applied | measured clean — 21 `prefers-reduced-motion` blocks, **0** elements retain a live animation under reduce |
| Emoji in UI | not applied | the 742 hits are in `static/js/emojiShortcodes.js` (an emoji-typing feature) + 4 in `app.js`; not rendered chrome |
| Generic AI-slop visual | not applied | pure-black canvas, monochrome ramp, no gradient-everything, no emoji icons |
| Dead / placeholder / TODO styling | not applied | `static/style.css:307` still says "NOT YET WIRED" for `--ease-out`/`--dur-*`, but consumers exist and measure correctly (`:41569` uses all three) |
| Favicon/manifest/logo churn | not applied | the `Zephyrus-Mark.png` tile is part of this run's work, not churn |

### Arithmetic note — the Craft floor is still an artefact

Mandated: `6.0 − 3.0 − 2.0 = 1.0`. A 1.0 is defined as *"Broken layouts, missing
states, no motion, lost focus, layout shift"* — **none of which is true of this
app.** The penalty table's maxima are calibrated for a single small diff, not a
41k-line stylesheet that the run inherited.

I report the mandated **1.0** because the rubric is the contract. My honest
unpenalised Craft is **6.0**, and the operator should read that number. On that
basis the weighted total is `5.6×.35 + 5.2×.30 + 6.0×.25 + 5.8×.10 = 5.60`.
The verdict is FAIL either way, and the Gate is FAIL either way.

---

## 2. Per-criterion justification

### Design Quality — 5.6

The app now reads as one deliberate system rather than a pile of surfaces, which
is a genuine structural change and the strongest thing about this iteration.

- **The overlay model is finally coherent.** `--shell-scrim` 55% + `blur(4px)` is
  extracted at `static/style.css:41524` and applied to `.modal`,
  `.modal-overlay`, `.search-overlay`. Measured live on Gallery, Cookbook,
  Compare, Brain, Library, Tasks, Calendar, Settings: `background-color: color(srgb
  0 0 0 / 0.55)`, `backdrop-filter: blur(4px)`. In `d-03-calendar.png` and
  `w2/x01-cookbook.png` the sidebar and transcript genuinely recede. At baseline
  the command palette was the only surface in the app that dimmed; now nothing is
  exempt except the docked Notes rail, which is a defensible exception.
- **Title bars are one height.** `--window-title-h: 40px` (`:365`); measured
  `40px` on Calendar, Cookbook, Compare, Library, Gallery, Brain, Tasks, Settings.
  Baseline had 17 / 20 / **63**. That alone removes the single loudest
  rhythm break.
- **Hover is genuinely distinct from selected.** Measured with Gallery open:
  open = `rgb(27,27,27)` + `box-shadow: rgb(241,241,241) 2px 0px 0px 0px inset`;
  Brain hovered = `rgb(20,20,20)`, no marker; at rest = transparent. Two greys
  **plus** a hue-carrying rule, and it survives a greyscale print. Verified in a
  still (`hov/nav-3.png`: Cookbook hovered flat, Notes showing its focus ring).
- **Login is on-system.** `--elevated` resolves to `#2b2b2b` (it resolved to the
  empty string at baseline); card = `--surface-2` + `--shadow-lg` + `border: 0`;
  inputs `--border-control` `#757575`; `Sign In` padding `12px 16px` (was
  `12.2px 11.2px 10.2px`); real logo; `outline: 2px solid rgb(241,241,241)` on
  focus. `lg01-desktop.png` looks like the same product as the app.
- **The sidebar has a base plate.** `.sidebar-user-bar` = `--surface-1` +
  `--border-subtle` divider, pinned bottom (`static/style.css:41560`). The
  comment is right that this is the one legitimate use of a border.

Against that, four things stop it short of 7.

- **The topographic field is no longer visible in the chat, and that is the
  identity.** Pixel-measured on the region right of the reading column
  (1150,200)–(1430,700): non-black pixels **16,312/140,000 (11.7%) → 561/140,000
  (0.4%)**, a 29× collapse; mean luminance 4.40 → 1.67. On
  (300,60)–(440,180): **2,420/16,800 → 0**. The layer is still there —
  `#chat-container::before` carries `url(topo-field.png)` at `opacity: 0.62`
  — but a 92%-opaque plate plus the radial scrim compound to black. The
  app's signature background is gone from the surface where users spend their
  time. That is an originality loss wearing a legibility fix's clothes.
- **Window geometry is only half-closed.** Widths measured: Compare **520**,
  Library **640**, Calendar/Brain/Tasks **760**, Cookbook **780**, Gallery
  **1080**. Centres: Cookbook **720**, Calendar **744**, everything else **860**.
  Five widths and three axes remain; only the title bar was unified. Compare and
  Library match neither `--window-w` (760) nor `--window-w-wide` (1080).
- **Dead space is untouched.** Cookbook: ~400px of empty panel under a 12px
  spinner (`w2/x01-cookbook.png`, y 480–860). Calendar: ~130px under "No events".
  Brain: empty state floats in a void (`x03-brain.png`). Gallery and Library
  empty states are still *italic*. Sidebar: still ~300px between `Tasks` and the
  base plate — now framed, but still a void.
- **Composition defects the notes call "deferred" are still on screen.**
  `static/index.html` Cookbook "Download from:☁HuggingFace" — the icon collides
  with the word, no space (`w2/x01-cookbook.png` y 185). The truncated selects
  still read `En… ?`, `Quant ?`, `Context ?`. The native OS `title` tooltip
  ("Notes is your basic todo list…") still overlaps its own header
  (`d-02-notes.png`). The tour-hint illustration is bigger but still reads as an
  empty black box with a cursor in it (`x01-cookbook.png` top-right).
- **One live composition error the notes missed:** `static/login.html:207` places
  the "Remember me" checkbox *inside* the username field. Measured: username
  input `x 572…868, y 250…293`; `.remember-toggle` `x 840…856, y 264…280`. A bare
  16px grey dot floating in a text box, with nothing labelling it on screen
  (`lg01-desktop.png`).

### Originality — 5.2

**Explicit test: strip the name and the logo — would you know it wasn't a generic
AI chat app?** Partly yes, and less than at baseline.

The mono/sans split is now real and it is the most distinctive thing on screen.
Measured: `body`, `.list-item`, `.send-btn`, `.settings-nav-item`,
`.modal-header`, `select` → `Inter, system-ui, …`; `.msg-ai`, `.msg-user`,
`.msg-footer`, `#message` prose, the textarea → `"Fira Code", monospace`.
**Zero** elements resolve both faces (audited on nine surfaces). `document.fonts`
confirms `Inter 400/500/600 loaded` and `Fira Code 400/600 loaded`. In `d-01` and
`fn/f02-after-send.png` the effect is unmistakable: `VIEW THINKING PROCESS` in
letterspaced Inter caps sits directly above monospaced prose. A transcript whose
*controls* are proportional and whose *content* is monospaced is a decision, not
an accident. Baseline measured `"Fira Code"` on every chrome element — this is
the fix the rubric named and it landed.

The ladder-based depth is real in the overlays and undermined in the composer
(§4 issue 3).

The topographic field is present in the asset and **absent from the chat**
(§2 above). The debug residue is genuinely gone as *text* — I cannot read
"2s456", "mo 731", "sneha" or any other annotation anywhere in the render — but
the `/6` mipmap derivation left the annotations as **bright square specks**.
`lg01-desktop.png` shows ~15 of them scattered across the field at roughly 3–6×
 the local contour luminance; contrast-boosted crop at
 `topo/smudge_a.png` shows one clearly: a hard-edged square with a soft halo, no
 longer legible as a glyph and not yet legible as terrain either. On the login
 they read as sensor dust. Better than legible debug text, not yet art.

So: of the three carriers the rubric names, one was restored (mono/sans), one is
real but compromised (ladder depth), and one is now absent from the primary
surface (topographic field). Everything else is convention — right-aligned user
bubbles, left-aligned assistant, `tok/s · icons` meta row, centred context pill,
a `Recent / Select / Tidy` chip row. **4.5 → 5.2.**

### Craft — 1.0 mandated / **6.0 unpenalised** (say this one, not the floor)

**Measured clean, and creditable:**

- **Single-layer `box-shadow`: 136 → 0 true single-layer elevation drops.** Source
  audit: baseline 289 declarations / 251 without `inset` / **136 with a non-zero
  offset**; current 165 / 127 / **15**, and every one of the 15 is a `0 0 0 Npx`
  selection ring, a `0 0 Npx Mpx` glow, a `@keyframes` pulse, or the
  `.notes-quick-add` spread trick. I agree with the note's reasoning that
  forcing rings and pulses through an elevation token would be wrong.
  **Runtime audit across nine surfaces: 1 non-inset shadow, and it is a focus
  ring** (`INPUT.gallery-search` on focus). The claim holds.
- **The font split has no leaks** (0 elements resolving both faces).
- **Reduced motion is genuinely honoured.** Under `reducedMotion: 'reduce'`,
  `matchMedia('(prefers-reduced-motion: reduce)').matches === true`, and
  `transition-duration: 0s` / `animation-name: none` on `.send-btn`, `.list-item`,
  `body`, `.msg-ai`, `.icon-rail-btn`, `.modal-content`, `#chat-history`,
  `textarea`. **Zero** elements retain a live animation. 21 blocks in
  `static/style.css`. The best-executed requirement in the codebase, and still
  correct.
- **Responsive holds.** `scrollWidth === innerWidth === 375` at every mobile stop
  (chat, drawer, Tasks sheet, Settings sheet, workspace). Zero horizontal overflow.
- **Off-scale values fell hard at runtime**, even though the note defers the
  sweep:

  | | baseline | iteration 1 |
  |---|---|---|
  | off-scale radii (live) | 382 decls | **33–46 per surface** |
  | off-scale font-size (live) | 195 elements | **1–14 per surface** |
  | elements below the 11px floor | 13 | **0 at 375px**; `.memory-count` still 9.6/8.4px on Tasks and Brain |
  | off-scale padding / gap (live) | 1170 | 132–317 / 12–98 |

- **`node --check` clean on all 6 touched JS files.**
- **Message action row** is now three SVG icons at one stroke weight
  (`fn/../topo/user-bubble.png` at 2× — the dingbats really are gone).
- **Footer divider** fixed: `.msg-footer` is `align-self: stretch` and its
  `border-top` is a fixed 362px, not shrink-to-fit. Baseline: variable width.
- **Native `<select>` styled** — `appearance: none`, `--surface-1`,
  `--border-control`, `--radius-sm`, Inter, dark `option`, two-gradient caret.
  Verified live on `#gallery-sort`: `appearance: none`,
  `background-color: rgb(12,12,12)`, `border-color: rgb(117,117,117)`.
  The rationale for the gradient caret (an SVG in `url()` can't read a token) is
  correct and the result is better than an inline SVG would have been.

**Measured not clean:**

- **A control edge on `--border`, live, in Settings.** `.settings-select`
  (`static/style.css:24731`) still declares `border: 1px solid var(--border)`,
  which beats the new bare-`select` rule at `:41642` on class specificity.
  Measured on `#set-defaultEpSelect` and 11 sibling selects:
  `border-color: rgb(55,55,55)` = `--border` = `#373737` on `--bg` = **1.76:1**,
  against a WCAG 1.4.11 floor of 3.0 and a token (`--border-control` `#757575`)
  that is right there at `:48`. This is the red line by name. Same class of
  defect at `:11458` `.memory-search-input { border: 1px solid var(--border) }`.
- **Sub-11px text is still live**, on Tasks and Brain:
  `SPAN.memory-count @9.6px`, `SPAN.memory-count @8.4px`,
  `DIV.memory-item-meta @10px`, `SPAN @9px`. Below 11px is for decorative glyphs
  only, and a count badge is readable text.
- **Off-scale values still everywhere**, in runs rather than one-offs:
  `r=4px` on eight button classes, `r=5px` on `.cal-nav`, `r=10px` on
  `.mode-toggle-btn` / `.scroll-nav-btn`, `r=14px` on `.gallery-chip`;
  `padding: 2px 6px` on `.msg-action-btn`; `padding: 5px 8px` on
  `.settings-select`; `gap: 1px` on `.cal-grid`. And three genuinely arbitrary
  sizes: `.send-btn` at **13.3333px**, a Cookbook `SPAN @15.4px`, Compare
  `BUTTON/SPAN @11.48px`.
- **Four selected-state vocabularies inside one panel, and it got worse.**
  `w2/x02-compare.png`: *Blind* selected = orange `#ff9800`; *Parallel* selected
  = **`#5b8def`**, a saturated blue that is not in the palette at all
  (`static/style.css:7989`); *Chat* selected = white; *Save* = nothing.
  Worse, `.compare-parallel-toggle` at `:7985` paints `#e0a050` on the
  **non-active** state too, so the row reads as two selections at once.
  These are live raw literals outside `:root` on an interactive affordance.
- **A raw green glow**: `#agent-indicator.active` at `static/style.css:6199`
  and `:8612` — `box-shadow: 0 0 10px rgba(0, 255, 0, 0.3)`. A literal pure
  green, outside `:root`, on an "agent is active" indicator.

Raw-literal accounting, honest split (my count matches the note's 220 for hex):
**hex outside `:root` 224 → 220** (flat), **`rgba()` outside `:root` 176 → 69**
(the shadow conversion did real work here). `var(--token, #fallback)` defensive
fallbacks 260 → 259, unchanged and not a bypass.

### Functionality — 5.8

**Verified working in-browser:**

- **Chat send → stream.** Typed "Say hello in one word." into `#message`, pressed
  Enter: message count 8 → 10, user bubble rendered with the text, assistant
  streamed (`Hey`), live metrics (`$0.0003 · 1%`), context pill updated to
  `10 msgs $0.0005` (`fn/f02-after-send.png`).
- **Sidebar nav reaches every workspace.** Notes, Calendar, Compare, Cookbook,
  Deep Research, Gallery, Library, Brain, Tasks — all nine opened and rendered.
- **Escape closes every overlay tested** — Calendar, Gallery, Cookbook, Compare,
  Library, Brain, Tasks, Settings: all reach a zero-rect or `pointer-events: none`
  state afterwards.
- **Search overlay** opens with the scrim + blur (`color(srgb 0 0 0 / 0.55)`,
  `blur(4px)`).
- **Responsive** — no horizontal overflow at 375px on any surface.
- **Auth path** — `curl /login` → `302 → /` under `AUTH_ENABLED=false`; the
  `/api/auth/*` 403/401s in the server log are correct refusals.
- **Server log**: 0 × 5xx, 0 tracebacks. Console: **0 `pageerror`**, 0 asset
  HTTP ≥400.
- **Login** renders and validates: focus ring present, `--elevated` resolves.

**Broken — and this is a Gate item.** `spec.md`'s invariant reads *"Modals open,
close, **trap focus**, and **restore it**."* Tested with real key events:

| | Gallery | Settings |
|---|---|---|
| focus moves into the panel on open | yes (`INPUT#gallery-search`) | **no** (`focusIn: false`) |
| focus trapped while tabbing | **no** — after 6 stops focus escaped to `BODY` and walked the sidebar (`hamburger-btn`, `sidebar-brand-btn`, `email-compose-btn`…) | **no** — first Tab landed on `#export-dl-btn`, which is in Cookbook, entirely outside Settings |
| focus restored to the trigger on Escape | **no** — landed on `BUTTON#email-compose-btn`, an unrelated sidebar element | **no** — landed on an unnamed `BUTTON` |

This is pre-existing, not a regression, and my baseline report explicitly could
not verify it either. But it is a named invariant in `spec.md`, which makes it
Gate 3 as written. **The note's claim that "modals open, close on Escape, and
restore — verified for Notes, Calendar and Settings" is false on the restore
half, and the note does not mention focus trapping at all.**

**Not verifiable, not credited:** settings + appearance preference persistence —
the harness pins `/api/prefs/appearance` to `{mono, comfortable, 100}`, so a
reload test cannot exercise it. I make no claim either way.

5.8: happy path fully works, a keyboard-accessibility invariant does not.

---

## 3. Gate results

| # | Gate | Result |
|---|---|---|
| 1 | `./venv/bin/python -m pytest` fully green | **PASS** |
| 2 | `node --check` on touched JS | **PASS** (6/6) |
| 3 | Functional invariants intact | **FAIL** |
| 4 | No new console errors / asset ≥400 | **PASS** |
| 5 | No hard red line violated | **FAIL** |

**Gate 1 — verified, not taken on trust.**
```
=========== 4620 passed, 3 skipped, 76 warnings in 182.21s (0:03:02) ===========
```
Baseline was `1 failed, 4619 passed, 3 skipped`. **The note's count is exact.**
I also checked the Generator did not weaken the suite to get there:
`tests/test_select_dropdown_theme_css.py` is modified in the working tree, but
`gan-harness/baseline/worktree.patch` already contains that diff, so it is
pre-existing baseline work, not a Generator edit. `tests/test_design_tokens_brutal.py`
is untracked and was in the baseline snapshot too.

**Gate 2 —** `node --check` clean on `static/app.js`, `static/js/chatRenderer.js`,
`static/js/models.js`, `static/js/spinner.js`, `static/js/tourHints.js`,
`static/sw.js`. (Also clean on the 12 files rendering the surfaces I audited.)

**Gate 3 — FAIL.** Modal focus trap and focus restore are broken on every
overlay tested (§2 Functionality). Table above. Note the Generator explicitly
claimed to have verified restore.

**Gate 4 — PASS.** Console triage across 14 driver runs:
- **Benign, expected:** `404 /api/research/status/6b1817af…` ×24 and
  `404 /api/chat/stream_status/6b1817af…` ×24 — stale-session polls for a
  session id no longer in `data/`. Identical to baseline.
- **Benign:** `[warning] TTS: not available` — no TTS binary in the container.
- **Benign under `AUTH_ENABLED=false`:** `403 /api/auth/integrations`,
  `403 /api/auth/users`, `401 /api/auth/2fa/status` (server log: 8 × 403, 2 × 401).
- **Zero `pageerror`. Zero asset HTTP ≥400.** Server log: 0 × 5xx, 0 tracebacks.
- **Not counted, same artefact as baseline:** `Executing inline script violates
  … 'script-src 'self' 'nonce-…''`, which fires **only** in the `login.log` run
  where I loaded `/static/login.html` as a raw static file.
  `static/login.html:10` carries a literal `nonce="{{CSP_NONCE}}"` placeholder
  that is only substituted on the real `/login` route, and that route 302s away
  with auth disabled. It is an artefact of my access method, identical to the
  baseline report, and I am not scoring it against the run.

**Gate 5 — FAIL.** Two hard red lines are clear; two are not.

Cleared:
- **Single-layer `box-shadow`** — 136 → 0 true single-layer elevation drops.
- **Chrome on `--font-content`** — inverted and verified; 0 elements on both faces.

Not cleared:
- **Control edges use `--border-control`, never `--border`.**
  `static/style.css:24731` `.settings-select { border: 1px solid var(--border) }`
  — every `<select>` in Settings measures `rgb(55,55,55)` = **1.76:1** on `--bg`,
  against a 3.0 floor, with `--border-control` (`#757575`) available at `:48`.
  The new bare-`select` rule at `:41642` does the right thing and is then
  overridden by class specificity. Same class of defect at `:11458`.
- **No new colour literals outside `:root`.** 220 hex + 69 `rgba()` remain, and
  several sit on live interactive affordances: `static/style.css:7985` `#e0a050`
  and `:7989` `#5b8def` (Compare's Parallel/Blind selected states),
  `:7974` `rgba(255,152,0,0.1)`, `:7986` `rgba(224,160,80,0.1)`,
  `:6199` / `:8612` `rgba(0,255,0,0.3)`, `:6982` `rgba(173,26,26,0.9)`.
- *Noted, not charged:* the open-workspace indicator at `static/style.css:1810`
  and `:1817` is `box-shadow: inset 2px 0 0 var(--accent-ink)` — a single-layer
  inset shadow. Technically it matches the red line's letter; it is an indicator,
  not elevation, and it is legible and consistent. I am **not** charging it. The
  note's claim that it is "a `::before`, not an inset shadow" is simply wrong,
  but the outcome is defensible and I am scoring the outcome.

---

## 4. Issues, ordered by severity

### 1. Modals do not trap focus and do not restore it — Gate 3

- **`static/js/` — the overlay open/close path.** Gallery moves focus in, then
  releases it after 6 tab stops; Settings never moves focus in. After `Escape`,
  focus lands on an unrelated sidebar element (`BUTTON#email-compose-btn`) or an
  unnamed button — never the trigger that opened the window.
- **Costs:** Gate 3, which fails the iteration regardless of score. Craft —
  `focus-visible` rings exist on everything and are then unreachable for keyboard
  users in the surface where keyboard use matters most.
- **Fix:** on open, record `document.activeElement`, move focus to the panel's
  first tabbable (or the panel itself with `tabindex="-1"`); on `keydown` Tab,
  if `activeElement` is the last tabbable inside the panel, wrap to the first,
  and vice versa; on close, `.focus()` the recorded element. One `keydown`
  listener on the `.modal` container covers trap + Escape + restore for all of
  them at once — Settings, the eight workspace windows, Rename, Prompt.

### 2. `.settings-select` draws its control edge on `--border`, not `--border-control` — Gate 5

- **`static/style.css:24731`** (`border: 1px solid var(--border);`), winning over
  the correct bare-`select` rule at **`static/style.css:41642`**
  (`border: 1px solid var(--border-control);`) purely on class specificity.
  Same defect at **`static/style.css:11458`** (`.memory-search-input`).
- **Costs:** Gate 5 — this is the red line named in `CONTRIBUTING.md` and in
  `spec.md`. Craft — a `--border` edge on a control boundary measures 1.76:1 on
  `--bg` and 1.20:1 on `--surface-1`, so every select in Settings and both search
  fields in Brain/Library are below the 1.4.11 floor by a factor of ~2.
- **Fix:** change `:24731` and `:11458` to `var(--border-control)`. Then check
  the six other class-level rules that re-declare a whole control's chrome —
  the note says it fixed `.gallery-model-filter` / `.gallery-sort` but
  `.settings-select` was missed. Grep for `border: 1px solid var(--border)` and
  check every hit for whether its element is a control.

### 3. The composer has no elevation, and a 2025-era rule silently cancels the fix — Craft, Design Quality

- **`static/style.css:41006`** `.chat-container .chat-input-bar { background: var(--bg); border: 1px solid var(--border-subtle); box-shadow: none; }` (specificity 0,2,0) overrides
  **`static/style.css:2735`** `.chat-input-bar { background: var(--elevated); border: none; box-shadow: var(--shadow-md); }` (0,1,0).
  Measured live: `background-color: rgb(0,0,0)`,
  `border-top: 1px rgb(43,43,43)`, `box-shadow: none`.
- The comment at `:2736` is a correct explanation of exactly why this matters —
  *"a drop shadow alone is invisible where it falls on pure black"* — and then a
  later rule removes it. On a pure-black canvas the composer is therefore
  `#000` against a `#000` plate with a `#2b2b2b` hairline: the one element in the
  app that is unambiguously in front of the transcript has the least depth in it.
- **Costs:** Craft (border faking elevation, penalty charged in §1), Design
  Quality (the composer is the most-looked-at surface in the product),
  Originality (the ladder-based depth carrier).
- **Fix:** delete the `background` / `border` / `box-shadow` declarations from
  `:41006` and let `:2735` win, or move the elevation rule to
  `.chat-container .chat-input-bar` and drop it from the other. Then re-measure:
  `background-color` must be `rgb(43,43,43)` and `box-shadow` must contain an
  `inset`. While there, `.chat-input-bar` padding is
  `var(--space-2) var(--space-4)` (8/16) at `:41011` against
  `var(--space-3) var(--space-4)` (12/16) at `:2744` — pick one.

### 4. The topographic field has been erased from the chat — Originality, Design Quality

- **`static/style.css`** — `#chat-container::before` carries
  `url(/static/icons/topo-field.png)` at `opacity: 0.62`, under a plate on
  `#chat-history` at `color(srgb 0 0 0 / 0.92)` across 12%–88% of the width,
  under a radial scrim. Measured result: 0.4% non-black pixels right of the
  reading column (was 11.7%); 0 non-black pixels top-left.
- **Costs:** Originality — the rubric's first named carrier, and the reason the
  baseline scored above "stock" at all. Design Quality — the identity is gone
  from the surface users live in. This is the difference between a 5.2 and a 7.
- **Fix:** the plate only has to be opaque across the reading *measure*, and the
  field is the only thing that makes this app not-a-ChatGPT-clone. Drop the plate
  to `--surface-1` at 70% rather than `--bg` at 92% over the measure, or narrow
  it to the prose column and let the field run at full strength in the 12% margins
  and around the composer, where nothing is read. Target: ≥5% non-black pixels in
  the region right of the reading column while keeping body copy at its current
  measured contrast. Verify by re-running the pixel count, not by eye.

### 5. Compare has three hues for one concept, and Parallel reads as always-on — Craft, Design Quality

- **`static/style.css:7984-7991`** — `.compare-parallel-toggle` paints
  `#e0a050` orange unconditionally; `.compare-parallel-toggle.active` paints
  `#5b8def` blue; `.compare-blind-toggle.active` paints `var(--color-blind-orange)`
  `#ff9800`; `.compare-dice-toggle.active` paints `var(--accent-ink)`. Four
  treatments for "this is on". Visible in `w2/x02-compare.png`.
- **Costs:** Craft (raw literals outside `:root` on live controls — charged in
  §1), Design Quality (baseline's "four selected-state vocabularies in one
  panel", unfixed and now with a blue that is not in the palette).
- **Fix:** one selected treatment for the whole Compare panel — `opacity: 1`,
  `color: var(--fg-strong)`, `border-color: var(--accent-ink)`,
  `background: color-mix(in srgb, var(--accent-ink) 10%, transparent)`, matching
  what `.compare-dice-toggle.active` already does. Delete the `#e0a050` /
  `#5b8def` declarations and the `rgba(...)` fills at `:7974` / `:7986` / `:7991`.
  If "blind" needs its own semantic colour, promote `#ff9800` to a named
  `--color-blind` token in `:root` and use it for the hint text only, never for
  the selected border.

### 6. The `/6` mipmap removed the debug text and left dust — Design Quality

- **`static/icons/topo-field.png`** (derived from `topo-dark.png`) — annotations
  are no longer legible anywhere, which is the win. What remains is ~15 hard-edged
  bright specks, 3–6× the local contour luminance, scattered across the field.
  Visible on `lg01-desktop.png`; contrast-boosted at `topo/smudge_a.png`.
- **Costs:** Design Quality on the login — the first surface the user sees now
  has dust on it.
- **Fix:** go one step further, `/8` or `/10`, or blur the derived asset by 1px
  after the downscale. The note already compared `/6`, `/8`, `/10` at 1:1 and
  picked `/6`; pick `/8` and re-check that the contours still read as contours.

### 7. Window geometry: five widths, three centre axes — Design Quality

- **Measured `.modal-content` rects at 1440×900:** Compare `520 @ cx 860`,
  Library `640 @ cx 860`, Calendar `760 @ cx 744`, Brain `760 @ cx 860`,
  Tasks `760 @ cx 860`, Cookbook `780 @ cx 720`, Gallery `1080 @ cx 860`.
  Only Calendar's 760 and Gallery's 1080 match a declared token.
- **Costs:** Design Quality — this was baseline issue 7 and it is half-closed.
  The note quoted Calendar and Settings, both of which happen to comply; the five
  that don't were not measured.
- **Fix:** the tokens already exist (`:363-365`). Make the rule at `:41485`
  unconditional — `.modal-content { width: var(--window-w); max-width: var(--window-w) }`
  with the four dense ones opting into `--window-w-wide` — and delete the per-module
  inline `style="width:…"` / `max-width` overrides that produce 520 and 640
  (search `static/js/compare/`, `static/js/documentLibrary.js`,
  `static/js/cookbook.js`, `static/index.html`). Then centre on one axis: every
  window should be centred in the main column, so either all at `cx 860` or all at
  `cx 720`. Today only Cookbook (720) and Calendar (744) break the majority.
  Add the measurement to the loop — a five-line `getBoundingClientRect()` assert
  per window is cheaper than reading a screenshot.

### 8. Sub-11px text and off-scale sizes, still live — Craft

- **`SPAN.memory-count @9.6px` and `@8.4px`, `DIV.memory-item-meta @10px`,
  `SPAN @9px`** on Tasks / Brain / Library. `r=4px` on eight button classes
  (`.section-header-btn`, `.list-item-plus-btn`, `.close-btn`, `.modal-minimize-btn`,
  `.msg-action-btn`, `.export-dl-btn`, `.minimize-btn`, `.modal-close`),
  `r=5px` on `.cal-nav` / `.cal-view-toggle`, `r=10px` on `.mode-toggle-btn` /
  `.scroll-nav-btn`, `r=14px` on `.gallery-chip`. Three arbitrary sizes:
  `.send-btn @13.3333px`, a Cookbook `SPAN @15.4px`, Compare `@11.48px`.
- **Costs:** Craft −2.0 (mandated, charged in §1).
- **Fix:** the scale now exists end to end (`--space-1…10` confirmed at
  `static/style.css:275-284`), so this is mechanical and can be split into three
  small PRs: (a) `.memory-count` / `.memory-item-meta` → `var(--text-xs)`, killing
  every sub-11px runnable in one edit; (b) the eight `4px` buttons → `var(--radius-sm)`,
  the two `5px` → `var(--radius-sm)`, `10px` → `var(--radius-full)`, `14px` →
  `var(--radius-full)`; (c) the three arbitrary font-sizes → the nearest
  `--text-*` step. Do not attempt all 132–317 padding/gap hits in one pass — most
  are 1–2px optical nudges and rewriting them blind will make it worse.

### 9. The mobile drawer has no scrim, and its base plate hides `Tasks` — Craft, Functionality

- **`static/style.css`** — the desktop `.modal` scrim was extracted, but the
  mobile drawer was not included. Measured at 375×812 with the drawer open:
  `document.elementsFromPoint(30,400)` returns `DIV#chat-history` as topmost — the
  chat behind the drawer is at full contrast. The drawer itself measures
  `box-shadow: none`, `backdrop-filter: none`.
- Separately, `.sidebar-inner` scrolls (`scrollHeight 764` vs `clientHeight 711`)
  but `Tasks` at `y 756…804` sits **behind** the `.sidebar-user-bar` base plate at
  375px (`m3/m21-drawer-full.png`: the list ends at `Notes`, then a hard plate).
  Reachable only by scrolling, with no scroll affordance — baseline issue 11,
  still open, now in a second place.
- **Costs:** Craft, Design Quality (depth), Functionality (a workspace reads as
  absent from the nav on mobile).
- **Fix:** give the mobile drawer the same `#shell-scrim` + `blur(4px)` treatment
  the modal got, or at least a `--shadow-lg`. Then give `.sidebar-inner`
  `padding-bottom` equal to the base plate's height so the last nav row clears
  it, plus the scroll-shadow/mask you already owe Tasks and Settings.

### 10. Login: a checkbox floating inside a text field — Craft, Design Quality

- **`static/login.html:207`** `.remember-toggle` is `position: absolute` inside
  `.pw-wrapper` for the password field, but the measured rect is
  `x 840…856, y 264…280` — **inside the username input** (`x 572…868,
  y 250…293`). A bare 16px grey dot with no on-screen label
  (`lg01-desktop.png`). It has `aria-label` and `title`, so it is accessible and
  not a functional bug, but it reads as an artefact.
- **Costs:** Craft, Design Quality (first-run surface).
- **Fix:** either move it below the password field as its own row with a visible
  label, or drop the overlay and render it as a real control in the card's
  footer row. Do not leave an unlabelled dot inside an input.

### 11. Cook book still renders truncated labels and a text collision — Craft

- **`static/index.html` / `static/js/cookbook.js`** — `En… ?`, `Quant ?`,
  `Context ?` selects (`w2/x01-cookbook.png` y 396) and the `Download
  from:☁HuggingFace` line where the inline SVG icon collides with the first word,
  no space (y 185).
- **Costs:** Craft — these read as broken, which is what the baseline called them.
- **Fix:** the icon needs a `margin-right`; the truncated labels need real text
  or a styled tooltip. Small, self-contained, and Cookbook is the first workspace
  anyone opens.

### 12. A raw green glow and the leftover "NOT YET WIRED" comment — Craft

- **`static/style.css:6199` and `:8612`** — `#agent-indicator.active`:
  `box-shadow: 0 0 10px rgba(0, 255, 0, 0.3)`. A pure-green literal outside
  `:root`, and green is reserved for added/success; an agent-active indicator is
  neither. Use `var(--color-agent-active)` with a `color-mix`, or promote a
  `--color-agent-glow` token.
- **`static/style.css:307`** — the comment still says `--ease-out` / `--dur-*`
  are "NOT YET WIRED". They are wired and measured working (`:41569`). Correct
  the comment or delete it; a stale "NOT YET WIRED" in the token block invites
  the next contributor to bypass the tokens.
- *Note the honest accounting:* the note said the audit's 23 remaining offset
  values are all rings, glows, keyframes or spread tricks. That is **correct** —
  I agree, and I did not charge them.

---

## 5. What genuinely works

- **The font split.** Verified in nine surfaces, zero leaks, both faces confirmed
  loaded. This is the one thing that moved Originality and it is real.
- **The overlay model.** Scrim + blur extracted once and applied everywhere;
  Settings and the eight workspace windows now read as overlays. The best
  structural change in the iteration.
- **The elevation tokens are now actually used.** Zero single-layer elevation
  shadows at runtime, verified by audit rather than by assertion.
- **Reduced motion.** 21 blocks, `0s` durations under reduce, zero live
  animations. Never faked, never regressed.
- **Login rebuilt.** On-system, `--elevated` resolves, real focus ring, the
  topographic field now starts the product instead of a dot grid.
- **Title bars at one height** across every window.
- **Hover vs selected** is a genuine information-design fix, not a shade change.
- **Message action row and thinking disclosure** reworked into the SVG icon
  language; footer divider now a fixed full-measure rule.
- **`node --check` clean, pytest green, zero `pageerror`, zero asset ≥400, zero
  5xx, zero horizontal overflow at 375px.**

---

## 6. The one change with the highest score-per-effort for iteration 2

**Fix the two Gate items first — they are nearly free and they fail the
iteration on their own.** Issue 1 (focus trap + restore) is one `keydown`
listener on `.modal`. Issue 2 is two `var(--border)` → `var(--border-control)`
declarations plus a grep. That is under an hour and it moves the Gate from FAIL
to potentially PASS, which no amount of design work can do.

**Then, as the single highest-leverage design change, put the topographic field
back at a visible but subordinate level in the chat** (issue 4). It is not the
biggest sweep and it is not the one the Generator queued, but it is the only
change that moves **two** of the four criteria at once: Originality (0.30) and
Design Quality (0.35). The off-scale sweep is ~1,200 edits and clears a Craft
penalty whose cap is already saturated — so as a score lever it moves the
weighted total by **zero**. The field moves it by more than a full point on two
criteria. Narrow the plate to the prose measure, keep the field at strength in
the margins and around the composer, and re-run the pixel count.

Third, and nearly as cheap: issue 3. The composer should be
`rgb(43,43,43)` with `--shadow-md`. One specificity fix on a rule the Generator
already wrote correctly 6,700 lines earlier.

---

## 7. Delta vs iteration 0

### Genuinely improved (verified, not claimed)

1. **Gate 1 flipped FAIL → PASS.** `4620 passed, 3 skipped`, run independently.
2. **The mono/sans split exists at runtime.** 0 elements on both faces; baseline
   had every chrome element on Fira Code.
3. **Single-layer elevation shadows: 136 → 0** at source, **14 → 0** live.
   Baseline's "on a `#000` canvas these panels get zero separation" is fixed.
4. **Overlays dim and blur, everywhere.** The single clearest "pile of surfaces"
   signal removed.
5. **Title bars unified at 40px** (was 17 / 20 / 63).
6. **Hover vs selected genuinely separated**, by fill *and* a hue-carrying rule.
7. **Login rebuilt onto the system.** Baseline's least-designed surface is now
   the most on-system one.
8. **Native `<select>` styled** on Gallery/Calendar/Compare — verified live.
9. **Reading plate works at both viewports**, feather drops to 2% at 375 and the
   prose stays legible. Baseline's worst-case defect is gone.
10. **Off-scale values collapsed at runtime**: radii 382 decls → 33–46 live;
    font-sizes 195 elements → 1–14 live; **zero sub-11px text at 375px**.
11. **`rgba()` literals outside `:root`: 176 → 69.** Real progress from the shadow
    conversion.
12. Sidebar base plate; message action row to SVG; footer divider to a full rule;
    thinking disclosure reworked; composer input background cleaned.

### Claimed by the Generator, NOT delivered

1. **"The transcript is a plate laid on a survey table."** True for legibility,
   false for the table: the survey is not visible in the chat. 11.7% → 0.4%
   non-black pixels. Legibility was bought with the identity.
2. **"No debug labels."** Legible text: genuinely gone (I could not read any
   annotation). But the `/6` derivation left bright square specks — dust, not
   terrain — scattered across the field on the login.
3. **"Three signals, one of them a hue."** Two landed. The third,
   `--fg-strong` label ink, is absent: open and rest both measure `rgb(210,210,210)`.
4. **"A `::before`, not an inset shadow."** It is an inset shadow —
   `static/style.css:1810,1817`, measured `rgb(241,241,241) 2px 0px 0px 0px
   inset`. The outcome is defensible (I did not charge it); the claim is wrong.
5. **"Window geometry closed."** Title bars yes. Widths 520 / 640 / 760 / 780 /
   1080 and centres 720 / 744 / 860 say otherwise. The note measured Calendar
   and Settings — the two that comply.
6. **"Modals open, close on Escape, and restore — verified."** Restore does not
   happen: focus lands on `BUTTON#email-compose-btn` or an unnamed button. Focus
   is not trapped anywhere, and Settings never receives focus at all. This is a
   false claim about a Gate item.
7. **"Raw colour literals ~256 → 220."** True for hex alone (224 → 220). The note
   did not mention that `rgba()` fell 176 → 69, which is the larger win and the
   one it earned.
8. **"The scrim now covers Settings, Cookbook, Calendar, Memory, Gallery,
   Compare, Docs and Rename."** True for those. Not applied to the mobile sidebar
   drawer, which measures `pointer-events` topmost at `#chat-history`.

### Regressions introduced

1. **The chat lost its identity.** This is the one that matters. The topographic
   field was the single strongest element at baseline and the reason Originality
   was 4.5 rather than stock. It is now effectively invisible in the primary
   surface. Originality rose only because the font split arrived; the field went
   the other way. Treat this as a regression in the app's distinguishing quality,
   dressed as a legibility fix.
2. **The composer lost its elevation, to a pre-existing rule.** `:2735` sets
   `--elevated` + `--shadow-md` with a correct explanatory comment; `:41006`
   overrides it with `--bg` + `--border-subtle` + `box-shadow: none`. Whether or
   not the Generator caused it, the Generator's own comment claims it as a fix and
   the measurement contradicts that.
3. **No other regression found.** No new console errors, no new 4xx, no new 5xx,
   no broken invariant beyond the pre-existing focus trap.

---

*Evaluator note on method: every screenshot referenced above was opened and
visually inspected, not inferred from the DOM — 40+ PNGs across two viewports.
Every numeric claim is either a `getComputedStyle` measurement in the running app
or a pixel count over the rendered PNG. Confidence in the design scoring: high.
The pytest gate result is deterministic. Two limitations stated explicitly:
appearance-preference persistence cannot be tested under the harness pin, and the
`/login` route 302s with auth disabled so `static/login.html` was evaluated as a
raw static file — which is also why its inline-script CSP error is an artefact of
my access method and is not scored.*