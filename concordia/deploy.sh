#!/bin/bash
# ── CONCORDIA Cloud Run Deployment ───────────────────────────────
set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="${REGION:-us-central1}"
SERVICE="concordia"

if [ -z "$PROJECT_ID" ]; then
  echo "ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT"
  exit 1
fi

echo ""
echo "  CONCORDIA — Cloud Run Deployment"
echo "  ================================="
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Service:  $SERVICE"
echo ""

# Build and push
echo "  Building container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE ./concordia

# Deploy with WebSocket support
echo ""
echo "  Deploying to Cloud Run..."
gcloud run deploy $SERVICE \
  --image gcr.io/$PROJECT_ID/$SERVICE \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --timeout 3600 \
  --session-affinity \
  --min-instances 1 \
  --set-env-vars "CONCORDIA_MODEL=gemini-2.0-flash"

URL=$(gcloud run services describe $SERVICE --region $REGION --format 'value(status.url)' 2>/dev/null)
echo ""
echo "  Deployed to: $URL"
echo ""
echo "  NOTE: Set your API key at runtime via the UI, or redeploy with:"
echo "  gcloud run services update $SERVICE --region $REGION --set-env-vars GOOGLE_API_KEY=your_key"
echo ""
