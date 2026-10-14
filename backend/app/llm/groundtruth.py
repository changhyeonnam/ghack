"""Reads the synthetic dataset's answer keys. Used by mock mode (offline dev) and by the benchmark."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


@lru_cache(maxsize=8)
def load_manifests(synth_dir: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    base = Path(synth_dir) / "cases"
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        mf = d / "manifest.json"
        if mf.exists():
            m = json.loads(mf.read_text("utf-8"))
            m["_dir"] = str(d)
            out[m["case_id"]] = m
    return out


def load_traps(synth_dir: str) -> list[dict[str, Any]]:
    p = Path(synth_dir) / "traps.json"
    return json.loads(p.read_text("utf-8"))["traps"] if p.exists() else []


def load_past_index(synth_dir: str) -> list[dict[str, Any]]:
    p = Path(synth_dir) / "past_cases" / "index.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else []


class GroundTruth:
    """Lookup of ground truth by (synthetic case id, filename)."""

    def __init__(self, synth_dir: str):
        self.synth_dir = synth_dir
        self.manifests = load_manifests(synth_dir)
        self._cache: dict[str, Any] = {}

    def refresh(self) -> None:
        load_manifests.cache_clear()
        self.manifests = load_manifests(self.synth_dir)
        self._cache.clear()

    def find_case_for_filename(self, filename: str, hint_case_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        if hint_case_id and hint_case_id in self.manifests:
            m = self.manifests[hint_case_id]
            if any(d["filename"] == filename for d in m["documents"]):
                return m
        for m in self.manifests.values():
            if any(d["filename"] == filename for d in m["documents"]):
                return m
        return None

    def doc_entry(self, manifest: dict[str, Any], filename: str) -> Optional[dict[str, Any]]:
        return next((d for d in manifest["documents"] if d["filename"] == filename), None)

    def _load(self, manifest: dict[str, Any], rel: str) -> Any:
        key = f"{manifest['case_id']}::{rel}"
        if key not in self._cache:
            p = Path(manifest["_dir"]) / rel
            if not p.exists():
                return None  # do not cache absence: the dataset may still be generating
            self._cache[key] = json.loads(p.read_text("utf-8"))
        return self._cache[key]

    def ground_truth_for(self, manifest: dict[str, Any], filename: str) -> tuple[Optional[str], Any]:
        """Return (doc_type, ground truth record for that file)."""
        d = self.doc_entry(manifest, filename)
        if not d:
            return None, None
        gt_path = d.get("ground_truth")
        if not gt_path:
            return d["doc_type"], None
        data = self._load(manifest, gt_path)
        if data is None:
            return d["doc_type"], None
        if isinstance(data, list):  # receipts / dashboards / ledger lists keyed by filename
            rec = next((x for x in data if x.get("filename") == filename), None)
            return d["doc_type"], rec
        return d["doc_type"], data
