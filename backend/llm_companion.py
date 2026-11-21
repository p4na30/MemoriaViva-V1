"""Gerontological Conversational Companion: Reminiscence Therapy + Naomi Feil Validation
+ Biographical RAG-Lite + Bidirectional Visual Anchor Theme Classification.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from backend.config import (
    MAX_ASSISTANT_WORDS,
    MEMORY_ALBUM_THEMES,
    get_gemini_api_key,
    get_gemini_model_chain,
    mark_model_unavailable,
)

logger = logging.getLogger("memoriaviva.llm")

_LAST_GEMINI_DIAGNOSTICS: Dict[str, Optional[str]] = {
    "last_model": None,
    "last_error": None,
}


def _sanitize_gemini_error(exc: Exception, api_key: str = "") -> str:
    """Return a concise, secret-free diagnostic string for /api/health and Cloud Run logs."""
    msg = str(exc).replace("\n", " ").strip()
    if api_key:
        msg = msg.replace(api_key, "[REDACTED]")
    msg = re.sub(r"AIza[0-9A-Za-z\-_]{10,}", "[REDACTED_KEY]", msg)
    if len(msg) > 180:
        msg = msg[:177] + "..."
    return f"{type(exc).__name__}: {msg}"


def get_gemini_diagnostics() -> Dict[str, Optional[str]]:
    """Return non-sensitive last Gemini model and error diagnostics."""
    return dict(_LAST_GEMINI_DIAGNOSTICS)


class CompanionStructuredOutput(BaseModel):
    assistant_reply: str = Field(..., description="Warm, direct geriatric reply (<=35 words)")
    emotional_state: str = Field(default="tranquilo")
    emergency_triggered: bool = Field(default=False)
    emergency_reason: Optional[str] = Field(default=None)
    biographical_rescue_triggered: bool = Field(default=False)
    rescued_entity: Optional[str] = Field(default=None)
    conversation_topic_summary: str = Field(default="Plática cálida de reminiscencia familiar")
    dinner_conversation_tip: str = Field(
        default="Pregúntale en la cena qué recuerdo bonito le vino a la mente hoy."
    )
    new_biographical_facts: List[str] = Field(default_factory=list)
    memory_album_theme: str = Field(default="familia_hogar")


CRISIS_KEYWORDS = [
    "no sé qué hago aquí",
    "no se que hago aqui",
    "no conozco esta casa",
    "me quiero ir a mi casa",
    "muy mareado",
    "asustado",
    "asustada",
    "tengo miedo",
    "me duele el pecho",
    "no puedo respirar",
    "me caí",
    "me cai",
    "auxilio",
    "socorro",
    "dónde estoy",
    "donde estoy",
]

UNDIGNIFIED_REPLY_PATTERNS = [
    r"\botra\s+vez\b",
    r"\bde\s+nuevo\b",
    r"\bnuevamente\b",
    r"ya\s+me\s+(?:lo\s+)?(?:hab[ií]a|dijo|cont[oó])",
    r"no\s+se\s+acuerda",
    r"se\s+le\s+olvid[oó]",
    r"lo\s+(?:est[aá]\s+)?repit",
    r"como\s+ya\s+(?:dijimos|hablamos|me\s+cont)",
    r"est[aá]\s+confundid[oa]",
]

UNSAFE_MEDICAL_REPLY_PATTERNS = [
    r"t[oó]m(?:ese|e)\s+(?:otra|dos|doble|media|una)\s+(?:pastilla|dosis|c[aá]psula|tableta)",
    r"duplique\s+la\s+dosis",
    r"suspenda\s+(?:su|el)\s+medicamento",
    r"(?:usted\s+)?tiene\s+(?:alzheimer|demencia|deterioro\s+cognitivo)",
]


def _contains_any_pattern(text: str, patterns: Sequence[str]) -> bool:
    low = (text or "").lower()
    return any(re.search(pat, low) for pat in patterns)


def sanitize_geriatric_reply(
    reply: str,
    user_text: str,
    profile: Dict[str, Any],
    repetition_info: Dict[str, Any],
    demo_scenario_id: Optional[str] = None,
) -> str:
    """Enforce gerontological warmth, dignity, and medical-safety guardrails on LLM text."""
    clean = enforce_word_limit(reply)
    paciente = profile.get("paciente", {})
    red = profile.get("red_familiar_y_afectiva", {})
    nombre = paciente.get("nombre_preferido", "Don Manuel")
    cuidador = red.get("hija_mayor_cuidadora", {}).get("nombre") or profile.get(
        "contacto_emergencia_telegram", {}
    ).get("nombre", "Laura")

    # 1. Hard block on pharmacological dosing or automated medical diagnosis
    if _contains_any_pattern(clean, UNSAFE_MEDICAL_REPLY_PATTERNS):
        return enforce_word_limit(
            f"Con los medicamentos prefiero que estemos bien seguros, {nombre}. "
            f"Mejor consúltelo ahorita con {cuidador} o su médico antes de cambiar cualquier toma."
        )

    # 2. Prevent abrupt/shaming repetition callouts (e.g. "¡Otra vez con ellos!", "¿No se acuerda?")
    if _contains_any_pattern(clean, UNDIGNIFIED_REPLY_PATTERNS):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        kept = [s for s in sentences if not _contains_any_pattern(s, UNDIGNIFIED_REPLY_PATTERNS)]
        rebuilt = " ".join(kept).strip()
        if len(rebuilt.split()) >= 7:
            return enforce_word_limit(rebuilt)
        safe = _deterministic_fallback_reply(
            user_text=user_text,
            profile=profile,
            repetition_info=repetition_info,
            demo_scenario_id=demo_scenario_id,
        )
        return enforce_word_limit(safe["assistant_reply"])

    return clean


def enforce_word_limit(text: str, max_words: int = MAX_ASSISTANT_WORDS) -> str:
    """Guarantee geriatric brevity (<= 35 words) without cutting mid-word."""
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).rstrip(",;:")
    if not clipped.endswith((".", "!", "?")):
        clipped += "."
    return clipped


def infer_visual_theme(text: str) -> str:
    """Infer best matching memory_album_theme from Spanish utterances."""
    low = text.lower()
    if any(k in low for k in ("perro", "sultán", "sultan", "mascota", "pastor alemán", "cachorro")):
        return "mascotas"
    if any(k in low for k in ("tren", "ferrocarril", "riel", "locomotora", "maquinista", "llave", "reloj", "jubil")):
        return "ferrocarril"
    if any(k in low for k in ("bolero", "panchos", "agustín lara", "música", "musica", "canción", "guitarra", "serenata")):
        return "musica_boleros"
    if any(k in low for k in ("playa", "manzanillo", "miramar", "mar", "cabaña", "colima", "costa")):
        return "playa_manzanillo"
    return "familia_hogar"


def build_master_prompt(
    profile: Dict[str, Any],
    recent_history: Sequence[Dict[str, Any]],
    user_text: str,
    repetition_info: Dict[str, Any],
) -> str:
    """Build the exact MemoriaViva RISE unified gerontological system+turn prompt."""
    paciente = profile.get("paciente", {})
    red = profile.get("red_familiar_y_afectiva", {})
    nombre_preferido = paciente.get("nombre_preferido", "Don Manuel")
    edad = paciente.get("edad", 72)
    ciudad = paciente.get("ciudad_residencia", "San Pedro Tlaquepaque, Jalisco")
    cuidador = red.get("hija_mayor_cuidadora", {}).get("nombre") or profile.get(
        "contacto_emergencia_telegram", {}
    ).get("nombre", "Laura")

    history_lines = []
    for h in list(recent_history)[-4:]:
        history_lines.append(f"- {nombre_preferido}: {h.get('user_text', '')}")
        history_lines.append(f"- MemoriaViva: {h.get('assistant_reply', '')}")
    history_block = "\n".join(history_lines) if history_lines else "(Inicio de sesión)"

    rep_context = (
        "REPETICIÓN DETECTADA: Responde con entusiasmo genuino como si fuera la primera vez "
        "y pide un detalle sensorial nuevo. PROHIBIDO decir 'otra vez', 'de nuevo', 'nuevamente' "
        "o insinuar que ya lo había contado antes."
        if repetition_info.get("is_repetition")
        else "Sin repetición semántica en este turno."
    )

    return f"""ERES "MEMORIAVIVA", UN COMPAÑERO CONVERSACIONAL CÁLIDO, EMPÁTICO Y REAL PARA {nombre_preferido} ({edad} AÑOS).

CONTEXTO BIOGRÁFICO ACTUAL DE {nombre_preferido} (ÚSALO SOLO COMO APOYO O SI ÉL LO MENCIONA/OLVIDA):
{json.dumps(profile, ensure_ascii=False, indent=2)}

HISTORIAL RECIENTE DE LA CONVERSACIÓN ACTUAL:
{history_block}

ESTADO DE REPETICIÓN EN ESTE TURNO: {rep_context}

MENSAJE ACTUAL DE {nombre_preferido}:
"{user_text}"

REGLAS INQUEBRANTABLES DEL MARCO RISE PARA `assistant_reply`:
1. TONO CÁLIDO Y CONVERSACIÓN REAL: Habla siempre de "usted" con ternura, respeto y paciencia (nunca seco, brusco, sarcástico ni clínico). Responde SIEMPRE de forma directa a lo que {nombre_preferido} acaba de decir sin cambiar de tema al azar.
2. BREVEDAD Y CLARIDAD GERIÁTRICA: `assistant_reply` NUNCA debe superar las 35 palabras (máximo 2 o 3 oraciones cortas). Haz SIEMPRE UNA SOLA pregunta natural relacionada con lo que acaba de contar (salvo en crisis).
3. RESCATE BIOGRÁFICO SIN EVIDENCIAR OLVIDOS: Si {nombre_preferido} titubea o no recuerda el nombre de un familiar, lugar o fecha que está en su perfil biográfico, proporciónaselo con cariño dentro de la frase. PROHIBIDO decir "¿No se acuerda?", "Se le olvidó" o "Ya me lo había dicho".
4. PACIENCIA INFINITA ANTE REPETICIONES: Si {nombre_preferido} cuenta la misma historia otra vez, escúchalo con ilusión como si fuera la primera vez y pídele un detalle sensorial nuevo. PROHIBIDO decir "otra vez", "de nuevo" o insinuar que lo repitió.
5. PROTOCOLO DE VALIDACIÓN DE FEIL (CRISIS O DESORIENTACIÓN) Y SEGURIDAD MÉDICA: Si expresa miedo, llanto, angustia, dolor físico, mareo o dice que no sabe dónde está:
   - SUSPENDE cualquier pregunta de memoria (0 signos de interrogación).
   - Valida su emoción con ternura, recuérdale que está seguro en su casa en {ciudad} y que su familiar {cuidador} ya fue avisado para llamarle.
   - PROHIBIDO emitir diagnósticos médicos o recomendar/ajustar medicamentos; ante preguntas de pastillas o dosis, deriva con cariño a {cuidador} o a su médico.
6. RETROALIMENTACIÓN Y MEMORIA VIVA (`new_biographical_facts`): Extrae cualquier dato nuevo que {nombre_preferido} mencione en este turno como frases claras para guardarlas permanentemente en su perfil JSON.

Devuelve EXCLUSIVAMENTE un objeto JSON válido con esta estructura exacta:
{{
  "assistant_reply": "Respuesta cálida, directa y contextual (máximo 35 palabras)",
  "emotional_state": "tranquilo | alegre | nostalgico | frustrado | crisis_desorientacion",
  "emergency_triggered": false,
  "emergency_reason": null,
  "biographical_rescue_triggered": false,
  "rescued_entity": null,
  "conversation_topic_summary": "Resumen cálido en 1 línea de lo que platicó hoy",
  "dinner_conversation_tip": "Sugerencia concreta de 1 pregunta para que {cuidador} le haga hoy en la cena",
  "new_biographical_facts": ["Frase(s) con datos nuevos que mencionó en este turno"],
  "memory_album_theme": "ferrocarril | musica_boleros | playa_manzanillo | familia_hogar | mascotas"
}}
"""


def _deterministic_fallback_reply(
    user_text: str,
    profile: Dict[str, Any],
    repetition_info: Dict[str, Any],
    demo_scenario_id: Optional[str] = None,
) -> Dict[str, Any]:
    """High-craft deterministic gerontological fallback (works 100% offline/without API key)."""
    paciente = profile.get("paciente", {})
    red = profile.get("red_familiar_y_afectiva", {})
    nombre = paciente.get("nombre_preferido", "Don Manuel")
    ciudad = paciente.get("ciudad_residencia", "San Pedro Tlaquepaque")
    cuidador = red.get("hija_mayor_cuidadora", {}).get("nombre") or profile.get(
        "contacto_emergencia_telegram", {}
    ).get("nombre", "Laura")
    hija_menor = red.get("hija_menor", {}).get("nombre", "Rocío")

    low = user_text.lower()

    # 1. Crisis / Acute disorientation (Naomi Feil Validation — ZERO cognitive questions)
    if demo_scenario_id == "demo_3_crisis" or any(k in low for k in CRISIS_KEYWORDS):
        reply = enforce_word_limit(
            f"Tranquilo, {nombre}, entiendo que se sienta asustado y mareado. "
            f"Respire despacito, está seguro en su casa en {ciudad} y {cuidador} ya fue avisada para llamarle ahorita."
        )
        return {
            "assistant_reply": reply,
            "emotional_state": "crisis_desorientacion",
            "emergency_triggered": True,
            "emergency_reason": "Desorientación aguda con mareo y angustia emocional; protocolo de Validación de Naomi Feil activado.",
            "biographical_rescue_triggered": False,
            "rescued_entity": None,
            "conversation_topic_summary": "Episodio de desorientación y mareo contenido con Validación de Naomi Feil.",
            "dinner_conversation_tip": f"Llamar de inmediato a {nombre} con voz serena para acompañarlo y verificar cómo se siente físicamente.",
            "new_biographical_facts": [],
            "memory_album_theme": "familia_hogar",
            "engine_used": "deterministic_fallback",
        }

    # 2. Act 1 — Biographical Rescue (Rocío) + New Fact Learning (Sultán)
    if demo_scenario_id == "demo_1_rescate" or ("sultán" in low or "sultan" in low) or (
        ("maestra" in low or "colima" in low) and ("cómo" in low or "nombre" in low or "rocío" in low)
    ):
        facts = []
        if "sultán" in low or "sultan" in low:
            facts.append("Tuvo en su casa un perro pastor alemán llamado Sultán.")
        reply = enforce_word_limit(
            f"Qué alegría que le llamara su hija {hija_menor} desde Colima, {nombre}, y qué hermoso recuerdo de su pastor alemán Sultán. "
            "¿Qué era lo más travieso que hacía Sultán en la casa?"
        )
        return {
            "assistant_reply": reply,
            "emotional_state": "alegre",
            "emergency_triggered": False,
            "emergency_reason": None,
            "biographical_rescue_triggered": True,
            "rescued_entity": hija_menor,
            "conversation_topic_summary": f"Platicó sobre la llamada de su hija {hija_menor} y recordó con cariño a su perro Sultán.",
            "dinner_conversation_tip": f"Pregúntale a {nombre} hoy en la cena qué anécdota recuerda con más cariño de su perro pastor alemán Sultán.",
            "new_biographical_facts": facts,
            "memory_album_theme": "mascotas" if facts else "playa_manzanillo",
            "engine_used": "deterministic_fallback",
        }

    # 3. Act 2 — Anomic pause + Railway work / Repetition
    if demo_scenario_id == "demo_2_anomia" or any(
        k in low for k in ("trenes", "rieles", "llave de cruz", "ferrocarril", "reloj")
    ):
        if repetition_info.get("is_repetition"):
            reply = enforce_word_limit(
                f"Me encanta escucharlo hablar con tanto orgullo de ese reloj de los ferrocarriles, {nombre}. "
                "¿Recuerda qué sonido hacían las locomotoras al salir temprano de Guadalajara?"
            )
        else:
            reply = enforce_word_limit(
                f"Qué gran oficio tenía con esa llave de cruz en los ferrocarriles de Guadalajara, {nombre}, y qué merecido ese reloj de jubilación. "
                "¿Cómo era el brillo o la correa de aquel reloj?"
            )
        return {
            "assistant_reply": reply,
            "emotional_state": "nostalgico",
            "emergency_triggered": False,
            "emergency_reason": None,
            "biographical_rescue_triggered": False,
            "rescued_entity": None,
            "conversation_topic_summary": "Evocó sus años de mecánico ferroviario en Guadalajara y su reloj de jubilación.",
            "dinner_conversation_tip": f"Pídele a {nombre} que te muestre o describa el reloj que le regalaron al jubilarse de los trenes.",
            "new_biographical_facts": [
                "Al jubilarse de Ferrocarriles Nacionales sus compañeros le regalaron un reloj especial."
            ]
            if "reloj" in low
            else [],
            "memory_album_theme": "ferrocarril",
            "engine_used": "deterministic_fallback",
        }

    # 4. General contextual reminiscence reply
    theme = infer_visual_theme(user_text)
    if theme == "musica_boleros":
        reply = enforce_word_limit(
            f"Qué hermosa música son los boleros, {nombre}, llenan la casa de bonitos recuerdos. "
            "¿Cuál canción de Los Panchos le gusta tararear más por las tardes?"
        )
        topic = "Compartió su gusto por los boleros clásicos y recuerdos musicales."
        tip = f"Pon un bolero del Trío Los Panchos hoy en la cena con {nombre} y pregúntale qué recuerdos le trae."
    elif theme == "playa_manzanillo":
        reply = enforce_word_limit(
            f"Qué bonito recordar el mar y la brisa de Manzanillo, {nombre}. "
            "¿Qué fue lo que más disfrutó la familia en aquel viaje a Playa Miramar?"
        )
        topic = "Recordó viajes familiares a la costa de Manzanillo."
        tip = f"Pregúntale a {nombre} cómo era el atardecer en las cabañas San Pedrito de Miramar."
    elif theme == "mascotas":
        reply = enforce_word_limit(
            f"Los perros siempre nos regalan una compañía inolvidable, {nombre}. "
            "¿Por dónde le gustaba salir a pasear con su mascota?"
        )
        topic = "Recordó con ternura a su mascota familiar."
        tip = f"Pregúntale a {nombre} cómo llegó su perro a la casa familiar."
    else:
        reply = enforce_word_limit(
            f"Qué gusto platicar con usted hoy, {nombre}, me encanta escuchar sus historias de casa y familia. "
            "¿Qué recuerdo bonito de esta semana le gustaría contarme ahora?"
        )
        topic = "Conversación afectiva sobre su día y recuerdos familiares."
        tip = f"Pregúntale a {nombre} en la cena qué fue lo más agradable de su tarde hoy."

    # Simple heuristic fact extraction for custom text inputs ("se llamaba X" / "mi amigo X")
    extracted: List[str] = []
    match_named = re.search(r"se llamaba\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)", user_text)
    if match_named:
        extracted.append(f"Mencionó un recuerdo especial relacionado con {match_named.group(1)}.")

    return {
        "assistant_reply": reply,
        "emotional_state": "tranquilo",
        "emergency_triggered": False,
        "emergency_reason": None,
        "biographical_rescue_triggered": False,
        "rescued_entity": None,
        "conversation_topic_summary": topic,
        "dinner_conversation_tip": tip,
        "new_biographical_facts": extracted,
        "memory_album_theme": theme,
        "engine_used": "deterministic_fallback",
    }


def _call_gemini_with_fallback(
    contents: Any,
    response_schema: Optional[Any] = None,
    temperature: float = 0.45,
) -> tuple[str, str]:
    """Invoke Gemini across the automatic fallback chain with thinking_budget=0 (< 1.5s latency).

    Tries each model in get_gemini_model_chain() (gemini-3.8-flash -> gemini-flash-latest
    -> gemini-2.5-flash). Returns (response_text, model_name_used) or ("", "") on total failure.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return "", ""

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    for model_name in get_gemini_model_chain():
        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "thinking_config": types.ThinkingConfig(thinking_budget=0),
        }
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = (response.text or "").strip()
            if text:
                _LAST_GEMINI_DIAGNOSTICS["last_model"] = model_name
                _LAST_GEMINI_DIAGNOSTICS["last_error"] = None
                return text, model_name
        except Exception as exc:
            safe_err = _sanitize_gemini_error(exc, api_key)
            _LAST_GEMINI_DIAGNOSTICS["last_error"] = f"{model_name} -> {safe_err}"
            logger.warning("Gemini model %s failed: %s", model_name, safe_err)
            err_txt = str(exc).upper()
            if "404" in err_txt or "NOT_FOUND" in err_txt or "NOT FOUND" in err_txt:
                mark_model_unavailable(model_name)
                continue
            # Immediately advance to next model on transient overload/quota errors (never re-enable thinking)
            if any(code in err_txt for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "DEADLINE", "TIMEOUT")):
                continue
            # Only retry without thinking_config if the model explicitly rejected thinking_budget=0
            if "THINKING" not in err_txt and "INVALID_ARGUMENT" not in err_txt and "400" not in err_txt:
                continue
            try:
                config_kwargs.pop("thinking_config", None)
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (response.text or "").strip()
                if text:
                    _LAST_GEMINI_DIAGNOSTICS["last_model"] = model_name
                    _LAST_GEMINI_DIAGNOSTICS["last_error"] = None
                    return text, model_name
            except Exception as exc2:
                safe_err2 = _sanitize_gemini_error(exc2, api_key)
                _LAST_GEMINI_DIAGNOSTICS["last_error"] = f"{model_name} -> {safe_err2}"
                logger.warning("Gemini model %s retry failed: %s", model_name, safe_err2)
                err_txt2 = str(exc2).upper()
                if "404" in err_txt2 or "NOT_FOUND" in err_txt2 or "NOT FOUND" in err_txt2:
                    mark_model_unavailable(model_name)
                continue

    return "", ""


def generate_companion_response(
    user_text: str,
    profile: Dict[str, Any],
    recent_history: Sequence[Dict[str, Any]],
    repetition_info: Dict[str, Any],
    demo_scenario_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke Gemini fallback chain with structured JSON output and thinking_budget=0."""
    low = user_text.lower()
    is_obvious_crisis = demo_scenario_id == "demo_3_crisis" or any(k in low for k in CRISIS_KEYWORDS)

    if get_gemini_api_key():
        try:
            prompt = build_master_prompt(profile, recent_history, user_text, repetition_info)
            raw_json, used_model = _call_gemini_with_fallback(
                contents=prompt,
                response_schema=CompanionStructuredOutput,
                temperature=0.45,
            )
            if raw_json:
                parsed = CompanionStructuredOutput.model_validate_json(raw_json).model_dump()

                # Enforce strict RISE warmth, dignity & safety guardrails on model output
                parsed["assistant_reply"] = sanitize_geriatric_reply(
                    reply=parsed["assistant_reply"],
                    user_text=user_text,
                    profile=profile,
                    repetition_info=repetition_info,
                    demo_scenario_id=demo_scenario_id,
                )
                if parsed["memory_album_theme"] not in MEMORY_ALBUM_THEMES:
                    parsed["memory_album_theme"] = infer_visual_theme(user_text)
                if is_obvious_crisis or parsed.get("emergency_triggered"):
                    parsed["emergency_triggered"] = True
                    parsed["emotional_state"] = "crisis_desorientacion"
                    # Clean Naomi Feil guardrail: if LLM slipped a question in crisis, substitute validated contention
                    if "?" in parsed["assistant_reply"] or "¿" in parsed["assistant_reply"]:
                        safe_feil = _deterministic_fallback_reply(
                            user_text=user_text,
                            profile=profile,
                            repetition_info=repetition_info,
                            demo_scenario_id="demo_3_crisis",
                        )
                        parsed["assistant_reply"] = safe_feil["assistant_reply"]
                parsed["engine_used"] = used_model
                return parsed
        except Exception as exc:
            safe_err = _sanitize_gemini_error(exc, get_gemini_api_key())
            _LAST_GEMINI_DIAGNOSTICS["last_error"] = f"parse -> {safe_err}"
            logger.warning("Gemini companion response handling failed: %s", safe_err)

    return _deterministic_fallback_reply(
        user_text=user_text,
        profile=profile,
        repetition_info=repetition_info,
        demo_scenario_id=demo_scenario_id,
    )


def generate_photo_starter(photo: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a warm Foto -> Voz reminiscence prompt for the currently displayed postcard."""
    nombre = profile.get("paciente", {}).get("nombre_preferido", "Don Manuel")
    title = photo.get("title", "esta fotografía")
    caption = photo.get("caption", "")
    theme = photo.get("theme", "familia_hogar")

    if get_gemini_api_key():
        try:
            prompt = (
                f"Eres MemoriaViva, compañero cálido para {nombre}. "
                f"Está viendo en su marco digital la foto '{title}' ({caption}). "
                "Escribe un saludo breve y cariñoso (máximo 28 palabras) con UNA SOLA pregunta "
                "abierta para invitarlo a recordar esa imagen sin presionarlo. Solo texto plano."
            )
            raw_text, used_model = _call_gemini_with_fallback(
                contents=prompt,
                response_schema=None,
                temperature=0.5,
            )
            text = enforce_word_limit(raw_text, max_words=35) if raw_text else ""
            if text:
                return {
                    "assistant_reply": text,
                    "memory_album_theme": theme,
                    "conversation_topic_summary": f"Inicio de reminiscencia visual sobre '{title}'.",
                    "engine_used": used_model,
                }
        except Exception:
            pass

    fallbacks = {
        "ferrocarril": f"Mire qué postal tan especial de {title}, {nombre}. ¿Qué es lo primero que recuerda de sus días trabajando entre trenes?",
        "musica_boleros": f"Qué linda imagen de {title}, {nombre}. ¿Qué bolero le gustaría escuchar ahora mismo mientras vemos esta postal?",
        "playa_manzanillo": f"Qué atardecer tan bonito en {title}, {nombre}. ¿Recuerda cómo se sentía la brisa del mar en aquel viaje familiar?",
        "mascotas": f"Qué compañero tan noble se ve en {title}, {nombre}. ¿Qué travesura o paseo recuerda con más cariño?",
        "familia_hogar": f"Qué bonita postal de {title}, {nombre}. ¿Qué anécdota alegre de la familia le viene a la mente al verla?",
    }
    return {
        "assistant_reply": enforce_word_limit(fallbacks.get(theme, fallbacks["familia_hogar"])),
        "memory_album_theme": theme,
        "conversation_topic_summary": f"Reminiscencia guiada a partir de la fotografía '{title}'.",
        "engine_used": "deterministic_fallback",
    }


def generate_consent_greeting(profile: Dict[str, Any]) -> str:
    """Warm, transparent Assisted Dual Consent spoken greeting for the elder."""
    nombre = profile.get("paciente", {}).get("nombre_preferido", "Don Manuel")
    cuidador = profile.get("red_familiar_y_afectiva", {}).get("hija_mayor_cuidadora", {}).get(
        "nombre"
    ) or profile.get("contacto_emergencia_telegram", {}).get("nombre", "Laura")
    return (
        f"Hola {nombre}, soy MemoriaViva, su compañero de fotos y plática. "
        "Nunca guardo grabaciones de su voz; solo la escucho al momento para platicar, "
        f"y le comparto a {cuidador} un breve resumen cariñoso para que sepan que usted está bien."
    )
