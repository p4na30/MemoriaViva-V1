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


def test_gemini_fallback_chain_and_thinking_budget_zero(monkeypatch) -> None:
    """Verify automatic fallback chain + 404 circuit-breaker + thinking_budget=0 + clean Feil guardrail."""
    import types as pytypes
    from backend.config import clear_unavailable_models

    clear_unavailable_models()
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL_COMPANION", "gemini-missing-404")

    calls = []

    class FakeModels:
        def generate_content(self, model, contents, config=None):
            budget = getattr(getattr(config, "thinking_config", None), "thinking_budget", None)
            calls.append((model, budget))
            if model == "gemini-missing-404":
                raise RuntimeError("404 NOT_FOUND model does not exist")
            payload = json.dumps(
                {
                    "assistant_reply": "Qué bonito recuerdo de sus trenes, Don Manuel. ¿Qué ruta disfrutaba más?",
                    "emotional_state": "alegre",
                    "emergency_triggered": False,
                    "emergency_reason": None,
                    "biographical_rescue_triggered": False,
                    "rescued_entity": None,
                    "conversation_topic_summary": "Platicó de los ferrocarriles.",
                    "dinner_conversation_tip": "Pregúntale cuál era su estación favorita.",
                    "new_biographical_facts": [],
                    "memory_album_theme": "ferrocarril",
                }
            )
            return pytypes.SimpleNamespace(text=payload)

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    from google import genai as real_genai

    monkeypatch.setattr(real_genai, "Client", FakeClient)

    storage = StorageManager()
    profile = storage.load_demo_seed_profile()

    # Turn 1: hits 404 on gemini-missing-404, marks it unavailable, succeeds on gemini-flash-latest
    res1 = generate_companion_response("Me encantaban los trenes de Guadalajara.", profile, [], {"is_repetition": False})
    assert res1["engine_used"] == "gemini-flash-latest"
    assert calls[0] == ("gemini-missing-404", 0)
    assert calls[1] == ("gemini-flash-latest", 0)

    # Turn 2: circuit breaker skips gemini-missing-404 completely (0ms wasted)
    calls.clear()
    res2 = generate_companion_response("Recordé el reloj de jubilación.", profile, [], {"is_repetition": False})
    assert res2["engine_used"] == "gemini-flash-latest"
    assert [m for m, _ in calls] == ["gemini-flash-latest"]

    # Crisis guardrail: if Gemini slips a question in crisis, substitute clean Naomi Feil text
    class CrisisSlipModels:
        def generate_content(self, model, contents, config=None):
            return pytypes.SimpleNamespace(
                text=json.dumps(
                    {
                        "assistant_reply": "Tranquilo Don Manuel. ¿Cómo se siente ahora?",
                        "emotional_state": "crisis_desorientacion",
                        "emergency_triggered": True,
                        "emergency_reason": "Desorientación",
                        "biographical_rescue_triggered": False,
                        "rescued_entity": None,
                        "conversation_topic_summary": "Crisis",
                        "dinner_conversation_tip": "Llamar",
                        "new_biographical_facts": [],
                        "memory_album_theme": "familia_hogar",
                    }
                )
            )

    class CrisisClient:
        def __init__(self, api_key=None):
            self.models = CrisisSlipModels()

    monkeypatch.setattr(real_genai, "Client", CrisisClient)
    res_crisis = generate_companion_response(
        "No sé qué hago aquí, estoy asustado", profile, [], {"is_repetition": False}
    )
    assert res_crisis["emergency_triggered"] is True
    assert "?" not in res_crisis["assistant_reply"]
    assert "¿" not in res_crisis["assistant_reply"]
    assert "Cómo se siente ahora" not in res_crisis["assistant_reply"]
    clear_unavailable_models()


def test_telegram_html_escaping_async_and_signed_formatting(tmp_path: Path, monkeypatch) -> None:
    """Verify Telegram escapes HTML entities (&, <, >), avoids '+-', and supports sync+async."""
    import time

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    db = DatabaseManager(db_path=tmp_path / "test_async.db", cloud_sync=False)
    tg = TelegramNotifier(db=db)
    sent_payloads = []

    def fake_send(chat_id: str, text: str):
        sent_payloads.append(text)
        time.sleep(0.03)
        return True, "delivered_telegram"

    monkeypatch.setattr(tg, "_send_raw_message", fake_send)

    # HTML escaping check on &, <, >
    tg.send_level1_daily_pulse(
        profile_id="don_manuel",
        elder_name="Don Manuel & Familia",
        emotional_state="alegre",
        topic_summary="Habló de trenes <antiguos> & boleros",
        dinner_tip="Preguntar por música > 1970",
        chat_id="99999",
        sync=True,
    )
    assert "&amp;" in sent_payloads[0]
    assert "&lt;antiguos&gt;" in sent_payloads[0]

    # Negative pause delta should format as -5.2%, NEVER +-5.2%
    neg_eval = {
        "delta_mattr_pct_display": 4.5,
        "z_mattr": 1.15,
        "delta_pause_pct_display": -5.2,
        "z_pause": -0.85,
    }
    entry = tg.send_level2_preventive_warning(
        profile_id="don_manuel",
        elder_name="Don Manuel",
        evaluation=neg_eval,
        chat_id="99999",
    )
    assert entry["channel_status"] == "queued_async"
    assert "+-" not in entry["message"]
    assert "Pausas -5.2%" in entry["message"]
    assert "MATTR +4.5%" in entry["message"]

    time.sleep(0.15)
    logs = db.get_telegram_logs("don_manuel", limit=5)
    assert logs[0]["delivered"] is True
    assert logs[0]["channel_status"] == "delivered_telegram"


def test_multiple_rms_pauses_injection_and_timezone_sundowning() -> None:
    """Verify all RMS pauses (multiple anomic + intermediate) are preserved and Mexico TZ works."""
    from datetime import datetime, timezone
    from backend.biomarkers import classify_circadian_period

    rms_mock = {
        "duration_sec": 12.0,
        "rms_pauses": [
            {"start_sec": 2.0, "end_sec": 4.4, "duration_sec": 2.4, "is_anomic": True},
            {"start_sec": 6.0, "end_sec": 7.1, "duration_sec": 1.1, "is_anomic": False},
            {"start_sec": 8.5, "end_sec": 11.2, "duration_sec": 2.7, "is_anomic": True},
        ],
        "max_rms_pause_sec": 2.7,
        "anomic_rms_count": 2,
    }
    merged = merge_rms_pauses_into_timestamps(
        "Cuando trabajaba en los trenes de Guadalajara usábamos una llave pesada muy grande",
        [],
        rms_mock,
    )
    pauses = compute_anomic_pauses(merged, threshold_sec=2.0)
    assert pauses["anomic_count"] == 2
    assert pauses["max_pause_sec"] == 2.7

    # 21:00 UTC == 15:00 America/Mexico_City -> must be vespertino_sundowning (NOT nocturno!)
    utc_pitch_time = datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc)
    assert classify_circadian_period(utc_pitch_time) == "vespertino_sundowning"
    # 16:00 UTC == 10:00 America/Mexico_City -> must be matutino!
    utc_morning = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)
    assert classify_circadian_period(utc_morning) == "matutino"

