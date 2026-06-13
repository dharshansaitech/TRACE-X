#!/bin/bash
# infra/scripts/setup-gcp.sh
# One-shot GCP project setup for TRACE-X
# Usage: ./setup-gcp.sh <PROJECT_ID> [REGION]
set -euo pipefail

PROJECT_ID="${1:-tracex-hackathon}"
REGION="${2:-us-central1}"
SA_NAME="tracex-backend"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TRACE-X GCP Setup"
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Set project ───────────────────────────────────────────────────────────────
gcloud config set project "${PROJECT_ID}"
gcloud config set compute/region "${REGION}"

# ── Enable APIs ───────────────────────────────────────────────────────────────
echo "▸ Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "✓ APIs enabled"

# ── Create Firestore database ─────────────────────────────────────────────────
echo "▸ Creating Firestore database..."
gcloud firestore databases create \
  --location=us-central \
  --project="${PROJECT_ID}" 2>/dev/null || echo "  (already exists)"

echo "✓ Firestore ready"

# ── Create BigQuery dataset ───────────────────────────────────────────────────
echo "▸ Creating BigQuery dataset..."
bq --location="${REGION}" mk \
  --dataset \
  --description="TRACE-X analytics" \
  "${PROJECT_ID}:tracex_analytics" 2>/dev/null || echo "  (already exists)"

echo "✓ BigQuery ready"

# ── Create Pub/Sub topics ─────────────────────────────────────────────────────
echo "▸ Creating Pub/Sub topics..."
for TOPIC in tracex-traces tracex-events tracex-repairs; do
  gcloud pubsub topics create "${TOPIC}" --project="${PROJECT_ID}" 2>/dev/null || echo "  ${TOPIC} already exists"
done

for PAIR in "tracex-traces-sub:tracex-traces" "tracex-events-sub:tracex-events"; do
  SUB="${PAIR%%:*}"
  TOPIC="${PAIR##*:}"
  gcloud pubsub subscriptions create "${SUB}" \
    --topic="${TOPIC}" \
    --ack-deadline=60 \
    --project="${PROJECT_ID}" 2>/dev/null || echo "  ${SUB} already exists"
done

echo "✓ Pub/Sub ready"

# ── Create Artifact Registry ──────────────────────────────────────────────────
echo "▸ Creating Artifact Registry..."
gcloud artifacts repositories create tracex \
  --repository-format=docker \
  --location="${REGION}" \
  --description="TRACE-X Docker images" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "  (already exists)"

echo "✓ Artifact Registry ready"

# ── Create Service Account ────────────────────────────────────────────────────
echo "▸ Creating service account..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="TRACE-X Backend" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "  (already exists)"

ROLES=(
  "roles/datastore.user"
  "roles/bigquery.dataEditor"
  "roles/pubsub.publisher"
  "roles/pubsub.subscriber"
  "roles/aiplatform.user"
  "roles/secretmanager.secretAccessor"
)

for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet 2>/dev/null || true
done

echo "✓ Service account ready: ${SA_EMAIL}"

# ── Create API key secret ─────────────────────────────────────────────────────
echo "▸ Creating API key secret..."
API_KEY="tracex-$(openssl rand -hex 16)"
echo -n "${API_KEY}" | gcloud secrets create tracex-api-key \
  --data-file=- \
  --project="${PROJECT_ID}" 2>/dev/null || \
  echo -n "${API_KEY}" | gcloud secrets versions add tracex-api-key \
    --data-file=- \
    --project="${PROJECT_ID}"

echo "✓ Secret created"

# ── Configure Docker auth ─────────────────────────────────────────────────────
echo "▸ Configuring Docker auth..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ TRACE-X GCP Setup Complete!"
echo ""
echo "  Next steps:"
echo "  1. Deploy with: gcloud builds submit --config=cloudbuild.yaml"
echo "  2. Or locally:  docker-compose up"
echo ""
echo "  Generated API key: ${API_KEY}"
echo "  (Store this securely!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
