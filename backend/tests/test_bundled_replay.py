"""A checkout without an API key replays the recorded Gemini run from data/llm_cache, and a decision signed in one
workspace (which changes the shared feedback priorities) does not break the Challenger replay in another."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def replay_client(tmp_path, monkeypatch):
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "LEDGERLENS_GOOGLE_API_KEY", "LEDGERLENS_LLM_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LEDGERLENS_LOCAL_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LEDGERLENS_DEMO_SEED_ON_STARTUP", "false")
    from app.config import get_settings
    get_settings.cache_clear()
    if not get_settings().has_bundled_cache:
        pytest.skip("no bundled LLM cache in this checkout")
    from app.main import app
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _case(client, ws, name):
    ids = client.post("/api/demo/seed", headers=ws).json()["cases"]
    return next(i for i in ids if client.get(f"/api/cases/{i}", headers=ws).json()["name"] == name)


def test_keyless_checkout_replays_the_live_run_and_survives_shared_feedback(replay_client):
    c = replay_client
    assert c.get("/api/health").json()["llm_mode"] == "cache_only"
    ws1, ws2 = {"X-LedgerLens-Workspace": "ws-replay-0001"}, {"X-LedgerLens-Workspace": "ws-replay-0002"}
    a = _case(c, ws1, "Reyes Auto Repair")
    r = c.post(f"/api/cases/{a}/run?stage=all", headers=ws1).json()
    assert r["status"] == "challenged" and r["stats"]["n_cached_calls"] == r["stats"]["n_llm_calls"] > 0
    traces = c.get(f"/api/cases/{a}/traces", headers=ws1).json()
    assert all(t["model"].startswith("gemini") for t in traces)  # real model, not mock/*
    body = {"outcome": "request_more_documents", "rationale": "Need March-April statements", "conditions": [], "signed_by": "qa"}
    assert c.post(f"/api/cases/{a}/decision", headers=ws1, json=body).status_code == 200
    b = _case(c, ws2, "Reyes Auto Repair")
    r2 = c.post(f"/api/cases/{b}/run?stage=all", headers=ws2).json()
    assert r2["status"] == "challenged", r2
