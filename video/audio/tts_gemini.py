#!/usr/bin/env python3
"""Narration with Gemini text-to-speech (one WAV per clip), cached so unchanged clips cost nothing.

  GOOGLE_API_KEY=... python3 video/audio/tts_gemini.py [--voice Charon] [--model gemini-3.8-flash-tts] [--out video/audio/out/tts]

Reads narration.json ({clip_id: text}). Gemini TTS reads the whole prompt aloud, so the prompt is the plain narration
text (no "say it like..." prefix); pick the tone with the voice. Output: 24 kHz mono WAV per clip plus manifest.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default="Charon")
    ap.add_argument("--model", default="gemini-3.8-flash-tts")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "tts")
    a = ap.parse_args()
    clips = {k: v for k, v in json.loads((HERE / "narration.json").read_text()).items() if not k.startswith("_")}
    a.out.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    cfg = types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=a.voice))))
    manifest, made = {}, 0
    for cid, text in clips.items():
        key = hashlib.sha256(f"{a.model}|{a.voice}|{text}".encode()).hexdigest()[:16]
        wav = a.out / f"{cid}_{a.voice}_{key}.wav"
        if not wav.exists():
            for attempt in range(8):  # TTS models allow ~10 requests/minute: wait as told and retry
                try:
                    r = client.models.generate_content(model=a.model, contents=text, config=cfg)
                    break
                except Exception as e:
                    m = re.search(r"retry in ([0-9.]+)s", str(e))
                    if "429" not in str(e) or attempt == 7:
                        raise
                    time.sleep(float(m.group(1)) + 1 if m else 10)
            wav.write_bytes(r.candidates[0].content.parts[0].inline_data.data)
            made += 1
        manifest[cid] = wav.name
    (a.out / "manifest.json").write_text(json.dumps({"voice": a.voice, "model": a.model, "clips": manifest}, indent=1))
    print(f"{len(manifest)} clips ({made} generated, {len(manifest) - made} cached) -> {a.out}")


if __name__ == "__main__":
    main()
