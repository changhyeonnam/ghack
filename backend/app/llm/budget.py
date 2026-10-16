"""Spend tracking and the AI usage limit, shared by every process (stored in the repository, not in memory).

Two things stop live Gemini calls:
  * our own cap: total estimated spend >= LEDGERLENS_BUDGET_CAP_USD (persisted, so restarts and new Cloud Run
    instances do not reset it), and
  * the provider: Gemini answers that the key's credits/quota are exhausted (e.g. 402 "prepayment credits are
    depleted"). That is remembered for a cool-down so every request does not hit it again.
Cached results keep working either way; the frontend shows a banner while the limit is in force.
"""
from __future__ import annotations

import re
import time
from typing import Any

from ..config import Settings
from ..storage import Repository

PROVIDER_DOC = "ai_provider_limit"
# Billing limits only. A 429 per-minute rate limit ("exceeded your current quota ... PerMinute ... retry in 6s") is
# transient and must not pause live analysis for the cool-down; it is retried by the runner instead.
_PROVIDER_LIMIT = re.compile(r"\b402\b|prepayment|credits? (?:are |is )?depleted|billing account|PerDay", re.IGNORECASE)
_TRANSIENT = re.compile(r"PerMinute|retry in [0-9.]+s|retryDelay", re.IGNORECASE)


class BudgetExceeded(RuntimeError):
    """Live Gemini calls are paused (our cap or the provider's limit). Cached results still replay."""


def is_provider_limit_error(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__}: {exc}"
    if _TRANSIENT.search(msg) and not re.search(r"\b402\b|prepayment|depleted", msg, re.IGNORECASE):
        return False
    return bool(_PROVIDER_LIMIT.search(msg))


def record_provider_limit(repo: Repository, exc: BaseException) -> None:
    repo.save_global(PROVIDER_DOC, {"at": time.time(), "reason": str(exc)[:300]})


def state(repo: Repository, settings: Settings) -> dict[str, Any]:
    spent = repo.get_spend()
    cap = settings.budget_cap_usd
    prov = repo.get_global(PROVIDER_DOC) or {}
    provider_active = bool(prov) and time.time() - float(prov.get("at", 0)) < settings.provider_limit_cooldown_s
    over_cap = spent >= cap
    reason = None
    if over_cap:
        reason = "budget_cap"
    elif provider_active:
        reason = "provider_limit"
    return {"exhausted": reason is not None, "reason": reason, "spent_usd": round(spent, 4), "cap_usd": cap,
            "provider_limit_since": prov.get("at") if provider_active else None}


def check(repo: Repository, settings: Settings) -> None:
    st = state(repo, settings)
    if st["exhausted"]:
        why = (f"the AI budget of USD {st['cap_usd']:.2f} is used up" if st["reason"] == "budget_cap"
               else "the Gemini API key has reached its billing limit")
        raise BudgetExceeded(f"Live AI analysis is paused: {why}. Previously analysed cases can still be opened.")
