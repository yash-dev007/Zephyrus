# Feedback — Iteration 0 (Baseline)

Evaluator: adversarial review of the working tree as rendered. No Generator has run.
Date: 2026-10-08. Mode: design. Screenshots: `/tmp/opencode/shots/iter0/`.

---

## 1. Verdict

| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Design Quality | **4.1** | 0.35 | 1.435 |
| Originality | **4.5** | 0.30 | 1.350 |
| Craft | **1.0** *(floored — see arithmetic note)* | 0.25 | 0.250 |
| Functionality | **6.5** | 0.10 | 0.650 |
| | | **1.00** | **3.685 → 3.7** |

**Weighted total: 3.7 / 10. Threshold 7.5. → FAIL**

**Gate: FAIL** (items 1 and 5). Any single gate failure fails the iteration regardless
of the weighted score, so iteration 0 fails twice over.

### Penalties applied

| Penalty | Applied | Where |
|---|---|---|
| Raw hex/rgb outside `:root` (max −3) | **−3.0** | 662 literal occurrences at `static/style.css:343+` |
| Off-scale spacing / radius / font-size (max −2) | **−2.0** | 382 off-scale `border-radius` decls; 195 elements at off-scale `font-size`; 1170 elements at off-scale padding/gap |
| Border used to fake elevation (max −2) | **−0.5** | one cluster: `static/login.html:19` card + Cookbook cards |
| Emoji in UI | not applied | the "☺" in empty states is SVG (`static/js/memory.js:698`, `static/js/notes.js:1947`), not a Unicode emoji |
| Animation with no reduced-motion counterpart | not applied | measured clean — see §3 |
| Generic AI-slop visual | not applied | the topographic field is a deliberate identity, not default greys |
| Dead/placeholder/TODO styling | not applied | `static/style.css:337` says "NOT YET WIRED" for `--ease-out`/`--dur-*` but consumers exist (e.g. `static/style.css:1508`) |

### Arithmetic note — the Craft penalty table does not fit a 41k-line stylesheet

The mandated Craft arithmetic is `5.2 − 3.0 − 2.0 = 0.2`, which floors at **1.0**.
A 1.0 is defined as "Broken layouts, missing states, no motion, lost focus, layout
shift" — **none of which is true of this app.** So the floor is an artefact of the
penalty table's maxima being calibrated for a single small diff, not a whole
stylesheet.

I report the mandated number (1.0, floored) because the rubric is the contract, but
the operator should read **Craft ≈ 4.5–5.0 unpenalised** as the true signal. For
reference, the *unpenalised* weighted total would be `4.6×.35 + 4.5×.30 + 5.2×.25 +
6.5×.10 = 5.1`. Either way the verdict is FAIL and the Gate is FAIL.

Fair split of the 662 literals outside `:root`, so the Generator knows where the
volume is: **261** are `var(--token, #fallback)` defensive fallbacks (the token wins
when defined — not a bypass); **145** are `rgba(0,0,0,α)` alpha-of-black shadow
drops; the remaining ~256 are genuine standalone literals.

---

## 2. Per-criterion justification

### Design Quality — 4.1

There *is* an identity here and it is not stock: a pure-black canvas
(`--bg: #000000`), a near-white accent (`static/style.css:119`), a topographic
contour field as ambient background, and a consistent floating-window-per-workspace
metaphod. `d-02-notes` through `d-08-brain` show the metaphor holding: Brain, Tasks,
Cookbook, Gallery, Library, Calendar and Compare all present as windows with a title
bar and window controls. That is a real concept, applied consistently enough to be
read as intent.

It falls apart on execution across surfaces.

- **No window geometry.** Five different widths and four different centre axes:
  Cookbook centred at x≈720, Calendar at x≈744, Brain at x≈863, Tasks at x≈861,
  Gallery at x≈860, Library at x≈859 (`d-04`…`d-08`). Three different title-bar
  heights: Cookbook 17px, Compare 20px, **Settings 63px** (`d-07` vs `d-09`). Nothing
  is on a grid. This is the "pile of surfaces" end of the rubric, not the
  "one deliberate piece of work" end.
- **The primary content surface has no surface.** The topographic field runs at full
  strength directly behind the transcript (`d-01`, `m-01`). There is no scrim, no
  plate, no `--bg`-derived surface behind body copy. The main thing a user reads all
  day sits on noise. At 375px it is worse — the contours are packed so densely the
  transcript reads as texture (`m-01`).
- **The field has debug residue baked in.** Stray labels sit inside the contour art:
  "2s456", "mo 731", "sneha", "4s4478", "73s33" — visible in `d-01`, `d-02`, `m-01`.
  They read as an unfinished shader debug view, not as an intentional map.
- **Hover and selected are the same state on the primary nav.** `hov-tools-3` shows
  Cookbook hovered with a flat `--surface-3` fill at 6px radius — pixel-identical to
  the fill used for the *currently open* workspace (`d-13` Compare, `d-08` Brain).
  The user cannot tell which of nine workspaces is open.
- **Four selected-state vocabularies inside one panel.** `d-13` Compare: "Blind"
  selected = gold fill + gold border (`static/style.css:7914`); "Parallel" selected =
  blue border; "Chat" selected = white border; "Save" = nothing. Three hues, three
  treatments, no rule.
- **Overlays that are not overlays.** Settings, Notes and the workspace windows sit on
  the busy background with **no scrim** (`d-09`, `d-10`, `d-02`) — the chat transcript
  and the topographic field are at full contrast right up to the panel edge. The
  search overlay (`d-12`) is the *only* one that dims and blurs, and it is by a wide
  margin the best-composed surface in the app. That contrast is the whole finding.
- **Dead space.** Sidebar is ~45% void (`d-01`, y≈580–850). Calendar has 160px of
  empty panel below the fold (`d-04`). Cookbook has ~320px of empty panel under a
  12px spinner (`d-07`). Notes/Brain/Library empty states float in 150–200px voids.
- **Clipping without a scroll affordance.** The Tasks list bisects the "Email Tags"
  row at the panel edge (`d-03`); the Settings panel bisects the "Sidebar" section
  header (`d-10`). Both look broken rather than scrollable.
- **Login is off-system** — see §4, issue 6.

Penalties: border-faking-elevation −0.5 (login card; Cookbook's `Direct Download` /
`Scan / Download` cards in `d-07` carry borders *and* a surface).

### Originality — 4.5

The originality test: strip the name and the logo — would you know it wasn't a generic
AI chat app? **Yes, and the reason is the topographic field.** `d-01` and `m-01` are
genuinely unlike a ChatGPT clone. That is a real creative decision and it is the
single strongest thing in this run.

The rubric names three carriers of a 7–8 score: *"the topographic field, the mono/sans
split, the ladder-based depth."* Measured, only one of the three is actually present.

- **Topographic field — present.** Strongest element. But it is decoration for its own
  sake: it aids no navigation and no hierarchy, and it measurably degrades transcript
  legibility. The rubric requires that original ideas *earn* their place.
- **Mono/sans split — absent at runtime.** This is the most consequential measurement
  in the run. `--font-ui` resolves to `'Inter', system-ui, …` and `--font-content` to
  `'Fira Code', ui-monospace, monospace`, but **every chrome element measures
  `"Fira Code"`**: `#tool-notes-btn span.grow`, `.list-item`, `.settings-nav-item`,
  `.send-btn`, and `body` itself. The cause: `--font-family` is runtime-owned and set
  to `'Fira Code', monospace` by the mono preference, `body` uses it directly, and
  `--font-ui` is never overwritten — so Inter is dead code. The tokens exist and the
  *correct* pattern is used elsewhere (`static/js/tourHints.js:6563`,
  `.tour-hint-dismiss { font-family: var(--font-ui); }`), which proves the token is
  live and simply not applied to navigation, buttons, or labels. Result: the app has
  no font split at all, and chrome and content read as one undifferentiated texture.
- **Ladder-based depth — undermined.** `--shadow-sm`/`--shadow-md` are correctly
  two-layer (measured: each contains exactly 1 `inset`). But **256 `box-shadow`
  declarations lack an `inset`** and **14 are live at runtime**, including `.sidebar`
  itself (`rgba(0,0,0,0.1) 0 4px 12px`), `.dropdown`, `.export-dropdown-menu`,
  `.overflow-menu`, `.search-popup`. On a `#000` canvas a black drop is a **no-op** —
  these panels get zero separation from the background. The ladder is not doing the
  work the tokens describe.

The remainder is convention: right-aligned user bubbles, left-aligned assistant, a
`tok/s | copy | × | ⋯ | %` meta row, a top search field, a `Recent / Select / Tidy`
chip row. All stock. One strong idea plus two absent carriers lands at 4.5 — above
"some customisation", short of "clear creative vision … used deliberately."

### Craft — 1.0 (floored; ~4.5–5.0 unpenalised)

**What is measurably right, and must be credited:**

- **Reduced motion is genuinely correct.** With `prefers-reduced-motion: reduce`,
  `getComputedStyle` returns `transition-duration: 0s` for `.send-btn`, `.list-item`,
  `body`, `.icon-rail-btn`, `.msg-ai`, `.rail-hover-label`, `.section-header-flex`.
  20 `prefers-reduced-motion` blocks exist in `static/style.css`. Only 14 elements
  retain any `animation-name`, and they are unreachable states. This is the single
  best-executed requirement in the codebase and it satisfies the CONTRIBUTING
  contract.
- **Both shadow tokens are two-layer.** `--shadow-sm: 0 1px 2px rgba(0,0,0,.4),
  inset 0 1px 0 rgba(255,255,255,.03)`; `--shadow-md` likewise.
- **`--border-control` exists and clears the bar**: `#757575`, 4.56:1 on `--bg`.
- **Responsive holds.** Zero horizontal overflow at 375×812 (`scrollWidth === innerWidth
  === 375`); drawer, Tasks sheet and Settings sheet all render correctly (`m-02`,
  `m-03`, `m-04`).
- **`node --check` clean on all 12 JS files** rendering the surfaces I audited.
- Motion resolves through `--dur-*` / `--ease-out` (`static/style.css:1508`).

**What is measurably wrong — every named craft failure in the rubric is present:**

| Named failure | Measured evidence |
|---|---|
| Chrome on `--font-content`, code on `--font-ui` | `.list-item`, `.settings-nav-item`, `.send-btn`, `#tool-notes-btn span`, `body` all `"Fira Code"` |
| Single-layer `box-shadow` | 256 declarations, 14 live, all `rgba(0,0,0,α)` — invisible on `#000` |
| Off-scale `border-radius` | **382 declarations** using 1,2,3,4,5,7,9,10,11,14,18px against a 6/8/12/999 scale |
| Off-scale `font-size` | **195 elements at runtime**, 13 below the 11px floor — `.memory-count` at 9.6px and **8.4px** |
| Off-scale `padding`/`gap` | **1170 elements at runtime**; `.section-header-btn { padding: 1px 3px }` (`static/style.css:1506`), `#doclib-search { padding-left: 28px }` |
| Raw hex/rgb outside `:root` | 662 occurrences |
| Incoherent repeated component | the message action row — paperclip (thin, 14px), bare red `✕` (~16px, no container), grey `⋯`; and separators mix `\|` and `·` in one row (`hov-msgact-1`) |
| Partial-width divider | the hairline above `91.91 tok/s` is ~258px and changes length with content (`d-01` vs `hov-msgact-1`) |

Also: **native, unstyled `<select>` in five workspaces** — Gallery `All sources` /
`Newest first` (`d-05`), Library, Cookbook `Standard` / `Local` / `Eng…?` (`d-07`),
Compare model picker (`d-13`), Settings `LLM` / `DeepSeek` (`d-09`). These are the only
light-grey OS-chrome elements left in a dark design system and they read as breakage.

Also: **the `--space-*` scale is incomplete** — `static/style.css:275-279` defines only
`--space-1..4` (4/8/12/16) and `--space-8` (32). `--space-5/6/7/9/10` do not exist, so
every honest value above 16px has no token and lands as a literal. This is the root
cause of the off-scale cluster, not a symptom.

### Functionality — 6.5

**Works, verified in-browser:** all eight sidebar workspaces open and render (Notes,
Tasks, Calendar, Gallery, Library, Cookbook, Brain, Compare); the Settings modal opens
and tab-switches (`d-09` services → `d-10` appearance → `d-11` shortcuts); Escape
closes every overlay; the search overlay opens with its blur scrim (`d-12`); the
transcript renders streamed content with token readouts; mobile drawer + Tasks sheet +
Settings sheet all render; zero horizontal overflow at 375px.

**Console log triage** (9 runs, full logs in `/tmp/opencode/shots/iter0/*.log`):

- **Benign, expected** — 404 `/api/research/status/6b1817af-…` ×9 and
  `/api/chat/stream_status/6b1817af-…` ×9. Stale-session status polls for a session id
  from `data/` that no longer exists. Per the brief, benign.
- **Benign, expected under `AUTH_ENABLED=false`** — 403 `/api/auth/integrations` ×6,
  403 `/api/auth/users` ×2, 401 `/api/auth/2fa/status` ×2. Admin/auth endpoints
  correctly refusing with no session.
- **Benign** — `[warning] TTS: not available` ×5; no TTS binary in the container.
- **Benign** — `/api/diagnostics/logs?limit=200 net::ERR_ABORTED` ×2. Aborted on
  navigation, not a fault.
- **NOT an app defect** — `Executing inline script violates … script-src 'self'
  'nonce-…'`. This fires **only** in the `d8-login` run, where I loaded
  `/static/login.html` as a raw static file. `static/login.html:10` and `:250` carry
  `nonce="{{CSP_NONCE}}"`, a literal template placeholder that is only substituted on
  the real `/login` route (which 302-redirects away with auth disabled). An artefact of
  my access method, not a regression. **I am not counting it against the run.**
- **`pageerror`: ZERO.** No asset HTTP ≥400.

**Against the score:** `pytest` is red (§3, Gate 1). And two invariants I could **not**
verify, which I am not going to claim: **settings/appearance persistence** cannot be
tested this run because the harness intercepts `/api/prefs/appearance` and pins the
reply; and **focus trap / focus restore** on modals was not exercised. On a 9–10 you
would need every invariant in `spec.md` verified — I verified most of the rest and it
holds. 6.5.

---

## 3. Gate results

| # | Gate | Result |
|---|---|---|
| 1 | `./venv/bin/python -m pytest` fully green | **FAIL** |
| 2 | `node --check` on touched JS | PASS (12/12 clean) |
| 3 | Functional invariants intact | PASS on everything tested; prefs-persistence and focus-trap unverifiable under the harness pin |
| 4 | No new console errors / asset ≥400 | PASS (zero `pageerror`; zero asset ≥400; only benign API 404/403/401) |
| 5 | No hard red line violated | **FAIL** |

**Gate 1 detail — pytest is RED:**

```
1 failed, 4619 passed, 3 skipped, 76 warnings in 172.31s (0:02:53)
FAILED tests/test_new_chat_model_preference.py::test_desktop_new_chat_actions_use_shared_preference_helper
```

The test slices `static/app.js` between the marker comments `"// Logo click → new
chat"` and `"const sidebarNewChatBtn = el('sidebar-new-chat-btn');"`. The end marker is
present at `static/app.js:3237`; the **start marker is gone** (`grep -c "Logo click"
static/app.js` → `0`), so `_slice` raises `ValueError: substring not found`. This is a
**pre-existing failure introduced by the uncommitted redesign work** — `static/app.js`
is modified (`git status`: `M static/app.js`, `M static/index.html`, `M static/style.css`,
last commit `916c571`). It is a comment-drift failure, not a behaviour failure, and it
is a one-line repair.

**Gate 5 detail — hard red lines violated** (full citations in §4):

- Single-layer `box-shadow` — 256 declarations (`static/style.css:610, 665, 1120, 1131,
  1139, …`). CONTRIBUTING: "Never write a single-layer box-shadow."
- Chrome text on `--font-content` — measured on `.list-item`, `.settings-nav-item`,
  `.send-btn`, `body`. CONTRIBUTING: "Chrome is `--font-ui`, content is
  `--font-content`."
- Border faking elevation — `static/login.html:19` `.card { border: 1px solid #697782;
  box-shadow: none }`. CONTRIBUTING: "Reach for the next rung instead of adding
  `border: 1px solid`."
- Raw colour literal outside `:root` on a live surface — `static/login.html` card border
  `#697782`, which is a **stale** `--border-control` (the token is now `#757575`), plus
  input borders on the same stale value.

---

## 4. Issues, ordered by severity

### 1. `pytest` is red — Gate 1 · fix first, it is nearly free
- **`tests/test_new_chat_model_preference.py:40`** (marker missing from `static/app.js`)
- The test needs the comment `// Logo click → new chat` to exist in `static/app.js`
  before `const sidebarNewChatBtn = el('sidebar-new-chat-btn');` at
  `static/app.js:3237`.
- **Costs:** Gate 1 fails the run outright, independent of any score.
- **Fix:** restore that one comment line in `static/app.js` above the logo-click
  handler. Do not change the test.

### 2. The transcript has no surface — the topographic field runs under body copy
- **`static/style.css`** — the chat message column has no `--bg`/`--surface-*` plate;
  `.msg-ai` sits directly on the live contour canvas.
- **Costs:** Design Quality (primary surface is unreadable), Craft (contrast is
  unmanaged), Originality (the one strong idea actively harms legibility).
  Evidence: `d-01`, `m-01` — contour lines and stray labels ("2s456", "mo 731") sit
  directly behind `No game was mentioned—I'm just here to help!`
- **Fix:** give the message column an opaque `--bg`-derived plate (e.g. a
  `background: color-mix(in srgb, var(--bg) 88%, transparent)` wrapper, or move the
  topographic layer to `z-index: -1` *behind* a solid `--bg` chat background). Then
  reduce the field's opacity where it does remain visible. Do **not** delete the field —
  it is the identity. Cap its contrast behind content.

### 3. Chrome renders on the content font — `--font-ui` is dead code
- **`static/style.css`** — `.list-item`, `.send-btn`, `.settings-nav-item`, `.modal-header`
  and `body` all compute `"Fira Code"`. `--font-ui` resolves to `'Inter', …` and is
  never applied. The correct pattern already exists at `static/js/tourHints.js:6563`.
- **Costs:** Craft (named red line), Design Quality ("the chrome and the content look
  like different products"), Originality (kills the mono/sans split the rubric names).
- **Fix:** set `font-family: var(--font-ui)` on the chrome layer — `.list-item`,
  `.section-title`, `.modal-header`, `.modal-footer`, `button`, `.settings-nav-item`,
  `.send-btn`, and every `.list-item-plus-btn`. Leave `.msg-ai`, `.msg-user`, `pre`,
  `code`, `.msg-actions` on `var(--font-content)`. Note that `--font-ui` must also be
  re-derived from `--font-family` when the mono pref is active, or the mono setting
  will keep overwriting chrome.

### 4. 256 single-layer box-shadows, invisible on a `#000` canvas
- **`static/style.css:610, 665, 1120, 1131, 1139, 1811, …`** — 14 are live at runtime,
  including `.sidebar` (`rgba(0,0,0,0.1) 0 4px 12px`), `.dropdown`,
  `.export-dropdown-menu`, `.overflow-menu`, `.search-popup`.
- **Costs:** Gate 5 red line; Craft — these panels currently get *zero* separation from
  the canvas, which is why Settings, Notes and the windows read as unmoored.
- **Fix:** replace every `box-shadow: 0 Npx Npx rgba(0,0,0,a)` with
  `var(--shadow-sm)` / `var(--shadow-md)`, which are already two-layer. For dropdowns
  and popovers specifically, add a ladder step (`--surface-4`) instead of relying on the
  drop.

### 5. Hover and selected are the same state on the primary navigation
- **`static/style.css:1509-1511`** — `.list-item:hover` paints
  `color-mix(in srgb, var(--fg) 7%, transparent)`; the open-workspace rule paints
  `--surface-3`. At `--surface-3` ≈ `#1b1b1b` the two are visually identical.
- **Costs:** Design Quality (information design failure on the app's primary
  affordance), Craft.
- **Fix:** give the *open* workspace a distinct, non-hover treatment — a 2px
  `var(--accent-ink)` left rule plus `--surface-2`, or move the open marker into the
  icon. Leave hover as the neutral `--surface-2` lift. Verify with `hoverAll
  shotEach: true` on `#tools-section .list-item` that the open row and a hovered row are
  distinguishable in a still frame.

### 6. Login is off-system: off-token palette, no elevation, asymmetric CTA padding
- **`static/login.html:19`** (inline `<style>`), **`:23`** (the file's own comment
  concedes it "cannot inherit those" tokens), **`:10, :250`** (`nonce="{{CSP_NONCE}}"`)
- Measured: `.card { background: rgb(20,28,35) /* #141c23 = --panel */; border: 1px
  solid rgb(105,119,130) /* #697782 — a stale --border-control */; box-shadow: none }`.
  `--elevated` resolves to the **empty string** on this page. `h1 { font-size: 32px }`
  (scale is 26 → 34). `button[type=submit] { padding: 12.2px 11.2px 10.2px }` — three
  different values, which is why "Sign In" sits off-centre. Inputs at `15.2px`
  (off-scale). The password toggle is a rounded illustrative glyph, not the app's
  monochrome SVG set. The wordmark is letterspaced monospace with no logo, while the
  welcome screen uses `/static/icons/Zephyrus-Logo.png`.
- **Costs:** Design Quality (first-run surface is the least designed thing in the
  product), Craft (off-scale padding, off-scale font-size, raw colour literal, border
  faking elevation), Gate 5.
- **Fix:** (a) give the card a real ladder rung + `--shadow-md` and drop the border;
  (b) replace `#697782` with `var(--border-control)`; (c) `h1` → `var(--text-3xl)`;
  (d) button padding → a single symmetric `--space-3`; (e) either link `style.css` or
  copy the surface ladder into the page's `<style>` so `--elevated` resolves; (f) use
  the logo. This is the highest-leverage *single surface* in the app after the
  transcript.

### 7. Window geometry: five widths, four centre axes, three title-bar heights
- **Cookbook `d-07` (centre 720, title-bar 17px) · Calendar `d-04` (744) · Brain
  `d-08` (863) · Tasks `d-03` (861) · Gallery `d-05` (860) · Library `d-06` (859) ·
  Compare `d-13` (858) · Settings `d-09` (title-bar 63px)**
- **Costs:** Design Quality (this is the single clearest "pile of surfaces" signal),
  Craft.
- **Fix:** introduce two tokens — `--window-w` (e.g. `min(760px, 92vw)`) and
  `--window-title-h` — and one `.modal-content` / window-chrome rule that centres the
  window and pads its title bar identically. Let the four genuinely data-dense
  workspaces (Cookbook, Gallery, Compare, Settings) opt into a wider `--window-w-wide`.
  Delete the per-module inline `style="width:…"` overrides (e.g.
  `static/index.html:972`, `static/js/gallery.js:1977`, `static/js/tasks.js:2739`).

### 8. Overlays have no scrim, so they don't read as overlays
- **Settings `d-09`/`d-10`, Notes `d-02`, every workspace window.** The chat,
  composer, sidebar and topographic field are at full contrast around the panel.
- **Costs:** Design Quality (depth), Craft.
- **Fix:** the search overlay (`d-12`) already does this correctly — a full-bleed
  `backdrop-filter: blur()` + `rgba(0,0,0,α)` scrim. Extract that rule and apply it to
  `.modal` and the window container. Keep window-drag affordances.

### 9. Native unstyled `<select>` in five workspaces
- **Gallery `d-05`** (`All sources`, `Newest first`) · **Cookbook `d-07`**
  (`Standard`, `Local`, `Eng…?`) · **Compare `d-13`** (model picker) · **Library
  `d-06`** · **Settings `d-09`** (`LLM`, `DeepSeek`)
- **Costs:** Craft (unstyled OS chrome is the only light-grey element left in a dark
  system), Design Quality.
- **Fix:** the app already has a custom select — the model picker
  (`static/js/modelPicker.js`). Extend it (or the `.dropdown` pattern at
  `static/style.css`) rather than adding a parallel one, per the "no parallel
  components" rule. Never leave a bare `<select>`.

### 10. Cookbook renders truncated labels that read as bugs: `Qu… ?`, `Context ?`
- **`static/js/cookbook.js`** — scan controls at `d-07`. The `Qu…` label is a
  truncated "Quantization" with a literal `?` after it, and `Context ?` is the same.
- **Costs:** Craft (looks broken), Design Quality.
- **Fix:** stop truncating the label; use a full word, an abbreviation that fits
  (`Q4_K_M` etc.), or move the description into a tooltip. If a tooltip is wanted,
  style it — the Notes panel currently shows a **native OS `title` tooltip**
  ("Notes is your basic todo list…") overlapping its own header at `d-02`.

### 11. Clipped list rows with no scroll affordance
- **Tasks `d-03`** (the "Email Tags" row is bisected at the panel edge) ·
  **Settings `d-10`** (the "Sidebar" section header is bisected)
- **Costs:** Craft, Functionality (reads as data loss).
- **Fix:** add a scroll shadow / edge mask on the scroll container so partial content
  reads as "more below", and verify the scrollbar is styled to the system rather than
  the OS default.

### 12. Empty states: voids, and one unowned component
- **Notes `d-02`, Brain `d-08`, Library `d-06`, Gallery `d-05`** — each empty state
  floats in 150–200px of nothing. Gallery's copy is *italic*, which is not in the type
  scale (`static/js/gallery.js:1199`); Library's is italic with a `⬆` text glyph
  (`static/js/documentLibrary.js:443`); Brain's carries a smiley SVG
  (`static/js/memory.js:698`).
- **Costs:** Craft, Design Quality.
- **Fix:** centre the empty state on a real baseline, add one concrete primary action
  (Library's underlined *Import* in `d-06` is the only one that has one — make it a
  button), and drop the italics.

### 13. `#doclib-search` is styled by `.memory-search-input`
- **`static/js/documentLibrary.js`** (Library search reuses the Brain surface's class;
  measured `padding-left: 28px`, off-scale)
- **Costs:** Craft (a third surface's class name on a second surface; guaranteed
  divergence).
- **Fix:** rename the primitive (`.search-input` + `.search-field`) and have both
  surfaces use it, per "no parallel components."

### 14. Off-scale drift: 382 radii, 195 font-sizes, 1170 padding/gap violations
- **Scale gaps:** `static/style.css:275-279` defines only `--space-1..4` and
  `--space-8`; `--space-5/6/7/9/10` **do not exist**. `static/style.css:250-257` text
  scale; `:287-290` radius scale. `static/style.css:1506`
  (`.section-header-btn { padding: 1px 3px; border-radius: 4px }`).
  Sub-11px text: `.memory-count` at 9.6px and **8.4px**
  (`static/style.css:12980`, `:26978`, `:18303`).
- **Costs:** Craft −2.0 (mandated), Design Quality (rhythm).
- **Fix:** finish the spacing scale to `--space-10` first — that is the root cause,
  not the 382 declarations. Then sweep radii to 6/8/12/999 and kill the 7/8/9/10px
  text (8.4px on a count badge is below the legibility floor, not decorative).

### 15. `--accent` is monochrome, not the documented ice-blue
- **`static/style.css:119`** — `--accent: #f1f1f1; /* monochrome ref match … (was
  ice-blue #7cc4f5) */`, while `CONTRIBUTING.md:93` still specifies "one ice-blue
  accent." `--panel: #141c23` (`:57`) is the only blue-tinted surface and it is what
  makes the login look like a different product.
- **Costs:** Documentation/design contract drift. Not a visual defect — the monochrome
  accent is a *defensible* decision and reads well.
- **Fix:** decide deliberately. Either restore ice-blue and update the direction, or
  keep monochrome and correct `CONTRIBUTING.md:93` so the contract matches the tokens.
  Also fix the stale comment at `static/style.css:228` (`/* #639dc4, 7.15:1 */` beside a
  white-mix value).

### 16. The tour hint illustration is unreadable
- **`static/js/tourHints.js:73-92`**, CSS at `static/style.css:6544-6550`
  (`stroke-opacity: 0.18` frame; modal rect `fill: var(--bg)` = pure black)
- At 160×96 the frame is nearly invisible and the "modal" is a black box with a
  hairline — in `d-02`/`d-03`/`d-04`/`d-05` it reads as a **broken-image icon**, not as
  an illustration.
- **Costs:** Craft.
- **Fix:** scale it to ~240×144, raise the frame to `stroke-opacity: 0.35`, fill the
  modal rect with `--surface-3`, and give the snap zone a visible `stroke`. It is a good
  idea executed at 40% legibility.

---

## 5. What genuinely works

Not a token amount — there is real craft here.

- **Reduced motion is properly done, and verified by measurement.** 20 blocks; under
  `prefers-reduced-motion: reduce` the computed `transition-duration` for `.send-btn`,
  `.list-item`, `body`, `.icon-rail-btn`, `.msg-ai`, `.rail-hover-label` and
  `.section-header-flex` is all `0s`. This is the requirement most often faked and it is
  genuinely met here.
- **The topographic field is a real idea** and it is the reason the app does not look
  like a ChatGPT clone. Strip the name and the contour field still identifies it.
- **The shadow tokens are correct.** `--shadow-sm`/`--shadow-md` are two-layer with the
  load-bearing light inset. The *call sites* are the problem, not the tokens.
- **`--border-control` exists and clears WCAG 1.4.11** (4.56:1 on `--bg`). The
  discipline is present; the usage is inconsistent.
- **The command-palette search overlay (`d-12`) is the best surface in the app** — blur
  scrim, centred field, grouped results. It is the reference implementation for
  issue 8.
- **The floating-window-per-workspace metaphor holds** across eight surfaces. The
  concept is sound; only its geometry is ad hoc.
- **Zero `pageerror` and zero asset HTTP ≥400 across nine runs.** The console is clean
  apart from the documented benign stale-session 404s and auth 403/401s.
- **`node --check` clean on 12/12 files** rendering the audited surfaces.
- **Mobile holds.** No horizontal overflow at 375×812; drawer, sheet and settings
  patterns all adapt.

---

## 6. The one change with the highest score-per-effort for iteration 1

**Restore the `// Logo click → new chat` comment marker in `static/app.js`.**

Two lines of work. It flips **Gate 1** from FAIL to PASS, and a Gate failure fails the
iteration *regardless of the weighted score* — so until this lands, no amount of design
improvement is scorable. Fix the comment, not the test.

**Then, as the single highest-leverage visual change, apply `var(--font-ui)` to the
chrome layer** (issue 3). One handful of selectors restores the mono/sans split that
the rubric names as one of three originality carriers, it clears a named hard red line
in Gate 5, and it immediately separates chrome from content across every surface at
once — the cheapest possible route to a visible jump in Design Quality, Originality and
Craft simultaneously. Pair it with the transcript plate (issue 2) if budget allows;
that is the loudest defect on the primary surface but costs more than the font fix.

---

*Evaluator note on method: every screenshot referenced above was opened and visually
inspected, not inferred from the DOM. All numeric claims are `getComputedStyle`
measurements taken in the running app. Confidence in the design scoring: high. The
pytest gate result is deterministic. One limitation is stated explicitly in §2 —
appearance-prefs persistence and modal focus trapping could not be verified this run
because the harness pins `/api/prefs/appearance`; I did not claim credit for them.*