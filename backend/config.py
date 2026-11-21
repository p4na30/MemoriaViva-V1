"""Centralized clinical thresholds, paths, runtime settings, and AI transparency catalog."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

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
SAMPLE_ASSETS_DIR = DATA_DIR / "sample_assets"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

ACCOUNT_CONFIG_PATH = DATA_DIR / "account_config.json"
HISTORY_SEED_PATH = DATA_DIR / "history_21_days.json"
DEMO_PROFILE_PATH = PROFILES_DIR / "don_manuel_simulacion.json"
SQLITE_PERSISTENT_PATH = DATA_DIR / "memoriaviva.db"

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

# LLM Configuration
GEMINI_MODEL_COMPANION: str = os.getenv("GEMINI_MODEL_COMPANION", "gemini-2.5-flash")
MAX_ASSISTANT_WORDS: int = 35

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
        "tool": "Google Gemini (gemini-2.5-flash)",
        "category": "Generación Conversacional & STT Multimodal Fallback",
        "role": "Conduce Terapia de Reminiscencia (<=35 palabras), aplica Validación de Naomi Feil en crisis, extrae hechos biográficos (RAG-Lite) y transcribe audio en RAM cuando el dispositivo no soporta Web Speech.",
        "privacy_and_limits": "Sin diagnóstico médico ni consejos farmacológicos. Audio enviado solo en RAM si hace falta STT, 0 bytes almacenados.",
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
        "role": "Normaliza audio en RAM con ffmpeg (pipe:0 -> pipe:1), detecta pausas anómicas >=2.0s y compara 21 días contra la propia línea base (D1-D14).",
        "privacy_and_limits": "100% local en CPU, determinista, auditable y libre de sesgos educativos o socioeconómicos.",
    },
    {
        "tool": "Scikit-Learn (TF-IDF Cosine) & MATTR (Ventana 20)",
        "category": "Biomarcadores Léxico-Semánticos Locales",
        "role": "Mide riqueza léxica invariante a la longitud (MATTR) y bucles semánticos intra-sesión (similitud coseno >=0.72).",
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
