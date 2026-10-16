"""Regression tests for QA findings: namesake self-transfers, missing per-row balances, 100x text-layer matches,
and rule objections being swallowed by weaker LLM objections."""
from __future__ import annotations

from app.agents.challenger import merge_objections
from app.schemas import Objection, Severity, SourceRef, Transaction
from app.tools.cashflow import compute_cashflow, recompute_balances
from app.tools.textlayer import PageWords, _find_amount

from test_tools import _src, _statement


def test_namesake_is_not_a_self_transfer():
    rows = [(f"2026-0{m}-10", "SHOPEE PAYOUT", 0, 20_000_000, None, False) for m in range(1, 7)]
    rows.append(("2026-02-12", "NHAN TU NGUYEN THI HOA", 0, 9_000_000, "NGUYEN THI HOA", False))
    rows.append(("2026-03-12", "CHUYEN TIEN TU NGUYEN THI LINH - VCB", 0, 24_000_000, "NGUYEN THI LINH", False))
    rows.sort(key=lambda r: r[0])
    cf = compute_cashflow([_statement(rows)], "VND", ["NGUYEN THI LINH"], 50_000_000)
    selfs = [f for f in cf.flagged if f.reason == "self_transfer"]
    assert len(selfs) == 1 and selfs[0].amount == 24_000_000


def test_rows_without_balance_carry_the_running_balance():
    ex = _statement([("2026-01-02", "A", 0, 1_000_000, None, False), ("2026-01-02", "B", 0, 500_000, None, False),
                     ("2026-01-03", "C", 200_000, 0, None, False)])
    ex.bank_statement.transactions[0].balance_after = None  # balance printed only on the last row of the day
    assert recompute_balances([ex]) == []


def test_text_layer_rejects_100x_misread_but_accepts_decimals():
    box = (10.0, 10.0, 50.0, 20.0)
    pw = PageWords(width=600, height=800, words=[], digits_index={"1250000": [box], "094": [box], "1480000": [box]},
                   cents_index={"094": [box], "1480000": [box]})  # printed: 1.250.000 (VND), 0.94, 14,800.00
    assert _find_amount(pw, 1_250_000) == [box]
    assert _find_amount(pw, 12_500) == []          # 100x misread of 1.250.000 must not pass
    assert _find_amount(pw, 0.94) == [box]
    assert _find_amount(pw, 14_800) == [box]


def _obj(q, sev, title, refs=None, tool=None):
    return Objection(id="X", question_id=q, severity=sev, title=title, claim=title, evidence_refs=refs or [], tool_evidence=tool,
                     suggested_action="check")


def test_rule_objections_survive_a_weak_llm_objection():
    ref = SourceRef(doc_id="D01", page=1)
    llm = [_obj("Q6", Severity.low, "Minor balance quirks", [ref])]
    rules = [_obj("Q6", Severity.critical, "Balance break T0010", [ref], "balance chain T0010"),
             _obj("Q6", Severity.critical, "Balance break T0042", [ref], "balance chain T0042")]
    out = merge_objections(llm, rules)
    assert len(out) == 2 and all(o.severity == Severity.critical for o in out)
    assert any("T0010" in (o.tool_evidence or "") for o in out) and any("T0042" in (o.tool_evidence or "") for o in out)


def test_statement_pages_merge_header_balances_and_renumber_rows():
    from app.agents.extractor import merge_statement_pages
    src = lambda p: {"doc_id": "D01", "page": p, "bbox": None}  # noqa: E731
    row = lambda d, p: {"row_id": "T0001", "date": d, "description": "x", "credit": 1.0, "debit": 0.0, "source": src(p)}  # noqa: E731
    pages = [{"bank_name": "VCB", "account_holder": "NGUYEN THI LINH", "currency": None, "opening_balance": {"value": 5.0, "source": src(1)},
              "transactions": [row("2026-01-02", 1), row("2026-01-03", 1)]},
             {"transactions": [row("2026-02-01", 2)], "closing_balance": {"value": 8.0, "source": src(2)}}]
    m = merge_statement_pages(pages, "VND")
    assert [t["row_id"] for t in m["transactions"]] == ["T0001", "T0002", "T0003"]
    assert m["bank_name"] == "VCB" and m["currency"] == "VND" and m["opening_balance"]["value"] == 5.0 and m["closing_balance"]["value"] == 8.0
    assert (m["period_start"], m["period_end"]) == ("2026-01-02", "2026-02-01")


def _ledger(doc_id, month, amounts, label=""):
    from app.schemas import DocType, DocumentExtraction, LedgerEntry, LedgerExtraction
    entries = [LedgerEntry(row_id=f"L{i:04d}", date=f"2026-{month:02d}-{(i % 27) + 1:02d}", description=f"job {i}", amount=a, kind="income",
                           source=SourceRef(doc_id=doc_id, page=1)) for i, a in enumerate(amounts, 1)]
    return DocumentExtraction(doc_id=doc_id, doc_type=DocType.handwritten_ledger,
                              handwritten_ledger=LedgerExtraction(period_label=label, entries=entries))


def test_ledger_vs_deposits_compares_like_with_like():
    """Case C shape: 6 ledger months but only Jan/Feb in the statement, one page re-photographed with the month
    changed, and a summary page restating monthly totals. Only Jan+Feb daily lines are comparable."""
    from app.tools.checks import reconcile_cash
    jan, feb, mar = [1000.0, 2000.0, 3000.0], [1500.0, 2500.0, 500.0], [700.0, 800.0, 900.0]
    exs = [_ledger("D02", 1, jan), _ledger("D03", 2, feb), _ledger("D04", 3, mar),
           _ledger("D07", 4, mar),  # March page photographed again as "April"
           _ledger("D09", 1, [6000.0], "summary")]
    summary = exs[-1].handwritten_ledger
    summary.entries += [summary.entries[0].model_copy(update={"row_id": "L0002", "date": "2026-02-01", "amount": 4500.0}),
                        summary.entries[0].model_copy(update={"row_id": "L0003", "date": "2026-03-01", "amount": 2400.0})]
    bank = _statement([("2026-01-08", "CASH DEPOSIT - BRANCH", 0, 6000, None, False),
                       ("2026-02-09", "CASH DEPOSIT - BRANCH", 0, 4500, None, False)], opening=1000.0)
    cf = compute_cashflow([bank, *exs], "PHP", ["RAMON REYES"], 50_000)
    assert set(cf.ledger_duplicate_doc_ids) == {"D07", "D09"}
    assert cf.ledger_income_total == 6000 + 4500 + 2400          # three real pages, all months
    assert cf.ledger_income_comparable == 6000 + 4500            # only statement months
    assert cf.off_ledger_income_estimate == 0
    assert reconcile_cash(cf).double_count_risk                  # deposits mirror the ledger: same money


def test_weekly_transfers_survive_a_gap_of_missing_statement_months():
    rows = []
    for d in ["01-02", "01-09", "01-16", "01-23", "01-30", "02-06", "02-13", "02-20", "02-27", "05-01", "05-08", "05-15", "05-22"]:
        rows.append((f"2026-{d}", "GCASH TRANSFER TO JUAN DELA CRUZ", 3000, 0, "JUAN DELA CRUZ", False))
    rows.append(("2026-01-05", "CASH DEPOSIT", 0, 50000, None, False))
    rows.sort(key=lambda r: r[0])
    cf = compute_cashflow([_statement(rows)], "PHP", ["RAMON REYES"], 50_000)
    juan = [r for r in cf.recurring_transfers if "JUAN" in r.counterparty]
    assert juan and juan[0].likely_debt_service and juan[0].occurrences == 13


def test_missing_months_rule_merges_with_llm_objection_naming_the_months():
    llm = [_obj("Q5", Severity.medium, "Statement omits March and April 2026", [SourceRef(doc_id="D01", page=1)])]
    rule = _obj("Q5", Severity.high, "No statement rows for 2026-03, 2026-04")
    out = merge_objections(llm, [rule])
    assert len(out) == 1 and out[0].severity == Severity.high


def test_entity_check_lists_only_mismatching_documents():
    from app.schemas import DocType, DocumentExtraction, PremisesExtraction
    from app.tools import checks
    exs = [DocumentExtraction(doc_id="D10", doc_type=DocType.premises_photo, premises=PremisesExtraction(signage_text="Reyes Auto Repair")),
           DocumentExtraction(doc_id="D11", doc_type=DocType.premises_photo, premises=PremisesExtraction(signage_text="SERVICE BAY 2"))]
    res = [e for e in checks.entity_consistency(exs, None, "Reyes Auto Repair", "PH", "PHP") if e.field == "business_name"][0]
    assert not res.consistent and set(res.values) == {"application", "D11"}


def test_absorbed_rule_finding_stays_visible_in_the_llm_objection():
    ref = SourceRef(doc_id="D01", page=1)
    llm = [_obj("Q3", Severity.high, "Self-transfers across rows T0037, T0126", [ref])]
    rule = _obj("Q3", Severity.high, "Credit of 24,000,000 on 2026-02-12 comes from the applicant's own account", [ref],
                "self-transfer detector T0037")
    out = merge_objections(llm, [rule])
    assert len(out) == 1 and "24,000,000" in out[0].tool_evidence and "T0037" in out[0].tool_evidence
