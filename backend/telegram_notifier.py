"""Telegram Family Bridge with Zero-BotFather UUID v4 Deep-Linking (/start <uuid>),
automatic background long-polling listener + unified webhook handler,
Bidirectional Family -> Kiosk bridge (text read aloud via Edge-TTS + live photos),
and 3-Level Triage Alerts enforcing the Abstract Summary Filter.
"""

from __future__ import annotations

import base64
import html
import io
import os
import threading
import time
from typing import Any, Dict, List, Optional

import qrcode
import requests

from backend.audio_engine import synthesize_elder_voice
from backend.config import (
    get_local_now,
    get_telegram_bot_token,
    get_telegram_bot_username,
    get_telegram_default_chat_id,
)

EMOTION_LABELS_ES: Dict[str, str] = {
    "tranquilo": "Tranquilo",
    "alegre": "Alegre",
    "nostalgico": "Nostálgico",
    "frustrado": "Frustrado",
    "crisis_desorientacion": "Crisis · desorientación",
}


def format_emotion_es(raw: str) -> str:
    key = (raw or "tranquilo").strip().lower()
    return EMOTION_LABELS_ES.get(key, key.replace("_", " ").capitalize())


def _clean_tg_first_name(raw: str) -> str:
    clean = (raw or "").strip()
    if clean.lower() in ("cuenta eliminada", "deleted account", "deleted", "none", "null"):
        return ""
    return clean


def _resolve_app_caregiver_names(cfg: Dict[str, Any], fallback_first: str = "") -> tuple[str, str]:
    """Return (display_name, voice_first_name) prioritizing the app-configured caregiver name."""
    raw_name = str(cfg.get("caregiver_name") or "").strip()
    if raw_name:
        first_pila = raw_name.split()[0].strip()
        return raw_name, first_pila or "su familiar"
    fb = _clean_tg_first_name(fallback_first)
    if fb:
        return fb, fb.split()[0].strip() or "su familiar"
    return "Familiar", "su familiar"
from backend.database import DatabaseManager


def format_signed(value: Any, decimals: int = 1) -> str:
    """Format numeric deltas/Z-scores with a single unambiguous sign (never '+-')."""
    num = float(value or 0.0)
    if abs(num) < (0.5 * (10 ** (-decimals))):
        return f"{0.0:.{decimals}f}"
    return f"{num:+.{decimals}f}"


class TelegramNotifier:
    """Handles UUID v4 deep-linking, bidirectional family messages, and 3-level clinical triage."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager()
        self._cached_bot_username: str = get_telegram_bot_username()
        self._last_update_id: int = 0
        self._updates_lock = threading.Lock()
        self._poll_stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

    @property
    def bot_token(self) -> str:
        return get_telegram_bot_token()

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def _file_url(self, file_path: str) -> str:
        return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"

    @staticmethod
    def generate_qr_base64(url: str) -> str:
        """Return a data URI PNG QR code for instant Telegram Deep-Linking."""
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    def verify_bot(self) -> Dict[str, Any]:
        """Verify centralized Telegram Bot via /getMe."""
        if not self.bot_token:
            username = self._cached_bot_username or "MemoriaVivaRISEBot"
            return {
                "connected": False,
                "mode": "preview_offline",
                "bot_username": username,
                "detail": "Token de Telegram no configurado en el servidor; operando en vista previa local.",
            }
        try:
            resp = requests.get(self._api_url("getMe"), timeout=6)
            data = resp.json()
            if resp.ok and data.get("ok"):
                username = data["result"].get("username", "")
                self._cached_bot_username = username
                return {
                    "connected": True,
                    "mode": "live",
                    "bot_username": username,
                    "bot_name": data["result"].get("first_name", "MemoriaViva RISE"),
                }
            return {
                "connected": False,
                "mode": "error",
                "bot_username": self._cached_bot_username or "MemoriaVivaRISEBot",
                "detail": data.get("description", "Token inválido"),
            }
        except Exception as exc:
            return {
                "connected": False,
                "mode": "offline_error",
                "bot_username": self._cached_bot_username or "MemoriaVivaRISEBot",
                "detail": str(exc),
            }

    def get_deep_link_info(
        self,
        link_uuid: str,
        chat_id: str = "",
        link_record: Optional[Dict[str, Any]] = None,
        caregiver_name: str = "",
    ) -> Dict[str, Any]:
        """Build Zero-BotFather deep link and QR code for /start <uuid>."""
        if self.bot_token and not self._cached_bot_username:
            # Resolve real bot username lazily once when token is available
            self.verify_bot()
        username = self._cached_bot_username or get_telegram_bot_username() or "MemoriaVivaRISEBot"
        clean_uuid = (link_record or {}).get("link_uuid") or link_uuid
        deep_link = f"https://t.me/{username}?start={clean_uuid}"
        record_chat = (link_record or {}).get("chat_id") or ""
        effective_chat = record_chat or chat_id or get_telegram_default_chat_id()
        status = (link_record or {}).get("status") or ("paired" if effective_chat else "pending")
        linked = status == "paired" or bool(effective_chat)
        app_owner = caregiver_name.strip()
        raw_tg_name = _clean_tg_first_name((link_record or {}).get("telegram_first_name") or "")
        linked_user_name = app_owner or raw_tg_name or "Familiar"
        return {
            "bot_configured": bool(self.bot_token),
            "bot_username": username,
            "link_uuid": clean_uuid,
            "link_code": clean_uuid,
            "status": "paired" if linked else "pending",
            "linked_user_name": linked_user_name,
            "deep_link": deep_link,
            "qr_base64": self.generate_qr_base64(deep_link),
            "chat_id": effective_chat,
            "linked": linked,
        }

    def _download_telegram_photo_bytes(self, file_id: str) -> Optional[bytes]:
        """Download highest-resolution Telegram photo bytes via getFile."""
        if not self.bot_token or not file_id:
            return None
        try:
            r_meta = requests.get(self._api_url("getFile"), params={"file_id": file_id}, timeout=8)
            meta = r_meta.json()
            if not r_meta.ok or not meta.get("ok"):
                return None
            file_path = meta["result"].get("file_path")
            if not file_path:
                return None
            r_bin = requests.get(self._file_url(file_path), timeout=12)
            return r_bin.content if r_bin.ok and r_bin.content else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Unified Incoming Update Processor (Polling Listener + Webhook)
    # ------------------------------------------------------------------
    def process_incoming_update(
        self,
        update: Dict[str, Any],
        storage: Any,
        tts_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Process a single Telegram update:
        1. Strict UUID v4 /start <uuid> pairing (pending -> paired, zero cross-user hijacking).
        2. Bidirectional inbound text or photo from authorized paired chat_id -> Elder Kiosk.
        """
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return {"handled": False, "action": "ignored_non_message"}

        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id") or "").strip()
        if not chat_id:
            return {"handled": False, "action": "missing_chat_id"}

        from_user = msg.get("from") or {}
        raw_tg_first = str(from_user.get("first_name") or chat.get("first_name") or "").strip()
        first_name = _clean_tg_first_name(raw_tg_first) or "Familiar"
        username = str(from_user.get("username") or chat.get("username") or "").strip()
        text = str(msg.get("text") or "").strip()
        caption = str(msg.get("caption") or "").strip()

        # Case 1: Deep-Link Pairing `/start <uuid>`
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            payload_uuid = parts[1].strip() if len(parts) == 2 else ""
            if not payload_uuid:
                self._send_raw_message(
                    chat_id,
                    "Para vincular tu celular de forma segura, escanea el código QR dentro de MemoriaViva RISE y pulsa Iniciar.",
                )
                return {"handled": False, "action": "start_without_uuid"}

            paired = self.db.pair_telegram_link(
                link_uuid=payload_uuid,
                chat_id=chat_id,
                first_name=first_name,
                username=username,
            )
            if not paired:
                self._send_raw_message(
                    chat_id,
                    "Ese enlace de vinculación no es válido o ya expiró. Genera un nuevo código QR en MemoriaViva RISE.",
                )
                return {"handled": False, "action": "invalid_or_revoked_uuid", "uuid": payload_uuid}

            pid = paired["profile_id"]
            profile = storage.load_profile(pid)
            elder_name = profile.get("paciente", {}).get("nombre_preferido", "su familiar")
            profile.setdefault("contacto_emergencia_telegram", {})["chat_id"] = chat_id
            storage.save_profile(profile, pid)

            cfg = storage.load_account_config()
            if cfg.get("active_profile_id") == pid:
                cfg["telegram_chat_id"] = chat_id
                cfg["telegram_link_code"] = paired["link_uuid"]
                storage.save_account_config(cfg)

            display_owner, _ = _resolve_app_caregiver_names(cfg, fallback_first=first_name)
            safe_first = html.escape(display_owner)
            safe_elder = html.escape(elder_name)
            self._send_raw_message(
                chat_id,
                f"<b>¡Hola {safe_first}!</b> Tu celular ha quedado vinculado con la estación de <b>{safe_elder}</b>.\n"
                "Aquí recibirás resúmenes breves y también puedes enviar recados o fotografías que aparecerán en su marco digital.",
            )
            self.db.insert_telegram_log(
                profile_id=pid,
                level=1,
                title=f"Celular vinculado: {display_owner}",
                message=f"Emparejamiento automático exitoso por UUID ({paired['link_uuid'][:8]}...).",
                delivered=True,
                channel_status="delivered_telegram",
            )
            return {
                "handled": True,
                "action": "paired",
                "profile_id": pid,
                "link_uuid": paired["link_uuid"],
                "chat_id": chat_id,
                "first_name": first_name,
            }

        # Case 2: Bidirectional Family -> Elder Kiosk (only authorized paired chat_ids)
        paired_links = self.db.get_paired_links_by_chat_id(chat_id)
        if not paired_links:
            return {"handled": False, "action": "unauthorized_chat_ignored"}

        link = paired_links[0]
        pid = link["profile_id"]
        profile = storage.load_profile(pid)
        elder_name = profile.get("paciente", {}).get("nombre_preferido", "Don Manuel")
        cfg = storage.load_account_config()
        voice_gender = cfg.get("voice_gender", "male")
        sender_display, sender_voice = _resolve_app_caregiver_names(
            cfg, fallback_first=str(link.get("telegram_first_name") or first_name)
        )

        # Subcase 2A: Family sent a Photo
        photos = msg.get("photo")
        if isinstance(photos, list) and len(photos) > 0:
            best_photo = photos[-1]
            raw_bytes = best_photo.get("_test_bytes") or self._download_telegram_photo_bytes(
                str(best_photo.get("file_id") or "")
            )
            if raw_bytes:
                short_caption = (
                    caption[:280].rstrip() + "…" if len(caption) > 280 else caption
                )
                photo_title = f"Foto enviada por {sender_display}"
                photo_caption = short_caption or f"Recuerdo recién compartido por {sender_display} desde Telegram."
                saved = storage.save_uploaded_photo(
                    original_filename=f"telegram_{sender_voice}.jpg",
                    raw_bytes=raw_bytes,
                    profile_id=pid,
                    title=photo_title,
                    caption=photo_caption,
                    theme="familia_hogar",
                )
                spoken_text = (
                    f"{elder_name}, {sender_voice} le acaba de enviar una nueva foto familiar. "
                    + (f"Dice: {short_caption}" if short_caption else "Mire qué bonito recuerdo llegó a su marco.")
                )
                audio_uri = synthesize_elder_voice(spoken_text, voice_gender=voice_gender, enabled=tts_enabled)
                inbound = self.db.insert_inbound_family_message(
                    profile_id=pid,
                    link_uuid=link["link_uuid"],
                    sender_name=sender_display,
                    message_type="photo",
                    text_content=spoken_text,
                    photo_filename=saved["filename"],
                    audio_data_uri=audio_uri,
                )
                self.db.insert_telegram_log(
                    profile_id=pid,
                    level=1,
                    title=f"Foto recibida de {sender_display} → Kiosco",
                    message=photo_caption,
                    delivered=True,
                    channel_status="delivered_telegram",
                )
                self._send_raw_message(
                    chat_id,
                    f"Fotografía agregada al álbum y enviada al marco digital de <b>{html.escape(elder_name)}</b>.",
                )
                return {
                    "handled": True,
                    "action": "inbound_photo",
                    "profile_id": pid,
                    "inbound_message": inbound,
                    "photo": saved,
                }

        # Subcase 2B: Family sent a Text Message
        if text:
            short_text = text[:280].rstrip() + "…" if len(text) > 280 else text
            spoken_text = f"Recado de {sender_voice}: {short_text}"
            audio_uri = synthesize_elder_voice(spoken_text, voice_gender=voice_gender, enabled=tts_enabled)
            inbound = self.db.insert_inbound_family_message(
                profile_id=pid,
                link_uuid=link["link_uuid"],
                sender_name=sender_display,
                message_type="text",
                text_content=spoken_text,
                photo_filename=None,
                audio_data_uri=audio_uri,
            )
            self.db.insert_telegram_log(
                profile_id=pid,
                level=1,
                title=f"Recado de {sender_display} → Kiosco",
                message=short_text,
                delivered=True,
                channel_status="delivered_telegram",
            )
            self._send_raw_message(
                chat_id,
                f"Recado enviado a la pantalla de <b>{html.escape(elder_name)}</b> para leerse en voz alta.",
            )
            return {
                "handled": True,
                "action": "inbound_text",
                "profile_id": pid,
                "inbound_message": inbound,
            }

        return {"handled": False, "action": "unsupported_message_type"}

    def discover_chat_id(self, link_uuid: str, storage: Any = None) -> Dict[str, Any]:
        """Check pairing status by strict UUID v4 without triggering HTTP 409 getUpdates collisions.

        If the background polling thread is alive, read directly from SQLite (updated continuously
        by the listener). Only call getUpdates (under _updates_lock) when background polling is off.
        """
        if not self.bot_token:
            return {
                "found": False,
                "chat_id": "",
                "detail": "Configura TELEGRAM_BOT_TOKEN en .env o en Configuración Avanzada para vincular un celular real.",
            }

        listener_alive = bool(self._poll_thread and self._poll_thread.is_alive())
        if not listener_alive:
            try:
                with self._updates_lock:
                    params: Dict[str, Any] = {"limit": 30}
                    if self._last_update_id > 0:
                        params["offset"] = self._last_update_id + 1
                    resp = requests.get(self._api_url("getUpdates"), params=params, timeout=8)
                    data = resp.json()
                    if not resp.ok or not data.get("ok"):
                        return {
                            "found": False,
                            "chat_id": "",
                            "detail": data.get("description", "No se pudo consultar getUpdates"),
                        }
                    updates = data.get("result") or []
                    for upd in updates:
                        uid = int(upd.get("update_id", 0))
                        if uid > self._last_update_id:
                            self._last_update_id = uid
                        if storage is not None:
                            self.process_incoming_update(upd, storage=storage)
            except Exception as exc:
                return {"found": False, "chat_id": "", "detail": f"Error de red: {exc}"}

        link = self.db.get_telegram_link_by_uuid(link_uuid)
        if link and link.get("status") == "paired" and link.get("chat_id"):
            app_owner = ""
            if storage is not None:
                try:
                    cfg = storage.load_account_config()
                    if cfg.get("is_registered"):
                        app_owner = str(cfg.get("caregiver_name") or "").strip()
                except Exception:
                    pass
            who = app_owner or _clean_tg_first_name(str(link.get("telegram_first_name") or "")) or "Familiar"
            return {
                "found": True,
                "chat_id": link["chat_id"],
                "user_label": who,
                "detail": f"Vinculado automáticamente con {who} (UUID {link_uuid[:8]}...).",
            }
        return {
            "found": False,
            "chat_id": "",
            "detail": "Esperando escaneo del QR único. Abre el enlace en Telegram y pulsa Iniciar.",
        }

    # ------------------------------------------------------------------
    # Background Long-Polling Listener Thread (Zero-Click Pairing + Inbound)
    # ------------------------------------------------------------------
    def start_background_polling(self, storage: Any) -> None:
        """Start lightweight daemon thread polling getUpdates for automatic pairing & inbound bridge."""
        if os.getenv("MV_DISABLE_TG_POLLING", "0") == "1":
            return
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_stop_event.clear()

        def _poll_loop() -> None:
            while not self._poll_stop_event.is_set():
                token = self.bot_token
                if not token:
                    self._poll_stop_event.wait(5.0)
                    continue
                try:
                    with self._updates_lock:
                        offset_val = self._last_update_id + 1 if self._last_update_id > 0 else 0
                    params: Dict[str, Any] = {
                        "timeout": 15,
                        "limit": 20,
                        "allowed_updates": '["message"]',
                    }
                    if offset_val > 0:
                        params["offset"] = offset_val
                    resp = requests.get(self._api_url("getUpdates"), params=params, timeout=22)
                    if resp.status_code == 409:
                        # Webhook is configured on this bot; yield cleanly without spamming
                        self._poll_stop_event.wait(30.0)
                        continue
                    data = resp.json()
                    if resp.ok and data.get("ok"):
                        for upd in data.get("result") or []:
                            uid = int(upd.get("update_id", 0))
                            with self._updates_lock:
                                if uid > self._last_update_id:
                                    self._last_update_id = uid
                            try:
                                self.process_incoming_update(upd, storage=storage)
                            except Exception:
                                pass
                    else:
                        self._poll_stop_event.wait(4.0)
                except Exception:
                    self._poll_stop_event.wait(4.0)

        self._poll_thread = threading.Thread(
            target=_poll_loop,
            name="telegram-uuid-listener",
            daemon=True,
        )
        self._poll_thread.start()

    def stop_background_polling(self) -> None:
        self._poll_stop_event.set()

    def _send_raw_message(self, chat_id: str, text: str) -> tuple[bool, str]:
        if not self.bot_token or not chat_id:
            return False, "local_preview"
        try:
            resp = requests.post(
                self._api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=6,
            )
            if resp.ok and resp.json().get("ok"):
                return True, "delivered_telegram"
            return False, f"telegram_error_{resp.status_code}"
        except Exception:
            return False, "network_fallback"

    def _queue_and_dispatch(
        self,
        profile_id: str,
        level: int,
        title: str,
        body: str,
        html_text: str,
        chat_id: str = "",
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Persist Telegram log immediately and dispatch HTTP POST (sync for parallel Cloud Run turns)."""
        link = self.db.get_active_telegram_link(profile_id)
        linked_chat = link["chat_id"] if (link and link.get("status") == "paired") else ""
        effective_chat = linked_chat or chat_id or get_telegram_default_chat_id()
        has_live_channel = bool(self.bot_token and effective_chat)
        initial_status = "queued_async" if has_live_channel else "local_preview"

        log_entry = self.db.insert_telegram_log(
            profile_id=profile_id,
            level=level,
            title=title,
            message=body,
            delivered=False,
            channel_status=initial_status,
        )

        if has_live_channel:
            log_id = int(log_entry["id"])

            def _worker() -> None:
                delivered, status = self._send_raw_message(effective_chat, html_text)
                try:
                    self.db.update_telegram_log_status(log_id, delivered, status)
                except Exception:
                    pass

            if sync:
                _worker()
                latest = next(
                    (x for x in self.db.get_telegram_logs(profile_id, limit=5) if x["id"] == log_id),
                    log_entry,
                )
                return latest

            threading.Thread(
                target=_worker,
                name=f"tg-alert-L{level}-{log_id}",
                daemon=True,
            ).start()

        return log_entry

    # ------------------------------------------------------------------
    # 3-Level Clinical Triage Alerts (Abstract Summary Filter enforced)
    # ------------------------------------------------------------------
    def send_level1_daily_pulse(
        self,
        profile_id: str,
        elder_name: str,
        emotional_state: str,
        topic_summary: str,
        dinner_tip: str,
        chat_id: str = "",
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Level 1 (Green): Warm daily pulse without raw transcript or audio."""
        title = f"Nivel 1 · Pulso Diario de {elder_name}"
        body = (
            f"Estado emocional: {format_emotion_es(emotional_state)}.\n"
            f"Resumen (Filtro de Privacidad): {topic_summary}\n"
            f"Sugerencia familiar: {dinner_tip}"
        )
        safe_name = html.escape(elder_name)
        safe_body = html.escape(body)
        return self._queue_and_dispatch(
            profile_id=profile_id,
            level=1,
            title=title,
            body=body,
            html_text=f"<b>[Nivel 1 - Pulso Diario] {safe_name}</b>\n{safe_body}",
            chat_id=chat_id,
            sync=sync,
        )

    def send_level2_preventive_warning(
        self,
        profile_id: str,
        elder_name: str,
        evaluation: Dict[str, Any],
        chat_id: str = "",
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Level 2 (Amber): Non-diagnostic longitudinal trend warning."""
        title = f"Nivel 2 · Aviso Preventivo de Tendencia ({elder_name})"
        recent_mattr = float(evaluation.get("recent_mattr_mean", 0.0))
        base_mattr = float(evaluation.get("baseline_mattr_mean", 0.0))
        mattr_pct = format_signed(evaluation.get("delta_mattr_pct_display", 0), 1)
        z_mattr = format_signed(evaluation.get("z_mattr", 0), 2)
        recent_pause = float(evaluation.get("recent_pause_mean", 0.0))
        base_pause = float(evaluation.get("baseline_pause_mean", 0.0))
        pause_pct = format_signed(evaluation.get("delta_pause_pct_display", 0), 1)
        z_pause = format_signed(evaluation.get("z_pause", 0), 2)
        body = (
            f"Se detectó una variación sostenida frente a la línea base personal (D1-D14): "
            f"MATTR {mattr_pct}% ({recent_mattr:.3f} vs base {base_mattr:.3f}, Z={z_mattr}), "
            f"Pausas {pause_pct}% ({recent_pause:.2f} s vs base {base_pause:.2f} s, Z={z_pause}).\n"
            "Aviso de apoyo clínico no diagnóstico: revisa variables de confusión (sueño, medicación, Sundowning) "
            "en Gobernanza RISE y comparte el PDF con su geriatra si persiste."
        )
        safe_name = html.escape(elder_name)
        safe_body = html.escape(body)
        return self._queue_and_dispatch(
            profile_id=profile_id,
            level=2,
            title=title,
            body=body,
            html_text=f"<b>[Nivel 2 - Aviso Preventivo] {safe_name}</b>\n{safe_body}",
            chat_id=chat_id,
            sync=sync,
        )

    def send_level3_sos_crisis(
        self,
        profile_id: str,
        elder_name: str,
        reason: str,
        dinner_tip: str,
        chat_id: str = "",
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Level 3 (Red): Immediate S.O.S. alert upon acute disorientation or distress."""
        now_hhmm = get_local_now().strftime("%H:%M")
        title = f"Nivel 3 · ALERTA ROJA S.O.S. ({elder_name})"
        body = (
            f"Hora local: {now_hhmm}\n"
            f"Motivo: {reason}\n"
            "Acción tomada: MemoriaViva suspendió preguntas cognitivas y aplicó Contención por Validación de Naomi Feil.\n"
            f"Acción recomendada: {dinner_tip}"
        )
        safe_name = html.escape(elder_name)
        safe_body = html.escape(body)
        return self._queue_and_dispatch(
            profile_id=profile_id,
            level=3,
            title=title,
            body=body,
            html_text=f"<b>[ALERTA ROJA S.O.S. - NIVEL 3] {safe_name}</b>\n{safe_body}",
            chat_id=chat_id,
            sync=sync,
        )
