"""Deterministic cash-flow model.

The LLM never computes a number. This module turns extracted transactions into monthly tables, flags,
recurring-transfer detection, balance-continuity checks and a *figure catalog* in which every value carries
the source references of the rows it was computed from. The Analyst may only cite catalog ids.
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable, Optional

from ..schemas import (
    BalanceCheck, CashflowSummary, DocumentExtraction, Figure, FlaggedTransaction, MonthlyRow,
    RecurringTransfer, SourceRef, Transaction,
)

PLATFORM_RE = re.compile(r"\b(SHOPEE|TOKOPEDIA|LAZADA|TIKTOK|BUKALAPAK|GRAB|GOJEK|GOFOOD|FOODPANDA|ZALORA|TIKI|SENDO)\b", re.I)
PAYOUT_RE = re.compile(r"(PAYOUT|SETTLEMENT|PENCAIRAN|THANH TOAN|DISBURSE|WITHDRAW)", re.I)
CASH_DEPOSIT_RE = re.compile(r"(CASH DEPOSIT|CASH DEP\b|SETOR TUNAI|SETORAN TUNAI|NOP TIEN MAT|NAP TIEN MAT|DEPOSIT TUNAI|CDM\b)", re.I)
SALES_SETTLEMENT_RE = re.compile(r"\b(QRIS|QR SALES|MERCHANT SETTLEMENT|EDC|GCASH QR|VIETQR)\b", re.I)
LENDER_RE = re.compile(
    r"(CREDIT|KREDIT|LOAN|LENDING|FINANCE|FINANCING|TRA GOP|CICILAN|ANGSURAN|INSTALL?MENT|PAYLATER|SPAYLATER|AKULAKU|KREDIVO|"
    r"HOME CREDIT|FE CREDIT|MCREDIT|CIMB NIAGA FINANCE|BDO AUTO|AUTO LOAN|PAG-?IBIG LOAN|SSS LOAN|CASHALO|TALA|KOINWORKS|MODALKU|FUNDING SOCIETIES)",
    re.I,
)
TRANSFER_WORDS_RE = re.compile(
    r"\b(TRANSFER|TRF|TRANSFER TO|TRANSFER FROM|CHUYEN TIEN|CHUYEN DEN|CHUYEN TU|NHAN TU|TRF DARI|TRF KE|GCASH TRANSFER|INSTAPAY|PESONET|NAPAS)\b", re.I
)
STOP_TOKENS = {"TRANSFER", "TRF", "FROM", "TO", "DARI", "KE", "CHUYEN", "TIEN", "TU", "DEN", "NHAN", "GCASH", "INSTAPAY", "PESONET",
               "PAYMENT", "PAY", "THANH", "TOAN", "BANK", "VCB", "BCA", "BRI", "BNI", "MANDIRI", "BDO", "BPI", "VIA", "MB", "TPB", "ACB"}


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.upper()).strip()


def _tokens(s: Optional[str]) -> set[str]:
    return {t for t in re.split(r"[^A-Z0-9]+", _norm(s)) if len(t) >= 3 and t not in STOP_TOKENS}


def _month(d: str) -> str:
    return d[:7]


def _parse_date(d: str) -> Optional[date]:
    try:
        return date.fromisoformat(d[:10])
    except Exception:
        return None


def _month_range(start: str, end: str) -> list[str]:
    s, e = _parse_date(start), _parse_date(end)
    if not s or not e:
        return []
    out = []
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _round(x: float, nd: int = 2) -> float:
    return float(round(x, nd))


class Row:
    """Internal flattened transaction with its document context."""

    __slots__ = ("doc_id", "tx", "d", "tags", "matched")

    def __init__(self, doc_id: str, tx: Transaction):
        self.doc_id = doc_id
        self.tx = tx
        self.d = _parse_date(tx.date)
        self.tags: set[str] = set()
        self.matched: Optional[str] = None


def flatten_transactions(extractions: Iterable[DocumentExtraction]) -> list[Row]:
    rows: list[Row] = []
    for ex in extractions:
        if ex.bank_statement:
            for tx in ex.bank_statement.transactions:
                if _parse_date(tx.date):
                    rows.append(Row(ex.doc_id, tx))
    rows.sort(key=lambda r: (r.d, r.doc_id, r.tx.row_id))
    return rows


# ---------------------------------------------------------------------------
# Balance continuity (Challenger question 6)
# ---------------------------------------------------------------------------
def recompute_balances(extractions: Iterable[DocumentExtraction], tolerance_ratio: float = 0.002) -> list[BalanceCheck]:
    checks: list[BalanceCheck] = []
    for ex in extractions:
        bs = ex.bank_statement
        if not bs:
            continue
        prev: Optional[float] = bs.opening_balance.value if bs.opening_balance else None
        for tx in bs.transactions:
            if tx.balance_after is None:
                # statements that print a balance only once per day: carry the running balance forward
                if prev is not None:
                    prev = prev + (tx.credit or 0) - (tx.debit or 0)
                continue
            if prev is not None:
                expected = prev + (tx.credit or 0) - (tx.debit or 0)
                tol = max(1.0, abs(expected) * tolerance_ratio)
                if abs(expected - tx.balance_after) > tol:
                    checks.append(BalanceCheck(row_id=tx.row_id, date=tx.date, expected_balance=_round(expected),
                                               reported_balance=_round(tx.balance_after), difference=_round(tx.balance_after - expected),
                                               source=tx.source))
            prev = tx.balance_after
        if bs.closing_balance and prev is not None:
            tol = max(1.0, abs(prev) * tolerance_ratio)
            if abs(bs.closing_balance.value - prev) > tol:
                checks.append(BalanceCheck(row_id="CLOSING", date=bs.period_end, expected_balance=_round(prev),
                                           reported_balance=_round(bs.closing_balance.value),
                                           difference=_round(bs.closing_balance.value - prev), source=bs.closing_balance.source))
    return checks


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify_rows(rows: list[Row], holder_names: list[str]) -> None:
    # A self-transfer needs every name token of one holder ("NGUYEN THI LINH"), not just a shared family name:
    # "NGUYEN THI HOA" is a different person.
    holder_sets = [t for t in (_tokens(n) for n in holder_names) if t]
    holder_tokens: set[str] = set().union(*holder_sets) if holder_sets else set()
    by_cp_amount: dict[tuple[str, float], list[Row]] = defaultdict(list)
    for r in rows:
        text = f"{r.tx.description} {r.tx.counterparty or ''}"
        if PLATFORM_RE.search(text) and (PAYOUT_RE.search(text) or r.tx.credit > 0):
            if r.tx.credit > 0:
                r.tags.add("platform_payout")
        if CASH_DEPOSIT_RE.search(text) and r.tx.credit > 0:
            r.tags.add("cash_deposit")
        if SALES_SETTLEMENT_RE.search(text) and r.tx.credit > 0:
            r.tags.add("sales_settlement")
        if LENDER_RE.search(text) and r.tx.debit > 0:
            r.tags.add("lender")
        cp_tokens = _tokens(r.tx.counterparty) or (_tokens(text) if TRANSFER_WORDS_RE.search(text) else set())
        if r.tx.credit > 0 and any(hs <= cp_tokens for hs in holder_sets):
            r.tags.add("self_transfer")
        key_cp = " ".join(sorted(cp_tokens)) if cp_tokens else _norm(r.tx.description)
        amt = r.tx.credit if r.tx.credit > 0 else r.tx.debit
        by_cp_amount[(key_cp, round(amt, -int(max(0, len(str(int(amt))) - 3)) if amt >= 1000 else 0))].append(r)
    # round trips: same counterparty key, same amount, one credit + one debit within 14 days
    for (_, _), group in by_cp_amount.items():
        credits = [r for r in group if r.tx.credit > 0 and r.d]
        debits = [r for r in group if r.tx.debit > 0 and r.d]
        for c in credits:
            for dbt in debits:
                if dbt.matched or c.matched:
                    continue
                if abs((dbt.d - c.d).days) <= 14 and abs(dbt.tx.debit - c.tx.credit) <= max(1.0, 0.01 * c.tx.credit):
                    c.tags.add("round_trip")
                    dbt.tags.add("round_trip_return")
                    c.matched, dbt.matched = dbt.tx.row_id, c.tx.row_id
    # large one-offs
    credits = [r.tx.credit for r in rows if r.tx.credit > 0 and not r.tags & {"self_transfer", "round_trip"}]
    if len(credits) >= 5:
        med = statistics.median(credits)
        total = sum(credits)
        for r in rows:
            if r.tx.credit > 0 and r.tx.credit > 4 * med and r.tx.credit > 0.08 * total and not r.tags & {"self_transfer", "round_trip", "platform_payout"}:
                r.tags.add("large_one_off")


def detect_recurring(rows: list[Row]) -> list[RecurringTransfer]:
    groups: dict[tuple[str, float], list[Row]] = defaultdict(list)
    for r in rows:
        if r.tx.debit <= 0 or not r.d:
            continue
        text = f"{r.tx.description} {r.tx.counterparty or ''}"
        toks = _tokens(r.tx.counterparty) or _tokens(text)
        key = " ".join(sorted(toks))[:60] if toks else _norm(r.tx.description)[:60]
        groups[(key, round(r.tx.debit, 0))].append(r)
    out: list[RecurringTransfer] = []
    for (key, amt), grp in groups.items():
        grp.sort(key=lambda r: r.d)
        months = sorted({_month(r.tx.date) for r in grp})
        if len(grp) < 3:
            continue
        days = [r.d.day for r in grp]
        gaps = [(grp[i + 1].d - grp[i].d).days for i in range(len(grp) - 1)]
        monthly = len(months) >= 3 and len(months) == len(grp) and (max(days) - min(days) <= 4 or (min(days) <= 2 and max(days) >= 28))
        # weekly: most gaps are about a week; a long gap is tolerated when statement months are missing in between
        weekly = len(grp) >= 6 and bool(gaps) and statistics.median(gaps) in (6, 7, 8) and \
            sum(1 for g in gaps if 5 <= g <= 9) >= 0.75 * len(gaps)
        if not (monthly or weekly):
            continue
        text = " ".join(f"{r.tx.description} {r.tx.counterparty or ''}" for r in grp[:3])
        is_lender = bool(LENDER_RE.search(text))
        person_like = bool(re.search(r"\b(TRANSFER TO|CHUYEN DEN|TRF KE|GCASH TRANSFER TO)\b", text, re.I)) and not re.search(
            r"(PLN|PDAM|LISTRIK|ELECTRIC|WATER|INTERNET|TELKOM|SEWA|RENT|THUE|UPAH|GAJI|SALARY|LUONG|MERALCO|MAYNILAD|GLOBE|SMART|PLDT|WIFI|VIETTEL|FPT|EVN|SUPPLIER|GROSIR)", text, re.I)
        likely = is_lender or (weekly and person_like)
        label = grp[0].tx.counterparty or grp[0].tx.description
        out.append(RecurringTransfer(
            counterparty=label, amount=_round(amt), day_of_month_mode=statistics.mode(days), months=months, occurrences=len(grp),
            row_ids=[r.tx.row_id for r in grp], likely_debt_service=likely, source_refs=[r.tx.source for r in grp][:12],
        ))
    out.sort(key=lambda r: (-int(r.likely_debt_service), -r.amount * r.occurrences))
    return out


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def duplicate_ledger_pages(extractions: Iterable[DocumentExtraction]) -> set[str]:
    """Ledger pages whose entries (day of month, amount, kind, description) repeat an earlier page exactly: the same
    page photographed again with only the month header changed. The later page is the duplicate."""
    seen: dict[tuple, str] = {}
    dups: set[str] = set()
    for ex in extractions:
        lg = ex.handwritten_ledger
        if not lg or len(lg.entries) < 3:
            continue
        # descriptions are left out: two reads of the same handwriting rarely transcribe them identically
        sig = tuple(sorted((e.date[8:10], round(e.amount), e.kind) for e in lg.entries))
        if sig in seen:
            dups.add(ex.doc_id)
        else:
            seen[sig] = ex.doc_id
    return dups


def ledger_summary_pages(extractions: Iterable[DocumentExtraction], tolerance: float = 0.01) -> set[str]:
    """Ledger pages that only restate other pages' monthly totals (a "Buod"/summary page). Their lines are not new
    income: a page is a summary when at least two of its income lines equal another page's income total for that month."""
    monthly: dict[str, dict[str, float]] = defaultdict(dict)   # month -> doc_id -> income total on that page
    for ex in extractions:
        lg = ex.handwritten_ledger
        if lg:
            for e in lg.entries:
                if e.kind == "income":
                    monthly[e.date[:7]][ex.doc_id] = monthly[e.date[:7]].get(ex.doc_id, 0.0) + e.amount
    out: set[str] = set()
    for ex in extractions:
        lg = ex.handwritten_ledger
        if not lg:
            continue
        hits = 0
        for e in lg.entries:
            if e.kind != "income" or e.amount <= 0:
                continue
            others = [v for d, v in monthly[e.date[:7]].items() if d != ex.doc_id]
            if any(abs(v - e.amount) <= tolerance * e.amount for v in others):
                hits += 1
        if hits >= 2:
            out.add(ex.doc_id)
    return out


def compute_cashflow(extractions: list[DocumentExtraction], currency: str, holder_names: list[str],
                     requested_amount: Optional[float] = None) -> CashflowSummary:
    rows = flatten_transactions(extractions)
    classify_rows(rows, holder_names)
    recurring = detect_recurring(rows)
    balance_checks = recompute_balances(extractions)

    # period from statements
    starts = [ex.bank_statement.period_start for ex in extractions if ex.bank_statement and _parse_date(ex.bank_statement.period_start)]
    ends = [ex.bank_statement.period_end for ex in extractions if ex.bank_statement and _parse_date(ex.bank_statement.period_end)]
    if rows:
        starts.append(rows[0].tx.date)
        ends.append(rows[-1].tx.date)
    period_start = min(starts) if starts else None
    period_end = max(ends) if ends else None
    months = _month_range(period_start, period_end) if period_start and period_end else []

    by_month: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_month[_month(r.tx.date)].append(r)

    monthly: list[MonthlyRow] = []
    for m in months:
        grp = by_month.get(m, [])
        inflow = sum(r.tx.credit for r in grp)
        outflow = sum(r.tx.debit for r in grp if "round_trip_return" not in r.tags)
        excluded = sum(r.tx.credit for r in grp if r.tags & {"self_transfer", "round_trip"})
        last_day = max((r.d for r in grp), default=None)
        eom_cut = None
        if grp:
            y, mo = int(m[:4]), int(m[5:7])
            nxt = date(y + (mo == 12), (mo % 12) + 1, 1)
            eom_cut = nxt - timedelta(days=5)
        eom = sum(r.tx.credit for r in grp if eom_cut and r.d >= eom_cut)
        closing = None
        for r in reversed(grp):
            if r.tx.balance_after is not None:
                closing = r.tx.balance_after
                break
        monthly.append(MonthlyRow(month=m, inflow=_round(inflow), outflow=_round(outflow), net=_round(inflow - outflow),
                                  business_inflow=_round(inflow - excluded), n_credits=sum(1 for r in grp if r.tx.credit > 0),
                                  n_debits=sum(1 for r in grp if r.tx.debit > 0),
                                  end_of_month_share=_round(eom / inflow, 4) if inflow else 0.0, closing_balance=closing))
    months_missing = [m.month for m in monthly if m.n_credits + m.n_debits == 0]
    active = [m for m in monthly if m.n_credits + m.n_debits > 0]
    n = len(active) or 1
    avg_in = sum(m.inflow for m in active) / n
    avg_out = sum(m.outflow for m in active) / n
    avg_biz = sum(m.business_inflow for m in active) / n
    trend = 0.0
    if len(active) >= 3 and avg_biz > 0:
        xs = list(range(len(active)))
        ys = [m.business_inflow for m in active]
        xm, ym = statistics.mean(xs), statistics.mean(ys)
        slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / (sum((x - xm) ** 2 for x in xs) or 1)
        trend = slope / ym * 100
    cv = (statistics.pstdev([m.business_inflow for m in active]) / avg_biz) if len(active) >= 2 and avg_biz > 0 else 0.0
    total_in = sum(m.inflow for m in active)
    eom_total = sum(m.end_of_month_share * m.inflow for m in active)

    flagged: list[FlaggedTransaction] = []
    for r in rows:
        for tag in ("self_transfer", "round_trip", "large_one_off", "platform_payout", "cash_deposit"):
            if tag in r.tags:
                flagged.append(FlaggedTransaction(row_id=r.tx.row_id, reason=tag, date=r.tx.date, description=r.tx.description,
                                                  amount=r.tx.credit if r.tx.credit > 0 else r.tx.debit, matched_row_id=r.matched, source=r.tx.source))

    # cross-source totals
    dash_gross = dash_payout = 0.0
    rec_purch = rec_sales = 0.0
    led_in = led_out = led_cmp = 0.0
    bank_months = {m.month for m in monthly if m.n_credits + m.n_debits > 0}
    dup_ledgers = duplicate_ledger_pages(extractions) | ledger_summary_pages(extractions)
    for ex in extractions:
        if ex.seller_dashboard:
            for mtr in ex.seller_dashboard.metrics:
                if mtr.key == "gross_sales":
                    dash_gross += mtr.value
                elif mtr.key == "payout":
                    dash_payout += mtr.value
        if ex.receipt and ex.receipt.total:
            if ex.receipt.direction == "sale":
                rec_sales += ex.receipt.total.value
            else:
                rec_purch += ex.receipt.total.value
        if ex.handwritten_ledger:
            for e in ex.handwritten_ledger.entries:
                if ex.doc_id in dup_ledgers:
                    continue  # re-photographed or summary page: its lines restate other pages
                if e.kind == "income":
                    led_in += e.amount
                    if e.date[:7] in bank_months:
                        led_cmp += e.amount
                else:
                    led_out += e.amount
    payout_total = sum(f.amount for f in flagged if f.reason == "platform_payout")
    cash_total = sum(f.amount for f in flagged if f.reason == "cash_deposit")
    self_total = sum(f.amount for f in flagged if f.reason == "self_transfer")
    rt_total = sum(f.amount for f in flagged if f.reason == "round_trip")
    # like-for-like: ledger months the statement covers, duplicates removed (6 ledger months vs 4 statement months
    # would otherwise read as "unbanked" income)
    off_ledger = max(0.0, led_cmp + rec_sales - cash_total) if bank_months else max(0.0, led_in + rec_sales - cash_total)
    debt_service = sum(r.amount * (4.33 if r.occurrences >= 6 and len(r.months) < r.occurrences else 1) for r in recurring if r.likely_debt_service)
    net_biz = avg_biz - avg_out
    capacity = max(0.0, 3 * net_biz)

    summary = CashflowSummary(
        currency=currency, period_start=period_start, period_end=period_end, months_covered=len(active), months_missing=months_missing,
        monthly=monthly, avg_monthly_inflow=_round(avg_in), avg_monthly_outflow=_round(avg_out), avg_monthly_net=_round(avg_in - avg_out),
        avg_monthly_business_inflow=_round(avg_biz), revenue_trend_pct_per_month=_round(trend, 2), inflow_volatility_cv=_round(cv, 3),
        end_of_month_concentration=_round(eom_total / total_in, 4) if total_in else 0.0, recurring_transfers=recurring, flagged=flagged,
        balance_checks=balance_checks, platform_payout_total=_round(payout_total), cash_deposit_total=_round(cash_total),
        dashboard_gross_sales_total=_round(dash_gross), dashboard_payout_total=_round(dash_payout), receipts_purchases_total=_round(rec_purch),
        receipts_sales_total=_round(rec_sales), ledger_income_total=_round(led_in), ledger_expense_total=_round(led_out),
        ledger_income_comparable=_round(led_cmp), ledger_duplicate_doc_ids=sorted(dup_ledgers),
        off_ledger_income_estimate=_round(off_ledger), suggested_capacity=_round(capacity),
    )
    summary.figures = build_figure_catalog(summary, rows, extractions, requested_amount, self_total, rt_total, debt_service)
    return summary


# ---------------------------------------------------------------------------
# Figure catalog
# ---------------------------------------------------------------------------
def _refs(rows: Iterable[Row], cap: int = 25) -> list[SourceRef]:
    out: list[SourceRef] = []
    for r in rows:
        out.append(r.tx.source)
        if len(out) >= cap:
            break
    return out


def build_figure_catalog(s: CashflowSummary, rows: list[Row], extractions: list[DocumentExtraction], requested_amount: Optional[float],
                         self_total: float, rt_total: float, debt_service: float) -> list[Figure]:
    cur = s.currency
    figs: list[Figure] = []
    by_month: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_month[_month(r.tx.date)].append(r)

    def add(fid: str, label: str, value: float, unit: str = "currency", refs: Optional[list[SourceRef]] = None,
            computation: Optional[str] = None, derived: Optional[list[str]] = None, origin: str = "computed") -> None:
        if origin == "document" and not refs:
            return  # a document figure without evidence is not a figure
        if origin == "computed" and not refs and not derived:
            return  # nothing to derive it from (e.g. no statement rows): not a figure either
        figs.append(Figure(id=fid, label=label, value=_round(value, 4 if unit in ("ratio", "percent") else 2), unit=unit,
                           currency=cur if unit == "currency" else None, source_refs=refs or [], computation=computation,
                           derived_from=derived or [], origin=origin))

    month_in_ids: list[str] = []
    for m in s.monthly:
        grp = by_month.get(m.month, [])
        credits = [r for r in grp if r.tx.credit > 0]
        debits = [r for r in grp if r.tx.debit > 0]
        biz = [r for r in credits if not r.tags & {"self_transfer", "round_trip"}]
        add(f"CF.m.{m.month}.inflow", f"Total inflow {m.month}", m.inflow, refs=_refs(credits), computation=f"Sum of {len(credits)} credit rows dated {m.month}")
        add(f"CF.m.{m.month}.outflow", f"Total outflow {m.month} (excl. round-trip returns)", m.outflow, refs=_refs([r for r in debits if "round_trip_return" not in r.tags]),
            computation=f"Sum of debit rows dated {m.month}, excluding the return leg of round-trips")
        add(f"CF.m.{m.month}.business_inflow", f"Business inflow {m.month} (excl. self-transfers/round-trips)", m.business_inflow, refs=_refs(biz),
            computation="Inflow minus credits tagged self_transfer or round_trip", derived=[f"CF.m.{m.month}.inflow"])
        add(f"CF.m.{m.month}.net", f"Net cash {m.month}", m.net, computation="inflow - outflow",
            derived=[f"CF.m.{m.month}.inflow", f"CF.m.{m.month}.outflow"], refs=_refs(grp, 10))
        if m.closing_balance is not None:
            last = next((r for r in reversed(grp) if r.tx.balance_after is not None), None)
            add(f"CF.m.{m.month}.closing_balance", f"Closing balance {m.month}", m.closing_balance, refs=[last.tx.source] if last else [], origin="document")
        month_in_ids.append(f"CF.m.{m.month}.business_inflow")

    active_ids = [f"CF.m.{m.month}.inflow" for m in s.monthly if m.n_credits + m.n_debits > 0]
    n = len(active_ids) or 1
    add("CF.months_covered", "Months with statement activity", s.months_covered, "months", computation="Count of months with at least one transaction", derived=active_ids[:12])
    add("CF.months_missing_count", "Months missing inside the statement period", len(s.months_missing), "months",
        computation=f"Months in period with zero rows: {', '.join(s.months_missing) or 'none'}", derived=["CF.months_covered"])
    add("CF.total_inflow", "Total inflow over period", sum(m.inflow for m in s.monthly), computation="Sum of monthly inflow", derived=active_ids)
    add("CF.total_outflow", "Total outflow over period", sum(m.outflow for m in s.monthly), computation="Sum of monthly outflow",
        derived=[f"CF.m.{m.month}.outflow" for m in s.monthly if m.n_debits])
    add("CF.avg_monthly_inflow", "Average monthly inflow", s.avg_monthly_inflow, computation=f"Total inflow / {n} active months", derived=active_ids)
    add("CF.avg_monthly_outflow", "Average monthly outflow", s.avg_monthly_outflow, computation=f"Total outflow / {n} active months",
        derived=[f"CF.m.{m.month}.outflow" for m in s.monthly if m.n_debits])
    add("CF.avg_monthly_net", "Average monthly net cash", s.avg_monthly_net, computation="avg inflow - avg outflow", derived=["CF.avg_monthly_inflow", "CF.avg_monthly_outflow"])
    add("CF.avg_monthly_business_inflow", "Average monthly business inflow", s.avg_monthly_business_inflow,
        computation="Average of monthly inflow excluding self-transfers and round-trips", derived=month_in_ids)
    add("CF.revenue_trend_pct", "Business inflow trend per month", s.revenue_trend_pct_per_month, "percent",
        computation="OLS slope of monthly business inflow divided by its mean, x100", derived=month_in_ids)
    add("CF.inflow_volatility_cv", "Inflow volatility (coefficient of variation)", s.inflow_volatility_cv, "ratio",
        computation="Population std-dev of monthly business inflow / mean", derived=month_in_ids)
    add("CF.end_of_month_concentration", "Share of inflow landing in the last 5 days of each month", s.end_of_month_concentration, "ratio",
        computation="Credits dated in the last 5 days of a month / total inflow", derived=active_ids)
    self_rows = [r for r in rows if "self_transfer" in r.tags]
    rt_rows = [r for r in rows if "round_trip" in r.tags]
    add("CF.self_transfer_total", "Credits from the applicant's own accounts", self_total, refs=_refs(self_rows), origin="document",
        computation=f"Sum of {len(self_rows)} credits whose sender matches the account holder")
    add("CF.self_transfer_count", "Number of own-account credits", len(self_rows), "count", refs=_refs(self_rows), origin="document")
    add("CF.round_trip_total", "Credits returned to the sender within 14 days", rt_total, refs=_refs(rt_rows), origin="document",
        computation=f"Sum of {len(rt_rows)} credits with a matching outgoing transfer")
    po_rows = [r for r in rows if "platform_payout" in r.tags]
    cd_rows = [r for r in rows if "cash_deposit" in r.tags]
    add("CF.platform_payout_total", "Marketplace payouts received in bank", s.platform_payout_total, refs=_refs(po_rows), origin="document",
        computation=f"Sum of {len(po_rows)} credits from marketplace platforms")
    add("CF.cash_deposit_total", "Cash deposits into bank", s.cash_deposit_total, refs=_refs(cd_rows), origin="document",
        computation=f"Sum of {len(cd_rows)} cash deposit credits")
    # dashboards / receipts / ledger
    dash_refs, pay_refs, rec_p, rec_s, led_refs, led_exp_refs = [], [], [], [], [], []
    for ex in extractions:
        if ex.seller_dashboard:
            for mtr in ex.seller_dashboard.metrics:
                if mtr.key == "gross_sales":
                    dash_refs.append(mtr.source)
                if mtr.key == "payout":
                    pay_refs.append(mtr.source)
                add(f"DOC.{ex.doc_id}.{mtr.key}", f"{mtr.label} ({ex.seller_dashboard.period_start or '?'} to {ex.seller_dashboard.period_end or '?'}, {ex.doc_id})",
                    mtr.value, "currency" if mtr.key in ("gross_sales", "net_sales", "payout", "ad_spend", "returns") else ("score" if mtr.key == "rating" else "count"),
                    refs=[mtr.source], origin="document")
        if ex.receipt and ex.receipt.total:
            (rec_s if ex.receipt.direction == "sale" else rec_p).append(ex.receipt.total.source)
            add(f"DOC.{ex.doc_id}.total", f"Receipt total {ex.receipt.merchant or ''} {ex.receipt.date or ''} ({ex.doc_id})", ex.receipt.total.value,
                refs=[ex.receipt.total.source], origin="document")
        if ex.handwritten_ledger:
            inc = [e for e in ex.handwritten_ledger.entries if e.kind == "income"]
            exp = [e for e in ex.handwritten_ledger.entries if e.kind == "expense"]
            if ex.doc_id not in s.ledger_duplicate_doc_ids:  # totals cite only the pages they sum
                led_refs += [e.source for e in inc]
                led_exp_refs += [e.source for e in exp]
            add(f"DOC.{ex.doc_id}.income_total", f"Ledger income {ex.handwritten_ledger.period_label or ''} ({ex.doc_id})", sum(e.amount for e in inc),
                refs=[e.source for e in inc][:25], origin="document", computation=f"Sum of {len(inc)} income lines on the page")
        if ex.bank_statement:
            if ex.bank_statement.opening_balance:
                add(f"DOC.{ex.doc_id}.opening_balance", f"Opening balance ({ex.doc_id})", ex.bank_statement.opening_balance.value, refs=[ex.bank_statement.opening_balance.source], origin="document")
            if ex.bank_statement.closing_balance:
                add(f"DOC.{ex.doc_id}.closing_balance", f"Closing balance ({ex.doc_id})", ex.bank_statement.closing_balance.value, refs=[ex.bank_statement.closing_balance.source], origin="document")
    add("CF.dashboard_gross_sales_total", "Marketplace gross sales (sum of dashboards)", s.dashboard_gross_sales_total, refs=dash_refs, origin="document")
    add("CF.dashboard_payout_total", "Marketplace payout (sum of dashboards)", s.dashboard_payout_total, refs=pay_refs, origin="document")
    add("CF.receipts_purchases_total", "Supplier purchases evidenced by receipts", s.receipts_purchases_total, refs=rec_p[:25], origin="document",
        computation=f"Sum of {len(rec_p)} purchase receipts")
    add("CF.receipts_count", "Number of receipts provided", len(rec_p) + len(rec_s), "count", refs=(rec_p + rec_s)[:25], origin="document")
    add("CF.receipts_sales_total", "Sales evidenced by receipts", s.receipts_sales_total, refs=rec_s[:25], origin="document")
    add("CF.ledger_income_total", "Cash income recorded in handwritten ledger", s.ledger_income_total, refs=led_refs[:25], origin="document",
        computation=f"Sum of {len(led_refs)} income lines across ledger pages"
                    + (f" (excluding duplicate/summary pages {', '.join(s.ledger_duplicate_doc_ids)})" if s.ledger_duplicate_doc_ids else ""))
    add("CF.ledger_expense_total", "Expenses recorded in handwritten ledger", s.ledger_expense_total, refs=led_exp_refs[:25], origin="document")
    add("CF.ledger_income_comparable", "Ledger cash income in months the bank statement covers (duplicate pages excluded)",
        s.ledger_income_comparable, refs=led_refs[:25], origin="document",
        computation="Ledger income lines dated in statement months"
                    + (f"; excludes re-photographed pages {', '.join(s.ledger_duplicate_doc_ids)}" if s.ledger_duplicate_doc_ids else ""))
    add("CF.off_ledger_income_estimate", "Income seen in ledger/receipts but not deposited (same months)", s.off_ledger_income_estimate,
        computation="max(0, comparable ledger income + receipt sales - bank cash deposits)",
        derived=["CF.ledger_income_comparable", "CF.receipts_sales_total", "CF.cash_deposit_total"])
    add("CF.recurring_debt_service_monthly", "Monthly outflow on recurring loan-like transfers", debt_service,
        refs=[ref for r in s.recurring_transfers if r.likely_debt_service for ref in r.source_refs][:25], origin="document",
        computation="Sum of recurring transfers flagged as likely debt service (weekly ones x4.33)")
    add("CF.suggested_capacity", "Illustrative repayment capacity (3 x avg monthly net business cash)", s.suggested_capacity,
        computation="3 x (avg monthly business inflow - avg monthly outflow); not a credit score", derived=["CF.avg_monthly_business_inflow", "CF.avg_monthly_outflow"])
    for i, r in enumerate(s.recurring_transfers, 1):
        add(f"CF.recurring.{i}.amount", f"Recurring transfer to {r.counterparty} ({r.occurrences}x, day {r.day_of_month_mode})", r.amount, refs=r.source_refs, origin="document")
        add(f"CF.recurring.{i}.occurrences", f"Occurrences of recurring transfer to {r.counterparty}", r.occurrences, "count", refs=r.source_refs, origin="document")
    for f in s.flagged:
        if f.reason in ("self_transfer", "round_trip", "large_one_off"):
            add(f"TX.{f.row_id}", f"{f.reason.replace('_', ' ')}: {f.description} ({f.date})", f.amount, refs=[f.source], origin="document")
    top_credits = sorted((r for r in rows if r.tx.credit > 0), key=lambda r: -r.tx.credit)[:8]
    top_debits = sorted((r for r in rows if r.tx.debit > 0), key=lambda r: -r.tx.debit)[:8]
    seen = {f.id for f in figs}
    for r in top_credits + top_debits:
        fid = f"TX.{r.tx.row_id}"
        if fid not in seen:
            seen.add(fid)
            add(fid, f"{'Credit' if r.tx.credit else 'Debit'}: {r.tx.description} ({r.tx.date})", r.tx.credit or r.tx.debit, refs=[r.tx.source], origin="document")
    if requested_amount:
        add("APP.requested_amount", "Requested loan amount", requested_amount, computation="Stated on the loan application", origin="application")
        if s.suggested_capacity > 0:
            add("CF.request_to_capacity", "Requested amount / illustrative capacity", requested_amount / s.suggested_capacity, "ratio",
                computation="requested amount / suggested capacity", derived=["APP.requested_amount", "CF.suggested_capacity"])
    return figs
