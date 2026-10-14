"""Feedback loop: underwriter accept/dismiss decisions become Challenger question priorities."""
from __future__ import annotations

from collections import defaultdict

from .schemas import ChallengeResult, ChallengerPriority, FeedbackPriorities
from .storage import Repository

PRIORITIES_KEY = "challenger_priorities"


def compute_priorities(repo: Repository) -> FeedbackPriorities:
    raised: dict[str, int] = defaultdict(int)
    accepted: dict[str, int] = defaultdict(int)
    dismissed: dict[str, int] = defaultdict(int)
    n_dec = 0
    for case in repo.list_cases():
        if not case.decision:
            continue
        art = repo.get_artifact(case.id, "challenge")
        if not art:
            continue
        n_dec += 1
        ch = ChallengeResult.model_validate(art)
        q_of = {o.id: o.question_id for o in ch.objections}
        for o in ch.objections:
            raised[o.question_id] += 1
        for r in case.decision.objection_resolutions or case.objection_resolutions:
            q = q_of.get(r.objection_id)
            if not q:
                continue
            if r.status == "accepted":
                accepted[q] += 1
            elif r.status == "dismissed":
                dismissed[q] += 1
    pri: list[ChallengerPriority] = []
    for q in [f"Q{i}" for i in range(1, 13)] + sorted(set(raised) - {f"Q{i}" for i in range(1, 13)}):
        a, d, r = accepted[q], dismissed[q], raised[q]
        rate = (a / (a + d)) if (a + d) else None
        weight = 1.0 if (a + d) < 2 else round(0.5 + rate, 2)
        pri.append(ChallengerPriority(question_id=q, raised=r, accepted=a, dismissed=d, acceptance_rate=round(rate, 3) if rate is not None else None, weight=weight))
    fp = FeedbackPriorities(n_decisions=n_dec, priorities=pri)
    repo.save_global(PRIORITIES_KEY, fp.model_dump(mode="json"))
    return fp


def load_priorities(repo: Repository) -> FeedbackPriorities:
    data = repo.get_global(PRIORITIES_KEY)
    return FeedbackPriorities.model_validate(data) if data else FeedbackPriorities()
