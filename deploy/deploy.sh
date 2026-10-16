#!/usr/bin/env bash
# Deploys LedgerLens to Cloud Run (+ optional Firebase Hosting). Budget-minded defaults: scale to zero, 1 vCPU, 1 GiB,
# request-based billing. Expected cost for the evaluation window at demo traffic: ~0 USD (inside the free tier).
#
# Prereqs: gcloud auth login; a project with billing enabled; GEMINI key in Secret Manager (see below).
#   export PROJECT_ID=your-project REGION=asia-southeast1
#   ./deploy/deploy.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"
SERVICE="${SERVICE:-ledgerlens-api}"
BUCKET="${BUCKET:-${PROJECT_ID}-ledgerlens-docs}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"   # set 1 only if you accept ~USD 10+/month for an always-warm instance
# auto = live Gemini for new uploads; demo cases replay the bundled recorded run for free. Spend is persisted in
# Firestore, and once BUDGET_CAP_USD (or the key's own billing limit) is reached the site shows a banner and keeps
# serving cached results. cache_only = replay only (new uploads return 503; only the customer letter calls Gemini).
LLM_MODE="${LLM_MODE:-auto}"
BUDGET_CAP_USD="${BUDGET_CAP_USD:-5}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"        # protects re-seeding the shared demo cases; per-browser demo copies need no token

cd "$(dirname "$0")/.."
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com generativelanguage.googleapis.com >/dev/null

# The Dockerfile sits at the repo root (it builds the frontend and the backend), so --source . finds it.
# Firestore (native mode) + bucket, idempotent
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 || gcloud firestore databases create --location="$REGION" --type=firestore-native
gsutil ls -b "gs://$BUCKET" >/dev/null 2>&1 || gsutil mb -l "$REGION" "gs://$BUCKET"

# Gemini key as a secret: echo -n "$GOOGLE_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
if ! gcloud secrets describe gemini-api-key >/dev/null 2>&1; then
  echo "Secret gemini-api-key missing. Create it with: echo -n \"\$GOOGLE_API_KEY\" | gcloud secrets create gemini-api-key --data-file=-"; exit 1
fi
# Cloud Run runs as the default compute service account; let it read the key.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')
gcloud secrets add-iam-policy-binding gemini-api-key --member "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role roles/secretmanager.secretAccessor --condition=None >/dev/null

gcloud run deploy "$SERVICE" --source . --region "$REGION" --platform managed --allow-unauthenticated --quiet \
  --cpu 1 --memory 2Gi --concurrency 8 --timeout 600 --min-instances "$MIN_INSTANCES" --max-instances 2 --cpu-boost \
  --set-env-vars "LEDGERLENS_STORAGE=gcp,LEDGERLENS_GCS_BUCKET=$BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,LEDGERLENS_LLM_MODE=$LLM_MODE,LEDGERLENS_BUDGET_CAP_USD=$BUDGET_CAP_USD,LEDGERLENS_ENV=prod${ADMIN_TOKEN:+,LEDGERLENS_ADMIN_TOKEN=$ADMIN_TOKEN}" \
  --set-secrets "GOOGLE_API_KEY=gemini-api-key:latest"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
echo "Cloud Run: $URL"
curl -fsS "$URL/api/health" && echo

# Budget alert (one-off): gcloud billing budgets create --billing-account=XXXX --display-name=ledgerlens --budget-amount=7USD --threshold-rule=percent=0.5 --threshold-rule=percent=0.9

# Firebase Hosting serves the same frontend; it calls the Cloud Run API directly (VITE_API_BASE) because Hosting
# rewrites time out after 60 s and a live extraction stage can take longer.
if command -v firebase >/dev/null 2>&1 && [ "${DEPLOY_FIREBASE:-0}" = "1" ]; then
  firebase projects:addfirebase "$PROJECT_ID" >/dev/null 2>&1 || true
  (cd frontend && npm ci && VITE_API_BASE="$URL" npm run build && firebase deploy --only hosting --project "$PROJECT_ID" --non-interactive)
fi
