"""Unit tests for Phase 2: RAM Audio Engine, RMS Pauses, LLM Companion, Telegram, PDF & Postcards."""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import numpy as np

from backend.audio_engine import (
    DEMO_SCENARIOS,
    detect_rms_pauses,
    merge_rms_pauses_into_timestamps,
    normalize_audio_to_wav_ram,
)
from backend.biomarkers import compute_anomic_pauses, evaluate_longitudinal_trend
from backend.config import HISTORY_SEED_PATH
from backend.database import DatabaseManager
from backend.llm_companion import generate_companion_response, generate_photo_starter
from backend.pdf_report import generate_clinical_pdf_bytes
from backend.storage_manager import StorageManager, hash_pin, verify_pin
from backend.telegram_notifier import TelegramNotifier


def _make_synthetic_wav_with_pause(pause_sec: float = 2.6, sr: int = 16000) -> bytes:
    """Create a synthetic WAV in memory with speech-like tone -> silence -> tone."""
    t1 = np.linspace(0, 1.0, int(sr * 1.0), endpoint=False)
    tone1 = (0.4 * np.sin(2 * np.pi * 240 * t1)).astype(np.float32)
    silence = np.zeros(int(sr * pause_sec), dtype=np.float32)
    t2 = np.linspace(0, 1.0, int(sr * 1.0), endpoint=False)
    tone2 = (0.4 * np.sin(2 * np.pi * 310 * t2)).astype(np.float32)

    signal = np.concatenate([tone1, silence, tone2])
    pcm16 = (signal * 32767).astype(np.int16).tobytes()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16)
    return buf.getvalue()


def test_ffmpeg_ram_normalization_and_rms_pause_precision() -> None:
    """Verify Zero-Raw-Cloud Audio normalization in RAM & RMS pause accuracy (< 150ms error)."""
    target_pause = 2.60
    raw_wav = _make_synthetic_wav_with_pause(pause_sec=target_pause)

    norm_wav, sr, samples = normalize_audio_to_wav_ram(raw_wav)
    assert sr == 16000
    assert len(norm_wav) > 1000
    assert samples.size > 0

    rms = detect_rms_pauses(samples, sample_rate=sr, min_pause_sec=2.0)
    assert rms["anomic_rms_count"] == 1
    assert abs(rms["max_rms_pause_sec"] - target_pause) < 0.15

    # Merge into empty browser timestamps preserves anomic pause
    merged = merge_rms_pauses_into_timestamps("una llave de cruz grande", [], rms)
    pauses = compute_anomic_pauses(merged, threshold_sec=2.0)
    assert pauses["anomic_count"] == 1


def test_llm_companion_three_demo_acts_and_guardrails(monkeypatch) -> None:
    """Verify 3 theatrical pitch acts respect <=35 words, Naomi Feil crisis rule, and RAG-Lite."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    storage = StorageManager()
    profile = storage.load_demo_seed_profile()

    # Act 1: Biographical rescue (Rocío) + learns Sultán
    r1 = generate_companion_response(
        DEMO_SCENARIOS["demo_1_rescate"]["transcript"],
        profile,
        [],
        {"is_repetition": False},
        demo_scenario_id="demo_1_rescate",
    )
    assert len(r1["assistant_reply"].split()) <= 35
    assert "Rocío" in r1["assistant_reply"]
    assert r1["emergency_triggered"] is False
    assert any("Sultán" in f for f in r1["new_biographical_facts"])
    assert r1["memory_album_theme"] == "mascotas"

    # Act 2: Anomia on trains
    r2 = generate_companion_response(
        DEMO_SCENARIOS["demo_2_anomia"]["transcript"],
        profile,
        [],
        {"is_repetition": False},
        demo_scenario_id="demo_2_anomia",
    )
    assert len(r2["assistant_reply"].split()) <= 35
    assert r2["memory_album_theme"] == "ferrocarril"
    assert r2["emergency_triggered"] is False

    # Act 3: Crisis S.O.S. + Naomi Feil (NO question marks!)
    r3 = generate_companion_response(
        DEMO_SCENARIOS["demo_3_crisis"]["transcript"],
        profile,
        [],
        {"is_repetition": False},
        demo_scenario_id="demo_3_crisis",
    )
    assert len(r3["assistant_reply"].split()) <= 35
    assert r3["emergency_triggered"] is True
    assert r3["emotional_state"] == "crisis_desorientacion"
    assert "?" not in r3["assistant_reply"]
    assert "¿" not in r3["assistant_reply"]

    # Foto -> Voz starter
    starter = generate_photo_starter(
        {"title": "Estación de Trenes", "caption": "Ferrocarriles Nacionales", "theme": "ferrocarril"},
        profile,
    )
    assert len(starter["assistant_reply"].split()) <= 35


def test_storage_pin_and_ten_themed_postcards(tmp_path: Path) -> None:
    hashed = hash_pin("1234")
    assert verify_pin("1234", hashed) is True
    assert verify_pin("9999", hashed) is False

    db = DatabaseManager(db_path=tmp_path / "test.db", cloud_sync=False)
    storage = StorageManager(db=db, data_dir=tmp_path)
    photos = storage.ensure_sample_photos("don_manuel")
    assert len(photos) >= 10
    themes = {p["theme"] for p in photos}
    assert {"ferrocarril", "musica_boleros", "playa_manzanillo", "familia_hogar", "mascotas"}.issubset(
        themes
    )

    matched = storage.find_photo_for_theme("mascotas", "don_manuel")
    assert matched is not None
    assert matched["theme"] == "mascotas"


def test_telegram_qr_three_levels_and_pdf_with_hitl(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    db = DatabaseManager(db_path=tmp_path / "test_tg.db", cloud_sync=False)
    tg = TelegramNotifier(db=db)

    deep = tg.get_deep_link_info("MV-1234")
    assert "start=MV-1234" in deep["deep_link"]
    assert deep["qr_base64"].startswith("data:image/png;base64,")

    l1 = tg.send_level1_daily_pulse("don_manuel", "Don Manuel", "alegre", "Recordó a Sultán", "Preguntar por Sultán")
    l3 = tg.send_level3_sos_crisis("don_manuel", "Don Manuel", "Desorientación aguda", "Llamar de inmediato")
    assert l1["level"] == 1
    assert l3["level"] == 3
    assert len(db.get_telegram_logs("don_manuel")) == 2

    # Generate PDF including Human-in-the-Loop review
    days = json.loads(HISTORY_SEED_PATH.read_text(encoding="utf-8"))
    ev = evaluate_longitudinal_trend(days)
    rev = db.insert_clinical_review(
        profile_id="don_manuel",
        reviewer_name="Laura González",
        reviewer_role="Familiar Cuidador",
        decision="contexto_externo",
        confounding_factors=["mal_sueno", "sundowning"],
        clinical_notes="Nota HITL verificada: anoche durmió poco por calor.",
        mattr_snapshot=0.55,
        pause_snapshot=3.12,
    )
    storage = StorageManager(db=db, data_dir=tmp_path)
    pdf_bytes = generate_clinical_pdf_bytes(
        profile=storage.load_demo_seed_profile(),
        history_days=days,
        evaluation=ev,
        clinical_reviews=[rev],
        recent_turns=[],
        consent_events=[],
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 2500
