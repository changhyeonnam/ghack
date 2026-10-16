"""Demo cases are per browser workspace: signing or resetting in one workspace never touches another."""
from __future__ import annotations

from test_pipeline_mock import client  # noqa: F401  (fixture)

WS1 = {"X-LedgerLens-Workspace": "ws-judge-0001"}
WS2 = {"X-LedgerLens-Workspace": "ws-judge-0002"}


def _ids(client, headers):  # noqa: F811
    return {c["id"] for c in client.get("/api/cases", headers=headers).json()}


def test_workspaces_get_their_own_demo_cases_and_reset_only_their_own(client):  # noqa: F811
    a = client.post("/api/demo/seed", headers=WS1).json()["cases"]
    b = client.post("/api/demo/seed", headers=WS2).json()["cases"]
    assert len(a) == 3 and len(b) == 3 and not set(a) & set(b)
    assert _ids(client, WS1) == set(a) and _ids(client, WS2) == set(b)
    assert _ids(client, {}) == set()  # shared space is separate
    # seeding again without force returns the same copies
    assert set(client.post("/api/demo/seed", headers=WS1).json()["cases"]) == set(a)
    # reset in WS1 replaces only WS1's cases
    a2 = client.post("/api/demo/seed?force=true", headers=WS1).json()["cases"]
    assert not set(a2) & set(a) and _ids(client, WS1) == set(a2) and _ids(client, WS2) == set(b)


def test_new_case_belongs_to_the_creating_workspace_and_bad_ids_are_ignored(client):  # noqa: F811
    body = {"name": "x", "business_name": "Shop", "currency": "VND"}
    cid = client.post("/api/cases", json=body, headers=WS1).json()["id"]
    assert cid in _ids(client, WS1) and cid not in _ids(client, WS2)
    bad = client.post("/api/cases", json=body, headers={"X-LedgerLens-Workspace": "../../x"}).json()["id"]
    assert bad in _ids(client, {})  # invalid header -> shared space


def test_workspace_ids_never_leave_the_api(client):  # noqa: F811
    """A shared case must not reveal its owner's workspace id (it would let anyone edit or delete the case)."""
    owner, other = {"X-LedgerLens-Workspace": "owner-ws-000001"}, {"X-LedgerLens-Workspace": "other-ws-000002"}
    cid = client.post("/api/cases", json={"name": "x", "business_name": "Shop", "currency": "VND"}, headers=owner).json()["id"]
    from app.main import app
    repo = app.state.pipeline.repo
    c = repo.get_case(cid); c.status = "challenged"; repo.save_case(c)
    mine = client.get(f"/api/cases/{cid}", headers=owner).json()
    theirs = [x for x in client.get("/api/cases", headers=other).json() if x["id"] == cid][0]
    assert mine["workspace"] == "you" and theirs["workspace"] == "shared"
    assert "owner-ws-000001" not in client.get(f"/api/cases/{cid}", headers=other).text
    assert client.delete(f"/api/cases/{cid}", headers=other).status_code == 403


def test_upload_limits(client, monkeypatch):  # noqa: F811
    import dataclasses
    from app.main import app
    from app.pipeline import PipelineError
    import pytest
    p = app.state.pipeline
    monkeypatch.setattr(p, "settings", p.settings.model_copy(update={"max_documents_per_case": 1}))
    case = p.create_case(__import__("app.schemas", fromlist=["CaseCreate"]).CaseCreate(name="x", business_name="b"))
    from test_pipeline_mock import tiny_pdf
    p.add_document(case, "a.pdf", tiny_pdf())
    with pytest.raises(PipelineError, match="at most 1"):
        p.add_document(case, "b.pdf", tiny_pdf())
