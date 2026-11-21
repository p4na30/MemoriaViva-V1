"""Local mathematical clinical biomarkers engine for MemoriaViva RISE v3.0.

Implements:
1. MATTR (Moving-Average Type-Token Ratio, window=20) over Spanish content words
   + anomic circumlocution/filler detection.
2. Anomic Pauses (>= 2.0s) from consecutive word timestamps.
3. Intra-session Semantic Repetition (TF-IDF Cosine >= 0.72).
4. Self-referenced 21-day Longitudinal Evaluation (Days 1-14 baseline vs last 5 days)
   computing % deltas, personal Z-Scores, Vitality index, and Level 2 alert status.
5. Circadian period tagging (matutino / vespertino_sundowning / nocturno).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import (
    ANOMIC_PAUSE_THRESHOLD_SEC,
    BASELINE_DAYS,
    CLINICAL_ALERT_MATTR_DROP_PCT,
    CLINICAL_ALERT_PAUSE_INCREASE_PCT,
    MATTR_WINDOW_SIZE,
    RECENT_WINDOW_DAYS,
    SEMANTIC_REPEAT_THRESHOLD,
    Z_SCORE_MATTR_ALERT,
    Z_SCORE_PAUSE_ALERT,
    get_local_now,
    get_local_timezone,
)

STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "y", "e", "o", "u", "que", "es", "son", "fue", "era", "eran",
    "por", "para", "con", "sin", "sobre", "entre", "hasta", "desde", "pero",
    "mas", "más", "como", "cómo", "este", "esta", "estos", "estas", "ese",
    "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas", "mi",
    "mis", "tu", "tus", "su", "sus", "nuestro", "nuestra", "me", "te", "se",
    "le", "les", "lo", "nos", "yo", "tú", "él", "ella", "ellos", "ellas",
    "nosotros", "ustedes", "sí", "si", "no", "ya", "muy", "también", "todo",
    "toda", "todos", "todas", "hay", "había", "han", "he", "ha", "ser",
    "estar", "estoy", "está", "están", "estaba", "estaban", "tengo", "tiene",
    "tenía", "teníamos", "hacer", "hago", "hace", "hacía", "allá", "aquí",
    "ahí", "así", "qué", "quién", "dónde", "cuándo", "porque", "pues", "bien",
    "tan", "ni", "solo", "sólo", "cuando", "donde", "quien", "cual", "cuales",
    "unos", "unas", "uno", "dos", "tres", "algo", "nada", "mucho", "poco",
    "entonces", "luego", "después", "antes", "otra", "otro", "vez", "mismo",
    "misma", "sea", "sido", "puede", "puedo", "podía", "voy", "iba", "fueron",
}

CONVERSATIONAL_FRAMING_WORDS = {
    "oye", "fíjate", "fijate", "conté", "conte", "acuerdo", "ayer", "hoy",
    "ratito", "cuando", "cómo", "como", "hola", "mira", "bueno", "decía",
    "decia", "digo", "sabes", "fui", "tarde", "mañana", "noche",
}

ANOMIC_CIRCUMLOCUTION_PATTERNS = [
    r"\beste\b",
    r"\beh+\b",
    r"\bmmm+\b",
    r"c[oó]mo\s+(?:es\s+que\s+)?se\s+llama",
    r"la\s+cosa\s+esa",
    r"el\s+aparato\s+ese",
    r"se\s+me\s+fue\s+el\s+nombre",
    r"no\s+me\s+acuerdo\s+c[oó]mo",
    r"en\s+la\s+punta\s+de\s+la\s+lengua",
]


def tokenize_spanish(text: str) -> List[str]:
    """Extract lowercase alphabetic Spanish tokens."""
    if not text:
        return []
    return re.findall(r"\b[a-záéíóúüñ]+\b", text.lower())


def extract_content_words(text: str) -> List[str]:
    """Return Spanish content words excluding stopwords and short tokens (len <= 2)."""
    tokens = tokenize_spanish(text)
    return [w for w in tokens if len(w) > 2 and w not in STOPWORDS_ES]


def detect_anomic_markers(text: str) -> List[str]:
    """Detect hesitations, fillers, and anomic circumlocutions in Spanish."""
    if not text:
        return []
    lowered = text.lower()
    matches: List[str] = []
    for pattern in ANOMIC_CIRCUMLOCUTION_PATTERNS:
        found = re.findall(pattern, lowered)
        matches.extend(found)
    return matches


def compute_mattr(text: str, window_size: int = MATTR_WINDOW_SIZE) -> Dict[str, Any]:
    """Compute Moving-Average Type-Token Ratio (MATTR) on content words.

    Returns a dict with mattr score, content_word_count, unique_content_words,
    and detected anomic_fillers.
    """
    content_words = extract_content_words(text)
    n = len(content_words)
    fillers = detect_anomic_markers(text)

    if n == 0:
        return {
            "mattr": 0.0,
            "content_word_count": 0,
            "unique_content_words": 0,
            "anomic_fillers": fillers,
            "anomic_filler_count": len(fillers),
        }

    if n < window_size:
        score = round(len(set(content_words)) / n, 3)
    else:
        window_scores = [
            len(set(content_words[i : i + window_size])) / window_size
            for i in range(n - window_size + 1)
        ]
        score = round(float(np.mean(window_scores)), 3)

    return {
        "mattr": score,
        "content_word_count": n,
        "unique_content_words": len(set(content_words)),
        "anomic_fillers": fillers,
        "anomic_filler_count": len(fillers),
    }


def compute_anomic_pauses(
    word_timestamps: Sequence[Dict[str, Any]],
    threshold_sec: float = ANOMIC_PAUSE_THRESHOLD_SEC,
) -> Dict[str, Any]:
    """Compute intra-sentence pause metrics and flag anomic pauses >= threshold_sec."""
    if not word_timestamps or len(word_timestamps) < 2:
        return {
            "mean_pause_sec": 0.0,
            "max_pause_sec": 0.0,
            "anomic_count": 0,
            "hesitation_events": [],
            "total_gaps": 0,
        }

    gaps: List[float] = []
    hesitation_events: List[Dict[str, Any]] = []

    for i in range(1, len(word_timestamps)):
        prev_item = word_timestamps[i - 1]
        curr_item = word_timestamps[i]
        prev_end = float(prev_item.get("end", 0.0))
        curr_start = float(curr_item.get("start", prev_end))
        gap = round(max(0.0, curr_start - prev_end), 3)
        gaps.append(gap)
        if gap >= threshold_sec:
            hesitation_events.append(
                {
                    "after_word": str(prev_item.get("word", "")),
                    "before_word": str(curr_item.get("word", "")),
                    "duration_sec": gap,
                    "start_sec": round(prev_end, 3),
                    "end_sec": round(curr_start, 3),
                }
            )

    positive_gaps = [g for g in gaps if g > 0.05]
    mean_pause = round(float(np.mean(positive_gaps)) if positive_gaps else 0.0, 3)
    max_pause = round(float(max(gaps)) if gaps else 0.0, 3)

    return {
        "mean_pause_sec": mean_pause,
        "max_pause_sec": max_pause,
        "anomic_count": len(hesitation_events),
        "hesitation_events": hesitation_events,
        "total_gaps": len(gaps),
    }


def _normalize_for_semantic_similarity(text: str) -> str:
    """Strip Spanish stopwords and conversational framing words for TF-IDF comparison."""
    tokens = tokenize_spanish(text)
    filtered = [
        w
        for w in tokens
        if len(w) > 2
        and w not in STOPWORDS_ES
        and w not in CONVERSATIONAL_FRAMING_WORDS
    ]
    return " ".join(filtered)


def compute_semantic_repetition(
    current_text: str,
    previous_utterances: Sequence[str],
    threshold: float = SEMANTIC_REPEAT_THRESHOLD,
) -> Dict[str, Any]:
    """Detect intra-session semantic repetition via TF-IDF cosine similarity >= threshold."""
    current_tokens = tokenize_spanish(current_text)
    if len(current_tokens) < 4 or not previous_utterances:
        return {
            "is_repetition": False,
            "max_similarity": 0.0,
            "matched_index": None,
            "matched_text": None,
        }

    valid_prev = [
        (idx, utt)
        for idx, utt in enumerate(previous_utterances)
        if len(tokenize_spanish(utt)) >= 4
    ]
    if not valid_prev:
        return {
            "is_repetition": False,
            "max_similarity": 0.0,
            "matched_index": None,
            "matched_text": None,
        }

    norm_current = _normalize_for_semantic_similarity(current_text)
    norm_prev = [_normalize_for_semantic_similarity(utt) for _, utt in valid_prev]

    if not norm_current.strip() or all(not p.strip() for p in norm_prev):
        return {
            "is_repetition": False,
            "max_similarity": 0.0,
            "matched_index": None,
            "matched_text": None,
        }

    corpus = norm_prev + [norm_current]
    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return {
            "is_repetition": False,
            "max_similarity": 0.0,
            "matched_index": None,
            "matched_text": None,
        }

    similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    best_pos = int(np.argmax(similarities))
    best_score = round(float(similarities[best_pos]), 3)
    matched_idx, matched_text = valid_prev[best_pos]

    return {
        "is_repetition": best_score >= threshold,
        "max_similarity": best_score,
        "matched_index": matched_idx if best_score >= threshold else None,
        "matched_text": matched_text if best_score >= threshold else None,
    }


def evaluate_longitudinal_trend(days: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate 21-day self-referenced baseline (Days 1-14) vs recent window (last 5 days).

    Eliminates socioeconomic/educational bias by comparing the elder strictly against
    their own personal linguistic baseline.
    """
    if not days:
        return {
            "baseline_mattr_mean": 0.0,
            "baseline_mattr_std": 0.0,
            "recent_mattr_mean": 0.0,
            "delta_mattr_pct": 0.0,
            "z_mattr": 0.0,
            "baseline_pause_mean": 0.0,
            "baseline_pause_std": 0.0,
            "recent_pause_mean": 0.0,
            "delta_pause_pct": 0.0,
            "z_pause": 0.0,
            "vitality_score": 100,
            "level2_alert_triggered": False,
            "alert_reasons": [],
            "circadian_summary": {"matutino": 0, "vespertino_sundowning": 0, "nocturno": 0},
        }

    sorted_days = sorted(days, key=lambda d: int(d.get("day_number", 0)))
    baseline_slice = sorted_days[:BASELINE_DAYS]
    recent_slice = sorted_days[-RECENT_WINDOW_DAYS:]

    base_mattrs = [float(d["mattr"]) for d in baseline_slice]
    rec_mattrs = [float(d["mattr"]) for d in recent_slice]
    base_pauses = [float(d["mean_pause"]) for d in baseline_slice]
    rec_pauses = [float(d["mean_pause"]) for d in recent_slice]

    mu_mattr_base = float(np.mean(base_mattrs))
    sd_mattr_base = float(np.std(base_mattrs, ddof=0))
    mu_mattr_rec = float(np.mean(rec_mattrs))

    mu_pause_base = float(np.mean(base_pauses))
    sd_pause_base = float(np.std(base_pauses, ddof=0))
    mu_pause_rec = float(np.mean(rec_pauses))

    delta_pause_pct = (mu_pause_rec - mu_pause_base) / max(0.1, mu_pause_base)
    z_pause = (mu_pause_rec - mu_pause_base) / max(0.05, sd_pause_base)

    delta_mattr_pct = (mu_mattr_base - mu_mattr_rec) / max(0.1, mu_mattr_base)
    z_mattr = (mu_mattr_rec - mu_mattr_base) / max(0.01, sd_mattr_base)

    alert_reasons: List[str] = []
    if delta_pause_pct >= CLINICAL_ALERT_PAUSE_INCREASE_PCT:
        alert_reasons.append(
            f"Incremento sostenido en pausas (+{round(delta_pause_pct * 100, 1)}% vs línea base)"
        )
    if delta_mattr_pct >= CLINICAL_ALERT_MATTR_DROP_PCT:
        alert_reasons.append(
            f"Disminución en riqueza léxica MATTR (-{round(delta_mattr_pct * 100, 1)}% vs línea base)"
        )
    if z_pause >= Z_SCORE_PAUSE_ALERT:
        alert_reasons.append(f"Z-Score de pausas elevado (Z = +{round(z_pause, 2)})")
    if z_mattr <= Z_SCORE_MATTR_ALERT:
        alert_reasons.append(f"Z-Score de MATTR descendido (Z = {round(z_mattr, 2)})")

    level2_triggered = len(alert_reasons) > 0

    # Composite conversational vitality score (0-100) for Caregiver KPI card
    mattr_penalty = max(0.0, delta_mattr_pct) * 120.0
    pause_penalty = min(40.0, max(0.0, delta_pause_pct) * 28.0)
    vitality_score = int(round(max(25.0, min(100.0, 96.0 - mattr_penalty - pause_penalty))))

    circadian_summary = {"matutino": 0, "vespertino_sundowning": 0, "nocturno": 0}
    for d in sorted_days:
        period = str(d.get("circadian_period", "matutino"))
        if period in circadian_summary:
            circadian_summary[period] += 1

    latest = sorted_days[-1]
    return {
        "baseline_mattr_mean": round(mu_mattr_base, 3),
        "baseline_mattr_std": round(sd_mattr_base, 3),
        "recent_mattr_mean": round(mu_mattr_rec, 3),
        "latest_mattr": round(float(latest["mattr"]), 3),
        "delta_mattr_pct": round(delta_mattr_pct, 3),
        "delta_mattr_pct_display": round(-delta_mattr_pct * 100.0, 1),
        "z_mattr": round(z_mattr, 2),
        "baseline_pause_mean": round(mu_pause_base, 3),
        "baseline_pause_std": round(sd_pause_base, 3),
        "recent_pause_mean": round(mu_pause_rec, 3),
        "latest_pause": round(float(latest["mean_pause"]), 3),
        "delta_pause_pct": round(delta_pause_pct, 3),
        "delta_pause_pct_display": round(delta_pause_pct * 100.0, 1),
        "z_pause": round(z_pause, 2),
        "vitality_score": vitality_score,
        "level2_alert_triggered": level2_triggered,
        "alert_reasons": alert_reasons,
        "circadian_summary": circadian_summary,
    }


def classify_circadian_period(dt: Optional[datetime] = None) -> str:
    """Tag circadian window in clinical local timezone to control for Sundowning effects."""
    if dt is None:
        now = get_local_now()
    elif dt.tzinfo is not None:
        now = dt.astimezone(get_local_timezone())
    else:
        now = dt
    hour = now.hour
    if 6 <= hour <= 13:
        return "matutino"
    if 14 <= hour <= 20:
        return "vespertino_sundowning"
    return "nocturno"
