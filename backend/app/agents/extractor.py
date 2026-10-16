"""Stage 2: structured extraction per document, one Gemini call per document, every value with a source ref."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from google.genai import types
from pydantic import BaseModel

from ..config import Settings
from ..schemas import (
    BankStatementExtraction, Case, DocType, DocumentExtraction, DocumentMeta, LedgerExtraction, MoneyField, PremisesExtraction,
    ReceiptExtraction, SellerDashboardExtraction, TextLayerCheck, Transaction,
)
from ..storage import Repository
from . import prompts
from ..tools.textlayer import cross_check_statement
from .common import case_facts, load_doc_bytes, page_parts
from .runner import AgentSpec, BudgetExceeded, run_agent

log = logging.getLogger("ledgerlens.extractor")


class BankStatementPage(BaseModel):
    """One page of a statement: header fields are optional because continuation pages do not print them."""
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    account_number_masked: Optional[str] = None
    address: Optional[str] = None
    currency: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    opening_balance: Optional[MoneyField] = None
    closing_balance: Optional[MoneyField] = None
    transactions: list[Transaction] = []


def merge_statement_pages(pages: list[dict[str, Any]], default_currency: str) -> dict[str, Any]:
    """Pages in order -> one statement: first non-null header field, opening balance from the first page that prints
    it, closing from the last, rows concatenated and renumbered T0001.. across pages."""
    out: dict[str, Any] = {}
    for k in ("bank_name", "account_holder", "account_number_masked", "address", "currency", "period_start", "period_end"):
        out[k] = next((p.get(k) for p in pages if p.get(k)), None)
    out["opening_balance"] = next((p["opening_balance"] for p in pages if p.get("opening_balance")), None)
    out["closing_balance"] = next((p["closing_balance"] for p in reversed(pages) if p.get("closing_balance")), None)
    rows = [dict(t) for p in pages for t in (p.get("transactions") or [])]
    for i, t in enumerate(rows, 1):
        t["row_id"] = f"T{i:04d}"
    out["transactions"] = rows
    dates = sorted(t["date"] for t in rows if t.get("date"))
    out["currency"] = out["currency"] or default_currency
    out["period_start"] = out["period_start"] or (dates[0] if dates else "")
    out["period_end"] = out["period_end"] or (dates[-1] if dates else "")
    return out

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
    head = [types.Part.from_text(text=case_facts(case))]
    all_pages = page_parts(repo, case, doc, settings)  # [label, image] per page
    ctx = {**mock_context, "doc": doc.model_dump(mode="json"), "doc_type": dtype.value}
    if field == "bank_statement" and doc.pages > 1 and settings.resolved_llm_mode != "mock":
        # One call per page, in parallel: a whole statement in one structured call (180+ rows, each with a bbox)
        # runs past the timeout. Pages are short, cache independently and fail independently.
        page_spec = AgentSpec(name=f"extractor:{dtype.value}:page", instruction=prompts.EXTRACTOR_BANK_PAGE,
                              prompt_version=prompts.PROMPT_VERSIONS["extractor_page"], model=model, output_schema=BankStatementPage,
                              description="Extracts one bank statement page")

        async def one_page(p: int) -> dict[str, Any]:
            parts = head + [types.Part.from_text(text=f"Document {doc.doc_id} ({doc.filename}), bank statement, page {p} of {doc.pages}. "
                                                      "Extract this page.")] + all_pages[2 * (p - 1): 2 * p]
            r = await run_agent(page_spec, parts, settings=settings, repo=repo, case_id=case.id, mock_context=ctx)
            pg = dict(r.parsed or {})
            _sanitize_refs(pg, doc)
            for t in pg.get("transactions") or []:
                if isinstance(t.get("source"), dict):
                    t["source"]["page"] = p  # the model only saw this page
            return pg

        pages = await asyncio.gather(*(one_page(p) for p in range(1, doc.pages + 1)))
        parsed = merge_statement_pages(list(pages), case.currency)
    else:
        parts = head + [types.Part.from_text(text=f"Document {doc.doc_id} ({doc.filename}), classified as {dtype.value}, {doc.pages} page(s). Extract it.")]
        parts += all_pages
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
            except BudgetExceeded:
                raise  # the AI limit applies to the whole case, not one document
            except Exception as e:  # isolate: one unreadable receipt must not block the case
                log.exception("extraction failed for %s", d.doc_id)
                return DocumentExtraction(doc_id=d.doc_id, doc_type=d.doc_type or DocType.other, extraction_notes=f"EXTRACTION FAILED: {type(e).__name__}: {str(e)[:300]}")

    docs = [d for d in case.documents if not only_doc_ids or d.doc_id in only_doc_ids]
    return list(await asyncio.gather(*(one(d) for d in docs)))
