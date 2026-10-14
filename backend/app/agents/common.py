"""Helpers shared by the agent stages: building multimodal parts and compact text contexts."""
from __future__ import annotations

import io
import json
import re
from typing import Any, Iterable, Optional

from google.genai import types
from PIL import Image

from ..config import Settings
from ..schemas import Case, DocumentExtraction, DocumentMeta, Figure, Memo, SourceRef
from ..storage import Repository
from ..tools.documents import pages_for_llm, thumbnail

FIG_TOKEN = re.compile(r"\{fig:([A-Za-z0-9_.\-]+)\}")


def doc_label(d: DocumentMeta) -> str:
    return f"{d.doc_id} ({d.filename})"


def load_doc_bytes(repo: Repository, d: DocumentMeta) -> bytes:
    data = repo.get_blob(d.storage_path)
    if data is None:
        raise FileNotFoundError(f"document bytes missing for {d.doc_id} at {d.storage_path}")
    return data


def page_parts(repo: Repository, case: Case, d: DocumentMeta, settings: Settings) -> list[types.Part]:
    """Label + JPEG for every page of a document, cached as blobs so re-runs do not re-render."""
    parts: list[types.Part] = []
    n = max(1, d.pages)
    rendered: list[bytes] = []
    missing = False
    for p in range(1, n + 1):
        b = repo.get_blob(f"cases/{case.id}/llm/{d.doc_id}/p{p}.jpg")
        if b is None:
            missing = True
            break
        rendered.append(b)
    if missing:
        rendered = []
        for lp in pages_for_llm(load_doc_bytes(repo, d), d.mime_type, max_width=settings.llm_page_max_width):
            repo.put_blob(f"cases/{case.id}/llm/{d.doc_id}/p{lp.page}.jpg", lp.data, "image/jpeg")
            rendered.append(lp.data)
    for p, data in enumerate(rendered, 1):
        parts.append(types.Part.from_text(text=f"doc_id={d.doc_id} page={p} of {len(rendered)}"))
        parts.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
    return parts


def thumbnail_part(repo: Repository, case: Case, d: DocumentMeta) -> list[types.Part]:
    key = f"cases/{case.id}/llm/{d.doc_id}/thumb.jpg"
    b = repo.get_blob(key)
    if b is None:
        b = thumbnail(load_doc_bytes(repo, d), d.mime_type)
        repo.put_blob(key, b, "image/jpeg")
    return [types.Part.from_text(text=f"doc_id={d.doc_id} filename={d.filename} pages={d.pages}"), types.Part.from_bytes(data=b, mime_type="image/jpeg")]


def inventory_text(case: Case) -> str:
    lines = [f"DOCUMENT INVENTORY ({len(case.documents)} files)"]
    for d in case.documents:
        lines.append(f"- {d.doc_id}: {d.filename} | type={d.doc_type.value if d.doc_type else '?'} | pages={d.pages} | language={d.language or '?'}"
                     + (f" | flags={','.join(f.value for f in d.quality_flags)}" if d.quality_flags else ""))
    return "\n".join(lines)


def case_facts(case: Case) -> str:
    return (f"CASE FACTS\n- Applicant business: {case.business_name}\n- Sector: {case.sector or 'unknown'}\n- Country: {case.country or 'unknown'}\n"
            f"- Stated language: {case.language}\n- Currency: {case.currency}\n- Requested amount: {('{:,.0f} ' + case.currency).format(case.requested_amount) if case.requested_amount else 'not stated'}")


def fmt_value(f: Figure) -> str:
    if f.unit == "currency":
        return f"{f.value:,.0f} {f.currency or ''}".strip()
    if f.unit == "percent":
        return f"{f.value:.2f}%"
    if f.unit == "ratio":
        return f"{f.value:.3f}"
    if f.unit in ("count", "months", "days"):
        return f"{int(round(f.value))} {f.unit if f.unit != 'count' else ''}".strip()
    return f"{f.value:g}"


def catalog_text(figures: Iterable[Figure], max_rows: int = 400) -> str:
    rows = ["FIGURE CATALOG (id | label | value | origin | evidence refs | computation)"]
    for i, f in enumerate(figures):
        if i >= max_rows:
            rows.append(f"... ({i} shown)")
            break
        rows.append(f"{f.id} | {f.label} | {fmt_value(f)} | {f.origin} | refs={len(f.source_refs)}" + (f" | {f.computation}" if f.computation else "")
                    + (f" | from={','.join(f.derived_from[:4])}" if f.derived_from else ""))
    return "\n".join(rows)


def render_memo_text(memo: Memo) -> str:
    by_id = {f.id: f for f in memo.figures}

    def sub(m: re.Match) -> str:
        f = by_id.get(m.group(1))
        return f"{fmt_value(f)} [{f.id}]" if f else f"[UNRESOLVED {m.group(1)}]"

    out = [f"HEADLINE: {FIG_TOKEN.sub(sub, memo.draft.headline)}", f"RECOMMENDATION: {memo.draft.recommendation}"]
    for s in memo.draft.sections:
        out.append(f"\n## {s.heading}")
        out += [FIG_TOKEN.sub(sub, p) for p in s.paragraphs]
    out.append("\nSTRENGTHS: " + " | ".join(FIG_TOKEN.sub(sub, x) for x in memo.draft.strengths))
    out.append("CONCERNS: " + " | ".join(FIG_TOKEN.sub(sub, x) for x in memo.draft.concerns))
    out.append("CONDITIONS: " + " | ".join(FIG_TOKEN.sub(sub, x) for x in memo.draft.conditions))
    out.append("RATIONALE: " + FIG_TOKEN.sub(sub, memo.draft.rationale))
    return "\n".join(out)


def ref_dict(r: SourceRef) -> dict[str, Any]:
    return {"doc_id": r.doc_id, "page": r.page, "bbox": [r.bbox.ymin, r.bbox.xmin, r.bbox.ymax, r.bbox.xmax] if r.bbox else None, "snippet": r.snippet}


def extraction_digest(extractions: list[DocumentExtraction], docs: dict[str, DocumentMeta], max_tx: int = 0) -> str:
    L = ["EXTRACTED DOCUMENT SUMMARY"]
    for ex in extractions:
        name = docs[ex.doc_id].filename if ex.doc_id in docs else ex.doc_id
        if ex.bank_statement:
            b = ex.bank_statement
            cr = sum(1 for t in b.transactions if t.credit > 0)
            L.append(f"- {ex.doc_id} ({name}) bank_statement: bank={b.bank_name} holder={b.account_holder} acct={b.account_number_masked} currency={b.currency} "
                     f"period={b.period_start}..{b.period_end} rows={len(b.transactions)} (credits {cr}, debits {len(b.transactions) - cr}) "
                     f"opening={b.opening_balance.value if b.opening_balance else None} closing={b.closing_balance.value if b.closing_balance else None}")
            if max_tx:
                for t in b.transactions[:max_tx]:
                    L.append(f"    {t.row_id} {t.date} {t.description[:50]} debit={t.debit:,.0f} credit={t.credit:,.0f} bal={t.balance_after}")
        elif ex.seller_dashboard:
            s = ex.seller_dashboard
            mets = ", ".join(f"{m.label}={m.value:,.0f}" for m in s.metrics)
            L.append(f"- {ex.doc_id} ({name}) seller_dashboard: platform={s.platform} shop={s.shop_name} period={s.period_start}..{s.period_end} as_of={s.data_as_of} | {mets}")
        elif ex.receipt:
            r = ex.receipt
            L.append(f"- {ex.doc_id} ({name}) receipt: merchant={r.merchant} date={r.date} no={r.receipt_number} total={r.total.value if r.total else None} {r.currency or ''} direction={r.direction} handwritten={r.handwritten}")
        elif ex.handwritten_ledger:
            lg = ex.handwritten_ledger
            inc = sum(e.amount for e in lg.entries if e.kind == "income")
            L.append(f"- {ex.doc_id} ({name}) handwritten_ledger: header={lg.business_name_header} period={lg.period_label} entries={len(lg.entries)} income_total={inc:,.0f} "
                     f"dates={min((e.date for e in lg.entries), default='?')}..{max((e.date for e in lg.entries), default='?')}")
        elif ex.premises:
            p = ex.premises
            L.append(f"- {ex.doc_id} ({name}) premises_photo: signage={p.signage_text} type={p.business_type_guess} size={p.apparent_size} inventory={p.inventory_level} | "
                     + "; ".join(o.text for o in p.observations[:5]))
        else:
            L.append(f"- {ex.doc_id} ({name}) {ex.doc_type.value}: no structured extraction ({ex.extraction_notes or ''})")
    return "\n".join(L)


def json_part(label: str, obj: Any) -> types.Part:
    return types.Part.from_text(text=f"{label}\n```json\n{json.dumps(obj, ensure_ascii=False, default=str)}\n```")


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as im:
        return im.size
