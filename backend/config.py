"""Centralized clinical thresholds, paths, runtime settings, and AI transparency catalog."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load .env if present (never overrides explicit environment variables)
load_dotenv(ENV_FILE, override=False)

DATA_DIR = Path(os.getenv("MV_DATA_DIR", str(BASE_DIR / "data")))
if not DATA_DIR.is_absolute():
    DATA_DIR = (BASE_DIR / DATA_DIR).resolve()

PROFILES_DIR = DATA_DIR / "profiles"
PHOTOS_DIR = DATA_DIR / "photos"
SEED_FALLBACK_DIR = BASE_DIR / "seed_data"


def _resolve_seed_path(relative: str) -> Path:
    """Resolve immutable seed files with fallback to /app/seed_data when Cloud Storage mounts /app/data."""
    primary = DATA_DIR / relative
    if primary.exists():
        return primary
    fallback = SEED_FALLBACK_DIR / relative
    if fallback.exists():
        return fallback
    return primary


SAMPLE_ASSETS_DIR = _resolve_seed_path("sample_assets")
ACCOUNT_CONFIG_PATH = DATA_DIR / "account_config.json"
HISTORY_SEED_PATH = _resolve_seed_path("history_21_days.json")
DEMO_PROFILE_PATH = _resolve_seed_path("profiles/don_manuel_simulacion.json")
SQLITE_PERSISTENT_PATH = DATA_DIR / "memoriaviva.db"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

# Cloud Run / GCS FUSE detection for SQLite shielding
IS_CLOUD_RUN = bool(os.getenv("K_SERVICE")) or os.getenv("MV_CLOUD_SYNC", "0") == "1"
SQLITE_WORKING_PATH = Path("/tmp/memoriaviva.db") if IS_CLOUD_RUN else SQLITE_PERSISTENT_PATH

# ---------------------------------------------------------------------------
# Clinical & Biomarker Thresholds (MemoriaViva RISE v3.0 Specification)
# ---------------------------------------------------------------------------
SILENCE_THRESHOLD_SEC: float = 3.8
ANOMIC_PAUSE_THRESHOLD_SEC: float = 2.0
MATTR_WINDOW_SIZE: int = 20
SEMANTIC_REPEAT_THRESHOLD: float = 0.72
CLINICAL_ALERT_PAUSE_INCREASE_PCT: float = 0.25
CLINICAL_ALERT_MATTR_DROP_PCT: float = 0.20
Z_SCORE_PAUSE_ALERT: float = 2.0
Z_SCORE_MATTR_ALERT: float = -2.0
BASELINE_DAYS: int = 14
RECENT_WINDOW_DAYS: int = 5
MIN_SCREENSAVER_PHOTOS: int = 10

# Geriatric Speech Synthesis (Presbycusis compensation)
TTS_VOICE_MALE: str = "es-MX-JorgeNeural"
TTS_VOICE_FEMALE: str = "es-MX-DaliaNeural"
TTS_RATE: str = "-15%"
TTS_PITCH: str = "-5Hz"

# Application Mode: "demo" (Hackathon Don Manuel showcase) vs "production" (Clean zero-seed app)
def get_app_mode() -> str:
    """Return active runtime mode: 'demo' (default) or 'production'."""
    raw = os.getenv("MV_APP_MODE", "demo").strip().lower()
    return "production" if raw in ("production", "prod", "clean") else "demo"


def is_production_mode() -> bool:
    """True when running the clean user-ready build without Don Manuel demo data."""
    return get_app_mode() == "production"


# Timezone for clinical circadian classification (Sundowning) and PDF reports
MV_TIMEZONE: str = os.getenv("MV_TIMEZONE", "America/Mexico_City")


def get_local_timezone() -> ZoneInfo | timezone:
    """Return configured clinical local timezone (defaults to America/Mexico_City)."""
    tz_name = os.getenv("MV_TIMEZONE", MV_TIMEZONE).strip() or "America/Mexico_City"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def get_local_now() -> datetime:
    """Return timezone-aware current datetime in configured clinical local timezone."""
    return datetime.now(get_local_timezone())


# LLM Configuration (verified fast 2-model fallback chain with thinking disabled + 404 circuit breaker)
GEMINI_MODEL_COMPANION: str = os.getenv("GEMINI_MODEL_COMPANION", "gemini-3.5-flash-lite")
GEMINI_MODEL_FALLBACK_CHAIN: List[str] = [
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
]
MAX_ASSISTANT_WORDS: int = 35

_UNAVAILABLE_MODELS: Set[str] = set()


def mark_model_unavailable(model_name: str) -> None:
    """Circuit-breaker: skip models returning 404/NOT_FOUND on subsequent turns (0ms wasted)."""
    _UNAVAILABLE_MODELS.add(model_name)


def clear_unavailable_models() -> None:
    """Reset in-memory unavailable model cache (used in tests)."""
    _UNAVAILABLE_MODELS.clear()


def get_gemini_model_chain() -> List[str]:
    """Return ordered deduplicated Gemini fallback chain excluding known-404 models."""
    primary = os.getenv("GEMINI_MODEL_COMPANION", GEMINI_MODEL_COMPANION).strip()
    chain: List[str] = []
    for model in [primary, *GEMINI_MODEL_FALLBACK_CHAIN]:
        if model and model not in chain and model not in _UNAVAILABLE_MODELS:
            chain.append(model)
    return chain

# Valid Visual Anchor Themes (Bidirectional Voice <-> Photo)
MEMORY_ALBUM_THEMES: List[str] = [
    "ferrocarril",
    "musica_boleros",
    "playa_manzanillo",
    "familia_hogar",
    "mascotas",
]

# Confounding Variables for Human-in-the-Loop Governance
CONFOUNDING_FACTORS: List[Dict[str, str]] = [
    {
        "id": "mal_sueno",
        "label": "Mal sueño / Insomnio",
        "description": "Descanso nocturno insuficiente o interrumpido que reduce la fluidez verbal.",
    },
    {
        "id": "cambio_medicacion",
        "label": "Cambio de medicación",
        "description": "Ajuste reciente en dosis o fármacos con posible somnolencia transitoria.",
    },
    {
        "id": "fatiga",
        "label": "Fatiga física o deshidratación",
        "description": "Cansancio agudo, calor o baja ingesta de agua durante el día.",
    },
    {
        "id": "sundowning",
        "label": "Episodio vespertino (Sundowning)",
        "description": "Variación circadiana habitual al caer la tarde (14:00 - 20:59).",
    },
]

# Notre Dame Global RISE AI Hackathon — Official "Identify Your Tools" Catalog
AI_TOOLS_DISCLOSURE: List[Dict[str, str]] = [
    {
        "tool": "Google Gemini (gemini-3.5-flash-lite → gemini-flash-latest → respaldo local)",
        "category": "Generación Conversacional & STT Multimodal Fallback",
        "role": "Cadena automática de respaldo con circuit-breaker anti-404 y thinking desactivado (thinking_budget=0) para respuestas ágiles y mínimo gasto de tokens: conduce Terapia de Reminiscencia (≤35 palabras), aplica Validación de Naomi Feil en crisis, extrae hechos biográficos (RAG-Lite) y transcribe audio en RAM.",
        "privacy_and_limits": "Sin diagnóstico médico ni consejos farmacológicos. Audio enviado solo en RAM si hace falta STT, 0 bytes almacenados; respaldo local determinista si no hay red.",
    },
    {
        "tool": "Microsoft Edge-TTS Neural (es-MX-JorgeNeural / DaliaNeural)",
        "category": "Síntesis de Voz Inclusiva",
        "role": "Emite voz en español mexicano ajustada a -15% de velocidad (~120 ppm) y -5Hz de tono grave para compensar presbiacusia.",
        "privacy_and_limits": "Generación en memoria (Base64 MP3); no retiene grabaciones del adulto mayor.",
    },
    {
        "tool": "Motor Matemático Local (Python / NumPy / SciPy)",
        "category": "Análisis Acústico RMS y Z-Score Personal",
        "role": "Normaliza audio en RAM con ffmpeg (pipe:0 → pipe:1), detecta pausas anómicas ≥2.0 s y compara 21 días contra la propia línea base (D1–D14).",
        "privacy_and_limits": "100% local en CPU, determinista y auditable. Diseñado para reducir sesgos educativos y socioeconómicos: compara a cada persona contra sí misma.",
    },
    {
        "tool": "Scikit-Learn (TF-IDF Cosine) & MATTR (Ventana 20)",
        "category": "Biomarcadores Léxico-Semánticos Locales",
        "role": "Mide riqueza léxica invariante a la longitud (MATTR) y bucles semánticos intra-sesión (similitud coseno ≥0.72).",
        "privacy_and_limits": "Cómputo ligero O(N) sin entrenamiento de modelos pesados; huella ambiental mínima.",
    },
]


def ensure_data_directories() -> None:
    """Create required runtime directories if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def get_gemini_api_key() -> str:
    """Return active Gemini API key from environment (Zero-API-Key UX)."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def get_telegram_bot_token() -> str:
    """Return active Telegram bot token from environment."""
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def get_telegram_bot_username() -> str:
    """Return configured Telegram bot username (without leading @)."""
    return os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")


def get_telegram_default_chat_id() -> str:
    """Return optional default Telegram chat ID from environment."""
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def update_runtime_credentials(
    gemini_api_key: str | None = None,
    telegram_bot_token: str | None = None,
    telegram_bot_username: str | None = None,
    telegram_chat_id: str | None = None,
    persist_env: bool = True,
) -> Dict[str, Any]:
    """Update runtime credentials (Admin Advanced accordion) and optionally sync .env."""
    updates: Dict[str, str] = {}
    if gemini_api_key is not None:
        os.environ["GEMINI_API_KEY"] = gemini_api_key.strip()
        updates["GEMINI_API_KEY"] = gemini_api_key.strip()
    if telegram_bot_token is not None:
        os.environ["TELEGRAM_BOT_TOKEN"] = telegram_bot_token.strip()
        updates["TELEGRAM_BOT_TOKEN"] = telegram_bot_token.strip()
    if telegram_bot_username is not None:
        clean_user = telegram_bot_username.strip().lstrip("@")
        os.environ["TELEGRAM_BOT_USERNAME"] = clean_user
        updates["TELEGRAM_BOT_USERNAME"] = clean_user
    if telegram_chat_id is not None:
        os.environ["TELEGRAM_CHAT_ID"] = telegram_chat_id.strip()
        updates["TELEGRAM_CHAT_ID"] = telegram_chat_id.strip()

    if persist_env and updates:
        existing_lines: List[str] = []
        if ENV_FILE.exists():
            existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        seen = set()
        new_lines: List[str] = []
        for line in existing_lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}")
                    seen.add(key)
                    continue
            new_lines.append(line)
        for key, value in updates.items():
            if key not in seen:
                new_lines.append(f"{key}={value}")
        ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {
        "gemini_configured": bool(get_gemini_api_key()),
        "telegram_bot_configured": bool(get_telegram_bot_token()),
        "telegram_bot_username": get_telegram_bot_username(),
    }
