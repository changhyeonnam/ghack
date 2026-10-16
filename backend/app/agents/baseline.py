"""Benchmark baseline: ONE prompt, all documents, no catalog, no challenger. Shows why the agents are separated."""
from __future__ import annotations

from typing import Any, Optional

from google.genai import types
from pydantic import BaseModel, Field

from ..config import Settings
from ..schemas import Case, Recommendation, Severity, SourceRef
from ..storage import Repository
from . import prompts
from .common import DEMO_DATASET_NOTE, case_facts, inventory_text, page_parts
from .runner import AgentSpec, run_agent


class BaselineFigure(BaseModel):
    label: str
    value: float
    source_refs: list[SourceRef] = Field(default_factory=list)


class BaselineConcern(BaseModel):
    title: str
    claim: str
    severity: Severity


class BaselineSection(BaseModel):
    heading: str
    paragraphs: list[str]


class BaselineMemo(BaseModel):
    headline: str
    sections: list[BaselineSection]
    figures: list[BaselineFigure]
    recommendation: Recommendation
    concerns: list[BaselineConcern]


async def run_baseline(case: Case, *, repo: Repository, settings: Settings, mock_context: dict[str, Any]) -> dict[str, Any]:
    parts: list[types.Part] = [types.Part.from_text(text=case_facts(case)), types.Part.from_text(text=inventory_text(case))]
    if case.is_demo:  # same dataset note as the agent team, so the comparison stays fair
        parts.insert(0, types.Part.from_text(text=DEMO_DATASET_NOTE))
    for d in case.documents:
        parts += page_parts(repo, case, d, settings)
    spec = AgentSpec(name="baseline", instruction=prompts.BASELINE_SINGLE_PROMPT, prompt_version=prompts.PROMPT_VERSIONS["baseline"], model=settings.model_pro,
                     output_schema=BaselineMemo, description="Single-prompt baseline")
    res = await run_agent(spec, parts, settings=settings, repo=repo, case_id=case.id, mock_context=mock_context)
    out = dict(res.parsed or {})
    out["_usage"] = {"input_tokens": res.input_tokens, "output_tokens": res.output_tokens, "thinking_tokens": res.thinking_tokens, "cost_usd": res.cost_usd,
                     "duration_ms": res.duration_ms, "cached": res.cached, "model": res.model}
    return out
