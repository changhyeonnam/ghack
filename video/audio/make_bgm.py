#!/usr/bin/env python3
"""Royalty-free background music for the demo video, synthesised from code (numpy only).

  python3 video/audio/make_bgm.py SECONDS [--out video/audio/out/bgm.wav] [--seed 7]

A calm ambient pad: a four-chord loop (Am9 - Fmaj7 - Cmaj7 - G6, 8 s each) played by soft detuned saws through a
low-pass filter, a sub-octave sine, and a sparse high "glass" arpeggio. Slow envelopes, gentle stereo movement,
fade in/out. Deterministic for a given seed. Mix it under the narration with mix_bgm.sh (the music ducks while
someone speaks).
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48_000
CHORDS = [  # MIDI notes
    [57, 60, 64, 67, 71],   # Am9  (A C E G B)
    [53, 57, 60, 64, 67],   # Fmaj7 add9-ish (F A C E G)
    [48, 55, 60, 64, 71],   # Cmaj7 (C G C E B)
    [55, 59, 62, 64, 69],   # G6/9 (G B D E A)
]
BAR = 8.0


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def saw(f: float, t: np.ndarray, phase: float) -> np.ndarray:
    x = (f * t + phase) % 1.0
    return 2 * x - 1


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):  # chunked one-pole filter, applied twice for 12 dB/oct
        seg = x[i:i + 4096]
        out = np.empty_like(seg)
        for j, v in enumerate(seg):
            acc = (1 - a) * v + a * acc
            out[j] = acc
        y[i:i + 4096] = out
    return y


def envelope(n: int, attack: float, release: float) -> np.ndarray:
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[n - r:] = np.linspace(1, 0, r) ** 2
    return e


def render(seconds: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    left, right = np.zeros(n), np.zeros(n)
    bar_n = int(BAR * SR)
    t_bar = np.arange(bar_n + SR * 3) / SR  # chords overlap by 3 s
    for b in range(int(np.ceil(seconds / BAR))):
        chord = CHORDS[b % len(CHORDS)]
        start = b * bar_n
        seg = np.zeros(len(t_bar))
        for k, m in enumerate(chord):
            f = hz(m)
            for det in (-0.12, 0.0, 0.12):           # three detuned saws per note
                seg += saw(f * 2 ** (det / 12), t_bar, rng.random()) * (0.55 if det == 0 else 0.35)
        seg = lowpass(lowpass(seg / (len(chord) * 3), 900.0), 900.0)
        seg += 0.35 * np.sin(2 * np.pi * hz(chord[0] - 12) * t_bar)    # sub
        seg *= envelope(len(seg), 2.5, 3.5)
        pan = 0.5 + 0.25 * np.sin(2 * np.pi * (b * 0.37 + t_bar / 11.0))
        end = min(n, start + len(seg))
        left[start:end] += seg[:end - start] * (1 - pan[:end - start])
        right[start:end] += seg[:end - start] * pan[:end - start]
        for step in range(4):                         # sparse glass arpeggio, two notes per bar
            if rng.random() < 0.5:
                continue
            m = chord[rng.integers(2, len(chord))] + 12
            on = start + int((step * 2 + rng.random()) * SR)
            dur = int(1.8 * SR)
            if on + dur >= n:
                continue
            tt = np.arange(dur) / SR
            note = (np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(4 * np.pi * hz(m) * tt)) * np.exp(-tt * 2.2) * 0.12
            p = rng.uniform(0.25, 0.75)
            left[on:on + dur] += note * (1 - p)
            right[on:on + dur] += note * p
    mix = np.stack([left, right], axis=1)
    mix *= envelope(n, 2.0, 4.0)[:, None]
    mix /= np.max(np.abs(mix)) + 1e-9
    return (mix * 0.8 * 32767).astype(np.int16)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seconds", type=float)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "out" / "bgm.wav")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pcm = render(a.seconds, a.seed)
    with wave.open(str(a.out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"{a.seconds:.1f} s -> {a.out}")


if __name__ == "__main__":
    main()
