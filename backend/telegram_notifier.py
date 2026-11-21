"""Telegram Family Bridge with Zero-BotFather Deep-Linking (/start MV-XXXX),
QR generation, on-demand /getUpdates discovery, optional webhook handling,
and 3-Level Triage Alerts enforcing the Abstract Summary Filter.
"""

from __future__ import annotations

import base64
import io
from typing import Any, Dict, Optional

import qrcode
import requests

from backend.config import (
    get_telegram_bot_token,
    get_telegram_bot_username,
    get_telegram_default_chat_id,
)
from backend.database import DatabaseManager


class TelegramNotifier:
    """Handles Telegram deep-linking and non-intrusive 3-level clinical triage alerts."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager()
        self._cached_bot_username: str = get_telegram_bot_username()

    @property
    def bot_token(self) -> str:
        return get_telegram_bot_token()

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

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

    def get_deep_link_info(self, link_code: str, chat_id: str = "") -> Dict[str, Any]:
        """Build Zero-BotFather deep link and QR code for /start MV-XXXX."""
        username = self._cached_bot_username or get_telegram_bot_username() or "MemoriaVivaRISEBot"
        deep_link = f"https://t.me/{username}?start={link_code}"
        effective_chat = chat_id or get_telegram_default_chat_id()
        return {
            "bot_configured": bool(self.bot_token),
            "bot_username": username,
            "link_code": link_code,
            "deep_link": deep_link,
            "qr_base64": self.generate_qr_base64(deep_link),
            "chat_id": effective_chat,
            "linked": bool(effective_chat),
        }

    def discover_chat_id(self, link_code: str) -> Dict[str, Any]:
        """Poll /getUpdates on demand to match `/start MV-XXXX` and auto-bind caregiver chat_id."""
        if not self.bot_token:
            return {
                "found": False,
                "chat_id": "",
                "detail": "Configura TELEGRAM_BOT_TOKEN en .env o en Configuración Avanzada para vincular un celular real.",
            }
        try:
            resp = requests.get(self._api_url("getUpdates"), params={"limit": 30}, timeout=8)
            data = resp.json()
            if not resp.ok or not data.get("ok"):
                return {
                    "found": False,
                    "chat_id": "",
                    "detail": data.get("description", "No se pudo consultar getUpdates"),
                }

            updates = data.get("result") or []
            matched_chat: Optional[str] = None
            matched_user: str = ""

            # 1. Exact deep-link match `/start MV-XXXX`
            for upd in reversed(updates):
                msg = upd.get("message") or upd.get("edited_message") or {}
                text = str(msg.get("text") or "").strip()
                chat = msg.get("chat") or {}
                if link_code.lower() in text.lower() and chat.get("id"):
                    matched_chat = str(chat["id"])
                    matched_user = chat.get("first_name") or chat.get("username") or "Familiar"
                    break

            # 2. Fallback to most recent /start message if user tapped Iniciar without param
            if not matched_chat:
                for upd in reversed(updates):
                    msg = upd.get("message") or {}
                    chat = msg.get("chat") or {}
                    if chat.get("id"):
                        matched_chat = str(chat["id"])
                        matched_user = chat.get("first_name") or chat.get("username") or "Familiar"
                        break

            if matched_chat:
                self._send_raw_message(
                    matched_chat,
                    f"MemoriaViva RISE vinculado correctamente ({link_code}). "
                    "Recibirás resúmenes breves y avisos respetando la privacidad de tu familiar.",
                )
                return {
                    "found": True,
                    "chat_id": matched_chat,
                    "user_label": matched_user,
                    "detail": f"Vinculado automáticamente con {matched_user} (Chat ID {matched_chat}).",
                }
            return {
                "found": False,
                "chat_id": "",
                "detail": "Aún no recibimos tu mensaje /start. Escanea el QR, pulsa Iniciar en Telegram y vuelve a intentar.",
            }
        except Exception as exc:
            return {"found": False, "chat_id": "", "detail": f"Error de red: {exc}"}

    def extract_chat_from_webhook(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Parse an incoming Telegram webhook update for `/start MV-XXXX` deep-link binding."""
        msg = payload.get("message") or {}
        text = str(msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        code = ""
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                code = parts[1].strip()
        return {"chat_id": chat_id, "code": code, "first_name": str(chat.get("first_name") or "")}

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
    ) -> Dict[str, Any]:
        """Level 1 (Green): Warm daily pulse without raw transcript or audio."""
        title = f"Nivel 1 · Pulso Diario de {elder_name}"
        body = (
            f"Estado emocional: {emotional_state.replace('_', ' ').capitalize()}.\n"
            f"Resumen (Filtro de Privacidad): {topic_summary}\n"
            f"Sugerencia para la cena: {dinner_tip}"
        )
        effective_chat = chat_id or get_telegram_default_chat_id()
        delivered, status = self._send_raw_message(
            effective_chat,
            f"<b>[Nivel 1 - Pulso Diario] {elder_name}</b>\n{body}",
        )
        return self.db.insert_telegram_log(
            profile_id=profile_id,
            level=1,
            title=title,
            message=body,
            delivered=delivered,
            channel_status=status,
        )

    def send_level2_preventive_warning(
        self,
        profile_id: str,
        elder_name: str,
        evaluation: Dict[str, Any],
        chat_id: str = "",
    ) -> Dict[str, Any]:
        """Level 2 (Amber): Non-diagnostic longitudinal trend warning."""
        title = f"Nivel 2 · Aviso Preventivo de Tendencia ({elder_name})"
        body = (
            f"Se detectó una variación sostenida frente a la línea base personal (D1-D14): "
            f"MATTR {evaluation.get('delta_mattr_pct_display', 0)}% (Z={evaluation.get('z_mattr', 0)}), "
            f"Pausas +{evaluation.get('delta_pause_pct_display', 0)}% (Z={evaluation.get('z_pause', 0)}).\n"
            "Aviso de apoyo clínico no diagnóstico: revisa variables de confusión (sueño, medicación, Sundowning) "
            "en Gobernanza RISE y comparte el PDF con su geriatra si persiste."
        )
        effective_chat = chat_id or get_telegram_default_chat_id()
        delivered, status = self._send_raw_message(
            effective_chat,
            f"<b>[Nivel 2 - Aviso Preventivo] {elder_name}</b>\n{body}",
        )
        return self.db.insert_telegram_log(
            profile_id=profile_id,
            level=2,
            title=title,
            message=body,
            delivered=delivered,
            channel_status=status,
        )

    def send_level3_sos_crisis(
        self,
        profile_id: str,
        elder_name: str,
        reason: str,
        dinner_tip: str,
        chat_id: str = "",
    ) -> Dict[str, Any]:
        """Level 3 (Red): Immediate S.O.S. alert upon acute disorientation or distress."""
        title = f"Nivel 3 · ALERTA ROJA S.O.S. ({elder_name})"
        body = (
            f"Motivo: {reason}\n"
            "Acción tomada: MemoriaViva suspendió preguntas cognitivas y aplicó Contención por Validación de Naomi Feil.\n"
            f"Acción recomendada: {dinner_tip}"
        )
        effective_chat = chat_id or get_telegram_default_chat_id()
        delivered, status = self._send_raw_message(
            effective_chat,
            f"<b>[ALERTA ROJA S.O.S. - NIVEL 3] {elder_name}</b>\n{body}",
        )
        return self.db.insert_telegram_log(
            profile_id=profile_id,
            level=3,
            title=title,
            message=body,
            delivered=delivered,
            channel_status=status,
        )
