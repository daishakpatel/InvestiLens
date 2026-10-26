#!/usr/bin/env python3
"""Stitch the vertical-slice Playwright frames into docs/media/demo.gif (Phase 7l, NFR-ME-012).

    cd backend && uv run python ../scripts/make_demo_gif.py

Reads e2e/test-results/vertical-slice/NN-*.png (written by e2e/tests/vertical-slice.spec.ts) in
order and holds each frame for an equal share of `--seconds`, so the GIF always shows exactly
what the last passing run showed. Pillow is a dev dependency for this script only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
_FRAMES = _ROOT / "e2e" / "test-results" / "vertical-slice"
_OUT = _ROOT / "docs" / "media" / "demo.gif"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build docs/media/demo.gif from Playwright frames")
    parser.add_argument("--seconds", type=float, default=60.0, help="total length (default 60)")
    parser.add_argument("--width", type=int, default=960, help="output width in pixels")
    args = parser.parse_args()

    paths = sorted(_FRAMES.glob("[0-9][0-9]-*.png"))
    if not paths:
        print(f"no frames in {_FRAMES}; run scripts/vertical_slice.sh first")
        return 1
    frames = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        height = round(image.height * args.width / image.width)
        resized = image.resize((args.width, height), Image.Resampling.LANCZOS)
        frames.append(resized.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    hold_ms = int(args.seconds * 1000 / len(frames))
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        _OUT, save_all=True, append_images=frames[1:], duration=hold_ms, loop=0, optimize=True
    )
    size_kb = _OUT.stat().st_size // 1024
    print(f"wrote {_OUT.relative_to(_ROOT)}: {len(frames)} frames, {hold_ms} ms each, {size_kb} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
