#!/usr/bin/env python3
"""Sweep the tonal half of the field derivation against the acceptance bar.

`feedback-002` issue 2 is explicit that the previous iteration's mistake was
tuning the wrong metric: coverage rose 6.74% -> 25.07% while the image got
worse. So this prints gradSum - the metric the rubric adopted - next to coverage
for every candidate, and the candidates deliberately include the ones the
rubric forbids (blur, downscale, dim) so the cost of each is on the record
rather than argued about.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derive_field as D  # noqa: E402
from measure_field import gradient_sum  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def blur(img: Image.Image, r: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(r))


def pipeline_report() -> None:
    lum = D.luma(Image.open(D.SOURCE).convert("RGB"))
    markers = D.find_markers(lum)
    boxes = D.annotation_boxes(lum, markers)
    mask = D.build_mask(lum.shape, boxes)
    painted = D.inpaint(lum, mask, boxes)
    base = Image.fromarray(np.clip(painted, 0, 255).astype("uint8"))

    def grad(a):
        return gradient_sum(a)

    def cov(a, t=12):
        return 100 * (a > t).mean()

    def hi(a, t=48):
        return 100 * (a > t).mean()

    rows = []

    def add(name, arr):
        rows.append((name, arr.mean(), grad(arr), cov(arr), hi(arr)))

    add("source (no mask)", lum)
    add("mask only (1:1)", painted)
    add("mask + 0.4px blur", D.luma(blur(base, 0.4)))
    add("mask + 0.8px blur", D.luma(blur(base, 0.8)))
    add("mask + 1.2px blur  <- iter2 recipe", D.luma(blur(base, 1.2)))
    add("mask + unsharp r1 a0.8", D.luma(base.filter(
        ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0))))
    add("mask + unsharp r1 a0.8 -> 0.4px blur", D.luma(blur(base.filter(
        ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)), 0.4)))
    add("mask + unsharp r1 a0.6 -> 0.3px blur", D.luma(blur(base.filter(
        ImageFilter.UnsharpMask(radius=1, percent=60, threshold=0)), 0.3)))

    # the derivation iteration 2 actually shipped, for the record
    old = np.asarray(Image.open(D.DEST).convert("RGB"), np.float32) @ D.LUMA
    add("SHIPPED iter2 (mipmap+hist)", old)

    # scale variants, as the evaluator asked to see (/2, /3) - and what the
    # browser then does to them, which is the part iteration 2 missed
    for f, tag in ((2, "/2"), (3, "/3")):
        small = base.resize((base.width // f, base.height // f), Image.LANCZOS)
        s = D.luma(small)
        add(f"mask + {tag} LANCZOS", s)
        # browser draws it with cover at ~0.96x of 1672px, i.e. scaled back up
        back = D.luma(small.resize(base.size, Image.BICUBIC))
        add(f"mask + {tag} (as the browser draws it)", back)

    print(f"{'pipeline':<44}{'mean':>7}{'gradSum':>9}{'px>12':>9}{'px>48':>8}{'ratio':>7}")
    src_grad = rows[0][2]
    for name, m, g, c, h in rows:
        ratio = g / src_grad
        flag = ""
        if g < 5.0 and "iter2" not in name and "blur" not in name.split("+")[-1]:
            flag = "  FAIL"
        print(f"{name:<44}{m:7.2f}{g:9.2f}{c:8.2f}%{h:7.2f}%{ratio:7.2f}{flag}")


if __name__ == "__main__":
    pipeline_report()