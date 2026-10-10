#!/usr/bin/env python3
"""Locate the baked-in map annotations in the source artwork.

The evaluator's issue 2 says the right fix for the legible map labels
("2s456", "mo 731", "sneha") is "paint a mask over the ~30 known annotation
locations in the source ... rather than [suppressing them] by a filter". This
finds them so the mask is painted from measurements, not from eyeballing a
list of coordinates.

Method: 8-connected components of the luminance above a threshold. Contour
lines are long connected strokes that all link up into a handful of
continent-sized components; annotation markers and their text are small,
isolated, and numerous. So the separation is structural, not tonal.

Run with --dump to write an overlay for visual confirmation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static" / "icons" / "topo-dark.png"
THRESHOLD = 60.0        # annotations sit above this; contour cores below
MAX_COMPONENT = 4000    # px; anything larger is terrain, not a marker
CLUSTER_RADIUS = 46     # px; marker + its numeric label are within this


def luma(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.float32) @ np.array(
        [0.2126, 0.7152, 0.0722], dtype=np.float32
    )


def label_components(binary: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """8-connected labelling by row runs + union-find.

    No scipy in this environment, and a full-array flood fill over 1.57M px is
    slow enough to matter. Row-run labelling touches only the bright pixels,
    which are 0.2% of the image, so it runs in about a second.
    """
    h, w = binary.shape
    parent: list[int] = []

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # 1. runs per row
    runs: list[tuple[int, int, int]] = []  # (row, x0, x1_exclusive)
    run_label: list[int] = []
    padded = np.zeros((h, w + 2), dtype=bool)
    padded[:, 1:-1] = binary
    diff = np.diff(padded.astype(np.int8), axis=1)
    starts = np.argwhere(diff == 1)
    ends = np.argwhere(diff == -1)
    for (y, xs), (_, xe) in zip(starts, ends):
        parent.append(len(parent))
        runs.append((int(y), int(xs), int(xe)))
        run_label.append(len(parent) - 1)

    # 2. union runs that touch the previous row (8-connectivity: x overlap or
    #    diagonal adjacency of exactly one pixel)
    by_row: dict[int, list[int]] = {}
    for i, (y, _, _) in enumerate(runs):
        by_row.setdefault(y, []).append(i)
    for y in range(1, h):
        prev, cur = by_row.get(y - 1, []), by_row.get(y, [])
        j = 0
        for i in cur:
            _, x0, x1 = runs[i]
            while j < len(prev) and runs[prev[j]][2] < x0:
                j += 1
            k = j
            while k < len(prev) and runs[prev[k]][1] <= x1:
                union(run_label[i], run_label[prev[k]])
                k += 1

    # 3. flatten and collect per-label geometry
    out = np.zeros((h, w), dtype=np.int32)
    geo: dict[int, dict] = {}
    for i, (y, x0, x1) in enumerate(runs):
        root = find(run_label[i])
        out[y, x0:x1] = root
        g = geo.setdefault(
            root, {"n": 0, "x0": x1, "x1": x0, "y0": y, "y1": y, "root": root}
        )
        g["n"] += x1 - x0
        g["x0"] = min(g["x0"], x0)
        g["x1"] = max(g["x1"], x1)
        g["y1"] = max(g["y1"], y)
    return out, list(geo.values())


def cluster(boxes: list[tuple[int, int, int, int]], radius: int) -> list[list[int]]:
    """Single-link clustering on box proximity: a marker and the number printed
    beside it are one annotation, not two."""
    n = len(boxes)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        ax0, ay0, ax1, ay1 = boxes[i]
        for j in range(i + 1, n):
            bx0, by0, bx1, by1 = boxes[j]
            if (
                ax0 - radius <= bx1
                and bx0 - radius <= ax1
                and ay0 - radius <= by1
                and by0 - radius <= ay1
            ):
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def main() -> int:
    dump = "--dump" in sys.argv
    img = Image.open(SOURCE).convert("RGB")
    lum = luma(img)
    h, w = lum.shape
    print(f"source {img.size}  px>60 {100 * (lum > 60).mean():.2f}%")

    labels, geo = label_components(lum > THRESHOLD)
    sizes = sorted((g["n"] for g in geo), reverse=True)
    print(f"components above threshold: {len(geo)}")
    print(f"  largest 8: {sizes[:8]}")
    total = sum(g["n"] for g in geo)
    small = [g for g in geo if g["n"] <= MAX_COMPONENT]
    print(
        f"  components <= {MAX_COMPONENT}px: {len(small)}  covering "
        f"{100 * sum(g['n'] for g in small) / total:.1f}% of bright px"
    )
    giant = [g for g in geo if g["n"] > MAX_COMPONENT]
    print(
        f"  terrain components (>{MAX_COMPONENT}px): {len(giant)}  "
        f"sizes {[g['n'] for g in giant]}"
    )

    boxes = [(g["x0"], g["y0"], g["x1"], g["y1"]) for g in small]
    groups = cluster(boxes, CLUSTER_RADIUS)
    merged = []
    for g in groups:
        xs0 = min(boxes[i][0] for i in g)
        ys0 = min(boxes[i][1] for i in g)
        xs1 = max(boxes[i][2] for i in g)
        ys1 = max(boxes[i][3] for i in g)
        merged.append((xs0, ys0, xs1, ys1, len(g)))
    merged.sort(key=lambda b: (b[1], b[0]))
    print(f"\nannotation clusters: {len(merged)}")
    for i, (x0, y0, x1, y1, n) in enumerate(merged):
        print(f"  {i:>3}  x {x0:>5}-{x1:<5} y {y0:>5}-{y1:<5}  parts {n}")

    if dump:
        over = img.copy()
        d = ImageDraw.Draw(over)
        for x0, y0, x1, y1, _ in merged:
            d.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=(255, 0, 0), width=1)
        out = Path("/tmp/opencode/shots/gen3/anno_overlay.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        over.save(out)
        # gamma-boosted copy so the boxes are visible against the terrain
        boost = np.clip(np.power(np.clip(lum / 255, 0, 1), 0.35) * 255, 0, 255)
        bimg = Image.fromarray(boost.astype("uint8")).convert("RGB")
        d2 = ImageDraw.Draw(bimg)
        for x0, y0, x1, y1, _ in merged:
            d2.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=(255, 40, 40), width=1)
        bimg.save(out.with_name("anno_overlay_boost.png"))
        print(f"\nwrote {out} and {out.with_name('anno_overlay_boost.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())