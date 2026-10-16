"""Deterministic Challenger battery: the checks a careful underwriter runs by hand, run by code.

Each function is also exposed to the Challenger agent as a tool. Results feed `ToolFindings`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from ..schemas import (
    CashReconciliation, CashflowSummary, DocType, DocumentExtraction, DocumentMeta, EntityCheck, ImageDuplicate,
    IntakeResult, Memo, PayoutReconciliation, PeriodCheck, ToolFindings, UnsourcedNumeral,
)
from .cashflow import _month_range, _norm, _tokens, recompute_balances
from .documents import phash_distance

NEAR_DUP_TYPES = {DocType.receipt, DocType.logistics_receipt, DocType.handwritten_ledger, DocType.premises_photo, DocType.other}
NEAR_THRESHOLD = 8   # of 256 bits (phash 16x16). Same-template receipts with different content score >= 20.
PAST_THRESHOLD = 8
COUNTRY_LANG = {"ID": {"id", "en"}, "VN": {"vi", "en"}, "PH": {"tl", "en", "fil"}, "TH": {"th", "en"}, "MY": {"ms", "en"}, "SG": {"en", "zh", "ms"}}
COUNTRY_CUR = {"ID": "IDR", "VN": "VND", "PH": "PHP", "TH": "THB", "MY": "MYR", "SG": "SGD"}


# ---------------------------------------------------------------------------
# Q4: duplicate / reused images (within case and against past cases)
# ---------------------------------------------------------------------------
def image_similarity(documents: list[DocumentMeta], past_index: Optional[list[dict]] = None) -> list[ImageDuplicate]:
    out: list[ImageDuplicate] = []
    docs = [d for d in documents if d.page_hashes]
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            if a.sha256 == b.sha256:
                out.append(ImageDuplicate(doc_a=a.doc_id, page_a=1, doc_b=b.doc_id, page_b=1, hamming_distance=0, kind="exact"))
                continue
            ta, tb = a.doc_type or DocType.other, b.doc_type or DocType.other
            if ta not in NEAR_DUP_TYPES or tb not in NEAR_DUP_TYPES:
                continue
            for pa, ha in enumerate(a.page_hashes, 1):
                for pb, hb in enumerate(b.page_hashes, 1):
                    d = phash_distance(ha, hb)
                    if d <= NEAR_THRESHOLD:
                        out.append(ImageDuplicate(doc_a=a.doc_id, page_a=pa, doc_b=b.doc_id, page_b=pb, hamming_distance=d, kind="exact" if d == 0 else "near"))
    for d in docs:
        for past in past_index or []:
            if past.get("sha256") == d.sha256:
                out.append(ImageDuplicate(doc_a=d.doc_id, page_a=1, doc_b=past.get("filename", "?"), page_b=1, hamming_distance=0, kind="exact",
                                          cross_case=True, other_case_id=past.get("case_id")))
            else:
                ph = past.get("phash16") or past.get("phash")
                if ph and d.page_hashes and phash_distance(d.page_hashes[0], ph) <= PAST_THRESHOLD:
                    out.append(ImageDuplicate(doc_a=d.doc_id, page_a=1, doc_b=past.get("filename", "?"), page_b=1,
                                              hamming_distance=phash_distance(d.page_hashes[0], ph), kind="near", cross_case=True, other_case_id=past.get("case_id")))
    return out


# ---------------------------------------------------------------------------
# Q5: period coverage across sources
# ---------------------------------------------------------------------------
def _months_of(ex: DocumentExtraction) -> tuple[str, set[str]]:
    if ex.bank_statement:
        bs = ex.bank_statement
        months = set(_month_range(bs.period_start, bs.period_end))
        tx_months = {t.date[:7] for t in bs.transactions if len(t.date) >= 7}
        return (f"{bs.period_start}..{bs.period_end}", months or tx_months)
    if ex.seller_dashboard:
        sd = ex.seller_dashboard
        if sd.period_start and sd.period_end:
            return (f"{sd.period_start}..{sd.period_end}", set(_month_range(sd.period_start, sd.period_end)))
        return (sd.data_as_of or "?", set())
    if ex.handwritten_ledger:
        ms = {e.date[:7] for e in ex.handwritten_ledger.entries if len(e.date) >= 7}
        return (ex.handwritten_ledger.period_label or ",".join(sorted(ms)), ms)
    return ("", set())


def date_crosscheck(extractions: list[DocumentExtraction]) -> list[PeriodCheck]:
    banks = [e for e in extractions if e.bank_statement]
    dash = [e for e in extractions if e.seller_dashboard]
    ledg = [e for e in extractions if e.handwritten_ledger]
    out: list[PeriodCheck] = []
    bank_months: set[str] = set()
    bank_label = []
    tx_months: set[str] = set()
    for b in banks:
        lbl, ms = _months_of(b)
        bank_months |= ms
        bank_label.append(lbl)
        tx_months |= {t.date[:7] for t in b.bank_statement.transactions}
    if banks and tx_months and bank_months - tx_months:
        out.append(PeriodCheck(doc_a=banks[0].doc_id, period_a=" / ".join(bank_label), doc_b=banks[0].doc_id, period_b="rows present: " + ",".join(sorted(tx_months)),
                               overlap_months=sorted(bank_months & tx_months), only_in_a=sorted(bank_months - tx_months), only_in_b=[], consistent=False))
    for group, name in ((dash, "dashboards"), (ledg, "ledger")):
        if not group or not banks:
            continue
        g_months: set[str] = set()
        g_labels = []
        for e in group:
            lbl, ms = _months_of(e)
            g_months |= ms
            g_labels.append(lbl)
        cover = tx_months or bank_months
        out.append(PeriodCheck(doc_a=banks[0].doc_id, period_a=" / ".join(bank_label), doc_b=",".join(e.doc_id for e in group),
                               period_b=f"{name}: " + " / ".join(sorted(set(g_labels))), overlap_months=sorted(cover & g_months),
                               only_in_a=sorted(cover - g_months), only_in_b=sorted(g_months - cover), consistent=(g_months <= cover)))
    return out


# ---------------------------------------------------------------------------
# Q11 / Q12: entity, currency, language consistency
# ---------------------------------------------------------------------------
def entity_consistency(extractions: list[DocumentExtraction], intake: Optional[IntakeResult], business_name: str, country: str, currency: str) -> list[EntityCheck]:
    out: list[EntityCheck] = []
    names: dict[str, str] = {}
    holders: dict[str, str] = {}
    shop_names: dict[str, str] = {}
    addresses: dict[str, str] = {}
    currencies: dict[str, str] = {}
    for ex in extractions:
        if ex.bank_statement:
            if ex.bank_statement.account_holder:
                holders[ex.doc_id] = ex.bank_statement.account_holder
            if ex.bank_statement.address:
                addresses[ex.doc_id] = ex.bank_statement.address
            currencies[ex.doc_id] = ex.bank_statement.currency
        if ex.seller_dashboard and ex.seller_dashboard.shop_name:
            shop_names[ex.doc_id] = ex.seller_dashboard.shop_name
            names[ex.doc_id] = ex.seller_dashboard.shop_name
            if ex.seller_dashboard.currency:
                currencies[ex.doc_id] = ex.seller_dashboard.currency
        if ex.handwritten_ledger:
            if ex.handwritten_ledger.business_name_header:
                names[ex.doc_id] = ex.handwritten_ledger.business_name_header
            if ex.handwritten_ledger.address_header:
                addresses[ex.doc_id] = ex.handwritten_ledger.address_header
            if ex.handwritten_ledger.currency:
                currencies[ex.doc_id] = ex.handwritten_ledger.currency
        if ex.premises and ex.premises.signage_text:
            names[ex.doc_id] = ex.premises.signage_text
        if ex.receipt and ex.receipt.currency:
            currencies[ex.doc_id] = ex.receipt.currency
    # dashboards must agree with each other exactly
    if len(set(_norm(v) for v in shop_names.values())) > 1:
        out.append(EntityCheck(field="business_name", values=shop_names, consistent=False, note="Shop name differs between dashboard captures"))
    # business names vs application
    all_names = {"application": business_name, **names}
    app_tokens = _tokens(business_name)
    bad = {k: v for k, v in names.items() if app_tokens and not (_tokens(v) & app_tokens)}
    out.append(EntityCheck(field="business_name", values=all_names, consistent=not bad,
                           note=None if not bad else "Documents whose business name shares no token with the application: " + ", ".join(bad)))
    if holders:
        holder_tokens = set().union(*[_tokens(h) for h in holders.values()])
        related = bool(holder_tokens & app_tokens) or any(_tokens(v) & holder_tokens for v in names.values())
        out.append(EntityCheck(field="account_holder", values={**holders, "application": business_name}, consistent=related,
                               note=None if related else "Account holder name shares no token with the business name or other documents"))
    if len(addresses) > 1:
        toks = [_tokens(a) for a in addresses.values()]
        ok = all(toks[0] & t for t in toks[1:])
        out.append(EntityCheck(field="address", values=addresses, consistent=ok, note=None if ok else "Addresses differ between documents"))
    exp_cur = COUNTRY_CUR.get(country.upper(), currency)
    bad_cur = {k: v for k, v in currencies.items() if v and v.upper() not in {exp_cur, currency.upper()}}
    out.append(EntityCheck(field="currency", values={**currencies, "expected": exp_cur}, consistent=not bad_cur,
                           note=None if not bad_cur else "Currency on some documents does not match the stated country"))
    if intake:
        langs = {d.doc_id: d.language for d in intake.documents}
        allowed = COUNTRY_LANG.get(country.upper(), set())
        split = lambda v: {t.strip().lower() for t in re.split(r"[+/,; ]+", v or "") if t.strip()}  # noqa: E731
        bad_lang = {k: v for k, v in langs.items() if allowed and v and not (split(v) & allowed)}
        out.append(EntityCheck(field="language", values={**langs, "expected": "/".join(sorted(allowed)) or "?"}, consistent=not bad_lang,
                               note=None if not bad_lang else "Document language unexpected for the stated country"))
    return out


# ---------------------------------------------------------------------------
# Q1: same money twice
# ---------------------------------------------------------------------------
def reconcile_payouts(cf: CashflowSummary) -> Optional[PayoutReconciliation]:
    if cf.dashboard_gross_sales_total <= 0 and cf.platform_payout_total <= 0:
        return None
    ratio = (cf.platform_payout_total / cf.dashboard_payout_total) if cf.dashboard_payout_total else None
    base = cf.dashboard_payout_total or cf.dashboard_gross_sales_total
    risk = cf.platform_payout_total > 0 and base > 0 and 0.4 <= cf.platform_payout_total / base <= 1.6
    return PayoutReconciliation(dashboard_gross_sales=cf.dashboard_gross_sales_total, dashboard_payout=cf.dashboard_payout_total,
                                bank_platform_payouts=cf.platform_payout_total, ratio_payout_to_bank=round(ratio, 3) if ratio else None, double_count_risk=risk)


def reconcile_cash(cf: CashflowSummary) -> Optional[CashReconciliation]:
    src = cf.ledger_income_total + cf.receipts_sales_total
    if src <= 0 and cf.cash_deposit_total <= 0:
        return None
    risk = src > 0 and cf.cash_deposit_total > 0 and 0.4 <= cf.cash_deposit_total / src <= 1.6
    return CashReconciliation(ledger_income=cf.ledger_income_total, receipts_sales=cf.receipts_sales_total, bank_cash_deposits=cf.cash_deposit_total, double_count_risk=risk)


# ---------------------------------------------------------------------------
# Q9: every number sourced
# ---------------------------------------------------------------------------
FIG_TOKEN = re.compile(r"\{fig:([A-Za-z0-9_.\-]+)\}")
# Tolerated in prose: years (19xx/20xx, optionally -mm-dd), d/m(/y) dates, quarters and 1-2 digit counts/ordinals.
# Any other 4-digit number ("2500 customers", "9999 orders") is an amount and must be a figure token.
DATEISH = re.compile(r"^(?:(?:19|20)\d{2}(?:-\d{2}){0,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|Q[1-4]|\d{1,2}(?:st|nd|rd|th)?)$")
NUMERAL = re.compile(r"(?<![A-Za-z{:.\-])\d[\d,.]*%?")


def find_unsourced_numerals(memo: Memo) -> list[UnsourcedNumeral]:
    """Digits in memo prose that are not figure tokens (dates and ordinals are tolerated)."""
    out: list[UnsourcedNumeral] = []
    chunks: list[tuple[str, str]] = [("headline", memo.draft.headline), ("rationale", memo.draft.rationale)]
    for s in memo.draft.sections:
        chunks.append((s.heading, s.heading))  # headings are rendered too
        for p in s.paragraphs:
            chunks.append((s.heading, p))
    for lst, name in ((memo.draft.strengths, "strengths"), (memo.draft.concerns, "concerns"), (memo.draft.conditions, "conditions")):
        chunks += [(name, x) for x in lst]
    for section, text in chunks:
        stripped = FIG_TOKEN.sub(" ", text)
        for m in NUMERAL.finditer(stripped):
            tok = m.group(0).rstrip(".,")
            if DATEISH.match(tok) or _looks_like_date(stripped, m.start(), tok):
                continue
            ctx = stripped[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            out.append(UnsourcedNumeral(section=section, text=tok, context=ctx))
    return out


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
          "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec")


MONTH_RE = re.compile(r"\b(?:" + "|".join(MONTHS) + r")\b\.?", re.IGNORECASE)


def _looks_like_date(text: str, pos: int, tok: str = "") -> bool:
    """A day or year next to a month name ("14 March", "Mar 2026"). Whole words only: "margin" and "declined" are not
    months. Amounts (thousands separators, decimals, more than 4 digits) are never dates."""
    if "," in tok or "." in tok or len(tok.rstrip("%")) > 4 or tok.endswith("%"):
        return False
    window = text[max(0, pos - 12): pos + 16]
    return bool(MONTH_RE.search(window))


def unsourced_figure_ids(memo: Memo) -> list[str]:
    return [f.id for f in memo.figures if not f.is_sourced()] + list(memo.unresolved_figure_ids)


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------
def run_battery(*, documents: list[DocumentMeta], extractions: list[DocumentExtraction], intake: Optional[IntakeResult], cashflow: CashflowSummary,
                memo: Optional[Memo], business_name: str, country: str, currency: str, past_index: Optional[list[dict]] = None) -> ToolFindings:
    tf = ToolFindings(
        balance_checks=cashflow.balance_checks or recompute_balances(extractions),
        image_duplicates=image_similarity(documents, past_index),
        period_checks=date_crosscheck(extractions),
        entity_checks=entity_consistency(extractions, intake, business_name, country, currency),
        recurring_transfers=cashflow.recurring_transfers,
        self_transfers=[f for f in cashflow.flagged if f.reason == "self_transfer"],
        round_trips=[f for f in cashflow.flagged if f.reason == "round_trip"],
        payout_reconciliation=reconcile_payouts(cashflow),
        cash_reconciliation=reconcile_cash(cashflow),
        months_missing=cashflow.months_missing,
    )
    if memo:
        tf.unsourced_figure_ids = unsourced_figure_ids(memo)
        tf.unsourced_numerals = memo.unsourced_numerals or find_unsourced_numerals(memo)
    tf.text_layer_checks = [e.verification for e in extractions if e.verification]
    return tf


def findings_digest(tf: ToolFindings, doc_names: dict[str, str]) -> str:
    """Compact human-readable digest handed to the Challenger agent."""
    L: list[str] = []
    nm = lambda d: f"{d} ({doc_names.get(d, d)})"  # noqa: E731
    L.append(f"Balance continuity breaks: {len(tf.balance_checks)}")
    for b in tf.balance_checks[:12]:
        L.append(f"  - row {b.row_id} {b.date}: expected {b.expected_balance:,.0f} reported {b.reported_balance:,.0f} (diff {b.difference:+,.0f}) at {nm(b.source.doc_id)} p{b.source.page}")
    L.append(f"Image duplicates: {len(tf.image_duplicates)}")
    for d in tf.image_duplicates:
        where = f"PAST CASE {d.other_case_id} file {d.doc_b}" if d.cross_case else f"{nm(d.doc_b)} p{d.page_b}"
        L.append(f"  - {nm(d.doc_a)} p{d.page_a} vs {where}: {d.kind} (hamming {d.hamming_distance})")
    L.append(f"Period checks: {len(tf.period_checks)}")
    for p in tf.period_checks:
        L.append(f"  - {p.period_a} vs {p.period_b}: consistent={p.consistent}; only in first: {p.only_in_a or '-'}; only in second: {p.only_in_b or '-'}")
    L.append(f"Months with no statement rows: {tf.months_missing or 'none'}")
    L.append("Entity checks:")
    for e in tf.entity_checks:
        L.append(f"  - {e.field}: consistent={e.consistent}; values={e.values}" + (f"; note: {e.note}" if e.note else ""))
    L.append(f"Recurring debits: {len(tf.recurring_transfers)}")
    for r in tf.recurring_transfers[:12]:
        L.append(f"  - {r.counterparty}: {r.amount:,.0f} x{r.occurrences} (day {r.day_of_month_mode}, months {','.join(r.months)}), likely_debt_service={r.likely_debt_service}, rows {','.join(r.row_ids[:6])}")
    L.append(f"Self-transfers (sender = account holder): {len(tf.self_transfers)}")
    for f in tf.self_transfers[:10]:
        L.append(f"  - {f.row_id} {f.date} {f.description} {f.amount:,.0f}")
    L.append(f"Round-trips (credit returned within 14 days): {len(tf.round_trips)}")
    for f in tf.round_trips[:10]:
        L.append(f"  - {f.row_id} {f.date} {f.description} {f.amount:,.0f} -> returned in row {f.matched_row_id}")
    if tf.payout_reconciliation:
        p = tf.payout_reconciliation
        L.append(f"Payout reconciliation: dashboard gross {p.dashboard_gross_sales:,.0f}, dashboard payout {p.dashboard_payout:,.0f}, bank platform payouts {p.bank_platform_payouts:,.0f}, ratio {p.ratio_payout_to_bank}, double_count_risk={p.double_count_risk}")
    if tf.cash_reconciliation:
        c = tf.cash_reconciliation
        L.append(f"Cash reconciliation: ledger income {c.ledger_income:,.0f}, receipt sales {c.receipts_sales:,.0f}, bank cash deposits {c.bank_cash_deposits:,.0f}, double_count_risk={c.double_count_risk}")
    for v in tf.text_layer_checks:
        if v.text_layer:
            L.append(f"PDF text-layer cross-check {nm(v.doc_id)}: {v.amounts_found}/{v.rows} extracted amounts found verbatim in the PDF text "
                     f"({v.amount_match_rate}); bbox covers the amount text for {v.bbox_hits}/{v.amounts_found} ({v.bbox_match_rate}); "
                     f"missing: {[m['row_id'] for m in v.amounts_missing[:10]] or 'none'}; bbox misses: {v.bbox_misses[:10] or 'none'}")
        else:
            L.append(f"PDF text-layer cross-check {nm(v.doc_id)}: no text layer (scanned); relies on the model only")
    L.append(f"Unsourced figure ids in memo: {tf.unsourced_figure_ids or 'none'}")
    L.append(f"Unsourced numerals in memo prose: {len(tf.unsourced_numerals)}" + ("".join(f"\n  - [{u.section}] '{u.text}' in: {u.context}" for u in tf.unsourced_numerals[:10])))
    return "\n".join(L)
