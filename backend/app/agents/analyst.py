"""Stage 4: the Analyst drafts the memo. It can only *select* figure ids from the deterministic catalog."""
from __future__ import annotations

import re
from typing import Any

from google.genai import types

from ..config import Settings
from ..schemas import Case, CashflowSummary, DocumentExtraction, DocumentMeta, Figure, IntakeResult, Memo, MemoDraft
from ..storage import Repository
from ..tools.checks import find_unsourced_numerals
from ..tools.sector_benchmark import lookup_sector_benchmark
from . import prompts
from .common import FIG_TOKEN, case_facts, catalog_text, extraction_digest, inventory_text
from .runner import AgentSpec, run_agent


def cashflow_text(cf: CashflowSummary) -> str:
    L = [f"CASHFLOW SUMMARY (currency {cf.currency}; period {cf.period_start}..{cf.period_end}; months with activity {cf.months_covered}; missing {cf.months_missing or 'none'})",
         "month | inflow | outflow | net | business_inflow | credits | debits | end_of_month_share | closing_balance"]
    for m in cf.monthly:
        L.append(f"{m.month} | {m.inflow:,.0f} | {m.outflow:,.0f} | {m.net:,.0f} | {m.business_inflow:,.0f} | {m.n_credits} | {m.n_debits} | {m.end_of_month_share:.2f} | {m.closing_balance if m.closing_balance is not None else '-'}")
    L.append(f"Flags: self_transfers={sum(1 for f in cf.flagged if f.reason == 'self_transfer')}, round_trips={sum(1 for f in cf.flagged if f.reason == 'round_trip')}, "
             f"large_one_offs={sum(1 for f in cf.flagged if f.reason == 'large_one_off')}, platform_payouts={sum(1 for f in cf.flagged if f.reason == 'platform_payout')}, "
             f"cash_deposits={sum(1 for f in cf.flagged if f.reason == 'cash_deposit')}, balance_breaks={len(cf.balance_checks)}")
    for r in cf.recurring_transfers[:10]:
        L.append(f"Recurring debit: {r.counterparty} x{r.occurrences} on day ~{r.day_of_month_mode} ({','.join(r.months)}); likely_debt_service={r.likely_debt_service}")
    return "\n".join(L)


def assemble_memo(case: Case, draft: MemoDraft, catalog: list[Figure], model: str, prompt_version: str, baseline: bool = False) -> Memo:
    by_id = {f.id: f for f in catalog}
    used: list[str] = []

    def collect(text: str) -> None:
        for m in FIG_TOKEN.finditer(text):
            if m.group(1) not in used:
                used.append(m.group(1))

    collect(draft.headline)
    collect(draft.rationale)
    for s in draft.sections:
        for p in s.paragraphs:
            collect(p)
        for fid in s.figure_ids:
            if fid not in used:
                used.append(fid)
    for lst in (draft.strengths, draft.concerns, draft.conditions):
        for x in lst:
            collect(x)
    for fid in draft.key_figure_ids:
        if fid not in used:
            used.append(fid)
    # pull in derivation chains so the UI can drill down
    queue = list(used)
    while queue:
        fid = queue.pop()
        f = by_id.get(fid)
        if f:
            for d in f.derived_from:
                if d not in used and d in by_id:
                    used.append(d)
                    queue.append(d)
    figures = [by_id[f] for f in used if f in by_id]
    unresolved = [f for f in used if f not in by_id]
    memo = Memo(case_id=case.id, model=model, prompt_version=prompt_version, draft=draft, figures=figures, unresolved_figure_ids=unresolved, baseline=baseline)
    memo.unsourced_numerals = find_unsourced_numerals(memo)
    return memo


async def run_analyst(case: Case, *, cashflow: CashflowSummary, extractions: list[DocumentExtraction], intake: IntakeResult | None,
                      repo: Repository, settings: Settings, mock_context: dict[str, Any]) -> Memo:
    docs = {d.doc_id: d for d in case.documents}
    bench = lookup_sector_benchmark(case.sector, case.country)
    bench_txt = ("SECTOR REFERENCE (illustrative): " + f"typical monthly revenue band {bench.get('monthly_revenue_band')} {bench.get('currency') or ''}; "
                 f"gross margin {bench.get('gross_margin')}; seasonality: {bench.get('seasonality')}; cash share: {bench.get('cash_share')}")
    parts: list[types.Part] = [
        types.Part.from_text(text=case_facts(case)),
        types.Part.from_text(text=inventory_text(case)),
        types.Part.from_text(text=extraction_digest(extractions, docs)),
        types.Part.from_text(text=cashflow_text(cashflow)),
        types.Part.from_text(text=bench_txt),
        types.Part.from_text(text=catalog_text(cashflow.figures)),
        types.Part.from_text(text="Draft the memo now. Remember: no digits in prose, only {fig:ID} tokens from the catalog."),
    ]
    spec = AgentSpec(name="analyst", instruction=prompts.ANALYST, prompt_version=prompts.PROMPT_VERSIONS["analyst"], model=settings.model_pro,
                     output_schema=MemoDraft, description="Drafts the evidence-linked credit memo")
    signals = {
        "months_covered": cashflow.months_covered, "months_missing": cashflow.months_missing, "trend": cashflow.revenue_trend_pct_per_month,
        "cv": cashflow.inflow_volatility_cv, "eom": cashflow.end_of_month_concentration,
        "n_self": sum(1 for f in cashflow.flagged if f.reason == "self_transfer"), "n_round": sum(1 for f in cashflow.flagged if f.reason == "round_trip"),
        "n_large": sum(1 for f in cashflow.flagged if f.reason == "large_one_off"), "n_payouts": sum(1 for f in cashflow.flagged if f.reason == "platform_payout"),
        "n_cash": sum(1 for f in cashflow.flagged if f.reason == "cash_deposit"), "n_breaks": len(cashflow.balance_checks),
        "debt": [(r.counterparty, r.occurrences, r.likely_debt_service) for r in cashflow.recurring_transfers],
        "has_dashboards": cashflow.dashboard_gross_sales_total > 0, "has_ledger": cashflow.ledger_income_total > 0, "n_receipts": sum(1 for e in extractions if e.receipt),
        "has_premises": any(e.premises for e in extractions), "capacity": cashflow.suggested_capacity, "requested": case.requested_amount or 0,
        "avg_net": cashflow.avg_monthly_net, "period": f"{cashflow.period_start} to {cashflow.period_end}",
        "holder": next((e.bank_statement.account_holder for e in extractions if e.bank_statement and e.bank_statement.account_holder), None),
        "bank": next((e.bank_statement.bank_name for e in extractions if e.bank_statement and e.bank_statement.bank_name), None),
    }
    ctx = {**mock_context, "extra": {"catalog_ids": {f.id: f.label for f in cashflow.figures}, "expected_outcome": case.demo_expected_outcome, "signals": signals}}
    res = await run_agent(spec, parts, settings=settings, repo=repo, case_id=case.id, mock_context=ctx)
    draft = MemoDraft.model_validate(res.parsed)
    return assemble_memo(case, draft, cashflow.figures, model=res.model or spec.model, prompt_version=spec.prompt_version)


_ = re
