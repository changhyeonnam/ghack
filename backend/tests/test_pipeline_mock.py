"""End-to-end wiring test in mock mode with a tiny generated statement (no API key, no synthetic dataset needed)."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def tiny_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 800, "SYNTHETIC BANK - STATEMENT 01/2026")
    c.drawString(72, 780, "02/01/2026 QRIS SALES 1.250.000 CR 5.600.000")
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGERLENS_LLM_MODE", "mock")
    monkeypatch.setenv("LEDGERLENS_LOCAL_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LEDGERLENS_DEMO_SEED_ON_STARTUP", "false")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_full_pipeline_mock(client):
    r = client.post("/api/cases", json={"name": "T", "business_name": "Test Warung", "sector": "grocery retail", "country": "ID", "language": "id", "currency": "IDR", "requested_amount": 1000000})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = client.post(f"/api/cases/{cid}/documents", files=[("files", ("stmt.pdf", tiny_pdf(), "application/pdf"))])
    assert r.status_code == 200, r.text
    assert r.json()["documents"][0]["pages"] == 1
    for stage in ("intake", "extract", "cashflow", "analyze", "challenge"):
        r = client.post(f"/api/cases/{cid}/run", params={"stage": stage})
        assert r.status_code == 200, f"{stage}: {r.text}"
        st = next(s for s in r.json()["stages"] if s["name"] == stage)
        assert st["status"] == "done", st
    memo = client.get(f"/api/cases/{cid}/memo").json()
    assert memo["draft"]["recommendation"] in ("approve", "approve_with_conditions", "hold", "reject", "request_more_documents")
    ch = client.get(f"/api/cases/{cid}/challenge").json()
    assert "objections" in ch
    png = client.get(f"/api/cases/{cid}/documents/D01/pages/1")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    if ch["objections"]:
        oid = ch["objections"][0]["id"]
        r = client.post(f"/api/cases/{cid}/objections/{oid}/resolution", json={"status": "accepted", "by": "tester"})
        assert r.status_code == 200
    r = client.post(f"/api/cases/{cid}/decision", json={"outcome": "approve_with_conditions", "conditions": ["x"], "rationale": "ok", "underwriter": "tester"})
    assert r.status_code == 200 and r.json()["status"] == "decided"
    r = client.post(f"/api/cases/{cid}/letter", json={"language": "id"})
    assert r.status_code == 200 and r.json()["language"] == "id"
    assert client.get(f"/api/cases/{cid}/audit").json()
    assert client.get(f"/api/cases/{cid}/traces").json()
    assert client.get("/api/feedback/priorities").json()["n_decisions"] == 1
