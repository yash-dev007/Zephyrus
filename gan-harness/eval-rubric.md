# Design-Focused Eval Rubric

Weighted score = sum(score * weight). Pass >= 9.0. Max 10 iterations.

### Design Quality (weight: 0.35)
- 1-3: Generic, template-like, AI slop. Flat swatches, inconsistent hierarchy, clashing sections.
- 4-6: Competent but unremarkable. Follows conventions, no clear visual identity.
- 7-8: Distinctive, cohesive identity. Theme modal feels part of Zephyrus whole. Clear hierarchy, balanced rhythm.
- 9-10: Could pass for professional designer. Award-worthy cohesion: swatch previews, section rhythm, iconography, empty states all intentional. Would you screenshot this for a portfolio?

### Originality (weight: 0.30)
- 1-3: Default colors, stock layouts, no personality. 4-dot strip only.
- 4-6: Some custom choices, mostly standard patterns.
- 7-8: Clear creative vision: mini browser-chrome previews, zone-highlight, peek, harmony generator integrated as design tool not form.
- 9-10: Surprising, delightful, genuinely novel — e.g. live mini-chat preview per swatch, gradient brand mix, pattern-aware swatch glow — while reusing existing tokens/classes.

### Craft (weight: 0.25)
- 1-3: Broken layouts, missing states, no animations, focus lost, layout shift on tab switch.
- 4-6: Works but rough: inconsistent spacing/radius, reset buttons always visible, sliders unstyled.
- 7-8: Polished: 160ms cubic-bezier transitions, hover lift + active ring (`--red` 33% mix), focus-visible rings, reduced-motion respected, responsive grid + mobile sheet intact.
- 9-10: Pixel-perfect: 8px rhythm, 1px `var(--border)`, consistent radius, no hardcoded colors, `node --check` + `py_compile` clean, keyboard + screen-reader correct.

### Functionality (weight: 0.10)
- 1-3: Core broken: preset click doesn't apply/persist, custom save/delete broken.
- 4-6: Happy path works, edge cases fail (limit 8, built-in overwrite guard, advanced override tracking).
- 7-8: All features work, good error handling, server sync degrades gracefully.
- 9-10: Bulletproof: all invariants in spec.md hold, persistence + sync verified, no console errors.

### Evaluator stance
Ruthlessly strict. Ask "would this win a design award?" not "do all features work?". Never praise mediocre. File specific issues with file:line. Score each criterion 1-10 with one-decimal allowed, show weighted math.
