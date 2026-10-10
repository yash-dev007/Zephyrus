#!/usr/bin/env python3
"""Measure a topographic field asset the way the eval rubric asks for.

The rubric added *Identity presence != identity structure* after iteration 2,
and it is explicit that the metric that let a blur through was pixel coverage:

    coverage answers "is something there?"
    gradient energy answers "is it still structured?"

So this reports both, and gradient energy is the one that carries the decision.
`feedback-002` section 4 issue 2 sets the acceptance bar:

    mean gradient magnitude >= 5.0 against source 9.99
    px > 48 within 1% of source's 1.42%
    px > 12 (right of the reading column) >= 12%

Gradient energy is also what you want to be scale-aware about, so every metric is
reported twice: on the asset at its own resolution, and after resampling to the
source's 1672x941 - i.e. after the resample a browser applies before it draws
it. A `/2` asset that scores 6.0 on itself and 2.0 after `cover` is not a fix.

Usage:
    gan-harness/measure_field.py                      # source vs shipped
    gan-harness/measure_field.py a.png b.png c.png    # arbitrary assets
    gan-harness/measure_field.py --rendered shot.png  # coverage over a render
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static" / "icons" / "topo-dark.png"
SHIPPED = ROOT / "static" / "icons" / "topo-field.png"
REF_W, REF_H = 1672, 941
GRAD_FLOOR = 5.0          # feedback-002 issue 2 acceptance bar
HIGH_T = 48               # px>48 tracks the contour core + annotation residue
COVERAGE_T = 12           # the threshold that reproduces the evaluator's own
                          # iteration-0 baseline of 11.81%


def _luma(img: Image.Image) -> np.ndarray:
    """Rec.709 luminance as float32. max(channel) is not luminance and using
    it inflates every gradient number by counting the source's colour speckle
    as if it were structure."""
    return np.asarray(img.convert("RGB"), dtype=np.float32) @ np.array(
        [0.2126, 0.7152, 0.0722], dtype=np.float32
    )


def gradient_sum(lum: np.ndarray) -> float:
    """Mean gradient magnitude, summed across axes, per pixel.

    Shape-independent: the horizontal gradient is accumulated into an array
    one column short and the vertical into one row short, then both are placed
    in the same (H, W) buffer before averaging, so the answer is comparable
    across resolutions. Without that step a naive `diff(axis=1).mean()` divides
    by a different pixel count per axis and the two means do not sum cleanly.
    """
    gx = np.abs(np.diff(lum, axis=1))
    gy = np.abs(np.diff(lum, axis=0))
    acc = np.zeros(lum.shape, dtype=np.float32)
    acc[:, : gx.shape[1]] += gx
    acc[: gy.shape[0], :] += gy
    return float(acc.mean())


def stats(path: Path) -> dict:
    img = Image.open(path)
    lum = _luma(img)
    out = {
        "path": path,
        "size": img.size,
        "mode": img.mode,
        "bytes": path.stat().st_size,
        "mean": float(lum.mean()),
        "grad": gradient_sum(lum),
        "coverage": float((lum > COVERAGE_T).mean() * 100.0),
        "high": float((lum > HIGH_T).mean() * 100.0),
    }
    # as the browser would draw it: resample to the reference grid first
    if img.size != (REF_W, REF_H):
        resampled = np.asarray(
            img.convert("RGB").resize((REF_W, REF_H), Image.LANCZOS), dtype=np.float32
        ) @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    else:
        resampled = lum
    out["grad_resampled"] = gradient_sum(resampled)
    return out


def _row(s: dict, label: str) -> str:
    return (
        f"{label:<34} {s['size'][0]:>5}x{s['size'][1]:<5} "
        f"mean {s['mean']:6.2f}  "
        f"gradSum {s['grad']:6.2f}  "
        f"grad@1:1 {s['grad_resampled']:6.2f}  "
        f"px>12 {s['coverage']:6.2f}%  px>48 {s['high']:5.2f}%  "
        f"{s['bytes'] / 1024:7.0f} KB"
    )


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    if "--rendered" in argv:
        # Coverage over a rendered screenshot, region-limited so the composer,
        # the plate and the sidebar do not contaminate the reading.
        for p in args:
            lum = _luma(Image.open(p))
            box = (1150, 200, 1430, 700)  # right of the reading column
            sub = lum[box[1] : box[3], box[0] : box[2]]
            print(
                f"{p}  region {box}  "
                + "  ".join(
                    f"px>{t} {100 * (sub > t).mean():6.2f}%"
                    for t in (4, 12, 24, 48)
                )
                + f"  mean {sub.mean():.2f}"
            )
        return 0

    paths = [Path(a) if Path(a).exists() else (ROOT / a) for a in args]
    if not paths:
        paths = [SOURCE, SHIPPED]

    src = None
    if SOURCE.exists() and paths[0] != SOURCE:
        src = stats(SOURCE)

    rows = [s for s in (src,) if s] + [stats(p) for p in paths]
    labels = (["topo-dark.png (SOURCE)"] if src else []) + [
        p.name for p in paths
    ]
    for label, s in zip(labels, rows):
        print(_row(s, label))

    if src:
        print()
        print(f"  source gradSum {src['grad']:.2f}  "
              f"floor {GRAD_FLOOR:.1f}  "
              f"ratio required {GRAD_FLOOR / src['grad']:.2f}")
        for label, s in zip(labels[1:] if src else labels, rows[1:] if src else rows):
            ratio = s["grad"] / src["grad"]
            verdict = "PASS" if s["grad"] >= GRAD_FLOOR else "FAIL"
            print(
                f"  {label:<32} gradSum ratio {ratio:5.2f}  "
                f"({s['grad']:.2f})  {verdict}"
                + ("" if ratio >= 0.5 else "   <-- sub-0.5, defined as a regression")
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))