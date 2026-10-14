"""Customer-facing explanation of the decision, in the applicant's language. No numbers, no jargon."""
from __future__ import annotations

from typing import Any, Optional

from google.genai import types

from ..config import Settings
from ..schemas import Case, ChallengeResult, CustomerLetter, CustomerLetterDraft, Decision, Memo
from ..storage import Repository
from . import prompts
from .runner import AgentSpec, run_agent

LANG_NAMES = {"id": "Bahasa Indonesia", "vi": "Vietnamese (Tiếng Việt)", "tl": "Tagalog / Filipino", "en": "English", "th": "Thai", "ms": "Bahasa Melayu"}


async def run_explainer(case: Case, *, decision: Decision, challenge: Optional[ChallengeResult], memo: Optional[Memo], language: str,
                        repo: Repository, settings: Settings, mock_context: dict[str, Any]) -> CustomerLetter:
    accepted_ids = {r.objection_id for r in decision.objection_resolutions if r.status == "accepted"} | {r.objection_id for r in case.objection_resolutions if r.status == "accepted"}
    reasons = []
    if challenge:
        for o in challenge.objections:
            if o.id in accepted_ids:
                reasons.append(f"- {o.title}: {o.suggested_action}")
    if memo:
        reasons += [f"- (analyst concern) {c}" for c in memo.draft.concerns[:4]]
    text = (f"Business: {case.business_name} ({case.sector}, {case.country}).\nDecision: {decision.outcome}.\n"
            f"Conditions: {'; '.join(decision.conditions) or 'none'}.\nUnderwriter rationale (internal, rephrase in plain words): {decision.rationale}\n"
            f"Reasons accepted by the underwriter:\n" + ("\n".join(reasons) or "- none") + f"\n\nWrite the letter in {LANG_NAMES.get(language, language)} (code {language}).")
    spec = AgentSpec(name="explainer", instruction=prompts.EXPLAINER, prompt_version=prompts.PROMPT_VERSIONS["explainer"], model=settings.model_flash,
                     output_schema=CustomerLetterDraft, description="Explains the decision to the customer")
    ctx = {**mock_context, "extra": {"language": language, "outcome": decision.outcome}}
    res = await run_agent(spec, [types.Part.from_text(text=text)], settings=settings, repo=repo, case_id=case.id, mock_context=ctx,
                          cache_extra={"decided_at": decision.decided_at, "language": language})
    draft = CustomerLetterDraft.model_validate(res.parsed)
    return CustomerLetter(case_id=case.id, model=res.model or spec.model, prompt_version=spec.prompt_version, **draft.model_dump())
