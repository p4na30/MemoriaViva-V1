# MemoriaViva RISE v3.0

**Plataforma Conversacional de Terapia de Reminiscencia y Detección Temprana No Invasiva de Deterioro Cognitivo Leve para Adultos Mayores**  
*Notre Dame's 2026 Global R.I.S.E. AI Hackathon — University of Notre Dame (DAC Initiative & Hesburgh Libraries), Universidad de Colima, Universidad de Guadalajara*

---

## 1. El Problema Complejo (*Wicked Problem*)

En América Latina, la mayoría de los casos de Deterioro Cognitivo Leve (DCL/MCI) se detectan en etapas avanzadas debido a tres barreras entrelazadas:
1. **La Paradoja de la Evaluación Clínica:** pruebas como MoCA o MMSE en consultorio provocan estrés agudo (*síndrome de bata blanca*) y presentan sesgos educativos y culturales.
2. **Brecha de Alfabetización Digital y Barreras Geriátricas:** adultos mayores con artritis, temblor o presbiacusia quedan excluidos de interfaces complejas o asistentes que los interrumpen tras 1 segundo de silencio.
3. **Aislamiento y Carga del Cuidador:** la familia trabajadora sufre incertidumbre sobre la evolución diaria de sus padres mientras teme por la privacidad de grabaciones en la nube.

**MemoriaViva RISE** transforma una tablet Android o navegador web en un **marco digital de fotografías familiares** que conversa con calidez mediante **Terapia de Reminiscencia** y **Terapia de Validación de Naomi Feil**, mientras analiza pasivamente biomarcadores locales del habla espontánea y fortalece el vínculo con la familia.

---

## 2. Alineación con las 5 Rúbricas Oficiales de Notre Dame (20% c/u)

| Rúbrica (20% c/u) | Implementación Verificable en MemoriaViva RISE v3.0 |
| :--- | :--- |
| **1. Usability (UXD)** | **Zero-API-Key UX**, vinculación Telegram en 5s vía QR (`/start MV-XXXX`), botón **1-clic "Activación Rápida Demo (Don Manuel)"**, **Modo Dual de Voz Inclusivo** (*Toque simple Auto-VAD 3.8s* + *Mantener presionado `ESPACIO`/táctil*) y estética **Clínico Moderno (Día/Noche)** sin emojis crudos (`lucide-react` + `Inter` con `tabular-nums`). |
| **2. R.I.S.E. Framework** | **Responsible:** carácter no diagnóstico + control **Human-in-the-Loop** con variables de confusión (*Mal sueño*, *Medicación*, *Fatiga*, *Sundowning*). **Inclusive:** voz geriátrica (`-15%`, `-5Hz`) + Z-Score personal libre de sesgo educativo. **Safe:** **Zero-Raw-Cloud Audio** (0 bytes persistidos) + protocolo de crisis de Naomi Feil + *Consentimiento Dual Asistido*. **Empowering:** puente familiar en la cena y soberanía local de datos. |
| **3. Technical Merit** | **FastAPI + SQLite blindado** (compatible con GCP Cloud Run/GCS FUSE) + JSON RAG-Lite + React 18/TypeScript/Tailwind/Recharts + Docker multi-stage + Capacitor 6 APK. Cada turno, foto, nota *Human-in-the-Loop* y simulación persiste en SQLite, recalcula Z-Scores en vivo y regenera el PDF clínico. |
| **4. Innovation** | **Evaluación Neuropsicológica Invisible** con **Anclaje Visual Multimodal Bidireccional (`Voz ↔ Foto`)** sobre 10 postales nostálgicas etiquetadas, **Aura de Respiración Emocional** (4s) y aprendizaje biográfico continuo (*Biographical RAG-Lite*). |
| **5. Execution** | Flujo extremo a extremo probado con 11 pruebas automatizadas (`pytest`), build estricto de TypeScript/Vite, **Modo Fail-Safe** (3 actos precalibrados accesibles en Kiosco con teclas `1`/`2`/`3` y en el *Simulador Demo*) y botón **Reiniciar Demo** para ensayos del pitch. |

---

## 3. Declaración de Herramientas IA (*Identify Your Tools*)

Cumpliendo los principios oficiales **Use of AI** de Notre Dame (también visible dentro de la pestaña **Gobernanza RISE & IA** y en cada PDF generado):

- **Google Gemini (`gemini-3.5-flash-lite` → `gemini-3.8-flash` → `gemini-3.7-flash` → respaldo local, `thinking_budget=0`):** cadena automática con *circuit-breaker* anti-404 y salto inmediato en `503` para latencia `< 1.5s`, generación conversacional empática ($\le 35$ palabras), extracción biográfica estructurada (JSON) y transcripción multimodal en RAM como respaldo cuando el dispositivo (ej. Android WebView) no soporta Web Speech API. Cuenta con respaldo determinista local 100% funcional sin API key.
- **Microsoft Edge-TTS Neural (`es-MX-JorgeNeural` / `DaliaNeural`):** síntesis de voz en memoria compensada para presbiacusia (`-15%` velocidad, `-5Hz` tono).
- **Motor Matemático Local (`Python / NumPy / SciPy / Scikit-Learn`):** normalización de audio en RAM mediante tuberías `ffmpeg` (`pipe:0 -> pipe:1`), detección acústica de pausas anómicas ($\ge 2.0\text{ s}$), riqueza léxica `MATTR` (ventana móvil `W=20`), bucle semántico `TF-IDF Cosine` ($\ge 0.72$) y Z-Score longitudinal de 21 días (Días 1–14 línea base vs últimos 5 días).
- **Generación de Postales Semilla:** las 10 postales nostálgicas del caso simulado *Don Manuel* (`data/sample_assets/`) son imágenes sintéticas generadas con IA (sin personas reales identificables), respaldadas por un generador programático `Pillow`.

---

## 4. Arranque Rápido Local

### Requisitos
- Python 3.11+ (probado también en 3.14), Node 20+, `ffmpeg`

### 1. Variables de entorno (opcional)
```bash
cp .env.example .env
# Agrega GEMINI_API_KEY y TELEGRAM_BOT_TOKEN si deseas respuestas LLM y alertas Telegram en vivo.
# Sin llaves, la app funciona al 100% con respaldo determinista local y vista previa de Telegram.
```

### 2. Backend y Frontend en un solo servidor (`http://localhost:8080`)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend && npm ci && npm run build && cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 3. Ejecutar pruebas automatizadas
```bash
pytest backend/tests/ -v
```

---

## 5. Despliegue con Docker y Google Cloud Run

### Docker Compose local
```bash
docker compose up --build
```

### Google Cloud Run (con persistencia en Cloud Storage y blindaje SQLite)
```bash
export GCP_PROJECT_ID="tu-proyecto-gcp"
export GEMINI_API_KEY="tu-llave-opcional"
export TELEGRAM_BOT_TOKEN="tu-token-opcional"
./deploy/cloudrun-deploy.sh
```
> **Nota técnica:** El servidor activa automáticamente `MV_CLOUD_SYNC=1` en Cloud Run, trabajando sobre `/tmp/memoriaviva.db` (`PRAGMA journal_mode=DELETE`) y sincronizando atómicamente con `/app/data` para evitar bloqueos de SQLite en GCS FUSE, además de mantener copia inmutable de semillas en `/app/seed_data`.

---

## 6. Empaquetado Android APK (Capacitor 6 + GitHub Actions)

El workflow [`.github/workflows/build-apk.yml`](.github/workflows/build-apk.yml) compila automáticamente:
- **`app-debug.apk`** como Artifact en cada `push` a `main` o `workflow_dispatch`.
- **`app-release.apk`** firmado y publicado en GitHub Releases al crear un tag `v*.*.*`.

Configura la variable de repositorio `APP_SERVER_URL` con tu URL HTTPS de Cloud Run antes de disparar el workflow.

---

## 7. Guion del Demo en Vivo (5 Minutos por Zoom)

1. **0:00 – 0:50 | Wicked Problem (RISE):** Diagnóstico tardío por ansiedad de MoCA/MMSE y brecha digital geriátrica.
2. **0:50 – 1:35 | Arquitectura & *Identify Your Tools*:** FastAPI + SQLite + React/Tailwind + Capacitor APK + *Zero-Raw-Cloud Audio*.
3. **1:35 – 4:15 | Demo en Vivo (Activar caso Don Manuel en 1 clic — PIN `1234`):**
   - **Escena 1 (Kiosco + Anclaje Visual):** Hablar o pulsar tecla `1` (*Acto 1 · Rescate Biográfico*). Escuchar el rescate afectuoso de *Rocío*, ver el crossfade automático hacia la postal de *Sultán* y el chip de memoria aprendida. Probar **"Platicar sobre esta foto"** (*Foto → Voz*).
   - **Escena 2 (Anomia y Crisis S.O.S.):** Pulsar `2` (*Pausa anómica 3.18s*) y `3` (*Desorientación aguda* → Validación de Naomi Feil sin preguntas cognitivas + Alerta Roja Nivel 3 en Telegram).
   - **Escena 3 (Panel Clínico, *Human-in-the-Loop* y PDF):** Desbloquear con candado (`1234`), explorar la gráfica de 21 días (`Combinada` / `MATTR` / `Pausas` + banda D1–D14), registrar una revisión *Human-in-the-Loop* con variables de confusión en **Gobernanza RISE & IA** y descargar el **Reporte Clínico PDF** con la nota incluida.
4. **4:15 – 5:00 | Impacto RISE y Q&A.**

> **Nota de Arquitectura y Seguridad (Q&A):** En este prototipo de 24 horas el PIN (SHA-256 con salt) protege la transición entre el Modo Kiosco del adulto mayor y el Panel Familiar en el dispositivo; la hoja de ruta clínica v4 incorpora autenticación OAuth2/JWT por rol (Cuidador vs. Geriatra) y cifrado en reposo compatible con LFPDPPP/HIPAA.
