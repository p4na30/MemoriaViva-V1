"""Zero-Raw-Cloud Audio Engine: RAM ffmpeg normalization, RMS pause detection,
Gemini multimodal STT fallback, Edge-TTS geriatric voice, and 3 precalibrated demo acts.
"""

from __future__ import annotations

import asyncio
import base64
import io
import subprocess
import wave
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.config import (
    ANOMIC_PAUSE_THRESHOLD_SEC,
    TTS_PITCH,
    TTS_RATE,
    TTS_VOICE_FEMALE,
    TTS_VOICE_MALE,
    get_gemini_api_key,
    get_gemini_model_chain,
    mark_model_unavailable,
)

# ---------------------------------------------------------------------------
# Precalibrated 3 Theatrical Pitch Scenarios (Fail-Safe Live Zoom Demo)
# ---------------------------------------------------------------------------
DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "demo_1_rescate": {
        "id": "demo_1_rescate",
        "title": "Acto 1 · Rescate Biográfico y Aprendizaje",
        "subtitle": "Olvida el nombre de su hija Rocío y comparte un nuevo recuerdo de su perro Sultán.",
        "transcript": (
            "Hola... oye, fíjate que ayer por la tarde me habló por teléfono mi hija... "
            "la más chica, la que es maestra allá en la costa de Colima... "
            "ay, ¿cómo es que se llama?... se me fue el nombre... "
            "Sí, mi hija Rocío, le conté que me acordé de cuando teníamos en la casa "
            "aquel perro pastor alemán que se llamaba Sultán."
        ),
        "word_timestamps": [
            {"word": "Hola", "start": 0.0, "end": 0.45},
            {"word": "oye", "start": 0.70, "end": 1.00},
            {"word": "fíjate", "start": 1.15, "end": 1.55},
            {"word": "ayer", "start": 1.70, "end": 2.00},
            {"word": "tarde", "start": 2.15, "end": 2.50},
            {"word": "habló", "start": 2.65, "end": 3.00},
            {"word": "teléfono", "start": 3.15, "end": 3.65},
            {"word": "hija", "start": 3.80, "end": 4.20},
            {"word": "maestra", "start": 4.95, "end": 5.45},
            {"word": "costa", "start": 5.60, "end": 6.00},
            {"word": "Colima", "start": 6.15, "end": 6.65},
            {"word": "llama", "start": 7.60, "end": 8.00},
            {"word": "nombre", "start": 8.85, "end": 9.35},
            # 1.65s pause (< 2.0s threshold -> non-anomic)
            {"word": "Rocío", "start": 11.00, "end": 11.55},
            {"word": "conté", "start": 11.80, "end": 12.20},
            {"word": "acordé", "start": 12.40, "end": 12.85},
            {"word": "perro", "start": 13.10, "end": 13.50},
            {"word": "pastor", "start": 13.65, "end": 14.10},
            {"word": "alemán", "start": 14.20, "end": 14.70},
            {"word": "Sultán", "start": 14.90, "end": 15.50},
        ],
        "expected_theme": "mascotas",
    },
    "demo_2_anomia": {
        "id": "demo_2_anomia",
        "title": "Acto 2 · Pausa Anómica (3.18s) y Bucle Semántico",
        "subtitle": "Vacilación léxica real al evocar una herramienta ferroviaria y repetición del reloj.",
        "transcript": (
            "Cuando yo trabajaba en los trenes de Guadalajara, usábamos una herramienta pesada "
            "para apretar los rieles... una... una llave de cruz grande. "
            "Y como te decía hace ratito, cuando me jubilé de los trenes me regalaron un reloj."
        ),
        "word_timestamps": [
            {"word": "Cuando", "start": 0.0, "end": 0.45},
            {"word": "trabajaba", "start": 0.60, "end": 1.20},
            {"word": "trenes", "start": 1.35, "end": 1.80},
            {"word": "Guadalajara", "start": 1.95, "end": 2.65},
            {"word": "usábamos", "start": 2.85, "end": 3.40},
            {"word": "herramienta", "start": 3.55, "end": 4.25},
            {"word": "pesada", "start": 4.40, "end": 4.90},
            {"word": "apretar", "start": 5.10, "end": 5.60},
            {"word": "rieles", "start": 5.80, "end": 6.30},
            {"word": "una", "start": 6.70, "end": 7.02},
            # Exact 3.18s anomic pause between "una" and "llave"
            {"word": "llave", "start": 10.20, "end": 10.70},
            {"word": "cruz", "start": 10.85, "end": 11.25},
            {"word": "grande", "start": 11.40, "end": 11.90},
            {"word": "decía", "start": 12.50, "end": 12.95},
            {"word": "ratito", "start": 13.10, "end": 13.55},
            {"word": "jubilé", "start": 13.75, "end": 14.30},
            {"word": "trenes", "start": 14.45, "end": 14.90},
            {"word": "regalaron", "start": 15.10, "end": 15.65},
            {"word": "reloj", "start": 15.80, "end": 16.30},
        ],
        "expected_theme": "ferrocarril",
    },
    "demo_3_crisis": {
        "id": "demo_3_crisis",
        "title": "Acto 3 · Desorientación Aguda, Validación Feil y S.O.S.",
        "subtitle": "Suspende preguntas cognitivas, contiene con ternura y dispara Alerta Roja Nivel 3.",
        "transcript": (
            "Oye... no sé qué hago aquí, no conozco esta casa... "
            "¿dónde está Carmen?, me quiero ir a mi casa, me siento muy mareado y asustado..."
        ),
        "word_timestamps": [
            {"word": "Oye", "start": 0.0, "end": 0.45},
            {"word": "conozco", "start": 1.25, "end": 1.85},
            {"word": "casa", "start": 2.00, "end": 2.45},
            # 2.25s pause due to distress/disorientation
            {"word": "Carmen", "start": 4.70, "end": 5.30},
            {"word": "quiero", "start": 5.80, "end": 6.20},
            {"word": "casa", "start": 6.40, "end": 6.85},
            {"word": "siento", "start": 7.50, "end": 7.95},
            {"word": "mareado", "start": 8.15, "end": 8.80},
            {"word": "asustado", "start": 9.30, "end": 10.05},
        ],
        "expected_theme": "familia_hogar",
    },
}


def decode_base64_audio(audio_base64: str) -> bytes:
    """Decode base64 audio string (with or without data URI header) strictly in RAM."""
    payload = audio_base64.strip()
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]
    return base64.b64decode(payload)


def normalize_audio_to_wav_ram(raw_audio_bytes: bytes) -> Tuple[bytes, int, np.ndarray]:
    """Normalize arbitrary audio (WebM/Opus/WAV/MP4) to 16kHz mono PCM WAV purely in RAM.

    Strictly enforces Zero-Raw-Cloud Audio: uses ffmpeg pipe:0 -> pipe:1 with zero disk writes.
    Returns (wav_bytes, sample_rate, float32_samples_in_minus1_to_1).
    """
    if not raw_audio_bytes:
        return b"", 16000, np.array([], dtype=np.float32)

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            "-f",
            "wav",
            "pipe:1",
        ],
        input=raw_audio_bytes,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"ffmpeg RAM normalization failed: {proc.stderr.decode('utf-8', 'ignore')}")

    wav_bytes = proc.stdout
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        pcm = wf.readframes(n_frames)

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return wav_bytes, sample_rate, samples


def detect_rms_pauses(
    samples: np.ndarray,
    sample_rate: int = 16000,
    frame_ms: int = 30,
    min_pause_sec: float = ANOMIC_PAUSE_THRESHOLD_SEC,
) -> Dict[str, Any]:
    """Measure real intra-speech silences via 30ms RMS energy windows in RAM.

    Leading and trailing silence are trimmed so only genuine intra-utterance
    hesitations/pauses are measured.
    """
    if samples.size == 0 or sample_rate <= 0:
        return {
            "duration_sec": 0.0,
            "rms_pauses": [],
            "max_rms_pause_sec": 0.0,
            "anomic_rms_count": 0,
        }

    frame_len = max(1, int(sample_rate * (frame_ms / 1000.0)))
    n_frames = samples.size // frame_len
    if n_frames < 3:
        return {
            "duration_sec": round(samples.size / sample_rate, 3),
            "rms_pauses": [],
            "max_rms_pause_sec": 0.0,
            "anomic_rms_count": 0,
        }

    trimmed = samples[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(trimmed ** 2, axis=1))
    peak = float(np.max(rms)) if rms.size else 0.0
    if peak < 1e-4:
        return {
            "duration_sec": round(samples.size / sample_rate, 3),
            "rms_pauses": [],
            "max_rms_pause_sec": 0.0,
            "anomic_rms_count": 0,
        }

    norm_rms = rms / peak
    # Adaptive silence threshold balancing quiet speech and room floor noise
    noise_floor = float(np.percentile(norm_rms, 15))
    speech_threshold = max(0.08, min(0.22, noise_floor * 2.5 + 0.05))
    is_speech = norm_rms >= speech_threshold

    speech_indices = np.where(is_speech)[0]
    if speech_indices.size < 2:
        return {
            "duration_sec": round(samples.size / sample_rate, 3),
            "rms_pauses": [],
            "max_rms_pause_sec": 0.0,
            "anomic_rms_count": 0,
        }

    first_speech = int(speech_indices[0])
    last_speech = int(speech_indices[-1])
    frame_sec = frame_len / float(sample_rate)

    pauses: List[Dict[str, Any]] = []
    silence_start: Optional[int] = None
    for idx in range(first_speech, last_speech + 1):
        if not is_speech[idx]:
            if silence_start is None:
                silence_start = idx
        else:
            if silence_start is not None:
                dur = (idx - silence_start) * frame_sec
                if dur >= 0.45:
                    pauses.append(
                        {
                            "start_sec": round(silence_start * frame_sec, 3),
                            "end_sec": round(idx * frame_sec, 3),
                            "duration_sec": round(dur, 3),
                            "is_anomic": dur >= min_pause_sec,
                        }
                    )
                silence_start = None

    anomic_pauses = [p for p in pauses if p["is_anomic"]]
    max_pause = round(max((p["duration_sec"] for p in pauses), default=0.0), 3)
    return {
        "duration_sec": round(samples.size / sample_rate, 3),
        "rms_pauses": pauses,
        "max_rms_pause_sec": max_pause,
        "anomic_rms_count": len(anomic_pauses),
    }


def merge_rms_pauses_into_timestamps(
    transcript: str,
    word_timestamps: Optional[Sequence[Dict[str, Any]]],
    rms_analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Combine browser word timestamps with acoustic RMS pauses.

    If browser STT omitted an acoustic pause >= 2.0s (or provided no timestamps),
    synthesize/inject the real acoustic gap so biomarker calculations stay accurate.
    """
    ts_list = [dict(item) for item in (word_timestamps or [])]
    rms_pauses = rms_analysis.get("rms_pauses") or []

    if ts_list:
        max_ts_gap = 0.0
        for i in range(1, len(ts_list)):
            gap = max(0.0, float(ts_list[i]["start"]) - float(ts_list[i - 1]["end"]))
            if gap > max_ts_gap:
                max_ts_gap = gap
        # If RMS measured a deeper anomic pause missed by browser timestamps, inject it
        for rp in rms_pauses:
            if rp.get("is_anomic") and rp["duration_sec"] > max_ts_gap + 0.35 and len(ts_list) >= 2:
                mid = len(ts_list) // 2
                shift = rp["duration_sec"] - max(
                    0.0, float(ts_list[mid]["start"]) - float(ts_list[mid - 1]["end"])
                )
                for j in range(mid, len(ts_list)):
                    ts_list[j]["start"] = round(float(ts_list[j]["start"]) + shift, 3)
                    ts_list[j]["end"] = round(float(ts_list[j]["end"]) + shift, 3)
                break
        return ts_list

    # Build synthetic timestamps from transcript distributing ALL real RMS pauses proportionally
    words = [w for w in transcript.split() if w.strip()]
    if not words:
        return []

    total_dur = float(rms_analysis.get("duration_sec") or max(1.5, len(words) * 0.42))
    gap_map: Dict[int, float] = {}
    if rms_pauses and len(words) >= 2:
        for p in sorted(rms_pauses, key=lambda item: float(item.get("start_sec", 0.0))):
            dur = float(p.get("duration_sec", 0.0))
            if dur < 0.45:
                continue
            pivot = max(
                1,
                min(len(words) - 1, int(round((float(p.get("start_sec", 0.0)) / max(0.5, total_dur)) * len(words)))),
            )
            # Avoid overwriting an already-assigned gap if two pauses map to the same word boundary
            while pivot in gap_map and pivot < len(words) - 1:
                pivot += 1
            if pivot in gap_map:
                gap_map[pivot] = max(gap_map[pivot], dur)
            else:
                gap_map[pivot] = dur

    result: List[Dict[str, Any]] = []
    cursor = 0.0
    for idx, w in enumerate(words):
        if idx in gap_map:
            cursor += gap_map[idx]
        elif idx > 0:
            cursor += 0.12
        word_dur = 0.34
        result.append({"word": w, "start": round(cursor, 3), "end": round(cursor + word_dur, 3)})
        cursor += word_dur
    return result


def _run_with_hard_timeout(fn: Any, timeout_sec: float) -> Any:
    """Execute fn in a worker thread without blocking on shutdown(wait=True) when timeout expires."""
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_sec)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def transcribe_audio_ram_google_free(wav_bytes: bytes) -> str:
    """Zero-API-Key Spanish (es-MX) STT in RAM via SpeechRecognition (works on Firefox & Android APK)."""
    if not wav_bytes:
        return ""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="es-MX")
        return str(text or "").strip()
    except Exception:
        return ""


def transcribe_audio_ram_gemini(wav_bytes: bytes) -> str:
    """Resilient multimodal STT on RAM WAV:
    1. Runs zero-key es-MX SpeechRecognition in RAM first (~0.4s, 0 RPD / 0 Gemini quota).
    2. Only if empty and GEMINI_API_KEY is set, tries at most 1 Gemini model with a 6.0s hard timeout.
    """
    if not wav_bytes:
        return ""

    # 1. Fast zero-RPD es-MX STT in RAM first
    free_text = transcribe_audio_ram_google_free(wav_bytes)
    if free_text:
        return free_text

    # 2. Single-model Gemini multimodal fallback (max 1 RPD, 6.0s hard timeout)
    api_key = get_gemini_api_key()
    chain = get_gemini_model_chain()
    if api_key and chain:
        model_name = chain[0]
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            contents = [
                types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                (
                    "Transcribe fielmente en español mexicano lo que dice el adulto mayor en este audio. "
                    "Conserva muletillas naturales como 'este', 'eh', 'mmm' si existen. "
                    "Devuelve únicamente el texto transcrito sin comentarios adicionales."
                ),
            ]

            def _call_stt() -> str:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                return (resp.text or "").strip()

            text = _run_with_hard_timeout(_call_stt, 6.0)
            if text:
                return text
        except Exception as exc:
            err_txt = str(exc).upper()
            if "404" in err_txt or "NOT_FOUND" in err_txt or "NOT FOUND" in err_txt:
                mark_model_unavailable(model_name)

    return ""


_TTS_RAM_CACHE: Dict[tuple[str, str], str] = {}
_TTS_RAM_CACHE_MAX = 64


async def _edge_tts_bytes(text: str, voice: str, rate: str, pitch: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def synthesize_elder_voice(
    text: str,
    voice_gender: str = "male",
    enabled: bool = True,
) -> Optional[str]:
    """Synthesize warm geriatric speech via Edge-TTS (-15% rate, -5Hz pitch) as Base64 MP3 URI.

    Uses a bounded in-RAM cache for repeated phrases and fails gracefully offline.
    """
    if not enabled or not text or not text.strip():
        return None

    voice = TTS_VOICE_FEMALE if voice_gender == "female" else TTS_VOICE_MALE
    cache_key = (voice, text.strip())
    cached = _TTS_RAM_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        mp3_bytes = _run_with_hard_timeout(
            lambda: asyncio.run(
                asyncio.wait_for(_edge_tts_bytes(text, voice, TTS_RATE, TTS_PITCH), timeout=4.0)
            ),
            4.5,
        )

        if not mp3_bytes:
            return None
        b64 = base64.b64encode(mp3_bytes).decode("ascii")
        data_uri = f"data:audio/mpeg;base64,{b64}"
        if len(_TTS_RAM_CACHE) >= _TTS_RAM_CACHE_MAX:
            _TTS_RAM_CACHE.pop(next(iter(_TTS_RAM_CACHE)))
        _TTS_RAM_CACHE[cache_key] = data_uri
        return data_uri
    except Exception:
        return None
