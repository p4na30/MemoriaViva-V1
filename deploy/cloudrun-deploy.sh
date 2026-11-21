#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# MemoriaViva RISE v3.0 — Google Cloud Run Deployment Script
# Includes Cloud Storage volume mount at /app/data + SQLite GCS FUSE shielding
# ==============================================================================

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-memoriaviva-rise}"
BUCKET_NAME="${GCS_DATA_BUCKET:-memoriaviva-data-${PROJECT_ID}}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: define GCP_PROJECT_ID o ejecuta 'gcloud config set project TU_PROYECTO'."
  exit 1
fi

echo "==> Proyecto: ${PROJECT_ID} | Región: ${REGION} | Servicio: ${SERVICE_NAME}"
echo "==> Verificando bucket de persistencia gs://${BUCKET_NAME} ..."
gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}"

ENV_VARS="MV_DATA_DIR=/app/data,MV_CLOUD_SYNC=1"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  ENV_VARS="${ENV_VARS},TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}"
fi
if [[ -n "${TELEGRAM_BOT_USERNAME:-}" ]]; then
  ENV_VARS="${ENV_VARS},TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME}"
fi
if [[ -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  ENV_VARS="${ENV_VARS},TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}"
fi

echo "==> Desplegando contenedor multi-stage en Google Cloud Run ..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 1 \
  --session-affinity \
  --add-volume "name=mv-data,type=cloud-storage,bucket=${BUCKET_NAME}" \
  --add-volume-mount "volume=mv-data,mount-path=/app/data" \
  --set-env-vars "${ENV_VARS}"

echo "==> Despliegue completado."
