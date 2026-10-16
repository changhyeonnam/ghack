"""LedgerLens API. FastAPI on Cloud Run; also serves the built frontend when LEDGERLENS_STATIC_DIR is set."""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agents.runner import BudgetExceeded, CacheMiss, spent_usd
from .config import Settings, get_settings
from .feedback import compute_priorities, load_priorities
from .pipeline import Pipeline, PipelineError
from .schemas import Case, CaseCreate, Decision, Recommendation, ResolutionStatus, StageName
from .storage import build_repository
from .tools.documents import render_page

log = logging.getLogger("ledgerlens")


class ResolutionBody(BaseModel):
    status: ResolutionStatus
    note: Optional[str] = None
    by: Optional[str] = None


class DecisionBody(BaseModel):
    outcome: Recommendation
    conditions: list[str] = []
    rationale: str = ""
    underwriter: str = "demo-underwriter"


class LetterBody(BaseModel):
    language: str = "en"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    repo = build_repository(settings)
    app.state.settings = settings
    app.state.pipeline = Pipeline(repo, settings)
    log.info("LedgerLens starting: storage=%s llm_mode=%s flash=%s pro=%s", settings.storage, settings.resolved_llm_mode, settings.model_flash, settings.model_pro)
    if settings.demo_seed_on_startup:
        try:
            ids = app.state.pipeline.seed_demo_cases()
            log.info("demo cases ready: %s", ids)
        except Exception as e:  # never block startup on demo data
            log.warning("demo seeding skipped: %s", e)
    yield


app = FastAPI(title="LedgerLens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["*"], allow_headers=["*"])


def pipe(request: Request) -> Pipeline:
    return request.app.state.pipeline


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


@app.exception_handler(PipelineError)
async def _pipeline_error(_: Request, exc: PipelineError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(BudgetExceeded)
async def _budget_error(_: Request, exc: BudgetExceeded):
    return JSONResponse(status_code=402, content={"detail": str(exc)})


@app.exception_handler(CacheMiss)
async def _cache_error(_: Request, exc: CacheMiss):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _case_or_404(p: Pipeline, case_id: str) -> Case:
    c = p.repo.get_case(case_id)
    if not c:
        raise HTTPException(404, "case not found")
    return c


def _artifact_or_404(p: Pipeline, case_id: str, name: str) -> dict:
    _case_or_404(p, case_id)
    data = p.repo.get_artifact(case_id, name)
    if not data:
        raise HTTPException(404, "not ready")
    return data


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health(s: Settings = Depends(settings_dep)):
    return {"status": "ok", "llm_mode": s.resolved_llm_mode, "storage": s.storage, "models": {"flash": s.model_flash, "pro": s.model_pro},
            "spent_usd_this_process": round(spent_usd(), 4), "budget_cap_usd": s.budget_cap_usd}


# ---------------------------------------------------------------- cases
_WORKSPACE_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def workspace_dep(x_ledgerlens_workspace: Optional[str] = Header(default=None)) -> Optional[str]:
    """Per-browser workspace id sent by the frontend; invalid values are ignored (shared space)."""
    if x_ledgerlens_workspace and _WORKSPACE_RE.match(x_ledgerlens_workspace):
        return x_ledgerlens_workspace
    return None


@app.get("/api/cases", response_model=list[Case])
def list_cases(p: Pipeline = Depends(pipe), ws: Optional[str] = Depends(workspace_dep)):
    return p.list_cases(ws)


@app.post("/api/cases", response_model=Case)
def create_case(body: CaseCreate, p: Pipeline = Depends(pipe), ws: Optional[str] = Depends(workspace_dep)):
    return p.create_case(body, workspace=ws)


@app.get("/api/cases/{case_id}", response_model=Case)
def get_case(case_id: str, p: Pipeline = Depends(pipe)):
    return _case_or_404(p, case_id)


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, p: Pipeline = Depends(pipe)):
    _case_or_404(p, case_id)
    p.repo.delete_case(case_id)
    return {"deleted": True}


# ---------------------------------------------------------------- documents
@app.post("/api/cases/{case_id}/documents", response_model=Case)
async def upload_documents(case_id: str, files: list[UploadFile] = File(...), p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    if case.status == "decided":
        raise PipelineError("Case already decided")
    for f in files:
        data = await f.read()
        p.add_document(case, f.filename or "upload", data)
    for st in case.stages:  # new evidence invalidates the pipeline
        st.status = "pending"
    p.repo.save_case(case)
    p.audit(case.id, "system", "documents_uploaded", files=[f.filename for f in files])
    return case


@app.delete("/api/cases/{case_id}/documents/{doc_id}", response_model=Case)
def delete_document(case_id: str, doc_id: str, p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    p.remove_document(case, doc_id)
    for st in case.stages:
        st.status = "pending"
    p.repo.save_case(case)
    return case


@app.get("/api/cases/{case_id}/documents/{doc_id}/file")
def document_file(case_id: str, doc_id: str, p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    d = next((d for d in case.documents if d.doc_id == doc_id), None)
    if not d:
        raise HTTPException(404, "document not found")
    data = p.repo.get_blob(d.storage_path)
    if data is None:
        raise HTTPException(404, "file missing")
    return Response(content=data, media_type=d.mime_type, headers={"Content-Disposition": f'inline; filename="{d.filename}"'})


@app.get("/api/cases/{case_id}/documents/{doc_id}/pages/{page}")
def document_page(case_id: str, doc_id: str, page: int, scale: int = Query(1, ge=1, le=2), p: Pipeline = Depends(pipe), s: Settings = Depends(settings_dep)):
    case = _case_or_404(p, case_id)
    d = next((d for d in case.documents if d.doc_id == doc_id), None)
    if not d:
        raise HTTPException(404, "document not found")
    if page < 1 or page > max(1, d.pages):
        raise HTTPException(404, "page out of range")
    key = f"cases/{case_id}/renders/{doc_id}/p{page}_s{scale}.png"
    png = p.repo.get_blob(key)
    if png is None:
        data = p.repo.get_blob(d.storage_path)
        if data is None:
            raise HTTPException(404, "file missing")
        png = render_page(data, d.mime_type, page, dpi=s.page_render_dpi * scale, max_width=1200 * scale)
        p.repo.put_blob(key, png, "image/png")
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- pipeline
@app.post("/api/cases/{case_id}/run", response_model=Case)
async def run(case_id: str, stage: str = Query("all"), p: Pipeline = Depends(pipe)):
    _case_or_404(p, case_id)
    if stage == "all":
        return await p.run_all(case_id)
    try:
        st = StageName(stage)
    except ValueError:
        raise HTTPException(400, f"unknown stage {stage}")
    return await p.run_stage(case_id, st)


# ---------------------------------------------------------------- artifacts
@app.get("/api/cases/{case_id}/intake")
def get_intake(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "intake")


@app.get("/api/cases/{case_id}/extractions")
def get_extractions(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "extractions")["items"]


@app.get("/api/cases/{case_id}/cashflow")
def get_cashflow(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "cashflow")


@app.get("/api/cases/{case_id}/memo")
def get_memo(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "memo")


@app.get("/api/cases/{case_id}/challenge")
def get_challenge(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "challenge")


@app.get("/api/cases/{case_id}/letter")
def get_letter(case_id: str, p: Pipeline = Depends(pipe)):
    return _artifact_or_404(p, case_id, "letter")


@app.get("/api/cases/{case_id}/audit")
def get_audit(case_id: str, p: Pipeline = Depends(pipe)):
    _case_or_404(p, case_id)
    return [a.model_dump(mode="json") for a in p.repo.list_audit(case_id)]


@app.get("/api/cases/{case_id}/traces")
def get_traces(case_id: str, p: Pipeline = Depends(pipe)):
    _case_or_404(p, case_id)
    return [t.model_dump(mode="json") for t in p.repo.list_traces(case_id)]


# ---------------------------------------------------------------- underwriter actions
@app.post("/api/cases/{case_id}/objections/{objection_id}/resolution", response_model=Case)
def resolve(case_id: str, objection_id: str, body: ResolutionBody, p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    return p.resolve_objection(case, objection_id, body.status, body.note, body.by)


@app.post("/api/cases/{case_id}/decision", response_model=Case)
def decide(case_id: str, body: DecisionBody, p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    return p.sign_decision(case, Decision(case_id=case.id, outcome=body.outcome, conditions=body.conditions, rationale=body.rationale, underwriter=body.underwriter))


@app.post("/api/cases/{case_id}/letter")
async def letter(case_id: str, body: LetterBody, p: Pipeline = Depends(pipe)):
    case = _case_or_404(p, case_id)
    return (await p.explain(case, body.language)).model_dump(mode="json")


# ---------------------------------------------------------------- feedback, benchmark, demo
@app.get("/api/feedback/priorities")
def priorities(p: Pipeline = Depends(pipe)):
    fp = load_priorities(p.repo)
    if fp.n_decisions == 0:
        fp = compute_priorities(p.repo)
    return fp.model_dump(mode="json")


@app.get("/api/benchmark/latest")
def benchmark_latest(p: Pipeline = Depends(pipe)):
    data = p.repo.get_global("benchmark_latest")
    if not data:
        here = Path(__file__).resolve()
        # repo checkout: <root>/backend/app/main.py; container: /app/app/main.py with results copied to /app/benchmark
        bench_file = next((d / "benchmark" / "results" / "latest.json" for d in (here.parents[2], here.parents[1])
                           if (d / "benchmark" / "results" / "latest.json").exists()), None)
        if bench_file:
            import json
            return json.loads(bench_file.read_text("utf-8"))
        raise HTTPException(404, "no benchmark run yet")
    return data


@app.post("/api/demo/seed")
def seed(force: bool = False, x_admin_token: Optional[str] = Header(default=None), p: Pipeline = Depends(pipe), s: Settings = Depends(settings_dep),
         ws: Optional[str] = Depends(workspace_dep)):
    # A workspace may (re)seed only its own demo copies; touching the shared cases still needs the admin token.
    if ws is None and s.admin_token and x_admin_token != s.admin_token:
        raise HTTPException(403, "admin token required")
    return {"cases": p.seed_demo_cases(force=force, workspace=ws)}


# ---------------------------------------------------------------- static frontend (optional)
_static = get_settings().static_dir
if _static and Path(_static).exists():
    app.mount("/assets", StaticFiles(directory=str(Path(_static) / "assets")), name="assets")

    _static_root = Path(_static).resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (_static_root / full_path).resolve()
        # "..%2f" segments must not escape the static dir (would expose source, /etc, /proc/self/environ)
        if full_path and candidate.is_relative_to(_static_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_root / "index.html")
