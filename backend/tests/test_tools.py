"""Unit tests for the deterministic tools: detectors, balance check, duplicate images, memo numeral scan."""
from __future__ import annotations

from app.schemas import (
    BBox, BankStatementExtraction, DocType, DocumentExtraction, DocumentMeta, Memo, MemoDraft, MemoSection, MoneyField, SourceRef, Transaction,
)
from app.tools import checks
from app.tools.cashflow import compute_cashflow, recompute_balances


def _src(page=1):
    return SourceRef(doc_id="D01", page=page, bbox=BBox(ymin=100, xmin=0, ymax=120, xmax=1000))


def _statement(rows, opening=10_000_000.0):
    bal = opening
    txs = []
    for i, (date, desc, debit, credit, cp, breakbal) in enumerate(rows, 1):
        if not breakbal:
            bal = bal + credit - debit
        txs.append(Transaction(row_id=f"T{i:04d}", date=date, description=desc, counterparty=cp, debit=debit, credit=credit, balance_after=bal, source=_src()))
    return DocumentExtraction(doc_id="D01", doc_type=DocType.bank_statement, bank_statement=BankStatementExtraction(
        account_holder="NGUYEN THI LINH", currency="VND", period_start="2026-01-01", period_end="2026-06-30",
        opening_balance=MoneyField(value=opening, source=_src()), transactions=txs))


def test_detectors_find_self_transfer_round_trip_recurring_and_balance_break():
    rows = []
    for m in range(1, 7):
        rows.append((f"2026-{m:02d}-05", "CHUYEN DEN FE CREDIT - TRA GOP", 3_250_000, 0, "FE CREDIT", False))
        rows.append((f"2026-{m:02d}-10", "CHUYEN TIEN TU SHOPEE PAYOUT", 0, 20_000_000, None, False))
        rows.append((f"2026-{m:02d}-18", "THANH TOAN NCC", 9_000_000, 0, "NCC VAI", False))
    rows.append(("2026-02-12", "CHUYEN TIEN TU NGUYEN THI LINH - VCB", 0, 24_000_000, "NGUYEN THI LINH", False))
    rows.append(("2026-03-14", "NHAN TU NGUYEN VAN LONG", 0, 50_000_000, "NGUYEN VAN LONG", False))
    rows.append(("2026-03-20", "CHUYEN DEN NGUYEN VAN LONG", 50_000_000, 0, "NGUYEN VAN LONG", False))
    rows.append(("2026-04-07", "THANH TOAN DON HANG", 0, 18_500_000, None, True))  # balance does not move
    rows.sort(key=lambda r: r[0])
    ex = _statement(rows)
    cf = compute_cashflow([ex], "VND", ["NGUYEN THI LINH"], 150_000_000)
    reasons = {f.reason for f in cf.flagged}
    assert {"self_transfer", "round_trip", "platform_payout"} <= reasons
    assert any(r.likely_debt_service and "FE CREDIT" in r.counterparty for r in cf.recurring_transfers)
    assert any(not r.likely_debt_service for r in cf.recurring_transfers)  # supplier payments are recurring but not debt
    assert cf.months_covered == 6 and cf.months_missing == []
    # every figure is sourced
    assert all(f.is_sourced() for f in cf.figures)
    assert any(f.id == "APP.requested_amount" for f in cf.figures)


def test_balance_break_detected_once():
    rows = [("2026-01-02", "A", 0, 1_000_000, None, False), ("2026-01-03", "B", 0, 500_000, None, True), ("2026-01-04", "C", 200_000, 0, None, False)]
    breaks = recompute_balances([_statement(rows)])
    assert [b.row_id for b in breaks] == ["T0002"]
    assert breaks[0].difference == -500_000


def test_image_duplicates_only_for_near_identical_hashes():
    h_a = "f" * 64
    h_b = "f" * 63 + "e"      # 1 bit apart -> duplicate
    h_c = "0" * 64            # far apart
    docs = [DocumentMeta(doc_id=f"D0{i}", filename=f"r{i}.jpg", mime_type="image/jpeg", size_bytes=1, sha256=str(i), storage_path="x", page_hashes=[h], doc_type=DocType.receipt)
            for i, h in enumerate((h_a, h_b, h_c), 1)]
    dups = checks.image_similarity(docs, past_index=[{"case_id": "PAST-1", "filename": "p.jpg", "sha256": "zzz", "phash16": h_c}])
    pairs = {(d.doc_a, d.doc_b) for d in dups}
    assert ("D01", "D02") in pairs
    assert not any({"D01", "D03"} == {d.doc_a, d.doc_b} for d in dups if not d.cross_case)
    assert any(d.cross_case and d.doc_a == "D03" for d in dups)


def test_unsourced_numeral_scan_tolerates_dates_but_not_amounts():
    draft = MemoDraft(headline="h", sections=[MemoSection(heading="Cash flow", paragraphs=["Inflow was {fig:CF.x} in March 2026 and 12,500,000 in April."])],
                      key_figure_ids=[], strengths=[], concerns=[], recommendation="hold", rationale="r")
    memo = Memo(case_id="c", model="m", prompt_version="v", draft=draft, figures=[])
    found = checks.find_unsourced_numerals(memo)
    assert [u.text for u in found] == ["12,500,000"]
