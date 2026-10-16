"""Persistence. One interface, two backends:

* LocalRepository  - JSON files under data/runtime (dev, tests, offline demo)
* GcpRepository    - Firestore (cases, artifacts, audit, traces, cache) + Cloud Storage (documents, renders)

Artifacts are whole JSON documents keyed by (case_id, name). Audit and traces are append-only.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from .config import Settings
from .schemas import AgentTrace, AuditEntry, Case


class Repository(ABC):
    # ---- cases ----
    @abstractmethod
    def list_cases(self) -> list[Case]: ...
    @abstractmethod
    def get_case(self, case_id: str) -> Optional[Case]: ...
    @abstractmethod
    def save_case(self, case: Case) -> None: ...
    @abstractmethod
    def delete_case(self, case_id: str) -> None: ...

    # ---- blobs ----
    @abstractmethod
    def put_blob(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    @abstractmethod
    def get_blob(self, path: str) -> Optional[bytes]: ...
    @abstractmethod
    def delete_blob_prefix(self, prefix: str) -> None: ...

    # ---- artifacts ----
    @abstractmethod
    def save_artifact(self, case_id: str, name: str, data: dict[str, Any]) -> None: ...
    @abstractmethod
    def get_artifact(self, case_id: str, name: str) -> Optional[dict[str, Any]]: ...
    @abstractmethod
    def delete_artifact(self, case_id: str, name: str) -> None: ...

    # ---- append-only ----
    @abstractmethod
    def add_audit(self, entry: AuditEntry) -> None: ...
    @abstractmethod
    def list_audit(self, case_id: str) -> list[AuditEntry]: ...
    @abstractmethod
    def add_trace(self, trace: AgentTrace) -> None: ...
    @abstractmethod
    def list_traces(self, case_id: str) -> list[AgentTrace]: ...

    # ---- llm cache & globals ----
    @abstractmethod
    def cache_get(self, key: str) -> Optional[dict[str, Any]]: ...
    @abstractmethod
    def cache_put(self, key: str, value: dict[str, Any]) -> None: ...
    @abstractmethod
    def get_global(self, name: str) -> Optional[dict[str, Any]]: ...
    @abstractmethod
    def save_global(self, name: str, data: dict[str, Any]) -> None: ...

    # ---- AI spend (persisted so the budget cap survives restarts and spans instances) ----
    def get_spend(self) -> float:
        return float((self.get_global("ai_spend") or {}).get("total_usd", 0.0))

    def add_spend(self, usd: float) -> float:
        total = self.get_spend() + usd
        self.save_global("ai_spend", {"total_usd": total})
        return total


# ---------------------------------------------------------------------------
# Local filesystem
# ---------------------------------------------------------------------------
class LocalRepository(Repository):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _case_dir(self, case_id: str) -> Path:
        return self.root / "cases" / case_id

    @staticmethod
    def _read_json(path: Path) -> Optional[dict[str, Any]]:
        if not path.exists():
            return None
        return json.loads(path.read_text("utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(path)

    # cases
    def list_cases(self) -> list[Case]:
        out: list[Case] = []
        base = self.root / "cases"
        if base.exists():
            for d in base.iterdir():
                data = self._read_json(d / "case.json")
                if data:
                    out.append(Case.model_validate(data))
        out.sort(key=lambda c: c.created_at, reverse=True)
        return out

    def get_case(self, case_id: str) -> Optional[Case]:
        data = self._read_json(self._case_dir(case_id) / "case.json")
        return Case.model_validate(data) if data else None

    def save_case(self, case: Case) -> None:
        with self._lock:
            self._write_json(self._case_dir(case.id) / "case.json", case.model_dump(mode="json"))

    def delete_case(self, case_id: str) -> None:
        import shutil
        with self._lock:
            shutil.rmtree(self._case_dir(case_id), ignore_errors=True)
            shutil.rmtree(self.root / "blobs" / "cases" / case_id, ignore_errors=True)

    # blobs
    def put_blob(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self.root / "blobs" / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_blob(self, path: str) -> Optional[bytes]:
        p = self.root / "blobs" / path
        return p.read_bytes() if p.exists() else None

    def delete_blob_prefix(self, prefix: str) -> None:
        import shutil
        p = self.root / "blobs" / prefix
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

    # artifacts
    def save_artifact(self, case_id: str, name: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._write_json(self._case_dir(case_id) / "artifacts" / f"{name}.json", data)

    def get_artifact(self, case_id: str, name: str) -> Optional[dict[str, Any]]:
        return self._read_json(self._case_dir(case_id) / "artifacts" / f"{name}.json")

    def delete_artifact(self, case_id: str, name: str) -> None:
        p = self._case_dir(case_id) / "artifacts" / f"{name}.json"
        if p.exists():
            p.unlink()

    # append-only
    def _append(self, path: Path, data: dict[str, Any]) -> None:
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read_lines(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]

    def add_audit(self, entry: AuditEntry) -> None:
        self._append(self._case_dir(entry.case_id) / "audit.jsonl", entry.model_dump(mode="json"))

    def list_audit(self, case_id: str) -> list[AuditEntry]:
        return [AuditEntry.model_validate(x) for x in self._read_lines(self._case_dir(case_id) / "audit.jsonl")]

    def add_trace(self, trace: AgentTrace) -> None:
        self._append(self._case_dir(trace.case_id) / "traces.jsonl", trace.model_dump(mode="json"))

    def list_traces(self, case_id: str) -> list[AgentTrace]:
        return [AgentTrace.model_validate(x) for x in self._read_lines(self._case_dir(case_id) / "traces.jsonl")]

    # cache & globals
    def cache_get(self, key: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.root / "cache" / f"{key}.json")

    def cache_put(self, key: str, value: dict[str, Any]) -> None:
        self._write_json(self.root / "cache" / f"{key}.json", value)

    def get_global(self, name: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.root / "global" / f"{name}.json")

    def add_spend(self, usd: float) -> float:
        with self._lock:
            return super().add_spend(usd)

    def save_global(self, name: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._write_json(self.root / "global" / f"{name}.json", data)


# ---------------------------------------------------------------------------
# Google Cloud: Firestore + Cloud Storage
# ---------------------------------------------------------------------------
class GcpRepository(Repository):
    """Firestore documents are capped at 1 MiB; anything bigger is spilled to GCS with a pointer."""

    SPILL_BYTES = 900_000

    def __init__(self, project: Optional[str], bucket: str, database: str = "(default)", prefix: str = "ledgerlens"):
        from google.cloud import firestore, storage  # lazy: only needed in cloud mode

        self.db = firestore.Client(project=project, database=database)
        self.gcs = storage.Client(project=project)
        self.bucket = self.gcs.bucket(bucket)
        self.prefix = prefix

    def _col(self, name: str):
        return self.db.collection(f"{self.prefix}_{name}")

    # cases
    def list_cases(self) -> list[Case]:
        docs = self._col("cases").order_by("created_at", direction="DESCENDING").stream()
        return [Case.model_validate(d.to_dict()) for d in docs]

    def get_case(self, case_id: str) -> Optional[Case]:
        snap = self._col("cases").document(case_id).get()
        return Case.model_validate(snap.to_dict()) if snap.exists else None

    def save_case(self, case: Case) -> None:
        self._col("cases").document(case.id).set(case.model_dump(mode="json"))

    def delete_case(self, case_id: str) -> None:
        ref = self._col("cases").document(case_id)
        for sub in ("artifacts", "audit", "traces"):
            for d in ref.collection(sub).stream():
                d.reference.delete()
        ref.delete()
        self.delete_blob_prefix(f"cases/{case_id}/")

    # blobs
    def put_blob(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.bucket.blob(path).upload_from_string(data, content_type=content_type)

    def get_blob(self, path: str) -> Optional[bytes]:
        blob = self.bucket.blob(path)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    def delete_blob_prefix(self, prefix: str) -> None:
        for blob in self.gcs.list_blobs(self.bucket, prefix=prefix):
            blob.delete()

    # artifacts
    def _art_ref(self, case_id: str, name: str):
        return self._col("cases").document(case_id).collection("artifacts").document(name)

    def save_artifact(self, case_id: str, name: str, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False)
        if len(raw.encode("utf-8")) > self.SPILL_BYTES:
            path = f"cases/{case_id}/artifacts/{name}.json"
            self.put_blob(path, raw.encode("utf-8"), "application/json")
            self._art_ref(case_id, name).set({"gcs_blob": path})
        else:
            self._art_ref(case_id, name).set({"json_blob": raw})

    def get_artifact(self, case_id: str, name: str) -> Optional[dict[str, Any]]:
        snap = self._art_ref(case_id, name).get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        if "gcs_blob" in d:
            raw = self.get_blob(d["gcs_blob"])
            return json.loads(raw) if raw else None
        if "json_blob" in d:
            return json.loads(d["json_blob"])
        return d

    def delete_artifact(self, case_id: str, name: str) -> None:
        self._art_ref(case_id, name).delete()

    # append-only
    def add_audit(self, entry: AuditEntry) -> None:
        self._col("cases").document(entry.case_id).collection("audit").document(entry.id).set(entry.model_dump(mode="json"))

    def list_audit(self, case_id: str) -> list[AuditEntry]:
        docs = self._col("cases").document(case_id).collection("audit").order_by("at").stream()
        return [AuditEntry.model_validate(d.to_dict()) for d in docs]

    def add_trace(self, trace: AgentTrace) -> None:
        self._col("cases").document(trace.case_id).collection("traces").document(trace.id).set(trace.model_dump(mode="json"))

    def list_traces(self, case_id: str) -> list[AgentTrace]:
        docs = self._col("cases").document(case_id).collection("traces").order_by("started_at").stream()
        return [AgentTrace.model_validate(d.to_dict()) for d in docs]

    # cache & globals
    def cache_get(self, key: str) -> Optional[dict[str, Any]]:
        snap = self._col("llm_cache").document(key).get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        if "gcs_blob" in d:
            raw = self.get_blob(d["gcs_blob"])
            return json.loads(raw) if raw else None
        return json.loads(d["json_blob"]) if "json_blob" in d else d

    def cache_put(self, key: str, value: dict[str, Any]) -> None:
        raw = json.dumps(value, ensure_ascii=False)
        if len(raw.encode("utf-8")) > self.SPILL_BYTES:
            path = f"llm_cache/{key}.json"
            self.put_blob(path, raw.encode("utf-8"), "application/json")
            self._col("llm_cache").document(key).set({"gcs_blob": path})
        else:
            self._col("llm_cache").document(key).set({"json_blob": raw})

    def get_global(self, name: str) -> Optional[dict[str, Any]]:
        snap = self._col("global").document(name).get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        return json.loads(d["json_blob"]) if "json_blob" in d else d

    def save_global(self, name: str, data: dict[str, Any]) -> None:
        self._col("global").document(name).set({"json_blob": json.dumps(data, ensure_ascii=False)})

    def get_spend(self) -> float:
        snap = self._col("global").document("ai_spend_counter").get()
        return float((snap.to_dict() or {}).get("total_usd", 0.0)) if snap.exists else 0.0

    def add_spend(self, usd: float) -> float:
        from google.cloud import firestore
        ref = self._col("global").document("ai_spend_counter")
        ref.set({"total_usd": firestore.Increment(usd)}, merge=True)  # atomic across instances
        return self.get_spend()


def build_repository(settings: Settings) -> Repository:
    if settings.storage == "gcp":
        if not settings.gcs_bucket:
            raise RuntimeError("LEDGERLENS_GCS_BUCKET is required when LEDGERLENS_STORAGE=gcp")
        return GcpRepository(settings.gcp_project, settings.gcs_bucket, settings.firestore_database, settings.firestore_prefix)
    return LocalRepository(settings.local_data_dir)
