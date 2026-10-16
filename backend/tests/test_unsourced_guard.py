"""The memo source check: scanner gaps found in QA, and the reject-and-redraft loop."""
from __future__ import annotations

import asyncio

from app.agents import analyst
from app.agents.runner import AgentResult, CacheMiss
from app.schemas import Memo, MemoDraft, MemoSection
from app.tools import checks


def _memo(paragraph: str, heading: str = "Cash flow") -> Memo:
    draft = MemoDraft(headline="h", sections=[MemoSection(heading=heading, paragraphs=[paragraph])], key_figure_ids=[], strengths=[],
                      concerns=[], recommendation="hold", rationale="r")
    return Memo(case_id="c", model="m", prompt_version="v", draft=draft, figures=[])


def _found(paragraph: str, heading: str = "Cash flow") -> list[str]:
    return [u.text for u in checks.find_unsourced_numerals(_memo(paragraph, heading))]


def test_scanner_gaps_from_qa_are_closed():
    assert _found("Gross margin of 35,000,000 is healthy.") == ["35,000,000"]      # "mar" in margin is not March
    assert _found("Sales declined to 48,000,000.") == ["48,000,000"]               # "dec" in declined
    assert _found("About 2500 customers and 9999 orders.") == ["2500", "9999"]     # 4-digit amounts are not years
    assert _found("Text.", heading="Revenue 99,000,000") == ["99,000,000"]          # headings are scanned
    assert _found("Statements cover March 2026 and 14 Mar; FY2025 and 2026-01-31.") == []


def test_analyst_redrafts_until_the_memo_is_clean(monkeypatch):
    drafts = [
        {"headline": "h", "sections": [{"heading": "Cash", "paragraphs": ["Inflow was 12,500,000."]}], "key_figure_ids": [], "strengths": [],
         "concerns": [], "recommendation": "hold", "rationale": "r"},
        {"headline": "h", "sections": [{"heading": "Cash", "paragraphs": ["Inflow was {fig:CF.x}."]}], "key_figure_ids": [], "strengths": [],
         "concerns": [], "recommendation": "hold", "rationale": "r"},
    ]
    seen_prompts: list[str] = []

    async def fake_run_agent(spec, parts, **kw):
        seen_prompts.append(parts[-1].text)
        return AgentResult(text="", parsed=drafts[min(len(seen_prompts) - 1, 1)], model="m")

    monkeypatch.setattr(analyst, "run_agent", fake_run_agent)
    memo = asyncio.run(_run(monkeypatch))
    assert len(seen_prompts) == 2 and "REJECTED" in seen_prompts[1] and "12,500,000" in seen_prompts[1]
    assert memo.unsourced_numerals == []


def test_cache_only_miss_keeps_the_flagged_memo(monkeypatch):
    calls = []

    async def fake_run_agent(spec, parts, **kw):
        calls.append(1)
        if len(calls) > 1:
            raise CacheMiss("miss")
        return AgentResult(text="", parsed={"headline": "h", "sections": [{"heading": "C", "paragraphs": ["It was 12,500,000."]}],
                                            "key_figure_ids": [], "strengths": [], "concerns": [], "recommendation": "hold", "rationale": "r"}, model="m")

    monkeypatch.setattr(analyst, "run_agent", fake_run_agent)
    memo = asyncio.run(_run(monkeypatch))
    assert [u.text for u in memo.unsourced_numerals] == ["12,500,000"]


async def _run(monkeypatch):
    from app.schemas import Case, CashflowSummary
    from app.config import Settings
    monkeypatch.setattr(analyst, "lookup_sector_benchmark", lambda *a: {})
    case = Case(id="c", name="n", business_name="b", currency="VND")
    cf = CashflowSummary.model_validate({"currency": "VND"}) if hasattr(CashflowSummary, "model_validate") else None
    from app.agents.common import Figure  # noqa: F401
    cf.figures.append(analyst.Figure.model_validate({"id": "CF.x", "label": "x", "value": 1.0, "unit": "currency", "origin": "computed",
                                                     "source_refs": [{"doc_id": "D01", "page": 1}]}))
    return await analyst.run_analyst(case, cashflow=cf, extractions=[], intake=None, repo=None, settings=Settings(llm_mode="mock"), mock_context={})
