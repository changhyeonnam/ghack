"""Orchestrates the five stages, persists artifacts, writes audit entries and keeps case stats.

Stages: intake -> extract -> cashflow -> analyze -> challenge. Each stage is idempotent and re-runnable; running a
later stage automatically runs missing prerequisites.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .agents.analyst import run_analyst
from .agents.challenger import run_challenger
from .agents.explainer import run_explainer
from .agents.extractor import run_extraction
from .agents.intake import run_intake
from .agents.runner import BudgetExceeded, CacheMiss
from .config import Settings
from .feedback import compute_priorities, load_priorities
from .llm.groundtruth import GroundTruth, load_manifests, load_past_index
from .schemas import (
    AuditEntry, Case, CaseCreate, CashflowSummary, ChallengeResult, CustomerLetter, Decision, DocType, DocumentExtraction, DocumentMeta,
    IntakeResult, Memo, ObjectionResolution, StageName, utcnow_iso,
)
from .storage import Repository
from .tools.cashflow import compute_cashflow
from .tools.documents import page_count, phash16_of_file, phash_pages, sha256_hex, sniff_mime

log = logging.getLogger("ledgerlens.pipeline")
STAGE_ORDER = [StageName.intake, StageName.extract, StageName.cashflow, StageName.analyze, StageName.challenge]


@functools.lru_cache(maxsize=512)
def _doc_facts_cached(sha: str, mime: str, data: bytes) -> tuple[int, tuple[str, ...]]:
    return page_count(data, mime), tuple(phash_pages(data, mime))


def _doc_facts(sha: str, data: bytes, mime: str) -> tuple[int, tuple[str, ...]]:
    return _doc_facts_cached(sha, mime, data)


class PipelineError(RuntimeError):
    pass


class Pipeline:
    def __init__(self, repo: Repository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self._locks: dict[str, asyncio.Lock] = {}
        self._gt: Optional[GroundTruth] = None

    # ------------------------------------------------------------------ utils
    def lock(self, case_id: str) -> asyncio.Lock:
        return self._locks.setdefault(case_id, asyncio.Lock())

    def audit(self, case_id: str, actor: str, event: str, **details: Any) -> None:
        self.repo.add_audit(AuditEntry(id=uuid.uuid4().hex[:12], case_id=case_id, actor=actor, event=event, details=details))

    def ground_truth(self) -> GroundTruth:
        if self._gt is None:
            self._gt = GroundTruth(str(self.settings.synth_dir))
        return self._gt

    def mock_context(self, case: Case) -> dict[str, Any]:
        synth_id = next((t.split(":", 1)[1] for t in case.tags if t.startswith("synthetic:")), None)
        return {"case": case.model_dump(mode="json"), "docs": [d.model_dump(mode="json") for d in case.documents], "gt": self.ground_truth(), "synthetic_case_id": synth_id}

    def require_case(self, case_id: str) -> Case:
        c = self.repo.get_case(case_id)
        if not c:
            raise KeyError(case_id)
        return c

    def artifact(self, case_id: str, name: str, model: Any) -> Any:
        data = self.repo.get_artifact(case_id, name)
        return model.model_validate(data) if data else None

    def extractions(self, case_id: str) -> list[DocumentExtraction]:
        data = self.repo.get_artifact(case_id, "extractions")
        return [DocumentExtraction.model_validate(x) for x in (data or {}).get("items", [])]

    # ------------------------------------------------------------------ cases & documents
    def create_case(self, body: CaseCreate, *, is_demo: bool = False, tags: Optional[list[str]] = None, expected: Optional[str] = None,
                    workspace: Optional[str] = None) -> Case:
        case = Case(id=uuid.uuid4().hex[:10], **body.model_dump(), is_demo=is_demo, tags=tags or [], demo_expected_outcome=expected,
                    workspace=workspace)
        self.repo.save_case(case)
        self.audit(case.id, "system", "case_created", name=case.name, business=case.business_name)
        return case

    def add_document(self, case: Case, filename: str, data: bytes) -> DocumentMeta:
        mime = sniff_mime(filename, data)
        if mime not in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
            raise PipelineError(f"Unsupported file type for {filename}")
        if len(data) > self.settings.max_upload_mb * 1024 * 1024:
            raise PipelineError(f"{filename} exceeds {self.settings.max_upload_mb} MB")
        n = len(case.documents) + 1
        doc_id = f"D{n:02d}"
        while any(d.doc_id == doc_id for d in case.documents):
            n += 1
            doc_id = f"D{n:02d}"
        sha = sha256_hex(data)
        # Content-addressed: identical files (every browser's copy of a demo case) share one stored blob, and the page
        # count / perceptual hashes are computed once per process.
        path = f"docs/{sha}/{Path(filename).name}"
        if not self.repo.has_blob(path):
            self.repo.put_blob(path, data, mime)
        pages, hashes = _doc_facts(sha, data, mime)
        meta = DocumentMeta(doc_id=doc_id, filename=Path(filename).name, mime_type=mime, size_bytes=len(data), pages=pages,
                            sha256=sha, storage_path=path, page_hashes=list(hashes))
        case.documents.append(meta)
        case.status = "documents_uploaded" if case.status == "draft" else case.status
        case.updated_at = utcnow_iso()
        return meta

    def remove_document(self, case: Case, doc_id: str) -> None:
        case.documents = [d for d in case.documents if d.doc_id != doc_id]
        self.repo.delete_blob_prefix(f"cases/{case.id}/docs/{doc_id}/")
        self.repo.delete_blob_prefix(f"cases/{case.id}/llm/{doc_id}/")
        self.repo.delete_blob_prefix(f"cases/{case.id}/renders/{doc_id}/")
        case.updated_at = utcnow_iso()

    # ------------------------------------------------------------------ stages
    async def run_stage(self, case_id: str, stage: StageName) -> Case:
        async with self.lock(case_id):
            case = self.require_case(case_id)
            if not case.documents:
                raise PipelineError("Upload at least one document before running the pipeline")
            idx = STAGE_ORDER.index(stage)
            for prereq in STAGE_ORDER[:idx]:
                if case.stage(prereq).status != "done":
                    case = await self._run_one(case, prereq)
            return await self._run_one(case, stage)

    async def run_all(self, case_id: str) -> Case:
        case = self.require_case(case_id)
        for st in STAGE_ORDER:
            case = await self.run_stage(case_id, st)
        return case

    async def _run_one(self, case: Case, stage: StageName) -> Case:
        st = case.stage(stage)
        st.status, st.started_at, st.finished_at, st.error = "running", utcnow_iso(), None, None
        case.status = "processing"
        case.updated_at = utcnow_iso()
        self.repo.save_case(case)
        t0 = time.time()
        traces_before = len(self.repo.list_traces(case.id))
        try:
            if stage == StageName.intake:
                await self._intake(case)
            elif stage == StageName.extract:
                await self._extract(case)
            elif stage == StageName.cashflow:
                self._cashflow(case)
            elif stage == StageName.analyze:
                await self._analyze(case)
            elif stage == StageName.challenge:
                await self._challenge(case)
            st.status, st.finished_at = "done", utcnow_iso()
            # invalidate downstream stages
            for later in STAGE_ORDER[STAGE_ORDER.index(stage) + 1:]:
                ls = case.stage(later)
                if ls.status == "done":
                    ls.status = "pending"
            case.status = {"analyze": "memo_ready", "challenge": "challenged"}.get(stage.value, case.status)
            if stage not in (StageName.analyze, StageName.challenge):
                case.status = "processing" if any(s.status == "done" for s in case.stages) else "documents_uploaded"
                if case.stage(StageName.challenge).status == "done":
                    case.status = "challenged"
                elif case.stage(StageName.analyze).status == "done":
                    case.status = "memo_ready"
            self.audit(case.id, "system", f"stage_{stage.value}_done", seconds=round(time.time() - t0, 1))
        except Exception as e:  # keep the failure visible in the UI
            log.exception("stage %s failed for case %s", stage.value, case.id)
            st.status, st.finished_at, st.error = "failed", utcnow_iso(), f"{type(e).__name__}: {e}"[:500]
            case.status = "failed"
            self.audit(case.id, "system", f"stage_{stage.value}_failed", error=st.error)
            self._refresh_stats(case, time.time() - t0, traces_before)
            self.repo.save_case(case)
            if isinstance(e, (BudgetExceeded, CacheMiss)):
                raise  # surfaced as 402/503 so the UI can show the AI-limit notice
            raise PipelineError(st.error) from e
        new_traces = self.repo.list_traces(case.id)[traces_before:]
        st.cached = bool(new_traces) and all(t.cached for t in new_traces)
        self._refresh_stats(case, time.time() - t0, traces_before)
        case.updated_at = utcnow_iso()
        self.repo.save_case(case)
        return case

    def _refresh_stats(self, case: Case, seconds: float, traces_before: int) -> None:
        traces = self.repo.list_traces(case.id)
        case.stats.total_cost_usd = round(sum(t.cost_usd for t in traces), 6)
        case.stats.total_tokens = sum(t.input_tokens + t.output_tokens + t.thinking_tokens for t in traces)
        case.stats.n_llm_calls = len(traces)
        case.stats.n_cached_calls = sum(1 for t in traces if t.cached)
        case.stats.processing_seconds = round(case.stats.processing_seconds + seconds, 1)

    async def _intake(self, case: Case) -> None:
        res = await run_intake(case, repo=self.repo, settings=self.settings, mock_context=self.mock_context(case))
        self.repo.save_artifact(case.id, "intake", res.model_dump(mode="json"))
        self.audit(case.id, "agent:intake", "documents_classified", types={d.doc_id: d.doc_type.value for d in res.documents})

    async def _extract(self, case: Case) -> None:
        items = await run_extraction(case, repo=self.repo, settings=self.settings, mock_context=self.mock_context(case))
        self.repo.save_artifact(case.id, "extractions", {"items": [x.model_dump(mode="json") for x in items]})
        n_tx = sum(len(x.bank_statement.transactions) for x in items if x.bank_statement)
        failed = [x.doc_id for x in items if (x.extraction_notes or "").startswith("EXTRACTION FAILED")]
        self.audit(case.id, "agent:extractor", "documents_extracted", documents=len(items), transactions=n_tx, failed=failed)
        if failed and all(x.doc_id in failed for x in items if x.doc_type == DocType.bank_statement):
            raise PipelineError(f"Bank statement extraction failed for {', '.join(failed)}; see audit log")

    def _cashflow(self, case: Case) -> None:
        exs = self.extractions(case.id)
        holders = [x.bank_statement.account_holder for x in exs if x.bank_statement and x.bank_statement.account_holder] + [case.business_name]
        cf = compute_cashflow(exs, case.currency, holders, case.requested_amount)
        self.repo.save_artifact(case.id, "cashflow", cf.model_dump(mode="json"))
        case.stats.n_figures = len(cf.figures)
        self.audit(case.id, "tool:compute_cashflow", "cashflow_computed", months=cf.months_covered, figures=len(cf.figures), balance_breaks=len(cf.balance_checks),
                   recurring=len(cf.recurring_transfers))

    async def _analyze(self, case: Case) -> None:
        cf = self.artifact(case.id, "cashflow", CashflowSummary)
        intake = self.artifact(case.id, "intake", IntakeResult)
        exs = self.extractions(case.id)
        prev = self.repo.get_artifact(case.id, "memo")
        memo = await run_analyst(case, cashflow=cf, extractions=exs, intake=intake, repo=self.repo, settings=self.settings, mock_context=self.mock_context(case))
        memo.version = (prev or {}).get("version", 0) + 1
        self.repo.save_artifact(case.id, "memo", memo.model_dump(mode="json"))
        case.stats.n_unsourced = len(memo.unsourced_numerals) + len(memo.unresolved_figure_ids) + sum(1 for f in memo.figures if not f.is_sourced())
        self.audit(case.id, "agent:analyst", "memo_drafted", version=memo.version, recommendation=memo.draft.recommendation, figures=len(memo.figures),
                   unsourced=case.stats.n_unsourced, prompt_version=memo.prompt_version, model=memo.model)

    async def _challenge(self, case: Case) -> None:
        memo = self.artifact(case.id, "memo", Memo)
        cf = self.artifact(case.id, "cashflow", CashflowSummary)
        intake = self.artifact(case.id, "intake", IntakeResult)
        exs = self.extractions(case.id)
        past = (self.repo.get_global("past_case_index") or {}).get("items") or load_past_index(str(self.settings.synth_dir))
        prev = self.repo.get_artifact(case.id, "challenge")
        res = await run_challenger(case, memo=memo, cashflow=cf, extractions=exs, intake=intake, repo=self.repo, settings=self.settings,
                                   mock_context=self.mock_context(case), past_index=past, priorities=load_priorities(self.repo))
        res.version = (prev or {}).get("version", 0) + 1
        self.repo.save_artifact(case.id, "challenge", res.model_dump(mode="json"))
        case.stats.n_objections = len(res.objections)
        case.objection_resolutions = [ObjectionResolution(objection_id=o.id) for o in res.objections]
        self.audit(case.id, "agent:challenger", "memo_challenged", version=res.version, objections=len(res.objections),
                   by_severity={s: sum(1 for o in res.objections if o.severity.value == s) for s in ("critical", "high", "medium", "low")}, prompt_version=res.prompt_version)

    # ------------------------------------------------------------------ human decisions
    def resolve_objection(self, case: Case, objection_id: str, status: str, note: Optional[str], by: Optional[str]) -> Case:
        found = False
        for r in case.objection_resolutions:
            if r.objection_id == objection_id:
                r.status, r.note, r.by, r.at = status, note, by, utcnow_iso()  # type: ignore[assignment]
                found = True
        if not found:
            case.objection_resolutions.append(ObjectionResolution(objection_id=objection_id, status=status, note=note, by=by, at=utcnow_iso()))  # type: ignore[arg-type]
        case.updated_at = utcnow_iso()
        self.repo.save_case(case)
        self.audit(case.id, f"underwriter:{by or 'anonymous'}", "objection_resolved", objection_id=objection_id, status=status, note=note)
        return case

    def sign_decision(self, case: Case, decision: Decision) -> Case:
        decision.case_id = case.id
        decision.objection_resolutions = list(case.objection_resolutions)
        case.decision = decision
        case.status = "decided"
        case.updated_at = utcnow_iso()
        self.repo.save_case(case)
        self.audit(case.id, f"underwriter:{decision.underwriter}", "decision_signed", outcome=decision.outcome, conditions=decision.conditions,
                   accepted=[r.objection_id for r in decision.objection_resolutions if r.status == "accepted"],
                   dismissed=[r.objection_id for r in decision.objection_resolutions if r.status == "dismissed"])
        fp = compute_priorities(self.repo)
        self.audit(case.id, "system", "challenger_priorities_updated", n_decisions=fp.n_decisions)
        return case

    async def explain(self, case: Case, language: str) -> CustomerLetter:
        if not case.decision:
            raise PipelineError("Sign a decision before generating the customer letter")
        letter = await run_explainer(case, decision=case.decision, challenge=self.artifact(case.id, "challenge", ChallengeResult), memo=self.artifact(case.id, "memo", Memo),
                                     language=language, repo=self.repo, settings=self.settings, mock_context=self.mock_context(case))
        self.repo.save_artifact(case.id, "letter", letter.model_dump(mode="json"))
        self.audit(case.id, "agent:explainer", "customer_letter_generated", language=language)
        return letter

    # ------------------------------------------------------------------ demo data
    SHAREABLE_STATUSES = ("memo_ready", "challenged", "decided")

    def list_cases(self, workspace: Optional[str] = None) -> list[Case]:
        """A workspace sees its own cases plus analysed cases other visitors chose to share (never their demo copies)."""
        own = [c for c in self.repo.list_cases() if c.workspace == workspace]
        others = [c for c in self.repo.list_cases()
                  if c.workspace != workspace and c.workspace and c.shared and not c.is_demo and c.status in self.SHAREABLE_STATUSES]
        return own + others

    def own_cases(self, workspace: Optional[str]) -> list[Case]:
        return [c for c in self.repo.list_cases() if c.workspace == workspace]

    def seed_demo_cases(self, force: bool = False, workspace: Optional[str] = None) -> list[str]:
        """Demo cases per workspace, so one judge signing case B does not lock it for the next. LLM cache keys do not
        include the case id, so a workspace's copies replay the cached run at no Gemini cost."""
        self.ground_truth().refresh()
        manifests = self.ground_truth().manifests
        past = load_past_index(str(self.settings.synth_dir))
        if past:
            for entry in past:  # add a 16x16 perceptual hash computed from the file itself when available
                p = Path(self.settings.synth_dir) / "past_cases" / entry.get("case_id", "") / entry.get("filename", "")
                if p.exists() and not entry.get("phash16"):
                    try:
                        entry["phash16"] = phash16_of_file(str(p))
                    except Exception:
                        pass
            self.repo.save_global("past_case_index", {"items": past})
        created: list[str] = []
        existing = {next((t for t in c.tags if t.startswith("synthetic:")), None): c for c in self.own_cases(workspace) if c.is_demo}
        for sid, m in manifests.items():
            tag = f"synthetic:{sid}"
            if tag in existing and not force:
                created.append(existing[tag].id)
                continue
            if tag in existing and force:
                self.repo.delete_case(existing[tag].id)
            lang = str(m.get("language", "en")).replace("+", "/").split("/")[0].strip() or "en"
            body = CaseCreate(name=m["name"], business_name=m["business_name"], sector=m.get("sector", ""), country=m.get("country", ""), language=lang,
                              currency=m.get("currency", "USD"), requested_amount=m.get("requested_amount"))
            case = self.create_case(body, is_demo=True, tags=["synthetic", tag], expected=m.get("expected_outcome"), workspace=workspace)
            for d in m["documents"]:
                p = Path(m["_dir"]) / "docs" / d["filename"]
                if p.exists():
                    self.add_document(case, d["filename"], p.read_bytes())
            self.repo.save_case(case)
            created.append(case.id)
        return created


_ = (json, mimetypes, DocType)
