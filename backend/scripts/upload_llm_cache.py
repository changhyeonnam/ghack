#!/usr/bin/env python
"""Copy a local LLM cache (<data dir>/cache/*.json) into the deployed store, so a `cache_only` Cloud Run service
replays the demo cases without calling Gemini.

  # dry run: what would be copied
  backend/.venv/bin/python backend/scripts/upload_llm_cache.py data/runtime_live/cache --dry-run
  # into Firestore + GCS (uses your gcloud application-default credentials)
  LEDGERLENS_STORAGE=gcp GOOGLE_CLOUD_PROJECT=... LEDGERLENS_GCS_BUCKET=...-ledgerlens-docs \\
    backend/.venv/bin/python backend/scripts/upload_llm_cache.py data/runtime_live/cache

Build the cache with the same code you deploy (portable cache keys, see app/llm/image_ids.py): run
`benchmark/run_benchmark.py` live once, or replay an older cache with LEDGERLENS_LLM_MODE=cache_only to re-key it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402
from app.storage import Repository, build_repository  # noqa: E402


def copy_cache(src: Path, repo: Repository, dry_run: bool = False) -> dict[str, int]:
    files = sorted(src.glob("*.json"))
    stats = {"files": len(files), "copied": 0, "already_present": 0, "bytes": 0}
    for f in files:
        key = f.stem
        stats["bytes"] += f.stat().st_size
        if repo.cache_get(key) is not None:
            stats["already_present"] += 1
            continue
        if not dry_run:
            repo.cache_put(key, json.loads(f.read_text("utf-8")))
        stats["copied"] += 1
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cache_dir", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.cache_dir.is_dir():
        sys.exit(f"{a.cache_dir} is not a directory")
    s = get_settings()
    print(f"target storage={s.storage} project={s.gcp_project or '-'} bucket={s.gcs_bucket or '-'}{' (dry run)' if a.dry_run else ''}")
    print(copy_cache(a.cache_dir, build_repository(s), a.dry_run))


if __name__ == "__main__":
    main()
