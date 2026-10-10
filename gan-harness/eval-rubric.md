# Design-Focused Eval Rubric — Zephyrus Whole UI

Weighted score = Σ(score × weight). **Pass ≥ 7.5. Max 10 iterations.**
One decimal per criterion. Show the weighted arithmetic.

Mode: design. The Evaluator's job is to answer **"would this win a design
award?"** first and **"does it still work?"** second. Functionality is weighted
lowest *because* it is expected to be preserved, not because it is optional —
a functional regression still fails the run (see Gate below).

---

### Design Quality — weight 0.35

Does the UI read as one deliberate piece of work, or a pile of surfaces?

- **1–3** — Generic, template-like. Flat panels, no hierarchy, sections clash,
  the chrome and the content look like different products.
- **4–6** — Competent, unremarkable. Follows conventions; nothing to remember.
- **7–8** — Distinctive, cohesive. Clear hierarchy, consistent rhythm, the
  topographic/depth direction reads as intent rather than accident.
- **9–10** — A designer's portfolio piece. Every surface is composed, spacing
  is systematic, the visual identity survives contact with 20 different
  workspaces, and there is at least one moment that is genuinely delightful.

Judge against: sidebar, composer, transcript, one overlay, two workspaces,
settings, login.

### Originality — weight 0.30

Custom decisions vs. the default ChatGPT-clone vocabulary.

- **1–3** — Stock. Default greys, centred column, generic bubbles, no identity.
- **4–6** — Some customisation, mostly standard patterns.
- **7–8** — Clear creative vision: the topographic field, the mono/sans split,
  the ladder-based depth are used deliberately rather than decoratively.
- **9–10** — Surprising. At least one idea a competitor could not have shipped
  by copying. Ideas that *earn* their place: they aid navigation, hierarchy, or
  delight — not decoration for its own sake.

Explicit originality test: **if you stripped the Zephyrus name and logo, would
you still know it was not a generic AI chat app?**

### Craft — weight 0.25

- **1–3** — Broken layouts, missing states, no motion, lost focus, layout shift.
- **4–6** — Works, feels rough: off-scale spacing, inconsistent radii, states
  missing, focus rings absent, text at sizes not on the scale.
- **7–8** — Polished: `--dur-*` / `--ease-out` motion, hover/focus/active on
  every interactive element, `focus-visible` rings, correct empty + loading +
  error states, reduced-motion honoured, responsive holds at 375px.
- **9–10** — Pixel-perfect. Systematic rhythm across surfaces, consistent
  elevation, no layout shift anywhere, keyboard-complete, contrast measured
  rather than eyeballed.

Craft failures that must be cited with file:line — they are the ones that
actually recur in this codebase:
- off-scale `padding` / `margin` / `gap` / `border-radius` / `font-size`
- a raw hex/rgb literal outside `:root`
- a control edge using `--border` instead of `--border-control`
- a single-layer `box-shadow`
- an animation with no `prefers-reduced-motion` counterpart
- an emoji in the UI
- chrome text on `--font-content`, or code on `--font-ui`

### Functionality — weight 0.10

- **1–3** — Core broken: chat dead, nav dead, modals dead.
- **4–6** — Happy path works, edge cases fail.
- **7–8** — All features work, errors handled, no console errors.
- **9–10** — Bulletproof, every invariant in `spec.md` verified in a browser.

---

## Gate (independent of the weighted score)

Any one of these **fails the iteration** no matter how it scores:

1. `./venv/bin/python -m pytest` is not fully green.
2. `node --check` fails on any touched JS file.
3. A functional invariant in `spec.md` is broken.
4. New console errors, or a new HTTP ≥400 on an asset.
5. A hard red line from `spec.md` is violated (new colour literal outside
   `:root`, new off-scale value, emoji, parallel component, single-layer shadow).

## Anti-slop penalties

Subtract from the criterion they belong to. Cite file:line for each.

| Pattern | Effect |
|---|---|
| Raw hex/rgb outside `:root` | Craft −1.0 (max −1.5) |
| Off-scale spacing / radius / font-size | Craft −0.5 (max −1.0) |
| Border used to fake elevation | Design Quality −0.5 (max −1.0) |
| Emoji in UI | Craft −1.0, Design Quality −0.5 |
| Animation with no reduced-motion counterpart | Craft −1.0 |
| New widget duplicating an existing one | Design Quality −1.0 |
| Text below 4.5:1 on its real surface | Craft −1.0 (max −1.5) |
| Dead / placeholder / `TODO` styling left in | Craft −1.5 |
| Generic AI-slop visual | Design Quality −1.0 |
| Favicon/manifest/logo churn unrelated to this run | Craft −0.5 |

### How penalties are applied (recalibrated 2026-10-08)

Penalties are a **bounded correction, not the score**. Three rules:

1. **A penalty may not floor a criterion below 3.0.** Craft anchored at "1–3:
   broken layouts, missing states, no animations, focus lost" is a factual claim
   about the work. If the work is not broken, the arithmetic is wrong, not the
   score. When the penalty sum would floor a criterion, **report the floored
   number, then report the unpenalised score explicitly**, and use the
   unpenalised one for the weighted total.
2. **Aggregate, then cap.** Count distinct clusters, not raw occurrences. A
   1.3MB stylesheet with 220 legacy literals is one systemic problem worth one
   capped penalty — not 220. Reward the Generator for driving a cluster to
   zero; do not let a fixed backlog dominate the total for the whole run.
3. **The penalty table is not the run.** Legacy violations that predate this
   run are reported as backlog, not scored against the Generator every
   iteration. Score what this run introduced or failed to fix.

Penalties were originally capped at −3.0 and −2.0. On iteration 0 both caps
saturated immediately and floored Craft to 1.0 against a codebase that is
merely inconsistent, not broken — which made the weighted total a measure of
backlog size rather than design quality. Caps are now −1.5 / −1.0.

**Rule 1 is not an excuse to ignore penalties.** It means: report the
arithmetic honestly, and never let the floor invent a defect that isn't there.

## Evidence the Evaluator must produce

Non-negotiable — a score without these is invalid:

1. **Screenshots at 1440×900 and 375×812** for: shell/chat, one overlay, at
   least two workspaces, settings, login.
2. **A console log** for the run (pageerrors, failed requests, HTTP ≥400),
   with the benign ones (stale-session stream-status polls returning 404)
   identified as benign rather than ignored.
3. **Computed evidence** for the craft claims that matter: `getComputedStyle`
   readings for at least one control edge colour, one shadow, one font-family
   split, and the reduced-motion block.
4. **A pytest run** with the pass/fail count stated.
5. Per-issue `file:line` references, ordered by severity.

## Evaluator stance

Ruthlessly strict. **The single most common failure mode of this harness is a
lenient evaluator.** If iteration 1 scores ≥ 8, assume the rubric was applied
generously and re-read the screenshots before believing it. Never praise
mediocre work. Do not award a 9 anywhere without naming the specific thing that
earns it. **The Evaluator critiques only — it never edits code.** The Generator
fixes; the Evaluator never patches what it then praises.
The second most common failure mode is a **miscalibrated score** — one that
tracks the size of a legacy backlog rather than the quality of the work. If the
penalty arithmetic produces an absurd result (a floored score that contradicts
what you are looking at), say so and report both numbers rather than quietly
passing the arithmetic through.

## Identity regression check (hard rule)

If an iteration makes the app **less identifiable as Zephyrus** — removes a
distinguishing visual device, flattens a signature surface, or makes it read as
a generic AI chat app — that is a **regression**, not a trade-off, and it caps
Originality at 5 regardless of how sound the legibility argument is.

Fixing a legibility problem by deleting the thing that gave the surface its
identity is the exact failure this harness exists to catch. Narrow the offending
element to the reading measure; do not remove it. A surface that is legible
*because* the field was narrowed, and still recognisably Zephyrus, scores
strictly higher than one that is legible because the field is gone.

### Identity presence ≠ identity structure (added 2026-10-08, iteration 2)

Iteration 2 restored the topographic field and passed a naive check, but the
field had become a blur: **mean gradient magnitude 21% of source** (2.14 vs
9.99). Pixel-coverage metrics cannot see this — coverage went *up* while the
image went *down*.

When judging any background, texture, illustration, or image-derived surface,
measure **gradient energy** (mean gradient magnitude) against the source, not
coverage. Coverage answers "is something there?"; gradient energy answers "is
it still structured?" A surface can be present, correctly placed, correctly
scaled, and still be visual noise. Treat a sub-0.5 gradient-energy ratio as a
regression even when coverage improves.

Corollary for the Generator: fixing a legibility or size problem by blurring,
mipmapping, or dissolving a signature asset is the same failure as deleting it,
just less visible. Re-derive at higher resolution and mask, do not attenuate.
