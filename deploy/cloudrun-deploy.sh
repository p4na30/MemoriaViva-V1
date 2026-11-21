#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# MemoriaViva RISE v3.0 — Google Cloud Run Deployment Script
# Includes Cloud Storage volume mount at /app/data + SQLite GCS FUSE shielding
# ==============================================================================

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${GCP_REGION:-us-central1}"
APP_MODE="${MV_APP_MODE:-demo}"
if [[ "${APP_MODE}" == "production" || "${APP_MODE}" == "clean" ]]; then
  APP_MODE="production"
  DEFAULT_SERVICE="memoriaviva-clean"
  DEFAULT_BUCKET="memoriaviva-clean-data-${PROJECT_ID}"
  DEFAULT_MIN_INSTANCES="0"
  DEFAULT_TG_BOT_USERNAME="Memoria_viva_bot"
  RESOLVED_TG_TOKEN="${TELEGRAM_CLEAN_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
else
  APP_MODE="demo"
  DEFAULT_SERVICE="memoriaviva-rise"
  DEFAULT_BUCKET="memoriaviva-data-${PROJECT_ID}"
  DEFAULT_MIN_INSTANCES="1"
  DEFAULT_TG_BOT_USERNAME="Memoria_Viva_Demo_bot"
  RESOLVED_TG_TOKEN="${TELEGRAM_DEMO_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
fi
SERVICE_NAME="${CLOUD_RUN_SERVICE:-${DEFAULT_SERVICE}}"
BUCKET_NAME="${GCS_DATA_BUCKET:-${DEFAULT_BUCKET}}"
MIN_INSTANCES="${CLOUD_RUN_MIN_INSTANCES:-${DEFAULT_MIN_INSTANCES}}"
RESOLVED_TG_USERNAME="${TELEGRAM_BOT_USERNAME:-${DEFAULT_TG_BOT_USERNAME}}"
RESOLVED_TG_USERNAME="${RESOLVED_TG_USERNAME#@}"
TIMEZONE="${MV_TIMEZONE:-America/Mexico_City}"

# Anti-collision guard: never deploy demo and production pointing to the same Telegram bot
if [[ "${APP_MODE}" == "demo" && "${RESOLVED_TG_USERNAME,,}" == "memoria_viva_bot" ]]; then
  echo "Error: MV_APP_MODE=demo no debe usar @Memoria_viva_bot (reservado para memoriaviva-clean). Usa @Memoria_Viva_Demo_bot."
  exit 1
fi
if [[ "${APP_MODE}" == "production" && "${RESOLVED_TG_USERNAME,,}" == "memoria_viva_demo_bot" ]]; then
  echo "Error: MV_APP_MODE=production no debe usar @Memoria_Viva_Demo_bot (reservado para memoriaviva-rise). Usa @Memoria_viva_bot."
  exit 1
fi

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: define GCP_PROJECT_ID o ejecuta 'gcloud config set project TU_PROYECTO'."
  exit 1
fi

echo "==> Proyecto: ${PROJECT_ID} | Región: ${REGION} | Modo: ${APP_MODE} | Servicio: ${SERVICE_NAME} | Bot: @${RESOLVED_TG_USERNAME} | min-instances=${MIN_INSTANCES}"
echo "==> Verificando bucket de persistencia gs://${BUCKET_NAME} ..."
gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}"

ENV_VARS="MV_DATA_DIR=/app/data,MV_CLOUD_SYNC=1,MV_APP_MODE=${APP_MODE},MV_TIMEZONE=${TIMEZONE},TZ=${TIMEZONE},TELEGRAM_BOT_USERNAME=${RESOLVED_TG_USERNAME}"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi
if [[ -n "${RESOLVED_TG_TOKEN}" ]]; then
  ENV_VARS="${ENV_VARS},TELEGRAM_BOT_TOKEN=${RESOLVED_TG_TOKEN}"
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
  --no-cpu-throttling \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances 1 \
  --session-affinity \
  --add-volume "name=mv-data,type=cloud-storage,bucket=${BUCKET_NAME}" \
  --add-volume-mount "volume=mv-data,mount-path=/app/data" \
  --set-env-vars "${ENV_VARS}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)' 2>/dev/null || true)"
echo "==> Despliegue completado: ${SERVICE_URL}"
