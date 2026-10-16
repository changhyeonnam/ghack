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
