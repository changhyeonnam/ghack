"""Live use for visitors: a persisted AI budget with a visible limit, provider limit detection, and runs shared
read-only with other visitors."""
from __future__ import annotations

import asyncio

import pytest
from google.genai import types

from app.agents.runner import AgentSpec, BudgetExceeded, run_agent
from app.config import Settings
from app.llm import budget
from app.storage import build_repository

from test_pipeline_mock import client  # noqa: F401  (fixture)


def _repo(tmp_path, **kw):
    s = Settings(llm_mode="live", local_data_dir=str(tmp_path), google_api_key="test-key", **kw)
    return s, build_repository(s)


def test_spend_is_persisted_and_the_cap_survives_a_restart(tmp_path):
    s, repo = _repo(tmp_path, budget_cap_usd=0.10)
    repo.add_spend(0.06)
    assert not budget.state(repo, s)["exhausted"]
    s2, repo2 = _repo(tmp_path, budget_cap_usd=0.10)   # "restart": new settings and repository on the same store
    repo2.add_spend(0.05)
    st = budget.state(repo2, s2)
    assert st["exhausted"] and st["reason"] == "budget_cap" and st["spent_usd"] == pytest.approx(0.11)
    with pytest.raises(BudgetExceeded, match="paused"):
        asyncio.run(run_agent(AgentSpec(name="intake", instruction="x", prompt_version="v", model="gemini-3.8-flash"),
                              [types.Part.from_text(text="hi")], settings=s2, repo=repo2, case_id="c"))


def test_provider_limit_is_recognised_and_remembered(tmp_path):
    s, repo = _repo(tmp_path)
    err = RuntimeError("402 RESOURCE_EXHAUSTED. Your prepayment credits are depleted.")
    assert budget.is_provider_limit_error(err) and not budget.is_provider_limit_error(RuntimeError("503 UNAVAILABLE high demand"))
    budget.record_provider_limit(repo, err)
    st = budget.state(repo, s)
    assert st["exhausted"] and st["reason"] == "provider_limit"
    s_short = Settings(llm_mode="live", local_data_dir=str(tmp_path), google_api_key="k", provider_limit_cooldown_s=0)
    assert not budget.state(repo, s_short)["exhausted"]  # cool-down over: try live again


def test_health_reports_the_ai_limit(client):  # noqa: F811
    ai = client.get("/api/health").json()["ai_limit"]
    assert set(ai) >= {"exhausted", "reason", "spent_usd", "cap_usd", "live_available"}


def test_analysed_cases_are_shared_read_only(client):  # noqa: F811
    ws1, ws2 = {"X-LedgerLens-Workspace": "ws-owner-0001"}, {"X-LedgerLens-Workspace": "ws-viewer-0002"}
    cid = client.post("/api/cases", json={"name": "x", "business_name": "Shop", "currency": "VND"}, headers=ws1).json()["id"]
    hidden = client.post("/api/cases", json={"name": "y", "business_name": "Shop", "currency": "VND", "shared": False}, headers=ws1).json()["id"]
    ids2 = lambda: {c["id"] for c in client.get("/api/cases", headers=ws2).json()}  # noqa: E731
    assert cid not in ids2()  # not analysed yet
    from app.main import app
    repo = app.state.pipeline.repo
    for x in (cid, hidden):
        c = repo.get_case(x)
        c.status = "challenged"
        repo.save_case(c)
    assert cid in ids2() and hidden not in ids2()
    assert client.get(f"/api/cases/{cid}", headers=ws2).status_code == 200           # viewable
    r = client.post(f"/api/cases/{cid}/run?stage=all", headers=ws2)
    assert r.status_code == 403 and "read-only" in r.json()["detail"]                # not runnable by others
    assert client.delete(f"/api/cases/{cid}", headers=ws2).status_code == 403


def test_firestore_field_names_are_not_reserved():
    """Firestore rejects field names matching __.*__ (400 "field name __json__ is reserved")."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "storage.py").read_text()
    assert not re.findall(r'["\']__\w+__["\']', src)
