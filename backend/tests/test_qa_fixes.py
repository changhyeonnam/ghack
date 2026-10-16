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
