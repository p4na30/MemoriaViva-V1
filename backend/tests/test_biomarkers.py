"""Unit tests for Phase 1: Clinical Biomarkers & Shielded SQLite Persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.biomarkers import (
    classify_circadian_period,
    compute_anomic_pauses,
    compute_mattr,
    compute_semantic_repetition,
    evaluate_longitudinal_trend,
)
from backend.config import HISTORY_SEED_PATH
from backend.database import DatabaseManager


def test_mattr_short_and_long_spanish_text() -> None:
    short_text = "Ayer platiqué con mi hija Rocío sobre el ferrocarril antiguo de Guadalajara."
    res_short = compute_mattr(short_text, window_size=20)
    assert res_short["content_word_count"] > 0
    assert 0.8 <= res_short["mattr"] <= 1.0

    # Long text (> 20 content words) with deliberate lexical repetition
    repetitive_text = " ".join(
        ["trenes estación ferrocarril rieles viaje trenes estación ferrocarril"] * 5
    )
    res_rep = compute_mattr(repetitive_text, window_size=20)
    assert res_rep["content_word_count"] >= 20
    assert res_rep["mattr"] < 0.4

    # Anomic circumlocution detection
    anomic_text = "Ay, este, ¿cómo se llama? Se me fue el nombre de la cosa esa."
    res_anomic = compute_mattr(anomic_text)
    assert res_anomic["anomic_filler_count"] >= 3


def test_anomic_pauses_threshold_and_events() -> None:
    # Act 1 scenario: max pause 1.65s -> NOT anomic (< 2.0s)
    timestamps_act1 = [
        {"word": "hija", "start": 0.0, "end": 0.4},
        {"word": "Rocío", "start": 2.05, "end": 2.6},
        {"word": "Sultán", "start": 3.0, "end": 3.5},
    ]
    res1 = compute_anomic_pauses(timestamps_act1, threshold_sec=2.0)
    assert res1["anomic_count"] == 0
    assert res1["max_pause_sec"] == 1.65

    # Act 2 scenario: pause 3.18s between "una" and "llave" -> anomic
    timestamps_act2 = [
        {"word": "herramienta", "start": 0.0, "end": 0.8},
        {"word": "una", "start": 1.0, "end": 1.32},
        {"word": "llave", "start": 4.50, "end": 5.0},
        {"word": "cruz", "start": 5.2, "end": 5.6},
    ]
    res2 = compute_anomic_pauses(timestamps_act2, threshold_sec=2.0)
    assert res2["anomic_count"] == 1
    assert res2["max_pause_sec"] == 3.18
    assert res2["hesitation_events"][0]["after_word"] == "una"
    assert res2["hesitation_events"][0]["before_word"] == "llave"


def test_semantic_repetition_tfidf_cosine() -> None:
    prev = [
        "Cuando me jubilé de los ferrocarriles de Guadalajara mis compañeros me regalaron un reloj antiguo."
    ]
    repeated = (
        "Oye, fíjate que cuando me jubilé de los ferrocarriles en Guadalajara "
        "mis compañeros me regalaron un reloj antiguo."
    )
    novel = "Me gusta escuchar los boleros del Trío Los Panchos y recordar la playa de Miramar."

    res_rep = compute_semantic_repetition(repeated, prev, threshold=0.72)
    assert res_rep["is_repetition"] is True
    assert res_rep["max_similarity"] >= 0.72
    assert res_rep["matched_index"] == 0

    res_novel = compute_semantic_repetition(novel, prev, threshold=0.72)
    assert res_novel["is_repetition"] is False
    assert res_novel["max_similarity"] < 0.4


def test_longitudinal_21_days_seed_triggers_level2() -> None:
    days = json.loads(HISTORY_SEED_PATH.read_text(encoding="utf-8"))
    assert len(days) == 21

    ev = evaluate_longitudinal_trend(days)
    assert 0.74 <= ev["baseline_mattr_mean"] <= 0.77
    assert 1.05 <= ev["baseline_pause_mean"] <= 1.15
    assert ev["delta_pause_pct"] >= 0.25
    assert ev["delta_mattr_pct"] >= 0.20
    assert ev["z_pause"] >= 2.0
    assert ev["z_mattr"] <= -2.0
    assert ev["level2_alert_triggered"] is True
    assert len(ev["alert_reasons"]) >= 2


def test_circadian_classification() -> None:
    assert classify_circadian_period(datetime(2026, 11, 20, 9, 30)) == "matutino"
    assert classify_circadian_period(datetime(2026, 11, 20, 17, 15)) == "vespertino_sundowning"
    assert classify_circadian_period(datetime(2026, 11, 20, 22, 45)) == "nocturno"


def test_database_sqlite_persistence_and_cloud_sync(tmp_path: Path) -> None:
    work_db = tmp_path / "tmp_work.db"
    persist_db = tmp_path / "gcs_mount.db"
    db = DatabaseManager(db_path=work_db, persistent_path=persist_db, cloud_sync=True)

    # Seed 21 days
    days = db.seed_longitudinal_days("don_manuel")
    assert len(days) == 21
    assert persist_db.exists()  # Verify Cloud Run sync mirror works

    # Insert conversation turn and blend into Day 21
    turn = db.insert_turn(
        {
            "profile_id": "don_manuel",
            "circadian_period": "vespertino_sundowning",
            "user_text": "Mi perro pastor alemán se llamaba Sultán.",
            "assistant_reply": "Qué bonito recuerdo de Sultán, Don Manuel. ¿Le gustaba salir a caminar con usted?",
            "mattr": 0.76,
            "mean_pause_sec": 1.1,
            "max_pause_sec": 1.65,
            "anomic_count": 0,
            "is_repetition": False,
            "emotional_state": "alegre",
            "emergency_triggered": False,
            "memory_album_theme": "mascotas",
            "learned_facts": ["Tuvo un perro pastor alemán llamado Sultán."],
            "alert_level": 1,
            "source": "demo",
        }
    )
    assert turn["id"] >= 1
    assert turn["learned_facts"] == ["Tuvo un perro pastor alemán llamado Sultán."]

    updated_day = db.update_latest_day_with_turn(
        profile_id="don_manuel",
        mattr=0.76,
        mean_pause=1.1,
        anomic_count=1,
        is_repetition=False,
        mood="alegre",
        circadian_period="vespertino_sundowning",
    )
    assert updated_day["day_number"] == 21
    assert updated_day["anomic_pauses"] == 7

    # Insert Human-in-the-Loop clinical review
    review = db.insert_clinical_review(
        profile_id="don_manuel",
        reviewer_name="Laura González",
        reviewer_role="Familiar Cuidador",
        decision="contexto_externo",
        confounding_factors=["mal_sueno", "sundowning"],
        clinical_notes="Durmió solo 4 horas anoche; retomar evaluación por la mañana.",
        mattr_snapshot=0.55,
        pause_snapshot=3.12,
    )
    assert review["id"] >= 1
    reviews = db.get_clinical_reviews("don_manuel")
    assert len(reviews) == 1
    assert "mal_sueno" in reviews[0]["confounding_factors"]

    # Reset demo restores clean 21 days and clears turns/reviews
    db.reset_demo_state("don_manuel")
    assert db.get_recent_turns("don_manuel") == []
    assert db.get_clinical_reviews("don_manuel") == []
    assert db.get_longitudinal_days("don_manuel")[-1]["anomic_pauses"] == 6
