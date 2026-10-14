#!/usr/bin/env python
"""Cheap pre-flight for a Gemini API key: lists the configured models and makes one ~50-token call.

  GOOGLE_API_KEY=... backend/.venv/bin/python backend/scripts/check_gemini.py
Cost of this script: well under USD 0.001 (free on the Flash free tier).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402
from app.llm.pricing import estimate_cost_usd  # noqa: E402

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

s = get_settings()
if not s.google_api_key and not s.use_vertexai:
    sys.exit("No GOOGLE_API_KEY found (env or .env). Nothing was called.")
client = genai.Client(api_key=s.google_api_key) if not s.use_vertexai else genai.Client(vertexai=True, project=s.gcp_project, location=s.vertex_location)
names = {m.name.split("/")[-1] for m in client.models.list()}
for label, model in (("flash", s.model_flash), ("pro", s.model_pro)):
    print(f"{label}: {model} -> {'available' if model in names else 'NOT LISTED for this key'}")
candidates = sorted(n for n in names if n.startswith("gemini-3") and "image" not in n and "live" not in n and "tts" not in n)
print("other text models visible to this key:", ", ".join(candidates[:12]))
r = client.models.generate_content(model=s.model_flash, contents="Reply with the single word OK.",
                                   config=types.GenerateContentConfig(temperature=0, max_output_tokens=20))
u = r.usage_metadata
print("response:", (r.text or "").strip())
print(f"tokens in={u.prompt_token_count} out={u.candidates_token_count} thoughts={u.thoughts_token_count or 0}; "
      f"estimated cost USD {estimate_cost_usd(s.model_flash, u.prompt_token_count or 0, u.candidates_token_count or 0, u.thoughts_token_count or 0):.6f}")
