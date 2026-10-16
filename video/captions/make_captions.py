#!/usr/bin/env python3
"""Captions for the demo video: SRT for YouTube + transparent PNG overlays for burned-in subtitles.

  python3 video/captions/make_captions.py TIMELINE.json [--out video/captions/out] [--offset 0.0]

TIMELINE.json is the video's narration timeline: {"audio": [[clip_id, start_s, duration_s], ...], ...}.
captions.json (next to this script) holds the on-screen text per clip; " | " splits a clip into several captions,
and each caption gets a share of the clip's duration proportional to its length. Edit captions.json, re-run, then
run the printed ffmpeg command (or apply_captions.sh) to burn them in. Needs Pillow; ffmpeg does not need libass.
"""
from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H = 1920, 1080
FONT_CANDIDATES = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
                   "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
SIZE, MAX_CHARS, BOTTOM = 40, 64, 70          # px font size, chars per line, px from the bottom
MIN_CUE, GAP = 1.2, 0.08                       # shortest caption (s), gap between captions (s)


def font() -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, SIZE)
    return ImageFont.load_default()


def cues(timeline: dict, texts: dict[str, str], offset: float) -> list[tuple[float, float, str]]:
    out = []
    for clip, start, dur in sorted(timeline["audio"], key=lambda c: c[1]):
        parts = [p.strip() for p in texts.get(clip, "").split("|") if p.strip()]
        if not parts:
            continue
        total = sum(len(p) for p in parts)
        t = start + offset
        for p in parts:
            d = max(MIN_CUE, dur * len(p) / total)
            out.append((t, t + d - GAP, p))
            t += d
    return out


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def render_png(text: str, path: Path, fnt) -> None:
    lines = textwrap.wrap(text, MAX_CHARS)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line_h = int(SIZE * 1.3)
    widths = [d.textlength(l, font=fnt) for l in lines]
    box_w, box_h = int(max(widths)) + 56, line_h * len(lines) + 28
    x0, y0 = (W - box_w) // 2, H - BOTTOM - box_h
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=14, fill=(15, 20, 24, 190))
    for i, (l, w) in enumerate(zip(lines, widths)):
        d.text(((W - w) / 2, y0 + 14 + i * line_h), l, font=fnt, fill=(255, 255, 255, 255))
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timeline", type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "out")
    ap.add_argument("--offset", type=float, default=0.0, help="shift all captions (s), e.g. after inserting an intro")
    a = ap.parse_args()
    texts = {k: v for k, v in json.loads((HERE / "captions.json").read_text()).items() if not k.startswith("_")}
    cs = cues(json.loads(a.timeline.read_text()), texts, a.offset)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "captions.srt").write_text("".join(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(cs, 1)))
    fnt = font()
    for i, (_, _, t) in enumerate(cs, 1):
        render_png(t, a.out / f"cap_{i:03d}.png", fnt)
    (a.out / "cues.json").write_text(json.dumps([{"png": f"cap_{i:03d}.png", "start": round(s, 3), "end": round(e, 3)}
                                                 for i, (s, e, _) in enumerate(cs, 1)], indent=1))
    print(f"{len(cs)} captions -> {a.out}/captions.srt, cap_*.png, cues.json")


if __name__ == "__main__":
    main()
