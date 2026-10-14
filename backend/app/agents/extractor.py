"""Stage 2: structured extraction per document, one Gemini call per document, every value with a source ref."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from google.genai import types
from pydantic import BaseModel

from ..config import Settings
from ..schemas import (
    BankStatementExtraction, Case, DocType, DocumentExtraction, DocumentMeta, LedgerExtraction, PremisesExtraction,
    ReceiptExtraction, SellerDashboardExtraction, TextLayerCheck,
)
from ..storage import Repository
from . import prompts
from ..tools.textlayer import cross_check_statement
from .common import case_facts, load_doc_bytes, page_parts
from .runner import AgentSpec, run_agent

log = logging.getLogger("ledgerlens.extractor")

SPECS: dict[DocType, tuple[str, type[BaseModel], str]] = {
    DocType.bank_statement: (prompts.EXTRACTOR_BANK, BankStatementExtraction, "bank_statement"),
    DocType.seller_dashboard: (prompts.EXTRACTOR_DASHBOARD, SellerDashboardExtraction, "seller_dashboard"),
    DocType.receipt: (prompts.EXTRACTOR_RECEIPT, ReceiptExtraction, "receipt"),
    DocType.logistics_receipt: (prompts.EXTRACTOR_RECEIPT, ReceiptExtraction, "receipt"),
    DocType.handwritten_ledger: (prompts.EXTRACTOR_LEDGER, LedgerExtraction, "handwritten_ledger"),
    DocType.premises_photo: (prompts.EXTRACTOR_PREMISES, PremisesExtraction, "premises"),
}


def _sanitize_refs(obj: Any, doc: DocumentMeta) -> None:
    """Force every SourceRef to this document and a valid page (models occasionally drift)."""
    if isinstance(obj, dict):
        if "doc_id" in obj and "page" in obj and set(obj.keys()) <= {"doc_id", "page", "bbox", "snippet"}:
            obj["doc_id"] = doc.doc_id
            try:
                obj["page"] = min(max(int(obj.get("page") or 1), 1), max(1, doc.pages))
            except Exception:
                obj["page"] = 1
            b = obj.get("bbox")
            if isinstance(b, dict):
                for k in ("ymin", "xmin", "ymax", "xmax"):
                    try:
                        b[k] = min(max(int(round(float(b.get(k, 0)))), 0), 1000)
                    except Exception:
                        b[k] = 0
                if b["ymax"] < b["ymin"]:
                    b["ymin"], b["ymax"] = b["ymax"], b["ymin"]
                if b["xmax"] < b["xmin"]:
                    b["xmin"], b["xmax"] = b["xmax"], b["xmin"]
            return
        for v in obj.values():
            _sanitize_refs(v, doc)
    elif isinstance(obj, list):
        for v in obj:
            _sanitize_refs(v, doc)


def _dedupe_row_ids(parsed: dict[str, Any], key: str, prefix: str) -> None:
    rows = parsed.get(key) or []
    seen: set[str] = set()
    for i, r in enumerate(rows, 1):
        rid = r.get("row_id") or f"{prefix}{i:04d}"
        if rid in seen:
            rid = f"{prefix}{i:04d}"
        seen.add(rid)
        r["row_id"] = rid


async def extract_document(case: Case, doc: DocumentMeta, *, repo: Repository, settings: Settings, mock_context: dict[str, Any]) -> DocumentExtraction:
    dtype = doc.doc_type or DocType.other
    if dtype not in SPECS:
        return DocumentExtraction(doc_id=doc.doc_id, doc_type=dtype, extraction_notes="No extractor for this document type.")
    instruction, schema, field = SPECS[dtype]
    model = settings.model_pro if dtype in (DocType.bank_statement, DocType.handwritten_ledger) else settings.model_flash
    spec = AgentSpec(name=f"extractor:{dtype.value}", instruction=instruction, prompt_version=prompts.PROMPT_VERSIONS["extractor"], model=model,
                     output_schema=schema, description=f"Extracts {dtype.value} documents")
    parts: list[types.Part] = [types.Part.from_text(text=case_facts(case)),
                               types.Part.from_text(text=f"Document {doc.doc_id} ({doc.filename}), classified as {dtype.value}, {doc.pages} page(s). Extract it.")]
    parts += page_parts(repo, case, doc, settings)
    ctx = {**mock_context, "doc": doc.model_dump(mode="json"), "doc_type": dtype.value}
    res = await run_agent(spec, parts, settings=settings, repo=repo, case_id=case.id, mock_context=ctx)
    parsed = dict(res.parsed or {})
    _sanitize_refs(parsed, doc)
    if field == "bank_statement":
        _dedupe_row_ids(parsed, "transactions", "T")
    if field == "handwritten_ledger":
        _dedupe_row_ids(parsed, "entries", "L")
    section = schema.model_validate(parsed)
    ex = DocumentExtraction(doc_id=doc.doc_id, doc_type=dtype)
    setattr(ex, field, section)
    if field == "bank_statement" and doc.mime_type == "application/pdf":
        try:
            cc = cross_check_statement(load_doc_bytes(repo, doc), section)
            ex.verification = TextLayerCheck(doc_id=doc.doc_id, **cc.to_dict())
        except Exception as e:  # verification is best-effort; never block extraction
            ex.extraction_notes = f"text-layer check failed: {e}"
    return ex


async def run_extraction(case: Case, *, repo: Repository, settings: Settings, mock_context: dict[str, Any],
                         only_doc_ids: Optional[set[str]] = None) -> list[DocumentExtraction]:
    sem = asyncio.Semaphore(max(1, settings.llm_concurrency))

    async def one(d: DocumentMeta) -> DocumentExtraction:
        async with sem:
            try:
                return await extract_document(case, d, repo=repo, settings=settings, mock_context=mock_context)
            except Exception as e:  # isolate: one unreadable receipt must not block the case
                log.exception("extraction failed for %s", d.doc_id)
                return DocumentExtraction(doc_id=d.doc_id, doc_type=d.doc_type or DocType.other, extraction_notes=f"EXTRACTION FAILED: {type(e).__name__}: {str(e)[:300]}")

    docs = [d for d in case.documents if not only_doc_ids or d.doc_id in only_doc_ids]
    return list(await asyncio.gather(*(one(d) for d in docs)))
