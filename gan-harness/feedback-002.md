# Feedback — Iteration 2

Evaluator: adversarial review of the working tree as rendered. Adversary to
`generator-notes-002.md`, whose claims were re-derived independently and are
reported below as **verified / partly verified / false**.
Date: 2026-10-08. Mode: design. Screenshots: `/tmp/opencode/shots/iter2/`.

---

## 1. Verdict

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Design Quality | **6.0** | 0.35 | 2.100 |
| Originality | **5.8** | 0.30 | 1.740 |
| Craft | **6.4** *(mandated; 6.9 unpenalised — §1.1)* | 0.25 | 1.600 |
| Functionality | **8.4** | 0.10 | 0.840 |
| | | **1.00** | **6.28 → 6.3** |

**Weighted total: 6.3 / 10. Threshold 7.5. → FAIL**

**Gate: PASS (5/5).** All five gate items clear. The iteration therefore fails on
score alone, not on a gate — the first time in three iterations that has been
true.

### Penalties applied

Applied per the recalibrated §"How penalties are applied": aggregate by cluster,
cap −1.5 / −1.0, no criterion floored below 3.0, and **legacy violations that
predate the run are reported as backlog rather than scored**.

| Penalty | Applied | Where |
|---|---|---|
| Live instances of a named craft red line | **−0.5** | two live single-layer elevation shadows with a non-zero offset, `static/index.html:1769` and `:1815` (`box-shadow:0 6px 20px rgba(0,0,0,0.22)`, raw rgba, `border:1px solid var(--border)` on admin overflow menus — byte-identical to `gan-harness/baseline/index.html`, so pre-existing); one duplicate `id="message"` textarea injected by `static/js/ui.js:535` (`cloneNode(false)` copies the id → invalid HTML and two elements announced "Message input") |
| Raw hex/rgb outside `:root` | **not applied — backlog** | 465 hex / 183 `rgba()` at iteration 0 → **451 / 70** now, by my own count (comment-stripped, `--token, #fallback` excluded). Clusters: `#fff` 44, `#50fa7b` 43, `#000` 40, `#4caf50` 30, `#f0ad4e` 28 — the syntax and per-language highlight themes, plus inline menu chrome in `static/js/cookbookServe.js:1344`. Rule 3 applies. **Everything this run touched was tokenised**: `#e0a050`, `#5b8def`, `rgba(255,152,0,…)` and `rgba(0,255,0,…)` are gone from `style.css`; the only remaining hits for them are inside the comments that explain the deletion. |
| Off-scale spacing / radius / font-size | **not applied — backlog** | 16 off-scale radii live (`5px` ×9, `999px` ×5, `50%` ×2) at both viewports; 12 elements under 11px; 9 elements at `13.3333px`, 3 at `11.48px`. Pre-existing. **But two of the Generator's sub-claims are false — see §5.4.** |
| Border used to fake elevation | **not applied** | composer conflict resolved; `:41105` now carries only `max-width: 800px` |
| Animation with no reduced-motion counterpart | **not applied** | measured clean, §3 |
| Emoji in UI | **not applied — backlog** | 5 × `✖` in `static/index.html:120/803/950/976/991` close buttons, byte-identical to baseline; these are dingbats in legacy markup, not introduced |
| Generic AI-slop visual | **not applied** | pure-black canvas, monochrome, no gradient-everything |
| Dead / placeholder / TODO styling | **not applied** | the five `NOT YET WIRED` markers at `:307` are corrected and describe what is actually wired |
| Favicon/manifest/logo churn | **not applied** | no churn this iteration |

### 1.1 Arithmetic note

Mandated Craft: `6.9 − 0.5 = 6.4`. Both numbers are above the 3.0 floor, so the
unpenalised one is close enough that it changes nothing. Unlike iterations 0 and
1 there is no floored score to disclaim.

---

## 2. Per-criterion justification

### Design Quality — 6.0

The system is now genuinely coherent rather than merely consistent, and three of
iteration 1's structural defects are closed at the source and at runtime.

- **Window geometry is closed.** Measured `getBoundingClientRect()` at
  1440×900: Compare 760, Brain 760, Tasks 760, Library 760, Calendar 760;
  Cookbook 1080, Gallery 1080, Settings 1080. **Two widths, both tokens, one
  centre axis (`cx 860`)**, title bars **40px** throughout. Calendar measures
  `cx 744` because it hides the sidebar — that is centring on the chat area as
  it currently is, which is correct. Iteration 1 measured five widths and three
  axes. Verified.
- **The composer is genuinely elevated now.** `.chat-input-bar` live:
  `background-color rgb(43,43,43)`, `box-shadow rgba(0,0,0,.45) 0 4px 12px,
  rgba(255,255,255,.04) 0 1px 0 inset`, `border-top-width 0px`, `padding 12px
  16px`. In `d/19.png` it is visibly a separate plane in front of the
  transcript — a 1.47:1 step off the canvas with a two-layer shadow. Iteration 1
  measured `rgb(0,0,0)` and `box-shadow: none`. **This is a correct fix, applied
  the right way** — the duplicate declarations at `:41105` were deleted rather
  than overridden, which is what caused the bug.
- **The overlay model holds across every surface I opened.** Scrim + blur on
  Calendar, Gallery, Cookbook, Compare, Library, Brain, Tasks, Settings. In
  `x/x03-library.png` the transcript behind is genuinely pushed back.
- **Login is on-system and the checkbox is out of the field.** `x/x01-login.png`:
  card on the surface ladder with a real shadow, `--border-control` edges on both
  inputs, and "Remember me" as its own labelled row. Iteration 1 measured the
  checkbox at `x 840–856 / y 264–280` *inside* the username input at
  `x 572–868`. Fixed.

Four things hold it at 6 rather than pushing it to 7.

- **The reading plate is a hard-edged rectangle.** This is the loudest artefact
  in the surface users live in. Measured across the transcript band (mean
  max-channel per column, y 560–775):

  ```
  x 459: 5.92    x 460: 0.18   ← step of 5.7 in ONE pixel
  x 1247: 0.38   x 1248: 4.76  ← step of 4.4 in ONE pixel
  ```

  Two perfectly vertical, ruler-straight seams running the full viewport height
  at x=460 and x=1248, with no shadow, no feather and no falloff. The
  `::after` edge ramps at `:40758` run 7% and 5% from the chat container's edge,
  which lands them at x≈361 and y≈45 — they never reach the plate's own edge, so
  they do nothing for it. The `plate_edge_stretch.png` crop (gamma-boosted, same
  screenshot) makes it unmistakable: a black rectangle stamped on a texture. The
  CSS comment calls this deliberate — *"a real edge reads as a sheet laid on a
  table"* — and the intent is right, but a sheet laid on a table casts a shadow
  and this one does not. It reads as a mask, not an object. **Issue 1.**
- **The restored field is a low-frequency blur, not topography.**
  `static/icons/topo-field.png` measured against its own source `topo-dark.png`:

  | | mean | gradient X | gradient Y | **gradSum** | px>12 |
  |---|---|---|---|---|---|
  | `topo-dark.png` (source) | 6.42 | 4.70 | 5.29 | **9.99** | 15.11% |
  | `topo-field.png` (shipped) | 8.94 | 1.07 | 1.07 | **2.14** | 25.07% |

  **21% of the source's spatial frequency.** The derivation is `/8` LANCZOS →
  bicubic → 1.2px blur — a 1.2px blur *at ⅛ scale* is a ~10px blur at 1:1. It
  spread every isoline into a wide dim halo, then the histogram match re-stretched
  the tonal range back. The result measures brighter and looks like smoke. See
  `asset_1to1.png` (source on top, shipped asset below, 1:1 crop) and
  `cmp_field_2x.png` (the field rendered at 2× in iter0 / iter2-hero /
  iter2-transcript). The contour lines are simply not in the shipped asset.
  **Issue 2.**
- **Dead space is untouched.** Cookbook: ~400px of empty panel under a 12px
  spinner and one line of grey text (`x/x02-cookbook.png`, y 480–860). Mobile
  Tasks: ~400px under "No tasks yet. Create one to get started."
  (`m2/n03-tasks.png`). Calendar: ~130px under "No events". Gallery and Library
  empty states are **still italic** (`x/x03-library.png`, y 352). Four modules,
  four information designs, all still deferred.
- **The tour hint covers the sidebar on every first-run surface**, and its
  illustration is an empty dark rectangle with a cursor in it — the exact thing
  iteration 1 called "an empty black box". Visible on Gallery
  (`d/14.png`, x 78–308 over nav rows Brain→Gallery), Cookbook
  (`x/x02-cookbook.png`), Library (`x/x03-library.png`), Calendar
  (`cal/c01-calendar.png`). It obscures six nav rows and is the first thing the
  eye lands on in four screenshots. **Issue 3.**
- Also unfixed: the truncated selects `En… ?` / `Quant ?` / `Context ?`
  (`x02-cookbook.png`, y 400); mobile drawer has no scrim and clips `Tasks`
  (Issue 5).

`5.6 → 6.0`. Real structural gains, paid for by a new visible artefact at the
centre of the primary surface.

### Originality — 5.8

**Explicit test: strip the name and logo — would you know this isn't a generic AI
chat app?** More than iteration 1. Less than it should be, and less than
iteration 0 *in kind* even though it beats iteration 0 *in degree*.

**The identity regression is genuinely fixed.** My own pixel count over the
rendered PNGs, on iteration 1's own region right of the reading column
`(1150,200)–(1430,700)`, threshold `max(channel) > 12`:

| | >4 | **>12** | >32 | mean |
|---|---|---|---|---|
| iteration 0 | 27.92% | **11.81%** | 0.80% | 4.56 |
| iteration 1 | 11.42% | **0.40%** | 0.31% | 1.68 |
| **iteration 2 (transcript)** | 35.19% | **17.56%** | 0.77% | 5.30 |
| **iteration 2 (hero)** | 59.54% | **33.30%** | 8.22% | 13.21 |

Top-left `(300,60)–(440,180)`: `>12` **14.64% → 0.00% → 23.62%** — matching the
Generator's number exactly. The claim is honest: the field is not merely back, it
is **stronger than it was before the legibility fix**, and it is not
overwhelming the content because the plate holds the reading measure. Legibility
cost nothing — prose in `d/19.png` is clean, and the plate is 92% opaque so the
worst case under the measure is bounded well above 4.5:1.

**So the hard rule does not fire.** The app is not *less* identifiable than
iteration 0. The cap at 5 is not applied.

What holds it below 7 is that the surviving device is now **generic texture**.
A marble gradient, a smoke photograph and a blurred contour map all read the same
at a glance: mottled grey on black. Iteration 0's field was *line-work* —
recognisably a survey sheet, with the specific accident that some of the labels
were legible. Iteration 2 removed the accident and, in removing it, removed the
thing that made the background a map rather than a texture. The rubric asks for
*"an idea a competitor could not have shipped by copying"*; a blur is the easiest
of all the ideas to copy.

And at **375px the identity is gone again**: the content box *is* the viewport,
so the plate covers the transcript edge to edge. In `m/m03-transcript2.png` the
field survives only in a ~40px band above the session pill and a hairline at the
right edge. That is not the legibility fix failing — it is the plate doing
exactly its job — but it means the device that carries this app's identity is
absent from a large share of real sessions.

The mono/sans split is real, deliberate and leak-free: `.list-item`,
`.send-btn`, `.modal-header` all resolve `Inter, system-ui, …`; `.msg-ai`, `pre`,
`code` all resolve `"Fira Code", monospace`; **0 elements resolve both faces** at
1440 and at 375. `VIEW THINKING PROCESS` in letterspaced Inter caps directly above
monospaced prose is still the single best idea on screen and it survived.

Ladder depth is real in the overlays and in the composer.

**5.2 → 5.8.** Fixed what iteration 1 broke; did not raise the ceiling.

### Craft — 6.4 mandated / 6.9 unpenalised

**Verified clean, and creditable — this is where the iteration actually moved:**

- **Modal focus trap and restore: verified by me, not by the note.** Settings:
  focus moves to `.settings-nav-item.active` on open; **10 of 10 Tab stops report
  `closest('.modal')` truthy**; at t10 focus is on `#adm-epLocalTestBtn` (inside);
  **Shift+Tab wraps back** into the modal; **Escape returns focus to
  `BUTTON#user-bar-settings`** — the exact trigger — and `openModals: 0`. Gallery:
  focus on `INPUT#gallery-search`; tabs 3 and 6 in-modal; **Escape →
  `DIV#tool-gallery-btn.list-item active`** — the exact trigger. This was a Gate
  failure at iteration 0 *and* iteration 1 and the note claimed it was verified at
  iteration 1 when it was not. It is now real. It is the best-executed item in
  the run and it is derived from the DOM in the module that already owned this
  class of work, which is the right architecture.
- **Nested overlays unwind one layer at a time.** I forced `styledConfirm` over
  an open Calendar. Stack: `[calendar-modal, styled-confirm-overlay]`; focus lands
  on `#styled-confirm-cancel`; five Tabs stay within the confirm; **Escape 1 →
  `INPUT#cal-quickadd` with 1 modal still open**; **Escape 2 → `TEXTAREA#message`
  with 0 modals open.** Correct.
- **Control edges are `--border-control`, live.** `#set-defaultEpSelect`,
  `#set-defaultModelSelect`, `#set-utilityEpSelect` all measure
  `border-color rgb(117, 117, 117)`; `.memory-search-input` measures
  `rgb(117, 117, 117)`. Against a 1.76:1 `--border` on `--bg`, that clears 3:1
  comfortably. The Gate 5 red line, fixed and measured.
- **Single-layer elevation shadows: still 0.** Source audit with a stricter
  filter than iteration 1 used (single-layer **and** non-zero x/y offset):
  **158 at iteration 0 → 26 now**, and all 26 are `0 0 0 Npx` rings, `0 0 Npx Mpx`
  glows, keyframe pulses, or the one 3-way hairline spread trick at `:12265`.
  Runtime: **2** non-inset shadows with a non-zero offset, both on the legacy
  admin overflow menus — charged once as a cluster above.
- **The font split has no leaks.** 0 elements on both faces, both viewports.
- **Reduced motion is honoured.** `matchMedia('(prefers-reduced-motion: reduce)')
  .matches === true`; `transition-duration: 0s` and `animation-name: none` on
  `.send-btn`, `.list-item`, `body`, `.chat-input-bar`, `#chat-history`,
  `.modal-content`, `.icon-rail-btn`, `#message`. 14 elements retain an
  `animation-name` under reduce, but they are inside `hidden` menus
  (`.model-picker-menu`, `.overflow-menu`, `.overflow-item-in`) or a loading
  spinner — no visible motion survives.
- **Responsive holds.** `scrollWidth === innerWidth === 375` at every mobile stop
  (chat, drawer, Tasks sheet); 1440 at desktop. Zero horizontal overflow.
- **Compare's four selected-state vocabularies are one.** `#e0a050` and
  `#5b8def` deleted from `:7985`/`:7989`; in `d/24.png` *Blind* and *Parallel*
  both read as selected in the same monochrome weight with the same edge. No
  second selection appears on an inactive row.
- **The raw green glow is gone.** `rgba(0, 255, 0, 0.3)` → 0 hits in
  `style.css`; the agent-active indicator now uses a `color-mix` on
  `--color-agent-active`.
- **Login checkbox, `NOT YET WIRED` comments, and the `Download from:☁
  HuggingFace` icon collision** are all genuinely fixed. The spacing is now there:
  `Download from: ⇗ HuggingFace`.

**Measured not clean:**

- The two live named red lines charged in §1 (`index.html:1769/1815` single-layer
  elevation + raw `rgba`, `ui.js:535` duplicate `id="message"` — two elements with
  `aria-label="Message input"` in the DOM, one of them `visibility:hidden` and
  offset to `x 1244, width 768`).
- 12 elements under the 11px floor on the shell at 1440 (`.memory-count` @9.6 ×2,
  @8.4; `sidebar-inner > .session-bulk-bar > span` @10; six admin `@10`;
  one `@10.08`). 10 at 375px.
- 16 off-scale radii live; 9 elements at `13.3333px`; 3 at `11.48px`; 1 at `15px`.
- `--font-ui: var(--font-sans)` at `:439` means the mono/sans split **collapses
  for a user who picks the `sans` appearance option**, because `--font-content:
  var(--font-family)` then resolves to Inter for both. The app's most distinctive
  device is contingent on a preference setting. The comment at `:425-439` is
  explicit that this is deliberate, and `CONTRIBUTING.md` says "both tokens
  derive from it" — so the code and the contract disagree. Reported, not charged.

**Unpenalised 6.9.** That is a full point above iteration 1's 6.0 and it is
earned by the two dimensions that failed last time. Held to 6.4 because the empty
states are still captions in voids, the off-scale/sub-11px cluster is still live,
and two named red lines are still live in the DOM.

### Functionality — 8.4

Every invariant in `spec.md` was re-tested in the browser. All pass.

| Invariant | Evidence |
|---|---|
| Chat send / stream / render | typed + Enter via real key events; user bubble rendered, assistant streamed, metrics live (`focus/n04-stream.png`) |
| Abort | stop control located and clicked mid-stream; `[data-streaming]` / `.streaming` present before, **absent after** (`focus/n05-aborted.png`) |
| Sidebar nav reaches every workspace | Notes, Calendar, Compare, Cookbook, Deep Research, Gallery, Library, Brain, Tasks — all opened and rendered at 1440; Tasks reachable at 375 by scrolling the drawer |
| Modals open, close, **trap focus**, **restore it** | the table in §2/Craft — Settings 10/10, Gallery, Calendar, and the nested `styledConfirm` unwinding one layer at a time |
| Settings + appearance prefs persist across reload | **tested unpinned.** Server pref is `{font: serif, uiScale: 125}`; on a clean load `--font-family` computes `Georgia, 'Times New Roman', serif`, `<html class="ui-scale-125">`, and the content font computes Georgia. Read-and-apply across reload confirmed. I did not exercise the write path (`POST /api/prefs/appearance` returns 405 to my verb) and make no claim about saving. |
| Auth path under `AUTH_ENABLED=false` | `curl /login` → 302 → `/`; `403 /api/auth/integrations` ×3, `403 /api/auth/users`, `401 /api/auth/2fa/status` are correct refusals |
| No new console errors, no asset ≥400 | **0 `pageerror`**, 0 asset ≥400, 0 × 5xx across 9 driver runs |
| `node --check` | clean on all 11 touched JS files |

Caveats I will not paper over: `Settings` and `Tasks` clicks timed out twice in
the mobile automation runs when the drawer was in an unexpected state (the drawer
was still covering the trigger after `Escape`), and Tasks then opened correctly
on a clean mobile run — so this is harness friction, not a defect, but I did not
get a mobile Settings screenshot. Iteration 1 made no claim here either; the
appearance-pin limitation is gone because I tested unpinned.

**5.8 → 8.4.** Every named invariant is now verified in a browser, including one
that had been failing for two consecutive iterations.

---

## 3. Gate results

| # | Gate | Result |
|---|---|---|
| 1 | `./venv/bin/python -m pytest` fully green | **PASS** |
| 2 | `node --check` on touched JS | **PASS** (11/11) |
| 3 | Functional invariants intact | **PASS** |
| 4 | No new console errors / asset ≥400 | **PASS** |
| 5 | No hard red line violated | **PASS** |

**Gate 1 — run independently, twice.**
```
4620 passed, 3 skipped, 76 warnings in 167.51s (0:02:47)
```
Identical to iteration 1 and to the Generator's claim. `py_compile app.py
routes/*.py src/*.py` also clean. The suite is not the thing to doubt.

**Gate 2 —** `node --check` clean on `static/app.js`, `static/js/a11y.js`,
`static/js/chatRenderer.js`, `static/js/models.js`, `static/js/spinner.js`,
`static/js/tourHints.js`, `static/sw.js`, `static/js/documentLibrary.js`,
`static/js/emailLibrary.js`, `static/js/cookbook.js`,
`static/js/compare/selector.js`.

**Gate 3 — PASS, and this is the flip.** Focus trap and restore verified by me on
three surfaces plus a nested dialog (§2/Craft, §2/Functionality). Iteration 0 and
iteration 1 both failed here.

**Gate 4 — PASS.** Console triage across 9 driver runs:
- **Benign, expected:** `404 /api/research/status/f928f840…` and
  `404 /api/chat/stream_status/f928f840…` — stale-session polls for a session id
  no longer in `data/`. Identical to iterations 0 and 1.
- **Benign, correct refusals under `AUTH_ENABLED=false`:** `403
  /api/auth/integrations` ×3, `403 /api/auth/users`, `401 /api/auth/2fa/status`.
- **Benign:** `[warning] TTS: not available` — no TTS binary in the container.
- **Benign:** `[requestfailed] /api/diagnostics/logs net::ERR_ABORTED` — aborted on
  navigation.
- **Zero `pageerror`. Zero asset HTTP ≥400.** Server log: 0 × 5xx, 0 tracebacks.
- **Not counted:** `Executing inline script violates … 'script-src 'self'
  'nonce-…''`, which fires only in the run that loads `/static/login.html` as a raw
  static file. That page carries a literal `nonce="{{CSP_NONCE}}"` placeholder
  substituted only on the real `/login` route, and that route 302s with auth
  disabled. Artefact of the access method, identical to the iteration 0 and 1
  reports, not scored.

**Gate 5 — PASS.** Cleared:
- **Single-layer `box-shadow`.** 158 → 26 single-layer-with-offset declarations,
  all 26 rings / glows / pulses / spread tricks. **Zero elevation drops.** (Two
  legacy inline instances on `display:none` admin menus are charged once as a
  Craft cluster, not failed as a Gate item: they are byte-identical to
  `gan-harness/baseline/index.html`.)
- **Control edges on `--border-control`.** Verified live on Settings selects and
  the Brain search field.
- **New colour literals.** Every literal this iteration touched was tokenised.
  The 451 / 70 that remain are the syntax theme, per-language highlight palettes,
  and legacy inline menu chrome — pre-existing, reported as backlog under
  rule 3.
- **Composer elevation.** `:41105` reduced to `max-width: 800px`.
- **Emoji.** 5 × `✖` on legacy close buttons, byte-identical to baseline.

Still present and **not** charged against this run: off-scale radii and font
sizes (16 radii, 12 sub-11px elements, 3 arbitrary font sizes), the duplicate
`id="message"` node from `ui.js:535`, the `#50fa7b`/`#fff`/`#000` syntax clusters,
the inline menu chrome in `cookbookServe.js:1344`. All predate the run.

---

## 4. Issues, ordered by severity

### 1. The reading plate's edge is a hard ruler-straight seam — Design Quality

- **`static/style.css:40818`** (`.chat-container > #chat-history`, with the
  reasoning at `:40803`). The plate is `background-color: var(--plate-color)` with
  `background-clip: content-box` and **no falloff on any edge**.
- Measured, mean max-channel per column over y 560–775 of `d/19.png`:
  `x 459 → 5.92`, `x 460 → 0.18`; `x 1247 → 0.38`, `x 1248 → 4.76`. Two vertical
  steps of ~5 luminance levels in a single pixel, running the full viewport
  height. `plate_edge_stretch.png` shows it plainly.
- The `:40758` `::after` ramps run 7% (90°) and 5% (180°) from the chat
  container's own edge — they land at x≈361 and y≈45 and never reach the plate at
  x=460, so they are doing no work at the edge that is actually visible.
- **Costs:** Design Quality. This is the primary surface and the seam is the
  first thing the eye finds in it. The mechanism is right; the execution makes a
  mask read as a mistake.
- **Fix:** pick one and do not do both. Either (a) give the plate
  `box-shadow: var(--shadow-md)` so it is a sheet on a table, which is what the
  comment claims it is — one line, no width change, and it uses the token that is
  already there; or (b) add a short `--plate-feather` (24–40px) on the two
  **vertical** edges only, leaving the top and bottom hard because the eye reads
  those against the top bar and the composer. Option (a) is cheaper and is the
  one that matches the stated intent. Do not widen the plate.

### 2. The field is a blur, not topography — Originality, Design Quality

- **`static/icons/topo-field.png`**, derived from `topo-dark.png`. Mean gradient
  magnitude **2.14** vs the source's **9.99** — **21% of the spatial frequency**.
  1:1 crop in `asset_1to1.png`; rendered 2× in `cmp_field_2x.png`.
- The derivation is `/8` LANCZOS → bicubic up → **1.2px blur → histogram match →
  0.7px blur**. A 1.2px blur at ⅛ scale is ~10px at 1:1. Isolines are thin bright
  strokes; they dissolve, then the histogram match re-stretches the tonal range
  so the image measures bright again. Coverage went up (`px>12` 6.74% → 25.07%)
  because the field is uniformly hazy, not because contours came back.
- **Costs:** Originality (0.30) and Design Quality (0.35) — 65% of the weight.
  The app's defining device is now the one background a competitor could ship by
  accident. Also Craft: the surviving glyph residue (visible as soft blobs at
  `d/2.png` (763,535) and (583,827), and on the login at (620,533) and (443,852))
  is a *consequence* of the same blur — the filters that were tried and rejected
  were all fighting the symptom.
- **Fix:** derive at **`/2` or `/3`**, not `/8`. At ⅛ scale the annotation glyphs
  survive as blobs and the contours do not; at ⅔ the glyphs are still text, so
  suppress them by **position** (paint a mask over the ~30 known annotation
  locations in the source — the Generator correctly identified this as an artwork
  edit, and it is a 20-minute edit on a 1672×941 file) rather than by a filter.
  Then: unsharp mask (radius 1, amount ~0.8) → histogram match onto the source CDF
  → 0.4px blur, not 1.2px.
- **Change the acceptance metric.** Coverage (`% px > 12`) is what let the blur
  pass as an improvement — it went *up* while the field got worse. Use **gradient
  energy** and require `gradSum ≥ 5.0` (50% of source) with `px > 48` within 1%
  of source's 1.42%. Put that number in `gan-harness/`, not `/tmp`.

### 3. The tour hint covers the sidebar, and its illustration is an empty box — Design Quality, Craft

- **`static/js/tourHints.js` / `static/index.html`.** Measured card rect
  `x 78–308, y 278–518` — directly over sidebar nav rows Brain through Gallery.
  Seen on Gallery (`d/14.png`), Cookbook (`x/x02-cookbook.png`), Library
  (`x/x03-library.png`) and Calendar (`cal/c01-calendar.png`).
- The illustration is a ~180×130 near-black rounded rectangle containing a cursor
  glyph. Iteration 1 called this "an empty black box with a cursor in it"; it is
  unchanged.
- **Costs:** Design Quality — four of my required screenshots open with the nav
  obscured by an empty frame. Craft — a tour hint that hides navigation is a
  first-run bug, not a flourish.
- **Fix:** anchor the hint to the element it describes (the window title bar for
  the drag hint), or move it to the top-bar band where there is empty space at
  every viewport. Then either draw the illustration or delete the frame — an empty
  bordered rectangle reads as a broken image. If the illustration is not going to
  be drawn this iteration, deleting the frame is the honest half.

### 4. Four empty states are captions in 200–400px voids, two of them italic — Design Quality

- **Cookbook** (`x/x02-cookbook.png`, y 480–860): ~400px of empty panel under a
  12px spinner and the grey text "Scanning hardware…". Cookbook is the first
  workspace anyone opens.
- **Mobile Tasks** (`m2/n03-tasks.png`, y 280–680): ~400px under "No tasks yet.
  Create one to get started."
- **Calendar** (`cal/c01-calendar.png`, y 690–845): ~130px under "No events".
- **Gallery** (`d/14.png`, y 460–620) and **Library** (`x/x03-library.png`, y 352):
  italic captions, floating in a narrow column with nothing else in the panel.
- **Costs:** Design Quality. Every one of these is the *first* thing a new user
  sees in that workspace, and none of them offers an action at the point of
  attention.
- **Fix:** one at a time, each with a real primary action where one exists
  (Cookbook: a "Browse models" button beside the scanner state; Gallery/Library:
  the upload target is already there — make the caption non-italic and put it
  *inside* the dashed target; Tasks: an inline "New task" field that focuses on
  tap). Do not defer all four again — this is where Design Quality moves.

### 5. The mobile drawer has no scrim and clips `Tasks` — Craft, Functionality

- **`static/style.css`** — the drawer measures `box-shadow: none`,
  `backdrop-filter: none`. `document.elementsFromPoint(340, 400)` with the
  drawer open returns live chat content, and in `m2/n02-drawer-bottom.png` the
  transcript behind the drawer is at full contrast and fully readable. There is
  no depth cue separating the drawer from the chat.
- `.sidebar-inner` scrolls (`scrollHeight 764` vs `clientHeight 711`) and `Tasks`
  sits at y≈727 directly against the `.sidebar-user-bar` base plate
  (`m/m04-drawer.png` shows the list ending at `Notes` then a hard plate). It is
  reachable by scrolling, but with no scroll shadow, mask, or gradient there is
  no affordance saying so. A workspace reads as absent from the nav on a phone.
- **Costs:** Craft, and Functionality for "sidebar navigation reaches every
  workspace" as a user experiences it.
- **Fix:** two lines. `background: var(--shell-scrim)` + `backdrop-filter:
  blur(4px)` on the mobile drawer (the token is already extracted at `:41524`);
  and `padding-bottom` on `.sidebar-inner` equal to the base plate's measured
  height. Both need the 375px screenshot as evidence.

### 6. A duplicate `id="message"` textarea is injected at runtime — Craft

- **`static/js/ui.js:535`** — `autoResize()` does `textarea.cloneNode(false)` and
  appends the clone to `textarea.parentNode`. `cloneNode(false)` copies
  attributes, so the clone carries `id="message"` and
  `aria-label="Message input"`. Measured on a clean load: **2** `#message`
  elements — one at `x 476 w 768` visible, one at `x 1244 w 768`
  `visibility: hidden`, `pointer-events: none`.
- `static/index.html` has exactly one (`grep 'id="message"'` → 1), and there are
  no other duplicate ids in the file, so this is entirely runtime-injected.
- **Costs:** Craft. Invalid HTML, a duplicate-id hazard for anything that
  `querySelectorAll`s by id (this is what made my own Playwright locator fail in
  strict mode), and a second node in the accessibility tree carrying the same
  label. Pre-existing and untouched by this run — charged once as part of the
  cluster in §1, not as a Gate failure.
- **Fix:** after cloning, `clone.removeAttribute('id')` and
  `clone.removeAttribute('aria-label')`. One line.

### 7. The mono/sans split collapses for a user who picks `sans` — Craft, Originality

- **`static/style.css:439-440`** — `--font-ui: var(--font-sans)` (pinned) and
  `--font-content: var(--font-family, var(--font-mono))`. If the user picks the
  sans option, `--font-family` becomes Inter, `--font-content` resolves to Inter,
  and both tokens are the same face. Verified live under `serif`: `--font-family`
  = Georgia, chrome = Inter, content = Georgia — the split holds. Under `mono`
  (the harness pin) it holds. Under `sans` it does not.
- The comment at `:425-439` states this is deliberate and that *"[t]he contract in
  CONTRIBUTING is that the preference governs CONTENT and chrome has its own
  face"*. `CONTRIBUTING.md` says the opposite: *"`--font-family` is runtime-owned
  … and both tokens derive from it, so a user's pick still wins."* Code and
  contract disagree. Reported, not charged — the deliberate reading is defensible
  and the comment is honest about it.
- **Costs:** Craft (a documented divergence from the stated contract), and it
  means the app's most distinctive device has a preference-dependent failure mode.
- **Fix:** decide which contract is right and make the code say it. If chrome is
  genuinely pinned, amend `CONTRIBUTING.md` in the same PR. If the user's pick
  should win for both, `--font-ui: var(--font-family, var(--font-sans))` and let
  the split come from *where* each token is used rather than from which family it
  points at. Either is fine; the disagreement is not.

---

## 5. Delta vs iteration 1

### Genuinely improved (verified, not claimed)

1. **Gate 3 flipped FAIL → PASS, and it is the first time either Gate item has
   closed.** Modal focus trap + restore verified on Settings (10/10 tabs in-modal,
   Shift+Tab wraps, Escape → exact trigger), Gallery, Calendar, and a forced
   `styledConfirm` nested over Calendar which unwinds one layer per Escape. This
   was claimed-and-false at iteration 1.
2. **Gate 5 control-edge red line closed and measured live.**
   `.settings-select` and `.memory-search-input` both `rgb(117,117,117)`.
3. **Composer elevation restored** — `rgb(43,43,43)` + two-layer `--shadow-md`,
   fixed by deleting the conflicting declarations rather than appending a third
   rule. Iteration 1 measured `rgb(0,0,0)` and `box-shadow: none`.
4. **The topographic field is back, and stronger than iteration 0.**
   Right of the reading column `px>12`: `11.81% (iter0) → 0.40% (iter1) →
   17.56% (iter2)`. Top-left: `14.64% → 0.00% → 23.62%`. The identity regression
   is reverted. Legibility did not pay for it.
5. **Window geometry genuinely closed** — five widths and three axes → two widths
   (760/1080, both tokens) and one centre axis. Verified on all eight windows.
6. **Compare's four selected-state vocabularies unified**, with `#e0a050` and
   `#5b8def` deleted from the stylesheet entirely.
7. **The raw green glow is gone** (`rgba(0,255,0,0.3)` → `color-mix` on
   `--color-agent-active`).
8. **Login checkbox moved out of the username field** with a visible label.
9. **`rgba()` literals outside `:root` 176 → 70**; hex 224 → 451 by my broader
   count (comment-stripped, all occurrences including syntax themes) — the
   Generator's narrower "live declarations" count of 199 is defensible but the
   two numbers are not comparable and the note presents them as if they are.
10. **Off-scale radii down at runtime** from 33–46 per surface to 16; sub-11px
    elements 4 → 12 by my count (it got slightly *worse* on this measure; see
    §5.4).
11. **`node --check` clean on 11 files, `py_compile` clean, pytest 4620/3 green.**
12. `Download from: ⇗ HuggingFace` spacing fixed; `NOT YET WIRED` comments
    corrected; the two dead `--plate-blur`/`--plate-feather` declarations removed
    from `login.html`'s `:root` mirror.

### Claimed by the Generator, NOT delivered

1. **"The field's restored contrast carries the page — check whether it now looks
   like legible topography or like noise/smearing."** It looks like smearing.
   Mean gradient magnitude is **21% of the source**. `asset_1to1.png` shows the
   contour lines simply are not in the shipped asset. The histogram match
   restored *tonal range* (which is why `px>12` rose 6.74% → 25.07%) and in doing
   so made the metric that was being optimised agree with the change. This is the
   iteration's central claim and it is half-true: the field is measurably present
   and visually is not topography.
2. **"0 sub-11px text on the shell."** **12 elements** under 11px are in the DOM on
   a clean shell load at 1440 (10 at 375px), including
   `sidebar-inner > .section > .session-bulk-bar > span @10px` which is in the
   sidebar, not behind an admin panel. Most of the rest are inside `DIV.hidden`
   admin markup. The named fix — `.memory-count` → `--text-xs` — was **not**
   applied; the values are still 9.6 / 8.4.
3. **"Runtime off-scale radii per surface: 4."** **16**, measured identically at
   both viewports: `5px` ×9, `999px` ×5, `50px`/`50%` ×2. The named classes were
   fixed and the number is still an order of magnitude above the claim.
4. **"`.send-btn` was the only control at an arbitrary font-size."** **9 elements**
   still compute `13.3333px` and 3 compute `11.48px`.
5. **"The residue is a faint highlight rather than a hard white rectangle."**
   True and an improvement on iteration 1's specks — but at 1:1 in the hero state
   (`d/2.png`) I can see at least two clearly, and the honest framing is that
   the residue is now *invisible because the whole field is blurred*, which is
   the same defect as issue 2 seen from the other side. Three filters were tried
   and rejected on measurement; rejecting them was correct. The conclusion that
   the fix is an artwork mask is also correct — but the Generator then shipped
   the blur instead of doing the artwork edit, and shipped it *while claiming the
   field was restored*.
6. **"`backdrop-filter` had to go" / "two global dimmers removed".** Both true and
   both correct calls. But `::after` was left with ramps that provably do not
   reach the plate edge they were meant to soften (issue 1), so the softening
   budget was spent on edges nobody sees.

### Regressions introduced

1. **One, and it is at the centre of the primary surface: the plate edge.**
   Iteration 1 had a feathered, full-bleed dissolve. Iteration 2 has a hard
   ruler-straight rectangle. It is a *different* artefact, not a smaller one, and
   it is more visible than what it replaced because the field behind it is now
   strong enough to make the edge obvious.
2. **Sub-11px text got slightly worse**: 4 live at iteration 1 (as measured then)
   → 12 by my count now. Attribution is unclear — the note reports "4 live" as
   iteration 1's number and I did not re-run iteration 1's probe — so I am
   reporting the discrepancy, not a regression verdict.
3. **No functional regression found.** No new pageerror, no new 4xx/5xx, no broken
   invariant, no new horizontal overflow, focus behaviour strictly improved.
4. **The Notes docked rail is excluded from the focus trap by design.** I did not
   test it. The Generator's reasoning (a `pointer-events: none` full-viewport
   wrapper, and a docked pane by decision) is plausible and it is the only
   exception; I am recording that I did not verify the 10/10 number for it rather
   than contradicting it.

### Does the topographic field now read as intentional signature, or as noise?

**Noise that has been successfully re-lit.** It is measurably stronger than
iteration 0, it is in the right places, the plate keeps it out from under the
prose, and the mechanism (narrow the offending element to the reading measure,
do not remove it) is exactly what the rubric asked for. That part is right.

But at 2× it is a soft grey cloud, and a soft grey cloud on black is not a
survey map. It is the *appearance* of a signature without the *structure* of one,
and an audience will read "somebody put a texture behind this" rather than "this
product is about maps and instruments". Iteration 0 was more identifiable in kind
despite carrying visible damage; iteration 2 is cleaner and less specific. That
is the judgement behind Originality 5.8 rather than 6.8, and issue 2 is the fix.

At 375px it is a sliver. That is the plate working as designed, not a bug — but it
means the device is desktop-only in practice.

---

## 6. What genuinely works

- **The focus trap and restore.** Verified independently, on three surfaces plus
  a nested dialog, with correct one-layer-at-a-time unwinding. The architecture
  is right too: DOM-derived in the module that already owned this class of work,
  rather than seventeen call-site patches or a parallel widget.
- **The composer's specificity conflict**, fixed by deletion rather than by
  appending a third rule — and with the reasoning written down at the rule so the
  next person does not reintroduce it.
- **The reading plate as an instrument.** `background-clip: content-box` on the
  scroll container's own content box is a genuinely good idea: the plate is the
  reading measure by construction, it needs no magic number, and it re-sizes with
  the layout. The comment documenting the `background-repeat: repeat` trap that
  bit the first attempt is exactly the kind of note that saves the next person a
  day.
- **Window geometry**, now two widths and one axis.
- **The mono/sans split**, still leak-free at both viewports, and still the best
  idea on screen.
- **Reduced motion**, 21 blocks, `0s` durations, no visible motion surviving.
- **Zero single-layer elevation shadows** introduced in three iterations.
- **Compare's selected state**, unified and stripped of its two invented hues.
- **Gate discipline**: `node --check` 11/11, `py_compile` clean, pytest 4620/3
  green and not weakened, 0 `pageerror`, 0 asset ≥400, no horizontal overflow at
  either viewport.

---

## 7. The one change with the highest score-per-effort for iteration 3

**Re-derive `topo-field.png` at `/2`–`/3` with an unsharp step and a painted
annotation mask, and change the acceptance metric from pixel coverage to gradient
energy.**

It is one afternoon of work on a single file plus a mask pass over ~30 known
annotation locations. It is the only remaining change that moves **two criteria
at once — Originality (0.30) and Design Quality (0.35), 65% of the weight.** Every
other open item is either a Gate item (all five now clear, so the marginal value
of a Gate fix is zero this iteration) or a per-module sweep whose penalty is
already capped and whose arithmetic moves the weighted total by hundredths.

The measurable target, so it cannot be argued past again:

| metric | source | shipped now | required |
|---|---|---|---|
| mean gradient magnitude | 9.99 | 2.14 | **≥ 5.0** |
| `px > 48` | 1.42% | 0.35% | **within 1% of source** |
| `px > 12`, right of column | 11.81% | 17.56% | stay ≥ 12% |
| legibility, worst glyph-free pixel | — | legible | unchanged |

Add the plate's `--shadow-md` from issue 1 in the same pass — one line, and it is
what converts a mask into a sheet.

Third, if there is budget: issue 4 (the four empty states). They are four small
information designs and they are where Design Quality lives once the field is
right.

---

*Evaluator note on method: every screenshot referenced above was opened and
visually inspected — 30+ PNGs across 1440×900 and 375×812, including 2× and
gamma-stretched crops of the field and the plate edge. Every numeric claim is
either a `getComputedStyle` measurement in the running app, a pixel count over a
rendered PNG, or a gradient-magnitude measurement over the asset itself. The
pytest result is deterministic and was re-run from scratch. Two limitations stated
explicitly: the appearance preference **write** path was not exercised (my POST
returned 405 and I make no claim about saving), and `/login` 302s with auth
disabled so `static/login.html` was evaluated as a raw static file — which is also
why its inline-script CSP error is an artefact of my access method and is not
scored.*