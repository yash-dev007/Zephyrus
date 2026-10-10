# Generator Notes — Iteration 1

Date: 2026-10-08. Generator, GAN design harness. Baseline: `feedback-000.md` (3.7 / 10, Gate FAIL).

Everything below was verified in the running app against `127.0.0.1:7000` and read
back from the PNGs, not inferred from the DOM.

---

## 1. Gate failures — both closed first, before any aesthetic work

### Gate 1 — `pytest` is red → **PASS**

`tests/test_new_chat_model_preference.py:40` slices `static/app.js` between the marker
`// Logo click → new chat` and `const sidebarNewChatBtn = el('sidebar-new-chat-btn');`.
The marker was gone. I did **not** edit the test.

The comment was not restored as a bare string — the handler it names was **built**.
`static/index.html` gained a product mark tile in the sidebar header
(`#sidebar-brand-btn`, `static/icons/Zephyrus-Mark.png`) and `static/app.js:3237`
gained the handler behind the marker, on the same `_handleNewChatAction()` path as
every other new-chat affordance. The sidebar had no identity and no top anchor; this
kills two birds. Clicking the mark starts a new chat, which is what the comment has
always claimed.

`tests/test_design_tokens_brutal.py` was treated as the spec throughout — it pins
`.msg-ai { background: var(--bg) }`, `.msg-user { background: var(--surface-1) }`, the
`.msg-footer` hairline, `#sidebar-toggle-btn { display: none !important }`, and
zero `box-shadow` in the tail that is not a `--shadow-*` token. I reverted one of my
own designs (assistant bubble → transparent) because a test pinned it.

```
tests/test_new_chat_model_preference.py .... 2 passed
```

### Gate 5 — single-layer shadows + login literals → **PASS**

**128 elevation drops converted** to the two-layer `--shadow-sm/md/lg` tokens, plus
5 more that were a drop combined with a ring (`minimized-dock-chip`, its long-press
pulse, `chip-active`, and two Cookbook clear buttons). Rings (`0 0 0 2px …`), glows
(`0 0 10px …`), `@keyframes` pulses and the `.notes-quick-add` spread trick were left
alone — they are not elevation shadows and forcing them through a token would be
wrong.

Audit after: **0 single-layer elevation drops remain.** The 23 offset-bearing values
left in the file are all `0 0 0 Npx` selection rings, `0 0 Npx Mpx` soft glows, four
keyframe pulses, or two spread tricks.

`static/login.html` rewritten onto the system: stale `#697782` `--border-control` →
`#757575` (matching `style.css`); `.card` was `--panel` + `1px solid var(--border-control)`
+ `box-shadow: none` (a border faking elevation) and is now `--surface-2` + `--shadow-lg`
+ no border; `h1 { font-size: 32px }` → the logo; `padding: 12.2px 11.2px 10.2px` →
`var(--space-3) var(--space-4)` (the 1px optical nudge is why "Sign In" sat
off-centre); inputs `15.2px` → `--text-md`. Added Inter `@font-face` and a
`prefers-reduced-motion` gate — the login spinner was infinite with **no** gate.

---

## 2. Feedback items closed

### Issue 2 — the transcript has no surface → **CLOSED**

This was the loudest defect. The topographic field ran at `opacity: 0.9` with a flat
`rgba(0,0,0,0.3)` wash directly behind body copy.

The fix is compositional, not a dimmer. **The transcript is now a plate laid on a
survey table** (`static/style.css` §1):

- the scrim is a `radial-gradient` centred on the reading column instead of a flat
  wash, so the field's contrast budget is spent where nothing is read and kept out of
  the prose. A flat wash only made the field greyer; a gradient makes it produce
  hierarchy.
- `#chat-history` carries the plate: a `linear-gradient(90deg, transparent, --bg 92%,
  --bg 88%, transparent)` with `backdrop-filter: blur(10px)`. Solid at the reading
  measure, dissolving at both edges. It sits on the scroll container's own background
  rather than a pseudo-element, so there is no stacking contest with the message nodes
  — an element's own background always paints beneath its in-flow children.
- the welcome state opts out (`.welcome-active`): no plate, field at full strength. The
  hero is the one surface where the terrain is the subject.
- at ≤768px the feather drops to `2%` — at 375px a 12% dissolve is 45px, wide enough
  to push a bubble back off the plate onto live contours, which is the defect the plate
  exists to remove.

Measured: `background-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, color(srgb 0 0 0
/ 0.92) 12%, … 88%, rgba(0,0,0,0) 100%)`, `backdrop-filter: blur(10px)`.

### Debug residue in the field → **CLOSED** (the "2s456 / mo 731 / sneha" labels)

The source artwork `topo-dark.png` is a real survey sheet carrying real map
annotations. At render size they were legible enough to read as leftover shader debug
text.

Rather than repaint the field (and destroy the identity) or delete it, I derived
`static/icons/topo-field.png`: `topo-dark.png` through a **1/6 mipmap round trip**
(Lanczos down, bicubic up). Contour lines are long connected strokes and survive a
downscale; annotation glyphs are small isolated blobs and dissolve into unresolvable
smudges. Same landscape, no legible labels. I compared `/6`, `/8` and `/10` crops at
1:1 and picked `/6` as the point where labels are gone but contours are still clearly
contours. `topo-dark.png` stays in the repo as the source artwork.

### Issue 3 — chrome on the content font → **CLOSED** (the mono/sans split is real)

Root cause found and fixed at the token, not with 500 selectors:

```css
body { --font-ui: var(--font-family, var(--font-sans)); }   /* was */
body { --font-ui: var(--font-sans); }                        /* now */
```

`--font-family` is runtime-owned and the appearance preference wrote it to
`'Fira Code', monospace`, so `--font-ui` resolved to Fira Code and **Inter was dead
code** — the split did not exist at runtime. The contract is that the preference
governs *content*; chrome has its own face. The runtime writer's contract is untouched:
it still sets `--font-family`, and `--font-content` still follows the user's pick.

Then the split was inverted so it holds everywhere at once: **chrome is the default**
(`body { font-family: var(--font-ui) }`) and **content opts in** (§12) — transcript,
`pre`/`code`/`kbd`/`samp`/`.hljs`, logs, diffs, and text fields on `--font-content`;
modals, settings rows, dropdowns, toasts and message action controls on `--font-ui`.
A message is a document, so its prose is monospaced — but the controls sitting *on*
that document are chrome, or a transcript would be punctuated by proportionally-spaced
buttons.

Verified that both faces actually load first (`document.fonts` → Inter 400/500 and
Fira Code 400/600 loaded; the container has no system Inter, the repo self-hosts it).

Measured before → after: `body`, `.list-item`, `.send-btn`, `.settings-nav-item` all
`"Fira Code"` → now `Inter, system-ui, …`; `.msg-ai` stays `"Fira Code", monospace`.

### Issue 5 — hover and selected were the same state → **CLOSED**

Hover was `color-mix(--fg 7%)`, which lands on top of `--surface-3` — the fill the
*open* workspace used. Now: hover is a quiet `--surface-2` lift with no accent
anywhere; the open workspace is the only thing in the rail carrying accent ink, and it
carries it as a **2px `--accent-ink` rule in the gutter** (a `::before`, not an inset
shadow — `test_tail_shadows_are_two_layer_tokens_or_none` forbids non-token shadows in
the tail, and an indicator belongs on its own element anyway) plus `--surface-3` plus
`--fg-strong` label ink. Three signals, one of them a hue, so the state survives a
still frame and a greyscale print.

Evidence, one still with Notes open and Brain hovered
(`/tmp/opencode/shots/gen1-nav2/nav-states.png`):

```
open   (Notes)  bg=rgb(27,27,27)  fg=rgb(241,241,241)  marker=2px/rgb(241,241,241)
hover  (Brain)  bg=--surface-2    fg=rgb(210,210,210)  no marker
rest   (Gallery) bg=transparent   fg=rgb(210,210,210)  no marker
```

### Issue 6 — login was off-system → **CLOSED**

Card on a ladder rung with a real two-layer shadow and no hairline; the app's own
`Zephyrus-Logo.png` (dragon + wordmark) instead of a letterspaced gradient-clipped text
wordmark; Inter for chrome, Fira Code for the fields; `--border-control` corrected;
symmetric on-scale padding.

**The identity now starts on the login screen.** The page carried a 20px dot grid —
the one background in the product related to nothing else — and now carries the
topographic field with the same radial scrim as the chat. It is deliberately
*unconditional*: it used to hang off `body.bg-pattern-dots`, a class only an inline
script adds, so a CSP nonce that failed to substitute left the login with no background
at all. (I hit exactly that while testing.)

### Issue 7 — five widths, four centre axes, three title bars → **CLOSED**

Three new tokens — `--window-w` (760px), `--window-w-wide` (1080px), `--window-title-h`
(40px) — plus one rule set that centres the window and pads its title bar. Cookbook,
Gallery, Compare and Settings opt into the wide measure explicitly. Measured after:
Calendar **760px, centre 744, title bar 40px** (was 17px); Settings **1080px, centre
744, title bar 40px** (was 63px).

### Issue 8 — overlays had no scrim → **CLOSED**

`.modal` now gets `--shell-scrim` (55%) + `backdrop-filter: blur(4px)`, and the panels
sit above it on `--surface-2` + `--shadow-lg`. The command palette was the only
surface that dimmed and it was the best-composed overlay in the app; the rule is now
extracted so Settings, Cookbook, Calendar, Memory, Gallery, Compare, Docs and Rename
all behave the same way. Calendar at 1440×900 is now the reference frame.

> A docked window (Notes, right-rail) deliberately does **not** dim — the chat stays
> usable beside it — so it gets a ladder rung and shadow instead of a scrim.

### Issue 9 — native unstyled `<select>` in five workspaces → **CLOSED**

`appearance: none`, `--surface-1` well, `--border-control` edge (it is a control
boundary, so 1.4.11 applies, not `--border`), `--radius-sm`, Inter, and a dark option
list. The caret is **two rotated half-squares** rather than an inline SVG background:
an SVG in `url()` cannot read a token for its stroke, so it would have to hardcode a
colour, and a hardcoded colour is exactly what the design system forbids outside
`:root`.

Two module rules (`.gallery-model-filter/.gallery-sort`, and six more that re-declared
the whole control at class specificity, beating a bare `select`) had their duplicated
chrome removed rather than fought with `!important`. Measured on `#gallery-sort`:
`appearance: none`, `background-color: rgb(12,12,12)`, `border-color: rgb(117,117,117)`,
the two-gradient caret, `font-family: Inter`.

### Also closed

- **Message action row** — the row was Unicode dingbats (`✎ ✕ ⋯ ↻ ✲ ⊕ ?`) set as
  `textContent` at `--text-xl`: three stroke weights, three optical sizes, and the only
  non-SVG marks in a UI whose icon language is monochrome SVG. Replaced with the app's
  own 12px stroke set in `chatRenderer.js`, reusing the `html: true` path that
  `COPY_ICON` already used. Footer separators normalised from a mix of `|` and `·` to
  `·`.
- **Partial-width divider** — `.msg` is a flex column with `align-items: flex-start`
  (flex-end on the user side), so `.msg-footer` was shrink-to-fit and its `border-top`
  drew a rule only as wide as the content beside it. `align-self: stretch` makes it the
  full-measure rule it was always meant to be.
- **Thinking-process disclosure** — a full-width bordered box with a rotated triangle in
  a chip, which is pixel-for-pixel the silhouette of a native `<select>`. Now a
  micro-label in the same uppercase letterspaced register as the sidebar section
  titles, chevron beside the label (it was at `space-between`, 640px from its own
  label), zero inline padding so it shares the prose column's left edge.
- **Tour-hint illustration** (issue 16) — 160×96 with `stroke-opacity: 0.18` and the
  dragged window filled `--bg`. Now 200×120, frame at 0.4, window on `--surface-3`,
  and `--fg-subtle` instead of `--accent-ink`. I first tried 240×144 as the feedback
  suggested; the canvas scales its strokes, and the diagram became the loudest object
  on screen — a hint has to be quieter than the window it annotates.
- **Sidebar void** — the rail ended on a list and then ~270px of nothing before an
  unmarked user bar. Closed with a base plate (`--surface-1` + a divider, which is what
  a border is *for*), so the empty middle is negative space inside a framed column.
- **Spacing scale completed** to `--space-1 … --space-10` (issue 14's root cause).
  `--space-5/6/7/9/10` did not exist, which is *why* so much of the stylesheet had to
  spell 20/24/28/36/40px as a literal.
- **Standalone hex literals outside `:root`**: ~256 → **220** (ceiling 477).

---

## 3. Deliberately deferred

| Feedback | Why |
|---|---|
| **14 — the off-scale sweep** (382 radii, 195 font-sizes, 1170 padding/gap) | Root cause (the missing scale steps) is fixed, which unblocks it. Finishing the sweep is ~1,200 mechanical edits across every module; doing it badly is worse than not doing it. **First thing for iteration 2**, ideally as its own slice. |
| **1 — raw colour literals** | 220 hex + 79 rgba remain, concentrated in Cookbook / Gallery / Calendar / image-editor per-module palettes. The largest single cluster (`#fff` 43, `#000` 40) is mechanically sweepable; the rest are genuine per-feature colours that belong in `:root` as named tokens, one decision each. |
| **12 — empty states** (Notes/Brain/Library/Gallery float in 150–200px voids; Gallery + Library copy is *italic*) | Real, and cheap per surface, but four modules and I would rather land four correct ones than four rushed ones. Gallery's italic is a one-liner. |
| **11 — clipped rows with no scroll affordance** (Tasks "Email Tags", Settings "Sidebar" header) | Needs a scroll-shadow/mask on each scroll container; per-module. |
| **13 — `#doclib-search` styled by `.memory-search-input`** | Renaming a primitive used by two surfaces. Low visual return, real divergence risk. |
| **15 — `--accent` is monochrome, not the documented ice-blue** | This is a *contract* decision, not a design fix: either restore ice-blue or amend `CONTRIBUTING.md:93`. I left the tokens alone because changing the accent hue this late would recolour every surface I have not yet screenshotted, and the evaluator called monochrome "a defensible decision". Needs the maintainer's call. |
| **10 — Cookbook's truncated `Qu… ?` / `Context ?` labels** | Confirmed real. Fixing it means finding the truncation in `cookbook.js` and choosing real label text — an information decision per field. |
| **Nine-workspace verbatim sweep** | Six workspaces screenshotted (chat, Notes, Calendar, Gallery, Cookbook, Compare) + Settings + search + login. Cookbook and Brain were opened but not inspected in a still; they inherit the window geometry but have module-specific interiors I have not audited. |

---

## 4. Checks run, with real output

```
$ ./venv/bin/python -m pytest
=========== 4620 passed, 3 skipped, 76 warnings in 175.21s (0:02:55) ===========
```
Baseline was `1 failed, 4619 passed, 3 skipped`. **Gate 1 flipped FAIL → PASS.**
Run three times during the iteration; 4620/3 on every run.

```
$ node --check static/app.js              OK
$ node --check static/js/chatRenderer.js  OK
$ node --check static/js/tourHints.js     OK
```

Shadow audit: **0** single-layer elevation drops remain (from 133).

Console log, full run (`/tmp/opencode/shots/gen1-final/console.log`) — **zero
`pageerror`, zero asset HTTP ≥400**, and the console set is identical to the
baseline's:
- benign, expected: `404 /api/chat/stream_status/6b1817af…`, `404 /api/research/status/6b1817af…` (stale-session polls for a session id no longer in `data/`)
- benign under `AUTH_ENABLED=false`: `403 /api/auth/integrations`, `403 /api/auth/users`, `401 /api/auth/2fa/status`
- benign: `[warning] TTS: not available`; `ERR_ABORTED` on `/api/diagnostics/logs` (aborted on navigation)

Computed evidence for the craft claims:
```
body / .list-item / .send-btn   Inter, system-ui, -apple-system, "Segoe UI", sans-serif
.msg-ai                         "Fira Code", monospace
control edge (.model-picker-btn) rgb(117,117,117)          = --border-control
shadow (.sidebar-brand)         rgba(0,0,0,.4) 0 1px 2px, rgba(255,255,255,.03) 0 1px 0 inset
scrim (.modal)                  color(srgb 0 0 0 / 0.55) + blur(4px)
```

Functional invariants, exercised in-browser:
- chat send / streaming / abort — transcript renders, metrics live
- sidebar navigation reaches every workspace — Notes, Calendar, Gallery, Cookbook,
  Compare, Brain, Library, Tasks all open and render
- modals open, **close on Escape**, and restore — verified for Notes
  (`notesGone: true`), Calendar (`calGone: true`) and Settings (`class="modal hidden"`)
- settings + appearance prefs — untouched; the harness pins `/api/prefs/appearance`, so
  persistence is **not** claimed here, same as the baseline
- auth path — `/api/auth/*` correctly refuses under `AUTH_ENABLED=false`
- responsive: `scrollWidth === innerWidth === 375` at 375×812, no horizontal overflow,
  drawer / sheet / settings sheet all render

Evidence: `/tmp/opencode/shots/gen1-final/` (1440×900: chat, Calendar, Settings,
search), `gen1-nav2/` (open vs hover), `gen1o/` (375×812 chat, drawer, Tasks sheet,
Settings sheet), `gen1s2/` (login).

> Note on method: I spent part of this iteration chasing a "regression" where Escape
> stopped closing modals. It was a harness artefact — `shot.mjs` implements `press`,
> not `key`, so my `{"action":"key"}` steps were silent no-ops and the panels stacked.
> `press` verified clean on all three. Worth knowing for iteration 2.

---

## 5. What I would do next

1. **The off-scale sweep**, as one dedicated slice. The scale is closed now, so it is
   mechanical: 382 radii → 6/8/12/999, sub-11px text → `--text-xs`, the 1,170
   padding/gap values onto the grid. This is the largest remaining Craft penalty and
   it is the one thing I could not do partially.
2. **The colour-literal sweep**, in two passes: mechanical (`#fff`/`#000` → tokens)
   first, then promote each surviving per-feature palette into `:root` as a *named*
   token so Cookbook/Gallery/Calendar stop owning private hues.
3. **Empty states and scroll affordances** — four small, self-contained surfaces.
   Each needs one concrete primary action and a real baseline, not a caption floating
   in a void.
4. **The `#red` deprecation.** The `:root` comment says "treat any remaining
   `var(--red)` as a bug once that lands." That is a real migration and it would
   retire a named alias rather than add one.
5. **Composition, not polish** — the shell now has a focal point (the mark tile), a
   substrate (the survey field under a reading plate) and a frame (the sidebar base).
   What it still lacks is a *third* moment of the kind the topographic field is:
   something in the composer or the top bar that could not have been shipped by copying
   a competitor. The field and the mono/sans split are two; the rubric's ladder-based
   depth is three and is currently just good hygiene rather than an idea.
6. **Confirm the maintainer's call on `--accent`** (issue 15) before iterating further —
   a hue change now would invalidate a chunk of the evidence I have gathered.
