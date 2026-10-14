# LedgerLens REST API (contract for the frontend)

Base URL: same origin in production (`/api/...`, Firebase Hosting rewrites `/api/**` to Cloud Run, and the
FastAPI app also serves the built frontend). In local dev the Vite dev server proxies `/api` to `http://localhost:8080`.
All JSON. Schemas live in `backend/app/schemas.py` (Pydantic) — field names below are exactly those.

## Health
`GET /api/health` → `{status:"ok", llm_mode:"live"|"cache_only"|"mock", storage:"local"|"gcp", models:{flash, pro}}`

## Cases
- `GET /api/cases` → `Case[]` (newest first)
- `POST /api/cases` body `CaseCreate {name, business_name, sector, country, language, currency, requested_amount?}` → `Case`
- `GET /api/cases/{case_id}` → `Case`
- `DELETE /api/cases/{case_id}` → `{deleted:true}`

`Case` (abridged): `{id, name, business_name, sector, country, language, currency, requested_amount, status,
created_at, updated_at, documents: DocumentMeta[], stages: StageStatus[], stats: CaseStats,
decision: Decision|null, objection_resolutions: ObjectionResolution[], is_demo, demo_expected_outcome, tags[]}`

`status` ∈ `draft | documents_uploaded | processing | memo_ready | challenged | decided | failed`

`StageStatus {name: intake|extract|cashflow|analyze|challenge, status: pending|running|done|failed, started_at, finished_at, error, cached}`

`CaseStats {total_cost_usd, total_tokens, processing_seconds, n_llm_calls, n_cached_calls, n_figures, n_unsourced, n_objections}`

`DocumentMeta {doc_id, filename, mime_type, size_bytes, pages, sha256, storage_path, uploaded_at, page_hashes[], doc_type|null, language|null, quality_flags[]}`

## Documents
- `POST /api/cases/{case_id}/documents` multipart, field name `files` (repeatable). Accepts PDF/JPG/PNG/WEBP. → `Case`
- `DELETE /api/cases/{case_id}/documents/{doc_id}` → `Case`
- `GET /api/cases/{case_id}/documents/{doc_id}/file` → original bytes (Content-Type set)
- `GET /api/cases/{case_id}/documents/{doc_id}/pages/{page}` → PNG render of that page (1-based). Images are page 1.
  Query `?scale=1|2` (default 1 ≈ 1200px wide max). The frontend draws bbox overlays on this image using
  normalized coords: left = xmin/1000*width, top = ymin/1000*height, etc.

## Pipeline
- `POST /api/cases/{case_id}/run?stage=intake|extract|cashflow|analyze|challenge|all` → `Case` (synchronous; a
  stage takes 5–90 s; `all` can take up to 3 min). Stages must run in order; the server runs missing
  prerequisites automatically. Errors are returned as `409` with `{detail}` when prerequisites cannot be met.
- Progress: poll `GET /api/cases/{case_id}` every ~2 s while a stage is `running` (the UI calls the stages one by
  one so it always knows the current one).

## Artifacts
- `GET /api/cases/{case_id}/intake` → `IntakeResult`
- `GET /api/cases/{case_id}/extractions` → `DocumentExtraction[]` (one per document)
- `GET /api/cases/{case_id}/cashflow` → `CashflowSummary`
- `GET /api/cases/{case_id}/memo` → `Memo`
- `GET /api/cases/{case_id}/challenge` → `ChallengeResult`
- `GET /api/cases/{case_id}/letter` → `CustomerLetter` (404 if not generated)
- `GET /api/cases/{case_id}/audit` → `AuditEntry[]`
- `GET /api/cases/{case_id}/traces` → `AgentTrace[]` (one per LLM call: agent, model, prompt_version, tokens, cost_usd, cached)
Each returns 404 `{detail:"not ready"}` until its stage has run.

### Memo shape (the heart of the UI)
```
Memo {
  case_id, version, created_at, model, prompt_version, baseline,
  draft: {
    headline,
    sections: [{heading, paragraphs: string[], figure_ids: string[]}],
    key_figure_ids: string[], strengths: string[], concerns: string[],
    recommendation: approve|approve_with_conditions|hold|reject|request_more_documents,
    conditions: string[], rationale
  },
  figures: Figure[],            // the ONLY numbers allowed in the memo
  unresolved_figure_ids: string[],
  unsourced_numerals: [{section, text, context}]   // should be empty; show as red badge if not
}
Figure { id, label, value, unit: currency|count|ratio|percent|months|days|score, currency,
         source_refs: SourceRef[], computation, derived_from: string[], origin: document|computed }
SourceRef { doc_id, page, bbox: {ymin,xmin,ymax,xmax} | null, snippet }
```
Paragraph text contains tokens like `{fig:CF.avg_monthly_inflow}` or `{fig:F012}`. The UI replaces each token
with a clickable chip showing the formatted value; clicking a chip opens the first `source_ref` in the document
viewer (page render + bbox highlight) and lists all refs. A `computed` figure shows its `computation` and lets
the user drill into `derived_from` figures.

### Challenge shape
```
ChallengeResult { case_id, version, created_at, model, prompt_version, baseline,
  objections: Objection[], questions_checked: string[], investigation_notes, overall_assessment,
  tool_findings: ToolFindings }
Objection { id, question_id ("Q1".."Q12"|"CUSTOM"), severity: critical|high|medium|low, title, claim,
            evidence_refs: SourceRef[], figure_ids: string[], tool_evidence, suggested_action, financial_impact }
```
Fixed checklist titles (for display): Q1 Double counting across sources · Q2 Seasonality vs one-off inflows ·
Q3 Self-transfers · Q4 Duplicate receipt/image reuse · Q5 Dashboard period vs statement period ·
Q6 Balance continuity · Q7 Undisclosed debt service · Q8 Premises vs claimed scale · Q9 Every number sourced ·
Q10 End-of-month concentration · Q11 Entity name/address consistency · Q12 Language/currency vs location.

## Underwriter actions
- `POST /api/cases/{case_id}/objections/{objection_id}/resolution` body `{status: accepted|dismissed|open, note?, by?}` → `Case`
- `POST /api/cases/{case_id}/decision` body `{outcome, conditions: string[], rationale, underwriter}` → `Case`
  (sets `case.status = decided`, writes audit, updates feedback priorities)
- `POST /api/cases/{case_id}/letter` body `{language: "id"|"vi"|"tl"|"en"|...}` → `CustomerLetter {language, subject, body, next_steps[]}`

## Feedback loop & misc
- `GET /api/feedback/priorities` → `FeedbackPriorities {computed_at, n_decisions, priorities: [{question_id, raised, accepted, dismissed, acceptance_rate, weight}]}`
- `GET /api/benchmark/latest` → benchmark JSON (`{generated_at, cases:[...], summary:{trap_recall, baseline_trap_recall, false_positive_rate, unsourced_numbers, avg_seconds, avg_cost_usd}}`) or 404
- `POST /api/demo/seed` → `{cases: string[]}` (re)loads the three synthetic demo cases. Idempotent.

## Errors
Standard FastAPI `{detail: string}` with 400/404/409/500.
