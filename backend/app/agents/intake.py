"""Stage 1: classify every document (type, language, currency, quality)."""
from __future__ import annotations

from typing import Any

from google.genai import types

from ..config import Settings
from ..schemas import Case, DocType, IntakeResult
from ..storage import Repository
from . import prompts
from .common import case_facts, thumbnail_part
from .runner import AgentSpec, run_agent


async def run_intake(case: Case, *, repo: Repository, settings: Settings, mock_context: dict[str, Any]) -> IntakeResult:
    parts: list[types.Part] = [types.Part.from_text(text=case_facts(case)), types.Part.from_text(text=f"There are {len(case.documents)} documents. Classify each one.")]
    for d in case.documents:
        parts += thumbnail_part(repo, case, d)
    spec = AgentSpec(name="intake", instruction=prompts.INTAKE, prompt_version=prompts.PROMPT_VERSIONS["intake"], model=settings.model_flash,
                     output_schema=IntakeResult, description="Classifies uploaded documents")
    res = await run_agent(spec, parts, settings=settings, repo=repo, case_id=case.id, mock_context=mock_context)
    result = IntakeResult.model_validate(res.parsed)
    known = {d.doc_id for d in case.documents}
    result.documents = [d for d in result.documents if d.doc_id in known]
    seen = {d.doc_id for d in result.documents}
    for d in case.documents:
        if d.doc_id not in seen:
            result.documents.append(type(result.documents[0])(doc_id=d.doc_id, doc_type=DocType.other, language=case.language, currency=case.currency,
                                                             quality_flags=[], confidence=0.0, summary="Not classified by the model.") if result.documents else None)  # type: ignore[arg-type]
    # write classification back onto the case documents
    by_id = {d.doc_id: d for d in result.documents if d}
    for d in case.documents:
        r = by_id.get(d.doc_id)
        if r:
            d.doc_type, d.language, d.quality_flags = r.doc_type, r.language, r.quality_flags
    return result
