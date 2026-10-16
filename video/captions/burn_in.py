#!/usr/bin/env python3
"""Burn the caption PNGs (from make_captions.py) into a video with ffmpeg overlays.

  python3 video/captions/burn_in.py INPUT.mp4 OUTPUT.mp4 [--dir video/captions/out]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--dir", type=Path, default=HERE / "out")
    a = ap.parse_args()
    cues = json.loads((a.dir / "cues.json").read_text())
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(a.src)]
    for c in cues:
        cmd += ["-i", str(a.dir / c["png"])]
    chain, last = [], "0:v"
    for i, c in enumerate(cues, 1):
        out = f"v{i}"
        chain.append(f"[{last}][{i}:v]overlay=0:0:enable='between(t,{c['start']},{c['end']})'[{out}]")
        last = out
    cmd += ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?", "-c:v", "libx264", "-crf", "20",
            "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(a.dst)]
    subprocess.run(cmd, check=True)
    print(f"burned {len(cues)} captions -> {a.dst}")


if __name__ == "__main__":
    main()
