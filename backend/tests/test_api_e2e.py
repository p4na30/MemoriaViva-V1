"""End-to-End Integration Tests for Phase 3 FastAPI REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.database import DatabaseManager
from backend.main import create_app
from backend.storage_manager import StorageManager
from backend.telegram_notifier import TelegramNotifier


def _build_test_client(tmp_path: Path) -> TestClient:
    db = DatabaseManager(db_path=tmp_path / "e2e.db", cloud_sync=False)
    storage = StorageManager(db=db, data_dir=tmp_path)
    tg = TelegramNotifier(db=db)
    app = create_app(db_manager=db, storage_manager=storage, telegram_notifier=tg)
    return TestClient(app)


def test_full_pitch_flow_end_to_end(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    client = _build_test_client(tmp_path)

    # 1. Health & Initial State
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_init = client.get("/api/state")
    assert r_init.status_code == 200
    assert r_init.json()["account"]["is_registered"] is False
    assert len(r_init.json()["history_21_days"]) == 21
    assert len(r_init.json()["ai_tools_disclosure"]) >= 4

    # 2. 1-Click Demo Onboarding (Don Manuel)
    r_onb = client.post("/api/onboarding/complete", json={"use_demo_persona": True})
    assert r_onb.status_code == 200
    state = r_onb.json()["state"]
    assert state["account"]["is_registered"] is True
    assert state["account"]["kiosk_locked"] is True
    assert state["photo_count"] >= 10
    assert len(state["consent_events"]) == 1

    # Verify serving a postcard file works
    first_photo = state["photos"][0]
    r_img = client.get(first_photo["url"])
    assert r_img.status_code == 200
    assert r_img.headers["content-type"].startswith("image/")

    # 3. Assisted Dual Consent spoken greeting in Kiosk
    r_consent = client.post("/api/kiosk/consent-greeting?skip_tts=true")
    assert r_consent.status_code == 200
    assert "Don Manuel" in r_consent.json()["greeting_text"]

    # 4. Foto -> Voz (Bidirectional Visual Anchor)
    r_photo_turn = client.post(
        "/api/turn",
        json={"photo_filename": first_photo["filename"], "skip_tts": True},
    )
    assert r_photo_turn.status_code == 200
    assert r_photo_turn.json()["mode"] == "photo_starter"
    assert len(r_photo_turn.json()["assistant_reply"].split()) <= 35

    # 5. Act 1: Biographical Rescue (Rocío) + Learns Sultán + Level 1 Pulse
    r_act1 = client.post(
        "/api/turn",
        json={"demo_scenario_id": "demo_1_rescate", "skip_tts": True},
    )
    assert r_act1.status_code == 200
    act1 = r_act1.json()
    assert "Rocío" in act1["assistant_reply"]
    assert act1["emergency_triggered"] is False
    assert act1["memory_album_theme"] == "mascotas"
    assert act1["matched_photo"]["theme"] == "mascotas"
    assert any("Sultán" in f for f in act1["learned_facts"])
    assert act1["telegram_event"]["level"] == 1
    assert any("Sultán" in f for f in act1["state"]["profile"]["recuerdos_aprendidos"])

    # 6. Act 2: Anomic Pause 3.18s persisted in SQLite
    r_act2 = client.post(
        "/api/turn",
        json={"demo_scenario_id": "demo_2_anomia", "skip_tts": True},
    )
    assert r_act2.status_code == 200
    act2 = r_act2.json()
    assert act2["biomarkers"]["pauses"]["anomic_count"] == 1
    assert act2["biomarkers"]["pauses"]["max_pause_sec"] == 3.18
    assert act2["memory_album_theme"] == "ferrocarril"

    # 7. Act 3: Crisis S.O.S. + Naomi Feil Validation (no questions) + Level 3 Alert
    r_act3 = client.post(
        "/api/turn",
        json={"demo_scenario_id": "demo_3_crisis", "skip_tts": True},
    )
    assert r_act3.status_code == 200
    act3 = r_act3.json()
    assert act3["emergency_triggered"] is True
    assert "?" not in act3["assistant_reply"]
    assert act3["telegram_event"]["level"] == 3

    # 8. PIN Auth (reject bad PIN, unlock with 1234)
    assert client.post("/api/auth/verify-pin", json={"pin": "0000"}).status_code == 401
    r_pin = client.post("/api/auth/verify-pin", json={"pin": "1234"})
    assert r_pin.status_code == 200
    assert r_pin.json()["unlocked"] is True

    # 9. Human-in-the-Loop Clinical Review with Confounding Factors
    r_rev = client.post(
        "/api/reviews",
        json={
            "reviewer_name": "Laura González",
            "reviewer_role": "Familiar Cuidador",
            "decision": "contexto_externo",
            "confounding_factors": ["mal_sueno", "sundowning"],
            "clinical_notes": "Anoche durmió 4 horas y tuvo fatiga por la tarde.",
        },
    )
    assert r_rev.status_code == 200
    assert len(r_rev.json()["state"]["clinical_reviews"]) == 1

    # 10. Level 2 Preventive Telegram Warning
    r_l2 = client.post("/api/telegram/level2-warning")
    assert r_l2.status_code == 200
    assert r_l2.json()["telegram_event"]["level"] == 2

    # 11. Download Live Clinical PDF Report
    r_pdf = client.get("/api/report/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF-")

    # 12. Reset Demo for clean pitch rehearsal
    r_reset = client.post("/api/demo/reset")
    assert r_reset.status_code == 200
    reset_state = r_reset.json()["state"]
    assert reset_state["recent_turns"] == []
    assert reset_state["clinical_reviews"] == []
    assert reset_state["profile"]["recuerdos_aprendidos"] == []


def test_manual_onboarding_profile_isolation_and_jpg_upload(tmp_path: Path, monkeypatch) -> None:
    """Ensure manual onboarding never leaks Don Manuel's family data and isolates photo uploads as .jpg."""
    import io
    from PIL import Image

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    client = _build_test_client(tmp_path)

    r = client.post(
        "/api/onboarding/complete",
        json={
            "use_demo_persona": False,
            "nombre_completo": "Elena Morales Ruiz",
            "nombre_preferido": "Doña Elena",
            "caregiver_name": "Carlos Morales",
            "caregiver_username": "carlos.m",
            "pin": "5678",
            "edad": 78,
            "ciudad_residencia": "Colima, Colima",
            "ocupacion_historica": "Costurera",
            "consent_accepted": True,
        },
    )
    assert r.status_code == 200
    profile = r.json()["state"]["profile"]
    serialized = str(profile)
    assert "Doña Elena" in serialized
    assert "Carmen" not in serialized
    assert "Rocío" not in serialized
    assert "Vocho" not in serialized
    assert "Mateo" not in serialized

    # Upload a PNG image -> must be normalized and stored with .jpg extension
    buf = io.BytesIO()
    Image.new("RGB", (120, 80), color=(20, 110, 140)).save(buf, format="PNG")
    buf.seek(0)
    r_up = client.post(
        "/api/photos",
        files={"file": ("mi_foto_familiar.png", buf.getvalue(), "image/png")},
        data={"title": "Jardín de Colima", "caption": "Tarde en familia", "theme": "familia_hogar"},
    )
    assert r_up.status_code == 200
    assert r_up.json()["photo"]["filename"].endswith(".jpg")
    r_serve = client.get(r_up.json()["photo"]["url"])
    assert r_serve.status_code == 200


def test_telegram_uuid_multiuser_isolation_and_bidirectional_kiosk(tmp_path: Path, monkeypatch) -> None:
    """Verify UUID v4 pending->paired isolation across users and bidirectional Telegram->Kiosk text+photo."""
    import io
    import uuid
    from PIL import Image

    monkeypatch.setenv("MV_DISABLE_TG_POLLING", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    db = DatabaseManager(db_path=tmp_path / "tg_uuid.db", cloud_sync=False)
    storage = StorageManager(db=db, data_dir=tmp_path)
    tg = TelegramNotifier(db=db)
    app = create_app(db_manager=db, storage_manager=storage, telegram_notifier=tg)
    client = TestClient(app)

    # 1. Initial UUID v4 must be valid and pending
    r_st = client.get("/api/telegram/status")
    assert r_st.status_code == 200
    tg_st = r_st.json()["telegram_status"]
    link_uuid = tg_st["link_uuid"]
    assert uuid.UUID(link_uuid).version == 4
    assert tg_st["status"] == "pending"
    assert f"start={link_uuid}" in tg_st["deep_link"]

    # 2. Wrong UUID or empty /start MUST NOT pair Don Manuel
    r_bad1 = client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 77777}, "from": {"first_name": "Intruso"}, "text": "/start"}},
    )
    assert r_bad1.json()["handled"] is False
    r_bad2 = client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 77777}, "from": {"first_name": "Intruso"}, "text": f"/start {uuid.uuid4()}"}},
    )
    assert r_bad2.json()["handled"] is False
    assert client.get("/api/telegram/status").json()["telegram_status"]["status"] == "pending"

    # 3. Exact /start <uuid> pairs cleanly (pending -> paired)
    r_pair = client.post(
        "/api/telegram/webhook",
        json={
            "message": {
                "chat": {"id": 55501},
                "from": {"first_name": "Sofía", "username": "sofia_g"},
                "text": f"/start {link_uuid}",
            }
        },
    )
    assert r_pair.status_code == 200
    assert r_pair.json()["action"] == "paired"
    st_after = client.get("/api/telegram/status").json()["telegram_status"]
    assert st_after["status"] == "paired"
    assert st_after["chat_id"] == "55501"
    assert st_after["linked_user_name"] == "Sofía"

    # 4. Multi-user isolation: second patient gets distinct UUID and distinct chat_id
    other_uuid = str(uuid.uuid4())
    db.create_telegram_link("dona_elena", other_uuid)
    db.pair_telegram_link(other_uuid, "88802", first_name="Carlos")
    assert db.get_paired_links_by_chat_id("55501")[0]["profile_id"] == "don_manuel"
    assert db.get_paired_links_by_chat_id("88802")[0]["profile_id"] == "dona_elena"

    # 5. Bidirectional Bridge: authorized chat sends text -> appears in /api/kiosk/inbound
    r_txt = client.post(
        "/api/telegram/webhook",
        json={
            "message": {
                "chat": {"id": 55501},
                "from": {"first_name": "Sofía"},
                "text": "Hola abuelito, te llevo pan dulce a las 7.",
            }
        },
    )
    assert r_txt.json()["action"] == "inbound_text"

    # Unauthorized chat is ignored
    r_unauth = client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 99999}, "from": {"first_name": "Desconocido"}, "text": "Hola"}},
    )
    assert r_unauth.json()["action"] == "unauthorized_chat_ignored"

    # Authorized chat sends photo -> saved to album & queued for Kiosk
    buf = io.BytesIO()
    Image.new("RGB", (100, 80), color=(40, 120, 150)).save(buf, format="JPEG")
    res_photo = tg.process_incoming_update(
        {
            "message": {
                "chat": {"id": 55501},
                "from": {"first_name": "Sofía"},
                "caption": "Mira el pastel que hicimos",
                "photo": [{"file_id": "fake_id", "_test_bytes": buf.getvalue()}],
            }
        },
        storage=storage,
        tts_enabled=False,
    )
    assert res_photo["action"] == "inbound_photo"
    assert res_photo["photo"]["filename"].endswith(".jpg")

    r_inb = client.get("/api/kiosk/inbound")
    msgs = r_inb.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["message_type"] == "text"
    assert "pan dulce" in msgs[0]["text_content"]
    assert msgs[1]["message_type"] == "photo"

    # Ack both messages and verify audio_data_uri is purged to keep SQLite compact
    for m in msgs:
        assert client.post(f"/api/kiosk/inbound/{m['id']}/ack").status_code == 200
    assert client.get("/api/kiosk/inbound").json()["messages"] == []
    with db._connection(write=False) as conn:
        row = conn.execute(
            "SELECT audio_data_uri FROM family_inbound_messages WHERE id = ?", (msgs[0]["id"],)
        ).fetchone()
        assert row["audio_data_uri"] is None

    # Long inbound text (>280 chars) is truncated cleanly
    long_msg = "A" * 420
    r_long = tg.process_incoming_update(
        {"message": {"chat": {"id": 55501}, "from": {"first_name": "Sofía"}, "text": long_msg}},
        storage=storage,
        tts_enabled=False,
    )
    assert r_long["action"] == "inbound_text"
    assert len(r_long["inbound_message"]["text_content"]) < 320
    assert r_long["inbound_message"]["text_content"].endswith("…")

    # discover_chat_id must NOT call getUpdates when background poll thread is alive (prevents HTTP 409)
    class AliveDummyThread:
        def is_alive(self) -> bool:
            return True

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    tg._poll_thread = AliveDummyThread()  # type: ignore[assignment]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("getUpdates must not be called while listener thread is alive!")

    import backend.telegram_notifier as tg_mod

    monkeypatch.setattr(tg_mod.requests, "get", fail_if_called)
    disc = tg.discover_chat_id(link_uuid, storage=storage)
    assert disc["found"] is True
    assert disc["chat_id"] == "55501"
    tg._poll_thread = None

    # 6. Regenerate UUID revokes old link and creates fresh pending UUID v4
    r_regen = client.post("/api/telegram/regenerate-uuid")
    assert r_regen.status_code == 200
    new_st = r_regen.json()["telegram_status"]
    assert new_st["link_uuid"] != link_uuid
    assert uuid.UUID(new_st["link_uuid"]).version == 4
    assert new_st["status"] == "pending"


def test_manual_onboarding_preserves_step2_telegram_pairing(tmp_path: Path, monkeypatch) -> None:
    """Verify pairing Telegram in Step 2 is migrated to the new custom profile on Onboarding finish."""
    monkeypatch.setenv("MV_DISABLE_TG_POLLING", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    client = _build_test_client(tmp_path)
    init_uuid = client.get("/api/telegram/status").json()["telegram_status"]["link_uuid"]

    # Step 2: caregiver scans QR and pairs while active profile is still default don_manuel
    r_pair = client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 44422}, "from": {"first_name": "Carlos"}, "text": f"/start {init_uuid}"}},
    )
    assert r_pair.json()["action"] == "paired"

    # Step 4: finish manual onboarding creating a brand-new profile "Doña Elena"
    r_onb = client.post(
        "/api/onboarding/complete",
        json={
            "use_demo_persona": False,
            "nombre_completo": "Elena Morales Ruiz",
            "nombre_preferido": "Doña Elena",
            "caregiver_name": "Carlos Morales",
            "caregiver_username": "carlos.m",
            "pin": "5678",
            "consent_accepted": True,
        },
    )
    assert r_onb.status_code == 200
    tg_after = r_onb.json()["state"]["telegram_status"]
    assert tg_after["status"] == "paired"
    assert tg_after["link_uuid"] == init_uuid
    assert tg_after["chat_id"] == "44422"
    assert tg_after["linked_user_name"] == "Carlos"


def test_audio_only_turn_without_browser_transcript_or_gemini_key(tmp_path: Path, monkeypatch) -> None:
    """Verify Firefox / Android APK voice turn (audio_base64 only, no browser_transcript, no Gemini key) succeeds."""
    import base64
    import io
    import wave
    import numpy as np

    monkeypatch.setenv("MV_DISABLE_TG_POLLING", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    client = _build_test_client(tmp_path)
    client.post("/api/onboarding/complete", json={"use_demo_persona": True})

    # Create 1.2s of real audio energy in RAM (simulating Firefox / Android MediaRecorder payload)
    sr = 16000
    t = np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)
    pcm = (0.25 * np.sin(2 * np.pi * 240 * t) * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm)
    b64 = "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    r_turn = client.post(
        "/api/turn",
        json={"audio_base64": b64, "skip_tts": True},
    )
    assert r_turn.status_code == 200
    body = r_turn.json()
    assert body["ok"] is True
    assert len(body["assistant_reply"].split()) <= 35


def test_production_clean_mode_starts_empty_and_records_real_days(tmp_path: Path, monkeypatch) -> None:
    """Verify MV_APP_MODE=production starts 100% clean (zero Don Manuel data) and builds real Day 1..N."""
    monkeypatch.setenv("MV_APP_MODE", "production")
    monkeypatch.setenv("MV_DISABLE_TG_POLLING", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    client = _build_test_client(tmp_path)

    # 1. Health & clean initial state
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["app_mode"] == "production"

    r_init = client.get("/api/state")
    assert r_init.status_code == 200
    init_state = r_init.json()
    assert init_state["app_mode"] == "production"
    assert init_state["account"]["is_registered"] is False
    assert init_state["account"]["is_demo_mode"] is False
    assert init_state["history_21_days"] == []
    assert init_state["demo_scenarios"] == []
    assert init_state["min_screensaver_photos"] == 1
    assert init_state["evaluation"]["is_calibrating_baseline"] is True
    assert init_state["evaluation"]["days_recorded"] == 0
    assert init_state["evaluation"]["level2_alert_triggered"] is False
    assert "Don Manuel" not in str(init_state["profile"])
    assert "Carmen" not in str(init_state["profile"])

    # 2. Demo-only actions are disabled in production mode
    assert client.post("/api/onboarding/complete", json={"use_demo_persona": True}).status_code == 400
    assert client.post("/api/photos/sample").status_code == 403
    assert client.post("/api/demo/reset").status_code == 403
    assert client.post("/api/turn", json={"demo_scenario_id": "demo_1_rescate", "skip_tts": True}).status_code == 400

    # 3. Manual onboarding creates clean custom patient with zero seeded history or sample photos
    r_onb = client.post(
        "/api/onboarding/complete",
        json={
            "use_demo_persona": False,
            "nombre_completo": "Rosa María Hernández",
            "nombre_preferido": "Doña Rosa",
            "caregiver_name": "Ana Hernández",
            "caregiver_username": "ana.h",
            "pin": "4321",
            "edad": 76,
            "ciudad_residencia": "Monterrey, Nuevo León",
            "consent_accepted": True,
        },
    )
    assert r_onb.status_code == 200
    st = r_onb.json()["state"]
    assert st["account"]["is_registered"] is True
    assert st["account"]["is_demo_mode"] is False
    assert st["profile"]["paciente"]["nombre_preferido"] == "Doña Rosa"
    assert st["history_21_days"] == []
    assert st["photo_count"] == 0

    # 4. First real conversation turn creates real Día 1 while keeping baseline calibration active
    r_turn = client.post(
        "/api/turn",
        json={
            "custom_text": "Hoy preparé café con pan dulce en la mañana y estuve recordando el jardín de mi casa.",
            "skip_tts": True,
        },
    )
    assert r_turn.status_code == 200
    after = r_turn.json()["state"]
    assert len(after["history_21_days"]) == 1
    assert after["history_21_days"][0]["day_number"] == 1
    assert after["history_21_days"][0]["date_label"] == "Día 1"
    assert after["evaluation"]["days_recorded"] == 1
    assert after["evaluation"]["is_calibrating_baseline"] is True
    assert after["evaluation"]["level2_alert_triggered"] is False
