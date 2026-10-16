#!/usr/bin/env python3
"""Lay TTS clips onto the video timeline as one narration track.

  python3 video/audio/build_narration.py TIMELINE.json TTS_DIR OUT.wav [--max-tempo 1.3]

TIMELINE.json: {"total": s, "audio": [[clip_id, start_s, duration_s], ...]} (clip start times are fixed by the
picture). Each clip is trimmed of leading/trailing silence; if it is longer than its slot (until the next clip starts),
it is sped up just enough to fit (pitch kept, at most --max-tempo). Writes OUT.wav (48 kHz stereo) and
OUT.timeline.json with the real clip lengths, for captions.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

GAP = 0.15  # silence kept before the next clip


def duration(p: Path) -> float:
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timeline", type=Path)
    ap.add_argument("tts_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--max-tempo", type=float, default=1.3)
    a = ap.parse_args()
    tl = json.loads(a.timeline.read_text())
    files = json.loads((a.tts_dir / "manifest.json").read_text())["clips"]
    clips = sorted(tl["audio"], key=lambda c: c[1])
    total = float(tl["total"])
    tmp = Path(tempfile.mkdtemp())
    placed, report = [], []
    for i, (cid, start, _) in enumerate(clips):
        slot = (clips[i + 1][1] if i + 1 < len(clips) else total) - start - GAP
        trimmed = tmp / f"{cid}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a.tts_dir / files[cid]), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                        "-ar", "48000", "-ac", "2", str(trimmed)], check=True)
        d = duration(trimmed)
        tempo = max(1.0, d / slot) if slot > 0 else 1.0
        if tempo > a.max_tempo:
            report.append(f"WARNING {cid}: needs x{tempo:.2f} to fit {slot:.2f}s, capped at x{a.max_tempo}")
            tempo = a.max_tempo
        fitted = tmp / f"{cid}_fit.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(trimmed), "-af", f"atempo={tempo:.4f}", str(fitted)], check=True)
        fd = duration(fitted)
        placed.append((fitted, start, fd))
        report.append(f"{cid}: {d:.2f}s -> x{tempo:.2f} = {fd:.2f}s in slot {slot:.2f}s")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    for f, _, _ in placed:
        cmd += ["-i", str(f)]
    chains = [f"[{i}:a]adelay={int(s * 1000)}|{int(s * 1000)}[d{i}]" for i, (_, s, _) in enumerate(placed, 1)]
    mix = "".join(f"[d{i}]" for i in range(1, len(placed) + 1))
    cmd += ["-filter_complex", ";".join(chains) + f";[0:a]{mix}amix=inputs={len(placed) + 1}:duration=first:normalize=0[a]",
            "-map", "[a]", "-ar", "48000", str(a.out)]
    subprocess.run(cmd, check=True)
    out_tl = {"total": total, "audio": [[cid, s, round(fd, 3)] for (cid, _, _), (_, s, fd) in zip(clips, placed)]}
    a.out.with_suffix(".timeline.json").write_text(json.dumps(out_tl, indent=1))
    print("\n".join(report))
    print(f"narration -> {a.out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
