# LedgerLens

**The first credit memo with a clickable source for every number and a second AI that challenges it before a human signs.**

**Live app:** https://ledgerlens-api-629502893425.asia-southeast1.run.app (no login; the three demo cases load automatically)
· **Demo video:** https://www.youtube.com/watch?v=MBwsG0QQAUM

LedgerLens is a team of loan-underwriting agents for thin-file micro and small businesses in Southeast Asia. It reads
the unstructured records these businesses already have (mobile-banking statement PDFs, Shopee seller-dashboard
screenshots, paper receipts, handwritten ledgers, shop photos) with Gemini's multimodal models, drafts a credit memo
where **every figure carries a document id, page and bounding box**, then runs an independent **Challenger agent**
that challenges the memo using deterministic tools. A human underwriter accepts or dismisses each objection and
signs the decision. That decision shapes the Challenger's priorities. AI Builder Cup 2026, BFSI track.

> Humans decide. AI shows its work.

## Demo

![LedgerLens demo](docs/media/ledgerlens_demo.gif)

Full-resolution recording: [docs/media/ledgerlens_demo.mp4](docs/media/ledgerlens_demo.mp4) (40 s, offline demo mode on the synthetic case *Linh Fashion Online*: run the pipeline, click a memo figure to jump to its source row, accept and dismiss Challenger objections, sign the decision, generate the Vietnamese customer letter, review the audit trail).

| | |
|---|---|
| ![Portfolio](docs/media/01_portfolio.png) Portfolio showing pipeline status and objection severity for each case | ![Memo](docs/media/03_memo.png) Credit memo with a source for every value |
| ![Evidence](docs/media/04_evidence_highlight.png) Click a figure: the statement page opens with the source rows highlighted | ![Objections](docs/media/05_objections.png) Challenger objections with tool evidence and accept / dismiss actions |
| ![Decision](docs/media/08_decision_form.png) Underwriter decision with conditions and a warning for unresolved critical objections | ![Letter](docs/media/09_signed_decision_letter.png) Signed decision and plain-language customer letter |

More: [objection evidence](docs/media/07_objection_evidence.png) · [audit trail](docs/media/10_audit_trail.png) · [workbench before run](docs/media/02_workbench_before_run.png) · [pitch deck (PDF)](presentation/LedgerLens_AI_Builder_Cup_Submission.pdf)

## What makes it different

| Mechanism | How it works |
|---|---|
| **Evidence linking** | Extractor agents return JSON with a schema that *requires* a `source {doc_id, page, bbox}` on every value. A deterministic Python module turns rows into a *figure catalog*; the Analyst can only cite catalog IDs (`{fig:CF.avg_monthly_business_inflow}`), and a memo that contains an unsourced number is rejected and regenerated. Clicking a number in the UI opens the page with the source highlighted. |
| **Text-layer cross-check** | Born-digital statement PDFs have a text layer. We never extract from it (layouts vary), but use it to check values at no cost: every amount the model reads must occur verbatim on the page it cited, and the bounding box must cover those words. Match rates are stored with the extraction. A mismatch becomes a Challenger objection. |
| **Challenger agent** | A separate ADK agent that never sees the Analyst's prompt. A set of deterministic checks runs first (balance continuity, perceptual-hash image reuse including past cases, period cross-checks, self-transfer / round-trip / recurring-debt detectors, entity and currency consistency, unsourced-number scan); the agent then investigates 12 fixed questions with tools and writes severity-ranked objections. Findings proven by tools always appear. |
| **Decisions become data** | Each accept/dismiss decision and the signed outcome are stored with a full audit log (every agent call includes its model and prompt version). Acceptance rates per question re-weight the Challenger on the next case. |
| **Benchmark against a single prompt** | 3 synthetic businesses with 20 planted traps (`data/synth/traps.json`). The baseline uses one "read everything and write a memo" prompt on the same documents. See `benchmark/results/REPORT.md`. |

## Architecture

```
Browser (React/Vite, served by Cloud Run) ──/api──> Cloud Run (FastAPI)
                                                   ├─ ADK agents: Intake · Extractor×5 · Analyst · Challenger(investigator→writer) · Explainer
                                                   ├─ Deterministic tools: compute_cashflow · recompute_balance_chain · image_similarity · date_crosscheck · entity checks
                                                   ├─ Firestore: cases · extractions · memos · objections · decisions · audit · traces · LLM cache
                                                   └─ Cloud Storage: original documents, page renders
Models: Gemini 3.8 Flash for every agent in budget mode (current default). Production tiering is a config switch: LEDGERLENS_MODEL_PRO=gemini-3.1-pro-preview moves Extractor (statements, ledgers), Analyst and Challenger to Pro; Intake and Explainer stay on Flash.
No separate OCR engine: PDF pages and photos are rendered to images and read by Gemini, which returns values with page coordinates.
```

Pipeline: `upload → intake → extract → cashflow (Python) → analyze → challenge → human decision → customer letter`.

## Repository layout

```
backend/        FastAPI + ADK agents (app/agents), deterministic tools (app/tools), storage (local JSON or Firestore+GCS)
frontend/       React workbench: memo viewer with clickable figures, document viewer with bbox highlights, objection cards, decision panel, audit
data/synth/     Synthetic dataset generator, 3 cases, traps.json answer key (no real data; every file watermarked SYNTHETIC)
benchmark/      run_benchmark.py (LedgerLens vs single-prompt baseline), results/
deploy/         deploy.sh for Cloud Run (+ Firebase Hosting), launch config
docs/API.md     REST contract
LEDGERLENS_PLAN.md  product plan (Korean working document)
```

## Run locally

```bash
# backend (Python 3.12). Without GOOGLE_API_KEY it replays the recorded live Gemini run from data/llm_cache (cache_only):
# real model output, no cost; new uploads and the customer letter need a key.
cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp ../.env.example ../.env          # add GOOGLE_API_KEY=... for live Gemini calls
.venv/bin/uvicorn app.main:app --port 8080 --reload

# frontend
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8080)

# regenerate synthetic data / run tests / benchmark
backend/.venv/bin/python data/synth/generate.py --seed 7 --out cases && backend/.venv/bin/python data/synth/verify.py
cd backend && .venv/bin/python -m pytest -q
backend/.venv/bin/python benchmark/run_benchmark.py
```

Open the app: the three demo cases load automatically (each browser gets its own copy; **Reset demo** restores it). Open *Linh Fashion Online* (case B), press **Run all**, then click any number in the memo.

### LLM modes
| `LEDGERLENS_LLM_MODE` | Behavior |
|---|---|
| `auto` (default) | Use live Gemini when a key is present; otherwise replay the bundled cache (`data/llm_cache`, recorded live run) if available; otherwise use mock |
| `live` | Call Gemini; responses are cached by content hash (model + prompt version + inputs) so re-runs are free and deterministic |
| `cache_only` | Never call Gemini except for the customer letter (`LEDGERLENS_LIVE_AGENTS_IN_CACHE_ONLY=explainer`, one short Flash call per signed decision, under the budget cap); any other cache miss returns 503. Use for the public demo instance |
| `mock` | Offline; answers come from the synthetic answer key |

## Cost (budget mode)

All agents default to **Gemini 3.8 Flash** (list price USD 0.75 / 3.75 per 1M input / output tokens). Measured on the
live run of 2026-10-15: a **cold run costs about USD 0.26-0.31 per case and takes about 2 minutes** end to end; the
single-prompt baseline costs about USD 0.015 (with no checks). Every response is cached by content hash, so a
**cached re-run costs USD 0**. The public demo (like a checkout without an API key) runs in `cache_only` mode: the three demo cases replay the recorded live
Gemini run (USD 0) and only the customer letter calls Gemini live (about USD 0.0015 per letter). Each browser gets its own copy of
the demo cases with a **Reset demo** button. Cloud Run scales to zero (so the first request may hit a cold start);
Firestore and Cloud Storage stay well within their free quotas. `LEDGERLENS_BUDGET_CAP_USD` (default 5) stops further
Gemini calls once the process reaches that spending limit. Setting `MIN_INSTANCES=1` to avoid cold starts
costs ~USD 10+/month and is therefore **off** by default.

## Deploy

```bash
export PROJECT_ID=your-project REGION=asia-southeast1
echo -n "$GOOGLE_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
./deploy/deploy.sh                       # Cloud Run from source (Dockerfile builds the frontend too, served at /)
DEPLOY_FIREBASE=1 ./deploy/deploy.sh     # additionally publish the frontend on Firebase Hosting with /api rewritten to Cloud Run
LLM_MODE=cache_only ./deploy/deploy.sh   # public demo that only replays cached runs (no Gemini spend)
# fill the deployed cache once from a local live run (Firestore + GCS, uses your gcloud ADC):
LEDGERLENS_STORAGE=gcp GOOGLE_CLOUD_PROJECT=$PROJECT_ID LEDGERLENS_GCS_BUCKET=$PROJECT_ID-ledgerlens-docs \
  backend/.venv/bin/python backend/scripts/upload_llm_cache.py data/runtime_live/cache
```

## Public demo: getting started, limits and cold starts

- **Try it without an account:** open the link; the three demo cases are already in the portfolio. Open *Reyes Auto
  Repair* and press **Run all remaining**. Each browser gets its own copy (**Reset demo** restores them).
- **Your own documents:** **New case** uploads PDFs or photos and runs live Gemini. Upload generated or anonymized
  documents only. Cases are shared read-only with other visitors once analyzed (uncheck the box to keep one private).
- **AI budget:** live Gemini spend is capped (`LEDGERLENS_BUDGET_CAP_USD`, persisted in Firestore across instances).
  When the cap or the key's billing limit is reached, a banner says live analysis is paused, and every case analyzed so
  far, including other visitors' runs, can still be opened. Demo cases and re-runs of the same documents replay the
  recorded Gemini responses and cost nothing.
- **Cold start (Cloud Run scales to zero):** startup only loads the app (demo seeding moved to the
  browser's first visit); documents are stored by content hash and page renders are shared, so after the first visitor
  a demo copy loads in about 2 s and replays the full pipeline in about 5 s. A live case takes about 2 minutes;
  the request timeout is 600 s. (An optional Firebase Hosting mirror would call Cloud Run directly, because Hosting
  rewrites stop at 60 s.)
- **Agents:** the five agents are Google ADK `LlmAgent`s (the Challenger is a `SequentialAgent` with tools), deployed
  on Cloud Run, calling Gemini 3.8 Flash.

## Synthetic data and limits

No real customer data is used anywhere. The three businesses, their statements, dashboards, receipts, ledgers and
premises images are generated by `data/synth/generate.py`; every page carries a visible "SYNTHETIC · FOR DEMO" watermark.
The 20 traps come from real underwriting checklists (double counting, round-tripping, document reuse, period and balance
inconsistencies, hidden debt). LedgerLens does not produce a credit score and does not price loans; it organizes evidence
for a human decision.

## Benchmark

Live Gemini runs on `gemini-3.8-flash` (2026-10-15, re-run of the analyst, Challenger and baseline on 2026-10-16):
3 synthetic businesses, 43 documents, 20 planted traps (`data/synth/traps.json`). The baseline is one "read everything
and write a memo" prompt on the same documents and model. Scoring is strict: an objection counts for a trap only if it
includes the trap's identifying amount or document, and each objection counts for at most one trap.

| Metric | LedgerLens | Single-prompt baseline |
|---|---|---|
| Trap recall | **18/20** (95% Wilson CI 0.70-0.97) | 3/20 |
| Unsourced numbers in the memo | **0** | 62 |
| Objections on the clean case A | 0 | - |
| Statement rows extracted | 481/481 (100%)* | - |
| Evidence-link (bbox) accuracy | 100%* | - |
| Cold run per case | about 2 min, USD 0.26-0.31 | about USD 0.015 |
| Cached re-run | USD 0 | - |

\* On clean, born-digital synthetic PDFs; accuracy will be lower on real scans.

Recommendations: case C returned `request_more_documents` (matches expected); case A returned `approve_with_conditions`
(expected `approve`); case B returned `request_more_documents` (expected `approve_with_conditions`). Missed traps: dashboard
gross vs payout (T02) and COD revenue vs cash deposits (T03).

With n = 3 synthetic businesses, the results are indicative, not a validation. A checkout without an API key and the public demo replay
this recorded live Gemini run; only the customer letter calls Gemini live. Details: `benchmark/results/REPORT.md` (a
`cache_only` replay, so it reports time and cost of ~0), `benchmark/results/LIVE_RUN_2026-10-15.md` and
`benchmark/results/LIVE_RUN_2026-10-16.md` (console output of the live runs).

## License

The code in this repository is licensed under MIT. Synthetic data is free to reuse with attribution.
