"""FastAPI REST API & Static SPA server for MemoriaViva RISE v3.0."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.audio_engine import (
    DEMO_SCENARIOS,
    decode_base64_audio,
    detect_rms_pauses,
    merge_rms_pauses_into_timestamps,
    normalize_audio_to_wav_ram,
    synthesize_elder_voice,
    transcribe_audio_ram_gemini,
)
from backend.biomarkers import (
    classify_circadian_period,
    compute_anomic_pauses,
    compute_mattr,
    compute_semantic_repetition,
    evaluate_longitudinal_trend,
)
from backend.config import (
    AI_TOOLS_DISCLOSURE,
    CONFOUNDING_FACTORS,
    FRONTEND_DIST_DIR,
    IS_CLOUD_RUN,
    MEMORY_ALBUM_THEMES,
    MIN_SCREENSAVER_PHOTOS,
    SILENCE_THRESHOLD_SEC,
    ensure_data_directories,
    get_gemini_api_key,
    get_telegram_bot_token,
    update_runtime_credentials,
)
from backend.database import DatabaseManager
from backend.llm_companion import (
    generate_companion_response,
    generate_consent_greeting,
    generate_photo_starter,
)
from backend.pdf_report import generate_clinical_pdf_bytes
from backend.storage_manager import StorageManager, generate_link_code, hash_pin, verify_pin
from backend.telegram_notifier import TelegramNotifier


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------
class OnboardingCompleteRequest(BaseModel):
    use_demo_persona: bool = False
    nombre_completo: Optional[str] = None
    nombre_preferido: Optional[str] = None
    caregiver_name: Optional[str] = None
    caregiver_username: Optional[str] = None
    pin: str = "1234"
    edad: Optional[int] = 72
    ciudad_residencia: Optional[str] = None
    ocupacion_historica: Optional[str] = None
    esposa_o_pareja: Optional[str] = None
    hijos_detalle: Optional[str] = None
    nietos_detalle: Optional[str] = None
    anclas_de_reminiscencia: Optional[List[str]] = None
    consent_accepted: bool = True
    voice_gender: str = "male"
    launch_kiosk: bool = True


class PinVerifyRequest(BaseModel):
    pin: str


class TurnRequest(BaseModel):
    audio_base64: Optional[str] = None
    audio_mime: Optional[str] = None
    browser_transcript: Optional[str] = None
    browser_word_timestamps: Optional[List[Dict[str, Any]]] = None
    demo_scenario_id: Optional[str] = None
    custom_text: Optional[str] = None
    photo_filename: Optional[str] = None
    current_photo_filename: Optional[str] = None
    skip_tts: bool = False


class ClinicalReviewRequest(BaseModel):
    reviewer_name: str = Field(..., min_length=2)
    reviewer_role: str = Field(default="Familiar Cuidador")
    decision: str = Field(default="contexto_externo")
    confounding_factors: List[str] = Field(default_factory=list)
    clinical_notes: str = Field(..., min_length=3)


class ProfileUpdateRequest(BaseModel):
    nombre_completo: Optional[str] = None
    nombre_preferido: Optional[str] = None
    edad: Optional[int] = None
    ciudad_residencia: Optional[str] = None
    ocupacion_historica: Optional[str] = None
    rutinas_salud_suaves: Optional[List[str]] = None
    anclas_de_reminiscencia: Optional[List[str]] = None


class SettingsUpdateRequest(BaseModel):
    rotation_interval_sec: Optional[int] = None
    theme_mode: Optional[str] = None
    voice_gender: Optional[str] = None
    caregiver_name: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    new_pin: Optional[str] = None
    # Admin Advanced optional overrides
    gemini_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_bot_username: Optional[str] = None


def create_app(
    db_manager: Optional[DatabaseManager] = None,
    storage_manager: Optional[StorageManager] = None,
    telegram_notifier: Optional[TelegramNotifier] = None,
) -> FastAPI:
    """Create configured FastAPI application instance."""
    ensure_data_directories()
    db = db_manager or DatabaseManager()
    storage = storage_manager or StorageManager(db=db)
    telegram = telegram_notifier or TelegramNotifier(db=db)

    # Ensure 21-day baseline exists for Don Manuel on boot
    db.seed_longitudinal_days("don_manuel")

    app = FastAPI(
        title="MemoriaViva RISE API",
        version="3.0.0",
        description="Plataforma Conversacional de Terapia de Reminiscencia y Detección Temprana No Invasiva",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _active_profile_id() -> str:
        return str(storage.load_account_config().get("active_profile_id", "don_manuel"))

    def _build_full_state() -> Dict[str, Any]:
        account = storage.get_public_account_config()
        pid = account.get("active_profile_id", "don_manuel")
        profile = storage.load_profile(pid)
        days = db.get_longitudinal_days(pid)
        if not days:
            days = db.seed_longitudinal_days(pid)
        evaluation = evaluate_longitudinal_trend(days)
        photos = storage.list_photos(pid)
        deep_link = telegram.get_deep_link_info(
            link_code=account.get("telegram_link_code", "MV-1000"),
            chat_id=account.get("telegram_chat_id", ""),
        )
        return {
            "account": account,
            "profile": profile,
            "history_21_days": days,
            "evaluation": evaluation,
            "photos": photos,
            "photo_count": len(photos),
            "min_screensaver_photos": MIN_SCREENSAVER_PHOTOS,
            "silence_threshold_sec": SILENCE_THRESHOLD_SEC,
            "memory_album_themes": MEMORY_ALBUM_THEMES,
            "confounding_factors_catalog": CONFOUNDING_FACTORS,
            "telegram_status": deep_link,
            "telegram_logs": db.get_telegram_logs(pid, limit=25),
            "recent_turns": db.get_recent_turns(pid, limit=20),
            "clinical_reviews": db.get_clinical_reviews(pid, limit=30),
            "consent_events": db.get_consent_events(pid),
            "ai_tools_disclosure": AI_TOOLS_DISCLOSURE,
            "demo_scenarios": [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "subtitle": s["subtitle"],
                    "transcript": s["transcript"],
                    "expected_theme": s["expected_theme"],
                }
                for s in DEMO_SCENARIOS.values()
            ],
            "runtime_status": {
                "gemini_configured": bool(get_gemini_api_key()),
                "telegram_bot_configured": bool(get_telegram_bot_token()),
                "cloud_run_shield": IS_CLOUD_RUN,
            },
        }

    # ------------------------------------------------------------------
    # Health & State
    # ------------------------------------------------------------------
    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "MemoriaViva RISE v3.0",
            "cloud_run_shield": IS_CLOUD_RUN,
            "gemini_configured": bool(get_gemini_api_key()),
            "telegram_configured": bool(get_telegram_bot_token()),
        }

    @app.get("/api/state")
    def get_state() -> Dict[str, Any]:
        return _build_full_state()

    # ------------------------------------------------------------------
    # Onboarding, PIN Auth & Kiosk Lock
    # ------------------------------------------------------------------
    @app.post("/api/onboarding/complete")
    def complete_onboarding(req: OnboardingCompleteRequest) -> Dict[str, Any]:
        cfg = storage.load_account_config()

        if req.use_demo_persona:
            pid = "don_manuel"
            profile = storage.reset_demo_profile()
            db.seed_longitudinal_days(pid, force=False)
            cfg["active_profile_id"] = pid
            cfg["is_demo_mode"] = True
            cfg["caregiver_name"] = "Laura González"
            cfg["caregiver_username"] = "laura.gonzalez"
            cfg["pin_hash"] = hash_pin("1234")
            cfg["voice_gender"] = "male"
        else:
            clean_name = (req.nombre_completo or "Adulto Mayor").strip()
            preferred = (req.nombre_preferido or clean_name.split()[0]).strip()
            pid = (
                "".join(c.lower() for c in preferred if c.isalnum())[:18] or "paciente"
            )
            if pid == "donmanuel":
                pid = "paciente_custom"
            caregiver_clean = (req.caregiver_name or "Familiar Cuidador").strip()
            cleaned_anchors = [
                a.strip() for a in (req.anclas_de_reminiscencia or []) if a.strip()
            ]
            # Build a clean custom profile without cloning Don Manuel's personal family data
            custom_profile: Dict[str, Any] = {
                "paciente": {
                    "id": pid,
                    "tipo_perfil": "familiar_personalizado",
                    "nombre_completo": clean_name,
                    "nombre_preferido": preferred,
                    "edad": int(req.edad or 72),
                    "ciudad_residencia": (req.ciudad_residencia or "México").strip(),
                    "ocupacion_historica": (req.ocupacion_historica or "No especificada").strip(),
                },
                "red_familiar_y_afectiva": {
                    "esposa_finada": (req.esposa_o_pareja or "").strip(),
                    "hija_mayor_cuidadora": {
                        "nombre": caregiver_clean,
                        "ciudad": (req.ciudad_residencia or "").strip(),
                        "detalle": "Familiar responsable principal",
                    },
                    "hija_menor": {
                        "nombre": "",
                        "ciudad": "",
                        "ocupacion": "",
                        "detalle": (req.hijos_detalle or "").strip(),
                    },
                    "nietos": [],
                },
                "anclas_de_reminiscencia": cleaned_anchors,
                "recuerdos_aprendidos": [],
                "rutinas_salud_suaves": [
                    "Tomar un vaso de agua durante el día",
                ],
                "contacto_emergencia_telegram": {
                    "nombre": caregiver_clean,
                    "parentesco": "Familiar",
                    "chat_id": cfg.get("telegram_chat_id", ""),
                },
            }
            profile = storage.save_profile(custom_profile, pid)
            db.seed_longitudinal_days(pid, force=False)

            cfg["active_profile_id"] = pid
            cfg["is_demo_mode"] = False
            cfg["caregiver_name"] = (req.caregiver_name or "Familiar Cuidador").strip()
            cfg["caregiver_username"] = (req.caregiver_username or "familiar").strip()
            if len(req.pin.strip()) < 4:
                raise HTTPException(status_code=400, detail="El PIN debe tener al menos 4 dígitos.")
            cfg["pin_hash"] = hash_pin(req.pin.strip())
            cfg["voice_gender"] = req.voice_gender if req.voice_gender in ("male", "female") else "male"

        cfg["is_registered"] = True
        cfg["kiosk_locked"] = bool(req.launch_kiosk)
        cfg["consent_caregiver_accepted"] = bool(req.consent_accepted)
        cfg["consent_caregiver_at"] = datetime.now(timezone.utc).isoformat()
        if not cfg.get("telegram_link_code"):
            cfg["telegram_link_code"] = generate_link_code()
        storage.save_account_config(cfg)

        # Guarantee at least 10 themed photos for the Kiosk
        photos = storage.list_photos(pid)
        if len(photos) < MIN_SCREENSAVER_PHOTOS:
            storage.ensure_sample_photos(pid)

        db.insert_consent_event(
            profile_id=pid,
            consent_type="caregiver_onboarding",
            acknowledged_by=cfg["caregiver_name"],
            summary_text=(
                f"Consentimiento Dual RISE aceptado para {profile['paciente']['nombre_preferido']}. "
                "Privacidad Zero-Raw-Cloud Audio y carácter no diagnóstico confirmados."
            ),
        )

        return {"ok": True, "state": _build_full_state()}

    @app.post("/api/auth/verify-pin")
    def auth_verify_pin(req: PinVerifyRequest) -> Dict[str, Any]:
        cfg = storage.load_account_config()
        if not verify_pin(req.pin, cfg.get("pin_hash", "")):
            raise HTTPException(status_code=401, detail="PIN incorrecto. Verifica e intenta nuevamente.")
        cfg["kiosk_locked"] = False
        storage.save_account_config(cfg)
        return {"ok": True, "unlocked": True, "state": _build_full_state()}

    @app.post("/api/kiosk/lock")
    def lock_kiosk() -> Dict[str, Any]:
        cfg = storage.load_account_config()
        cfg["kiosk_locked"] = True
        storage.save_account_config(cfg)
        return {"ok": True, "kiosk_locked": True}

    @app.post("/api/kiosk/consent-greeting")
    def kiosk_consent_greeting(skip_tts: bool = False) -> Dict[str, Any]:
        cfg = storage.load_account_config()
        pid = cfg.get("active_profile_id", "don_manuel")
        profile = storage.load_profile(pid)
        greeting = generate_consent_greeting(profile)
        audio_uri = synthesize_elder_voice(
            greeting, voice_gender=cfg.get("voice_gender", "male"), enabled=not skip_tts
        )
        event = db.insert_consent_event(
            profile_id=pid,
            consent_type="elder_spoken_greeting",
            acknowledged_by=profile["paciente"]["nombre_preferido"],
            summary_text=greeting,
        )
        return {
            "ok": True,
            "greeting_text": greeting,
            "audio_data_uri": audio_uri,
            "consent_event": event,
        }

    # ------------------------------------------------------------------
    # Conversational Turn Pipeline (Voice / Photo->Voice / Demo / Text)
    # ------------------------------------------------------------------
    @app.post("/api/turn")
    def process_turn(req: TurnRequest) -> Dict[str, Any]:
        cfg = storage.load_account_config()
        pid = cfg.get("active_profile_id", "don_manuel")
        profile = storage.load_profile(pid)
        elder_name = profile["paciente"]["nombre_preferido"]

        # Branch A: Foto -> Voz (Initiate reminiscence about the currently visible photo)
        if req.photo_filename and not (
            req.audio_base64 or req.browser_transcript or req.demo_scenario_id or req.custom_text
        ):
            photos = storage.list_photos(pid)
            photo = next((p for p in photos if p["filename"] == req.photo_filename), None)
            if not photo:
                raise HTTPException(status_code=404, detail="Fotografía no encontrada en el álbum.")
            starter = generate_photo_starter(photo, profile)
            audio_uri = synthesize_elder_voice(
                starter["assistant_reply"],
                voice_gender=cfg.get("voice_gender", "male"),
                enabled=not req.skip_tts,
            )
            return {
                "ok": True,
                "mode": "photo_starter",
                "assistant_reply": starter["assistant_reply"],
                "audio_data_uri": audio_uri,
                "memory_album_theme": photo["theme"],
                "matched_photo": photo,
                "topic_summary": starter["conversation_topic_summary"],
                "engine_used": starter.get("engine_used", "deterministic_fallback"),
            }

        # Branch B: Demo Scenario / Real Voice / Custom Text
        source = "voice"
        transcript = ""
        word_timestamps: List[Dict[str, Any]] = []
        rms_analysis: Dict[str, Any] = {
            "duration_sec": 0.0,
            "rms_pauses": [],
            "max_rms_pause_sec": 0.0,
            "anomic_rms_count": 0,
        }

        if req.demo_scenario_id:
            scenario = DEMO_SCENARIOS.get(req.demo_scenario_id)
            if not scenario:
                raise HTTPException(status_code=400, detail="Escenario demo no reconocido.")
            source = "demo"
            transcript = scenario["transcript"]
            word_timestamps = list(scenario["word_timestamps"])
        else:
            transcript = (req.custom_text or req.browser_transcript or "").strip()
            if req.custom_text:
                source = "text"
            if req.audio_base64:
                source = "voice"
                raw_bytes = decode_base64_audio(req.audio_base64)
                try:
                    wav_bytes, sr, samples = normalize_audio_to_wav_ram(raw_bytes)
                    rms_analysis = detect_rms_pauses(samples, sample_rate=sr)
                    # Hybrid resilient STT: if browser SpeechRecognition was empty (Android APK/Safari),
                    # transcribe RAM WAV directly with Gemini 2.5 Flash
                    if not transcript and wav_bytes:
                        transcript = transcribe_audio_ram_gemini(wav_bytes)
                except Exception:
                    # Never crash the turn if browser audio codec was partial; preserve transcript
                    pass
                finally:
                    # Explicitly release raw audio buffers in RAM (Zero-Raw-Cloud Audio)
                    raw_bytes = b""

            if not transcript:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No se detectó voz o texto en este turno. Intenta hablar más cerca del micrófono "
                        "o escribe un mensaje de prueba."
                    ),
                )
            word_timestamps = merge_rms_pauses_into_timestamps(
                transcript=transcript,
                word_timestamps=req.browser_word_timestamps,
                rms_analysis=rms_analysis,
            )

        # 1. Local Mathematical Biomarkers (O(N), CPU, zero cloud audio)
        recent_turns = db.get_recent_turns(pid, limit=12)
        prev_utterances = [t["user_text"] for t in reversed(recent_turns)]

        mattr_res = compute_mattr(transcript)
        pause_res = compute_anomic_pauses(word_timestamps)
        rep_res = compute_semantic_repetition(transcript, prev_utterances)
        circadian = classify_circadian_period()

        # 2. Gerontological Companion (Gemini 2.5 Flash or Deterministic Fallback)
        llm_res = generate_companion_response(
            user_text=transcript,
            profile=profile,
            recent_history=list(reversed(recent_turns))[-4:],
            repetition_info=rep_res,
            demo_scenario_id=req.demo_scenario_id,
        )

        # 3. Biographical RAG-Lite persistence
        learned_facts = storage.append_learned_facts(
            llm_res.get("new_biographical_facts") or [], profile_id=pid
        )

        # 4. Persist Turn + Update Day 21 in SQLite
        alert_level = 3 if llm_res.get("emergency_triggered") else 1
        turn_record = db.insert_turn(
            {
                "profile_id": pid,
                "circadian_period": circadian,
                "user_text": transcript,
                "assistant_reply": llm_res["assistant_reply"],
                "mattr": mattr_res["mattr"],
                "mean_pause_sec": pause_res["mean_pause_sec"],
                "max_pause_sec": pause_res["max_pause_sec"],
                "anomic_count": pause_res["anomic_count"],
                "is_repetition": rep_res["is_repetition"],
                "repetition_score": rep_res["max_similarity"],
                "emotional_state": llm_res.get("emotional_state", "tranquilo"),
                "emergency_triggered": llm_res.get("emergency_triggered", False),
                "memory_album_theme": llm_res.get("memory_album_theme", "familia_hogar"),
                "learned_facts": learned_facts,
                "alert_level": alert_level,
                "source": source,
            }
        )

        db.update_latest_day_with_turn(
            profile_id=pid,
            mattr=mattr_res["mattr"],
            mean_pause=pause_res["mean_pause_sec"] or pause_res["max_pause_sec"],
            anomic_count=pause_res["anomic_count"],
            is_repetition=rep_res["is_repetition"],
            mood=llm_res.get("emotional_state", "tranquilo"),
            circadian_period=circadian,
        )

        # 5 & 6. Run Telegram delivery + Edge-TTS in parallel inside the request
        # Guarantees 0ms extra latency while preventing Cloud Run CPU throttling from freezing S.O.S. alerts
        chat_id = cfg.get("telegram_chat_id", "")

        def _dispatch_telegram() -> Dict[str, Any]:
            if llm_res.get("emergency_triggered"):
                return telegram.send_level3_sos_crisis(
                    profile_id=pid,
                    elder_name=elder_name,
                    reason=llm_res.get("emergency_reason") or "Desorientación o malestar agudo detectado.",
                    dinner_tip=llm_res.get("dinner_conversation_tip", "Llamar de inmediato al adulto mayor."),
                    chat_id=chat_id,
                    sync=True,
                )
            return telegram.send_level1_daily_pulse(
                profile_id=pid,
                elder_name=elder_name,
                emotional_state=llm_res.get("emotional_state", "tranquilo"),
                topic_summary=llm_res.get("conversation_topic_summary", "Conversación cálida de reminiscencia."),
                dinner_tip=llm_res.get("dinner_conversation_tip", "Pregúntale en la cena cómo estuvo su tarde."),
                chat_id=chat_id,
                sync=True,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            tg_future = pool.submit(_dispatch_telegram)
            tts_future = pool.submit(
                synthesize_elder_voice,
                llm_res["assistant_reply"],
                cfg.get("voice_gender", "male"),
                not req.skip_tts,
            )
            tg_event = tg_future.result()
            audio_uri = tts_future.result()

        # 7. Bidirectional Visual Anchor (Voice -> Photo)
        theme = llm_res.get("memory_album_theme", "familia_hogar")
        matched_photo = storage.find_photo_for_theme(
            theme=theme,
            profile_id=pid,
            current_filename=req.current_photo_filename,
        )

        return {
            "ok": True,
            "mode": source,
            "turn": turn_record,
            "transcript": transcript,
            "assistant_reply": llm_res["assistant_reply"],
            "audio_data_uri": audio_uri,
            "emotional_state": llm_res.get("emotional_state", "tranquilo"),
            "emergency_triggered": bool(llm_res.get("emergency_triggered", False)),
            "emergency_reason": llm_res.get("emergency_reason"),
            "biographical_rescue_triggered": bool(llm_res.get("biographical_rescue_triggered", False)),
            "rescued_entity": llm_res.get("rescued_entity"),
            "conversation_topic_summary": llm_res.get("conversation_topic_summary"),
            "dinner_conversation_tip": llm_res.get("dinner_conversation_tip"),
            "learned_facts": learned_facts,
            "memory_album_theme": theme,
            "matched_photo": matched_photo,
            "biomarkers": {
                "mattr": mattr_res,
                "pauses": pause_res,
                "rms": rms_analysis,
                "repetition": rep_res,
                "circadian_period": circadian,
            },
            "telegram_event": tg_event,
            "engine_used": llm_res.get("engine_used", "deterministic_fallback"),
            "state": _build_full_state(),
        }

    # ------------------------------------------------------------------
    # Human-in-the-Loop Clinical Reviews (RISE Governance)
    # ------------------------------------------------------------------
    @app.get("/api/reviews")
    def list_reviews() -> Dict[str, Any]:
        pid = _active_profile_id()
        return {"reviews": db.get_clinical_reviews(pid, limit=30)}

    @app.post("/api/reviews")
    def create_review(req: ClinicalReviewRequest) -> Dict[str, Any]:
        pid = _active_profile_id()
        days = db.get_longitudinal_days(pid)
        ev = evaluate_longitudinal_trend(days)
        review = db.insert_clinical_review(
            profile_id=pid,
            reviewer_name=req.reviewer_name,
            reviewer_role=req.reviewer_role,
            decision=req.decision,
            confounding_factors=req.confounding_factors,
            clinical_notes=req.clinical_notes,
            mattr_snapshot=float(ev.get("latest_mattr", 0.0)),
            pause_snapshot=float(ev.get("latest_pause", 0.0)),
        )
        return {"ok": True, "review": review, "state": _build_full_state()}

    # ------------------------------------------------------------------
    # Family Photo Album (10+ Postcards + Custom Uploads)
    # ------------------------------------------------------------------
    @app.get("/api/photos")
    def get_photos() -> Dict[str, Any]:
        pid = _active_profile_id()
        photos = storage.list_photos(pid)
        return {"photos": photos, "count": len(photos), "min_required": MIN_SCREENSAVER_PHOTOS}

    @app.post("/api/photos")
    async def upload_photo(
        file: UploadFile = File(...),
        title: str = Form(default=""),
        caption: str = Form(default=""),
        theme: str = Form(default="familia_hogar"),
    ) -> Dict[str, Any]:
        pid = _active_profile_id()
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="El archivo de imagen está vacío.")
        try:
            photo = storage.save_uploaded_photo(
                original_filename=file.filename or "foto.jpg",
                raw_bytes=raw,
                profile_id=pid,
                title=title,
                caption=caption,
                theme=theme,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Imagen inválida: {exc}") from exc
        return {"ok": True, "photo": photo, "photos": storage.list_photos(pid)}

    @app.post("/api/photos/sample")
    def generate_sample_photos() -> Dict[str, Any]:
        pid = _active_profile_id()
        photos = storage.ensure_sample_photos(pid)
        return {"ok": True, "photos": photos, "count": len(photos)}

    @app.delete("/api/photos/{filename}")
    def remove_photo(filename: str) -> Dict[str, Any]:
        pid = _active_profile_id()
        current = storage.list_photos(pid)
        if len(current) <= MIN_SCREENSAVER_PHOTOS:
            raise HTTPException(
                status_code=400,
                detail=f"El Modo Kiosco requiere al menos {MIN_SCREENSAVER_PHOTOS} fotografías en el álbum.",
            )
        deleted = storage.delete_photo(filename, pid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Fotografía no encontrada.")
        return {"ok": True, "photos": storage.list_photos(pid)}

    @app.get("/api/photos/file/{filename}")
    def serve_photo_file(filename: str) -> FileResponse:
        pid = _active_profile_id()
        file_path = storage.resolve_photo_file(filename, pid)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="Imagen no encontrada.")
        return FileResponse(file_path, media_type="image/jpeg")

    # ------------------------------------------------------------------
    # Profile & System Settings (incl. Admin Advanced accordion)
    # ------------------------------------------------------------------
    @app.put("/api/profile")
    def update_profile(req: ProfileUpdateRequest) -> Dict[str, Any]:
        pid = _active_profile_id()
        profile = storage.load_profile(pid)
        pac = profile.setdefault("paciente", {})
        if req.nombre_completo is not None:
            pac["nombre_completo"] = req.nombre_completo.strip()
        if req.nombre_preferido is not None:
            pac["nombre_preferido"] = req.nombre_preferido.strip()
        if req.edad is not None:
            pac["edad"] = int(req.edad)
        if req.ciudad_residencia is not None:
            pac["ciudad_residencia"] = req.ciudad_residencia.strip()
        if req.ocupacion_historica is not None:
            pac["ocupacion_historica"] = req.ocupacion_historica.strip()
        if req.rutinas_salud_suaves is not None:
            profile["rutinas_salud_suaves"] = [r.strip() for r in req.rutinas_salud_suaves if r.strip()]
        if req.anclas_de_reminiscencia is not None:
            profile["anclas_de_reminiscencia"] = [a.strip() for a in req.anclas_de_reminiscencia if a.strip()]
        storage.save_profile(profile, pid)
        return {"ok": True, "profile": profile, "state": _build_full_state()}

    @app.put("/api/settings")
    def update_settings(req: SettingsUpdateRequest) -> Dict[str, Any]:
        cfg = storage.load_account_config()
        if req.rotation_interval_sec is not None:
            cfg["rotation_interval_sec"] = max(4, min(15, int(req.rotation_interval_sec)))
        if req.theme_mode in ("light", "dark"):
            cfg["theme_mode"] = req.theme_mode
        if req.voice_gender in ("male", "female"):
            cfg["voice_gender"] = req.voice_gender
        if req.caregiver_name is not None and req.caregiver_name.strip():
            cfg["caregiver_name"] = req.caregiver_name.strip()
        if req.telegram_chat_id is not None:
            cfg["telegram_chat_id"] = req.telegram_chat_id.strip()
        if req.new_pin is not None and req.new_pin.strip():
            if len(req.new_pin.strip()) < 4:
                raise HTTPException(status_code=400, detail="El nuevo PIN debe tener al menos 4 dígitos.")
            cfg["pin_hash"] = hash_pin(req.new_pin.strip())
        storage.save_account_config(cfg)

        if any(
            v is not None
            for v in (req.gemini_api_key, req.telegram_bot_token, req.telegram_bot_username)
        ):
            update_runtime_credentials(
                gemini_api_key=req.gemini_api_key,
                telegram_bot_token=req.telegram_bot_token,
                telegram_bot_username=req.telegram_bot_username,
                telegram_chat_id=req.telegram_chat_id,
                persist_env=True,
            )

        return {"ok": True, "state": _build_full_state()}

    # ------------------------------------------------------------------
    # Telegram Deep-Link, Webhook & Level 2 Preventive Warning
    # ------------------------------------------------------------------
    @app.post("/api/telegram/verify")
    def telegram_verify() -> Dict[str, Any]:
        res = telegram.verify_bot()
        cfg = storage.load_account_config()
        deep = telegram.get_deep_link_info(
            link_code=cfg.get("telegram_link_code", "MV-1000"),
            chat_id=cfg.get("telegram_chat_id", ""),
        )
        return {"ok": True, "verification": res, "telegram_status": deep}

    @app.post("/api/telegram/discover-chat")
    def telegram_discover_chat() -> Dict[str, Any]:
        cfg = storage.load_account_config()
        code = cfg.get("telegram_link_code") or generate_link_code()
        res = telegram.discover_chat_id(code)
        if res.get("found") and res.get("chat_id"):
            cfg["telegram_chat_id"] = res["chat_id"]
            storage.save_account_config(cfg)
            pid = cfg.get("active_profile_id", "don_manuel")
            profile = storage.load_profile(pid)
            profile.setdefault("contacto_emergencia_telegram", {})["chat_id"] = res["chat_id"]
            storage.save_profile(profile, pid)
        return {"ok": bool(res.get("found")), "result": res, "state": _build_full_state()}

    @app.post("/api/telegram/webhook")
    async def telegram_webhook(request: Request) -> Dict[str, Any]:
        payload = await request.json()
        parsed = telegram.extract_chat_from_webhook(payload)
        cfg = storage.load_account_config()
        if parsed["chat_id"] and (
            not parsed["code"] or parsed["code"].upper() == cfg.get("telegram_link_code", "").upper()
        ):
            cfg["telegram_chat_id"] = parsed["chat_id"]
            storage.save_account_config(cfg)
            return {"ok": True, "linked_chat_id": parsed["chat_id"]}
        return {"ok": True, "ignored": True}

    @app.post("/api/telegram/level2-warning")
    def telegram_level2_warning() -> Dict[str, Any]:
        cfg = storage.load_account_config()
        pid = cfg.get("active_profile_id", "don_manuel")
        profile = storage.load_profile(pid)
        days = db.get_longitudinal_days(pid)
        ev = evaluate_longitudinal_trend(days)
        log_entry = telegram.send_level2_preventive_warning(
            profile_id=pid,
            elder_name=profile["paciente"]["nombre_preferido"],
            evaluation=ev,
            chat_id=cfg.get("telegram_chat_id", ""),
            sync=True,
        )
        return {"ok": True, "telegram_event": log_entry, "state": _build_full_state()}

    # ------------------------------------------------------------------
    # Clinical PDF Report Download
    # ------------------------------------------------------------------
    @app.get("/api/report/pdf")
    def download_clinical_pdf() -> Response:
        pid = _active_profile_id()
        profile = storage.load_profile(pid)
        days = db.get_longitudinal_days(pid)
        ev = evaluate_longitudinal_trend(days)
        reviews = db.get_clinical_reviews(pid, limit=30)
        turns = db.get_recent_turns(pid, limit=20)
        consents = db.get_consent_events(pid)

        pdf_bytes = generate_clinical_pdf_bytes(
            profile=profile,
            history_days=days,
            evaluation=ev,
            clinical_reviews=reviews,
            recent_turns=turns,
            consent_events=consents,
        )
        filename = f"Reporte_MemoriaViva_{pid}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ------------------------------------------------------------------
    # Demo Rehearsal Reset & Full Onboarding Reset
    # ------------------------------------------------------------------
    @app.post("/api/demo/reset")
    def reset_demo_rehearsal() -> Dict[str, Any]:
        """Reset Don Manuel's 21-day seed, turns, reviews and learned facts for pitch rehearsals."""
        pid = _active_profile_id()
        db.reset_demo_state(pid)
        if pid == "don_manuel":
            storage.reset_demo_profile()
        storage.ensure_sample_photos(pid)
        return {"ok": True, "message": "Estado demo restablecido limpiamente.", "state": _build_full_state()}

    @app.post("/api/system/reset")
    def reset_system_to_onboarding() -> Dict[str, Any]:
        pid = _active_profile_id()
        db.reset_demo_state(pid)
        cfg = storage.load_account_config()
        cfg["is_registered"] = False
        cfg["kiosk_locked"] = False
        cfg["telegram_link_code"] = generate_link_code()
        storage.save_account_config(cfg)
        return {"ok": True, "state": _build_full_state()}

    # ------------------------------------------------------------------
    # Static React Frontend (Single-Container Cloud Run Deployment)
    # ------------------------------------------------------------------
    if FRONTEND_DIST_DIR.exists():
        assets_dir = FRONTEND_DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str) -> Response:
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = FRONTEND_DIST_DIR / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            index_file = FRONTEND_DIST_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return JSONResponse({"detail": "Frontend build not found"}, status_code=404)

    return app


app = create_app()
