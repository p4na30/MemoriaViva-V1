# Guía Paso a Paso: Despliegue en GCP Cloud Run y Compilación de APK Android

Esta guía explica cómo desplegar el servidor unificado de **MemoriaViva RISE v3.0** (FastAPI + React + SQLite blindado + 10 postales semilla) en **Google Cloud Platform (Cloud Run + Cloud Storage)** y cómo compilar el **APK Android (.apk)** mediante **GitHub Actions** sin instalar Java ni Android SDK en tu computadora.

---

## Arquitectura del Flujo Nube + APK

```text
[ Tablet / Celular Android (.apk) ]
   ├── UI React/Tailwind empaquetada dentro del APK (Capacitor 6)
   ├── Permisos inyectados: RECORD_AUDIO, WAKE_LOCK, WebView getUserMedia
   └── Apunta vía HTTPS (VITE_API_URL) ──────────┐
                                                 ▼
[ Google Cloud Run (memoriaviva-rise) ]   https://memoriaviva-rise-xxxx-uc.a.run.app
   ├── Contenedor Docker multi-stage (FastAPI + frontend/dist en puerto $PORT)
   ├── Zero-Raw-Cloud Audio (ffmpeg en RAM + SciPy RMS + MATTR + TF-IDF)
   ├── Gemini 2.5 Flash + Edge-TTS (-15%, -5Hz) + Telegram Deep-Link
   └── Persistencia blindada (MV_CLOUD_SYNC=1): /tmp/memoriaviva.db ⇄ /app/data (GCS Bucket)
```

---

## 0. Prerrequisitos (5 minutos)

1. **Cuenta de Google Cloud Platform (GCP)** con un proyecto creado y facturación habilitada (puedes usar créditos de hackathon o la capa gratuita de Cloud Run).
2. **Repositorio en GitHub:** tu repo local ya está conectado a `https://github.com/p4na30/MemoriaViva-V1.git`.
3. **Llaves de servicios (opcionales pero recomendadas para el demo en vivo):**
   - `GEMINI_API_KEY`: obtenla en [Google AI Studio](https://aistudio.google.com/apikey). *(Si no la pones, el sistema usa su respaldo gerontológico determinista local).*
   - `TELEGRAM_BOT_TOKEN` y `TELEGRAM_BOT_USERNAME`: **solo el equipo técnico** crea un único bot centralizado en `@BotFather` (`/newbot`) para que los usuarios finales jamás toquen `@BotFather` (*Zero-API-Key UX* con Deep-Link `/start MV-XXXX`).

> **Tip sin instalar nada local:** Si no tienes `gcloud` instalado en tu PC, puedes ejecutar toda la **Parte 1** directamente desde **Google Cloud Shell** (el ícono de terminal `>_` en la esquina superior derecha de [console.cloud.google.com](https://console.cloud.google.com)), que ya trae `gcloud` y `git` listos.

---

## Parte 1: Configurar y Desplegar el Backend en Google Cloud Platform (GCP)

### Paso 1.1 — Subir el proyecto a GitHub (si aún no lo haces)

Desde tu máquina local en `/home/d13go/MemoriaViva-V1`:

```bash
git push -u origin main
```

*(Si usarás Google Cloud Shell en el navegador, luego podrás clonar tu repo ahí con `git clone https://github.com/p4na30/MemoriaViva-V1.git && cd MemoriaViva-V1`.)*

---

### Paso 1.2 — Seleccionar Proyecto y Habilitar APIs en GCP

En **Google Cloud Shell** (o en tu terminal local si tienes `gcloud CLI` instalado):

```bash
# 1. Inicia sesión (solo si estás en tu PC local; en Cloud Shell ya estás autenticado)
gcloud auth login

# 2. Define tu ID de proyecto de GCP (cámbialo por el tuyo)
export GCP_PROJECT_ID="tu-proyecto-gcp"
export GCP_REGION="us-central1"
export GCS_DATA_BUCKET="memoriaviva-data-${GCP_PROJECT_ID}"

gcloud config set project "${GCP_PROJECT_ID}"

# 3. Habilita las APIs necesarias (Cloud Run, Cloud Build, Artifact Registry, Cloud Storage)
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com
```

---

### Paso 1.3 — Crear el Bucket de Persistencia y Dar Permisos IAM a Cloud Run

MemoriaViva monta un bucket de **Cloud Storage** en `/app/data` para conservar la base SQLite (`memoriaviva.db`), el perfil aprendido (*RAG-Lite*) y las fotos subidas.

```bash
# 1. Crear el bucket en la misma región que Cloud Run
gcloud storage buckets create "gs://${GCS_DATA_BUCKET}" \
  --location="${GCP_REGION}" \
  --uniform-bucket-level-access

# 2. Obtener el número de proyecto y la cuenta de servicio por defecto de Cloud Run
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# 3. Otorgar permisos de lectura/escritura sobre el bucket a Cloud Run (PASO CRÍTICO)
gcloud storage buckets add-iam-policy-binding "gs://${GCS_DATA_BUCKET}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"
```

> **¿Por qué SQLite no falla sobre Cloud Storage (GCS FUSE) en este proyecto?**
> El proyecto ya incluye dos protecciones automáticas:
> 1. `MV_CLOUD_SYNC=1` (activado automáticamente en Cloud Run): SQLite trabaja sobre disco local rápido (`/tmp/memoriaviva.db` con `PRAGMA journal_mode=DELETE`) y sincroniza atómicamente cada escritura hacia `/app/data/memoriaviva.db`, evitando bloqueos POSIX de GCS FUSE.
> 2. El `Dockerfile` guarda copia inmutable de los archivos semilla y las 10 postales en `/app/seed_data/`, de modo que montar un bucket vacío en `/app/data` jamás oculta los datos iniciales.

---

### Paso 1.4 — Desplegar en Cloud Run (1 comando)

Desde la raíz del repositorio `MemoriaViva-V1`:

```bash
# Opcional: exporta tus llaves reales antes de desplegar
export GEMINI_API_KEY="AIzaSy..."
export TELEGRAM_BOT_TOKEN="123456789:AAH..."
export TELEGRAM_BOT_USERNAME="TuBotSinArroba"

# Ejecuta el script oficial de despliegue incluido en el repositorio
./deploy/cloudrun-deploy.sh
```

*(Alternativa manual equivalente sin el script):*

```bash
gcloud run deploy memoriaviva-rise \
  --source . \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 1 \
  --session-affinity \
  --add-volume "name=mv-data,type=cloud-storage,bucket=${GCS_DATA_BUCKET}" \
  --add-volume-mount "volume=mv-data,mount-path=/app/data" \
  --set-env-vars "MV_DATA_DIR=/app/data,MV_CLOUD_SYNC=1,GEMINI_API_KEY=${GEMINI_API_KEY:-},TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-},TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME:-}"
```

Al terminar (~3–5 minutos la primera vez porque Cloud Build compila el `Dockerfile` multi-stage), `gcloud` imprimirá tu URL pública HTTPS, por ejemplo:

```text
Service URL: https://memoriaviva-rise-xxxxxxxxxx-uc.a.run.app
```

**Guarda exactamente esa URL (sin `/` al final).**

---

### Paso 1.5 — Verificar la Instancia en GCP antes de Compilar el APK

Abre en tu navegador o prueba con `curl`:

```bash
curl https://memoriaviva-rise-xxxxxxxxxx-uc.a.run.app/api/health
```

Debe responder:
```json
{
  "status": "ok",
  "service": "MemoriaViva RISE v3.0",
  "cloud_run_shield": true,
  "gemini_configured": true,
  "telegram_configured": true
}
```

Abre también `https://memoriaviva-rise-xxxxxxxxxx-uc.a.run.app` en tu navegador y confirma que carga la pantalla de **Onboarding** de MemoriaViva RISE.

*(Opcional para Telegram en tiempo real sin pulsar "Detectar vinculación")*: Puedes registrar el webhook apuntando a tu Cloud Run:
```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://memoriaviva-rise-xxxxxxxxxx-uc.a.run.app/api/telegram/webhook"
```
*(Si prefieres el botón "Detectar vinculación" vía `getUpdates`, **no** ejecutes `setWebhook`, ya que Telegram desactiva `getUpdates` cuando hay un webhook activo).*

---

## Parte 2: Compilar el APK Android en GitHub Actions (Opción Recomendada)

Ahora que tu backend ya vive en HTTPS en Google Cloud Run, generaremos el `.apk` apuntando a esa URL.

### Paso 2.1 — Configurar la Variable `APP_SERVER_URL` en GitHub

1. Entra a tu repositorio en GitHub: `https://github.com/p4na30/MemoriaViva-V1`.
2. Ve a **Settings** → menú izquierdo **Secrets and variables** → **Actions**.
3. Haz clic en la pestaña **Variables** (no *Secrets*, porque es la URL pública de Cloud Run).
4. Haz clic en **New repository variable**:
   - **Name:** `APP_SERVER_URL`
   - **Value:** `https://memoriaviva-rise-xxxxxxxxxx-uc.a.run.app` *(exactamente tu Service URL de Cloud Run, **sin barra `/` al final**)*.
5. Haz clic en **Add variable**.

---

### Paso 2.2 — Disparar la Compilación del APK (`app-debug.apk`)

El workflow [.github/workflows/build-apk.yml](../.github/workflows/build-apk.yml) corre automáticamente en cada `push` a `main` o manualmente cuando quieras:

1. En GitHub ve a la pestaña **Actions**.
2. En el menú izquierdo selecciona **Build MemoriaViva RISE Android APK**.
3. Haz clic en el botón **Run workflow** (arriba a la derecha):
   - Branch: `main`
   - `server_url` *(opcional)*: puedes dejarlo vacío (tomará automáticamente `APP_SERVER_URL`) o pegar ahí directamente tu URL de Cloud Run para sobreescribirla en esa compilación.
4. Haz clic en **Run workflow** y espera ~2–3 minutos a que los pasos queden en verde:
   - Compila React (`npm ci && npm run build`) con `VITE_API_URL` apuntando a tu Cloud Run.
   - Agrega Capacitor 6 Android (`npx cap add android`).
   - Ejecuta `node scripts/configure-android.mjs` (inyecta permisos de micrófono, `WAKE_LOCK`, `FLAG_KEEP_SCREEN_ON` y `WebChromeClient.onPermissionRequest`).
   - Compila `app-debug.apk` con Gradle (`./gradlew assembleDebug`).
5. Entra al run completado, baja a la sección **Artifacts** y descarga **`memoriaviva-rise-debug-apk`**.
6. Descomprime el `.zip`: dentro está **`app-debug.apk`**, listo para instalar en cualquier celular o tablet Android.

---

### Paso 2.3 — (Opcional) Compilar APK Release Firmado en GitHub Releases

Si al final del hackathon deseas publicar un `app-release.apk` firmado profesionalmente:

1. Genera un keystore una sola vez (en cualquier máquina con `keytool` / JDK):
   ```bash
   keytool -genkey -v -keystore memoriaviva-release.keystore \
     -alias memoriaviva -keyalg RSA -keysize 2048 -validity 10000
   base64 -w 0 memoriaviva-release.keystore
   ```
2. En GitHub → **Settings → Secrets and variables → Actions → Secrets**, crea estos 4 secretos:
   - `ANDROID_KEYSTORE_BASE64`: salida en una sola línea de `base64`
   - `ANDROID_KEYSTORE_PASSWORD`: contraseña del keystore
   - `ANDROID_KEY_ALIAS`: `memoriaviva`
   - `ANDROID_KEY_PASSWORD`: contraseña de la llave
3. Publica un tag de versión:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   GitHub Actions compilará y creará automáticamente un **GitHub Release `v1.0.0`** con el APK listo para descargar por los jueces.

---

## Parte 3: Instalación y Verificación en Android (Pre-Pitch)

1. Transfiere `app-debug.apk` a tu tablet o teléfono Android (por cable USB, Google Drive o Telegram).
2. Al abrirlo, Android te pedirá habilitar **Instalar aplicaciones de orígenes desconocidos** para tu explorador de archivos → actívalo e instala **MemoriaViva RISE**.
3. Al abrir la app por primera vez:
   - Concede el permiso de **Micrófono** cuando lo solicite Android.
   - Pulsa **"Activación Rápida Demo (1 Clic)"** → entrarás al **Modo Kiosco** de Don Manuel con pantalla siempre encendida y las 10 postales cargando desde tu servidor Cloud Run.
   - Prueba hablar con **Toque simple (3.8s)** (el backend usará `ffmpeg` en RAM + Gemini STT fallback automáticamente si Android WebView no expone Web Speech).
   - Prueba **"Platicar sobre esta foto"** y los botones discretos **Demo (1, 2, 3)** en la esquina inferior izquierda.
   - Toca el candado superior derecho, ingresa PIN **`1234`**, verifica la gráfica de 21 días y guarda una nota **Human-in-the-Loop** en **Gobernanza RISE & IA**.

---

## Solución Rápida de Problemas (Troubleshooting)

| Síntoma | Causa Probable | Solución |
| :--- | :--- | :--- |
| Cloud Run falla al iniciar con error de volumen `/app/data` | Falta permiso IAM en el bucket de Cloud Storage | Repite el comando `gcloud storage buckets add-iam-policy-binding ... --role="roles/storage.objectAdmin"` del **Paso 1.3**. |
| El APK muestra *"Error de conexión con el servidor"* | `APP_SERVER_URL` estaba vacío, llevaba `/` al final o no usaba `https://` | Verifica la variable `APP_SERVER_URL` en GitHub Settings → Variables y vuelve a correr **Run workflow** en Actions. |
| El micrófono no graba dentro del APK | Permiso denegado en la primera apertura | En Android ve a **Ajustes → Aplicaciones → MemoriaViva RISE → Permisos → Micrófono → Permitir**. |
| Quiero actualizar cambios de código en la nube | Hiciste commits nuevos en `backend/` o `frontend/` | Vuelve a ejecutar `./deploy/cloudrun-deploy.sh` para actualizar Cloud Run; si cambiaste el frontend, haz `git push` para que GitHub Actions genere un nuevo APK. |
| Quiero limpiar todo antes del pitch de 5 min | Quedaron datos de ensayos en Cloud Run | Entra al Panel Familiar (PIN `1234`) → pestaña **Simulador Demo** → pulsa **"Reiniciar Demo (Estado Limpio)"**. |
