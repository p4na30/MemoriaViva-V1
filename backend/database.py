"""SQLite persistence layer shielded for both local execution and GCP Cloud Run (GCS FUSE).

Manages:
- conversation_turns (with circadian_period for Sundowning control)
- clinical_reviews (Human-in-the-Loop governance + confounding_factors_json)
- longitudinal_days (21-day self-referenced series, seeded and updated live)
- photo_metadata (Bidirectional Voice <-> Photo tags & captions)
- consent_events (Assisted Dual Consent audit trail)
- telegram_logs (3-level family bridge feed)
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from backend.config import (
    HISTORY_SEED_PATH,
    IS_CLOUD_RUN,
    SQLITE_PERSISTENT_PATH,
    SQLITE_WORKING_PATH,
    ensure_data_directories,
)

_DB_LOCK = threading.RLock()


class DatabaseManager:
    """Thread-safe SQLite manager with GCS FUSE shielding for Cloud Run."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        persistent_path: Optional[Path] = None,
        cloud_sync: Optional[bool] = None,
    ) -> None:
        ensure_data_directories()
        self.cloud_sync = IS_CLOUD_RUN if cloud_sync is None else cloud_sync
        self.persistent_path = Path(persistent_path or db_path or SQLITE_PERSISTENT_PATH)
        if db_path is not None and not self.cloud_sync:
            self.working_path = Path(db_path)
        elif self.cloud_sync:
            self.working_path = Path(db_path or SQLITE_WORKING_PATH)
        else:
            self.working_path = self.persistent_path

        self._bootstrap_from_persistent()
        self.init_schema()

    def _bootstrap_from_persistent(self) -> None:
        """If running in Cloud Run with GCS FUSE, copy persistent DB to local /tmp."""
        with _DB_LOCK:
            self.working_path.parent.mkdir(parents=True, exist_ok=True)
            self.persistent_path.parent.mkdir(parents=True, exist_ok=True)
            if (
                self.cloud_sync
                and self.working_path != self.persistent_path
                and self.persistent_path.exists()
                and not self.working_path.exists()
            ):
                shutil.copy2(self.persistent_path, self.working_path)

    def _sync_to_persistent(self) -> None:
        """Atomically mirror local /tmp SQLite file back to /app/data on Cloud Run."""
        if not self.cloud_sync or self.working_path == self.persistent_path:
            return
        tmp_target = self.persistent_path.with_suffix(".db.tmp")
        try:
            shutil.copy2(self.working_path, tmp_target)
            tmp_target.replace(self.persistent_path)
        except OSError:
            # Non-fatal fallback if volume is momentarily read-only; /tmp remains consistent
            if tmp_target.exists():
                tmp_target.unlink(missing_ok=True)

    @contextmanager
    def _connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        with _DB_LOCK:
            conn = sqlite3.connect(str(self.working_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            # DELETE journal avoids -shm/-wal mmap files incompatible with GCS FUSE
            conn.execute("PRAGMA journal_mode=DELETE;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            try:
                yield conn
                if write:
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            if write:
                self._sync_to_persistent()

    def init_schema(self) -> None:
        with self._connection(write=True) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    circadian_period TEXT NOT NULL DEFAULT 'matutino',
                    profile_id TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_reply TEXT NOT NULL,
                    mattr REAL NOT NULL DEFAULT 0.0,
                    mean_pause_sec REAL NOT NULL DEFAULT 0.0,
                    max_pause_sec REAL NOT NULL DEFAULT 0.0,
                    anomic_count INTEGER NOT NULL DEFAULT 0,
                    is_repetition INTEGER NOT NULL DEFAULT 0,
                    repetition_score REAL NOT NULL DEFAULT 0.0,
                    emotional_state TEXT NOT NULL DEFAULT 'tranquilo',
                    emergency_triggered INTEGER NOT NULL DEFAULT 0,
                    memory_album_theme TEXT NOT NULL DEFAULT 'familia_hogar',
                    learned_facts_json TEXT NOT NULL DEFAULT '[]',
                    alert_level INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'voice'
                );

                CREATE TABLE IF NOT EXISTS clinical_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confounding_factors_json TEXT NOT NULL DEFAULT '[]',
                    clinical_notes TEXT NOT NULL,
                    mattr_snapshot REAL NOT NULL DEFAULT 0.0,
                    pause_snapshot REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS longitudinal_days (
                    profile_id TEXT NOT NULL,
                    day_number INTEGER NOT NULL,
                    date_label TEXT NOT NULL,
                    mattr REAL NOT NULL,
                    mean_pause REAL NOT NULL,
                    anomic_pauses INTEGER NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    mood TEXT NOT NULL DEFAULT 'Tranquilo',
                    circadian_period TEXT NOT NULL DEFAULT 'matutino',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile_id, day_number)
                );

                CREATE TABLE IF NOT EXISTS photo_metadata (
                    filename TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    theme TEXT NOT NULL DEFAULT 'familia_hogar',
                    is_sample INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS consent_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    acknowledged_by TEXT NOT NULL,
                    summary_text TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    channel_status TEXT NOT NULL DEFAULT 'local_preview'
                );
                """
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Longitudinal 21-day series
    # ------------------------------------------------------------------
    def seed_longitudinal_days(
        self,
        profile_id: str = "don_manuel",
        seed_path: Optional[Path] = None,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        path = seed_path or HISTORY_SEED_PATH
        with self._connection(write=True) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM longitudinal_days WHERE profile_id = ?",
                (profile_id,),
            )
            existing_count = int(cur.fetchone()[0])
            if existing_count > 0 and not force:
                return self.get_longitudinal_days(profile_id)

            if force:
                conn.execute(
                    "DELETE FROM longitudinal_days WHERE profile_id = ?",
                    (profile_id,),
                )

            if path.exists():
                seed_data = json.loads(path.read_text(encoding="utf-8"))
            else:
                seed_data = []

            now = self._now_iso()
            for item in seed_data:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO longitudinal_days (
                        profile_id, day_number, date_label, mattr, mean_pause,
                        anomic_pauses, repetitions, mood, circadian_period, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_id,
                        int(item["day_number"]),
                        str(item.get("date_label", f"Día {item['day_number']}")),
                        float(item["mattr"]),
                        float(item["mean_pause"]),
                        int(item.get("anomic_pauses", 0)),
                        int(item.get("repetitions", 0)),
                        str(item.get("mood", "Tranquilo")),
                        str(item.get("circadian_period", "matutino")),
                        now,
                    ),
                )
        return self.get_longitudinal_days(profile_id)

    def get_longitudinal_days(self, profile_id: str = "don_manuel") -> List[Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                """
                SELECT day_number, date_label, mattr, mean_pause, anomic_pauses,
                       repetitions, mood, circadian_period, updated_at
                FROM longitudinal_days
                WHERE profile_id = ?
                ORDER BY day_number ASC
                """,
                (profile_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_latest_day_with_turn(
        self,
        profile_id: str,
        mattr: float,
        mean_pause: float,
        anomic_count: int,
        is_repetition: bool,
        mood: str,
        circadian_period: str,
    ) -> Dict[str, Any]:
        """Blend a newly recorded turn into Day 21 (current day) in SQLite."""
        days = self.get_longitudinal_days(profile_id)
        if not days:
            days = self.seed_longitudinal_days(profile_id)
        latest = days[-1]
        day_num = int(latest["day_number"])

        blended_mattr = round((float(latest["mattr"]) * 0.65) + (mattr * 0.35), 3) if mattr > 0 else float(latest["mattr"])
        blended_pause = round((float(latest["mean_pause"]) * 0.65) + (mean_pause * 0.35), 3) if mean_pause > 0 else float(latest["mean_pause"])
        new_anomic = int(latest["anomic_pauses"]) + int(anomic_count)
        new_reps = int(latest["repetitions"]) + (1 if is_repetition else 0)
        mood_label = mood.replace("_", " ").capitalize()

        with self._connection(write=True) as conn:
            conn.execute(
                """
                UPDATE longitudinal_days
                SET mattr = ?, mean_pause = ?, anomic_pauses = ?, repetitions = ?,
                    mood = ?, circadian_period = ?, updated_at = ?
                WHERE profile_id = ? AND day_number = ?
                """,
                (
                    blended_mattr,
                    blended_pause,
                    new_anomic,
                    new_reps,
                    mood_label,
                    circadian_period,
                    self._now_iso(),
                    profile_id,
                    day_num,
                ),
            )
        return self.get_longitudinal_days(profile_id)[-1]

    # ------------------------------------------------------------------
    # Conversation Turns
    # ------------------------------------------------------------------
    def insert_turn(self, turn: Dict[str, Any]) -> Dict[str, Any]:
        created_at = turn.get("created_at") or self._now_iso()
        learned_facts = turn.get("learned_facts") or []
        with self._connection(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO conversation_turns (
                    created_at, circadian_period, profile_id, user_text,
                    assistant_reply, mattr, mean_pause_sec, max_pause_sec,
                    anomic_count, is_repetition, repetition_score, emotional_state,
                    emergency_triggered, memory_album_theme, learned_facts_json,
                    alert_level, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    str(turn.get("circadian_period", "matutino")),
                    str(turn.get("profile_id", "don_manuel")),
                    str(turn.get("user_text", "")),
                    str(turn.get("assistant_reply", "")),
                    float(turn.get("mattr", 0.0)),
                    float(turn.get("mean_pause_sec", 0.0)),
                    float(turn.get("max_pause_sec", 0.0)),
                    int(turn.get("anomic_count", 0)),
                    1 if turn.get("is_repetition") else 0,
                    float(turn.get("repetition_score", 0.0)),
                    str(turn.get("emotional_state", "tranquilo")),
                    1 if turn.get("emergency_triggered") else 0,
                    str(turn.get("memory_album_theme", "familia_hogar")),
                    json.dumps(learned_facts, ensure_ascii=False),
                    int(turn.get("alert_level", 1)),
                    str(turn.get("source", "voice")),
                ),
            )
            turn_id = cur.lastrowid

        return self.get_turn_by_id(int(turn_id))  # type: ignore[arg-type]

    def get_turn_by_id(self, turn_id: int) -> Dict[str, Any]:
        with self._connection(write=False) as conn:
            row = conn.execute(
                "SELECT * FROM conversation_turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
            return self._row_to_turn(row) if row else {}

    def get_recent_turns(
        self, profile_id: str = "don_manuel", limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
            return [self._row_to_turn(r) for r in rows]

    @staticmethod
    def _row_to_turn(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["is_repetition"] = bool(data["is_repetition"])
        data["emergency_triggered"] = bool(data["emergency_triggered"])
        try:
            data["learned_facts"] = json.loads(data.get("learned_facts_json") or "[]")
        except json.JSONDecodeError:
            data["learned_facts"] = []
        return data

    # ------------------------------------------------------------------
    # Clinical Reviews (Human-in-the-Loop Governance)
    # ------------------------------------------------------------------
    def insert_clinical_review(
        self,
        profile_id: str,
        reviewer_name: str,
        reviewer_role: str,
        decision: str,
        confounding_factors: List[str],
        clinical_notes: str,
        mattr_snapshot: float = 0.0,
        pause_snapshot: float = 0.0,
    ) -> Dict[str, Any]:
        created_at = self._now_iso()
        with self._connection(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO clinical_reviews (
                    created_at, profile_id, reviewer_name, reviewer_role,
                    decision, confounding_factors_json, clinical_notes,
                    mattr_snapshot, pause_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    profile_id,
                    reviewer_name.strip(),
                    reviewer_role.strip(),
                    decision.strip(),
                    json.dumps(confounding_factors, ensure_ascii=False),
                    clinical_notes.strip(),
                    float(mattr_snapshot),
                    float(pause_snapshot),
                ),
            )
            review_id = int(cur.lastrowid)

        return {
            "id": review_id,
            "created_at": created_at,
            "profile_id": profile_id,
            "reviewer_name": reviewer_name.strip(),
            "reviewer_role": reviewer_role.strip(),
            "decision": decision.strip(),
            "confounding_factors": list(confounding_factors),
            "clinical_notes": clinical_notes.strip(),
            "mattr_snapshot": float(mattr_snapshot),
            "pause_snapshot": float(pause_snapshot),
        }

    def get_clinical_reviews(
        self, profile_id: str = "don_manuel", limit: int = 30
    ) -> List[Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                """
                SELECT * FROM clinical_reviews
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
            results: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["confounding_factors"] = json.loads(
                        item.get("confounding_factors_json") or "[]"
                    )
                except json.JSONDecodeError:
                    item["confounding_factors"] = []
                results.append(item)
            return results

    # ------------------------------------------------------------------
    # Photo Metadata (Bidirectional Visual Anchor)
    # ------------------------------------------------------------------
    def upsert_photo_metadata(
        self,
        filename: str,
        profile_id: str,
        title: str,
        caption: str,
        theme: str = "familia_hogar",
        is_sample: bool = False,
    ) -> Dict[str, Any]:
        created_at = self._now_iso()
        with self._connection(write=True) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO photo_metadata (
                    filename, profile_id, title, caption, theme, is_sample, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    profile_id,
                    title.strip() or filename,
                    caption.strip(),
                    theme.strip() or "familia_hogar",
                    1 if is_sample else 0,
                    created_at,
                ),
            )
        return {
            "filename": filename,
            "profile_id": profile_id,
            "title": title.strip() or filename,
            "caption": caption.strip(),
            "theme": theme.strip() or "familia_hogar",
            "is_sample": bool(is_sample),
            "created_at": created_at,
        }

    def get_photo_metadata_map(self, profile_id: str = "don_manuel") -> Dict[str, Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                "SELECT * FROM photo_metadata WHERE profile_id = ? ORDER BY created_at ASC",
                (profile_id,),
            ).fetchall()
            out: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                item = dict(r)
                item["is_sample"] = bool(item["is_sample"])
                out[item["filename"]] = item
            return out

    def delete_photo_metadata(self, filename: str) -> None:
        with self._connection(write=True) as conn:
            conn.execute("DELETE FROM photo_metadata WHERE filename = ?", (filename,))

    # ------------------------------------------------------------------
    # Assisted Dual Consent Events
    # ------------------------------------------------------------------
    def insert_consent_event(
        self,
        profile_id: str,
        consent_type: str,
        acknowledged_by: str,
        summary_text: str,
    ) -> Dict[str, Any]:
        created_at = self._now_iso()
        with self._connection(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO consent_events (
                    created_at, profile_id, consent_type, acknowledged_by, summary_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (created_at, profile_id, consent_type, acknowledged_by, summary_text),
            )
            event_id = int(cur.lastrowid)
        return {
            "id": event_id,
            "created_at": created_at,
            "profile_id": profile_id,
            "consent_type": consent_type,
            "acknowledged_by": acknowledged_by,
            "summary_text": summary_text,
        }

    def get_consent_events(self, profile_id: str = "don_manuel") -> List[Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                "SELECT * FROM consent_events WHERE profile_id = ? ORDER BY id DESC LIMIT 20",
                (profile_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Telegram Family Bridge Logs
    # ------------------------------------------------------------------
    def insert_telegram_log(
        self,
        profile_id: str,
        level: int,
        title: str,
        message: str,
        delivered: bool,
        channel_status: str,
    ) -> Dict[str, Any]:
        created_at = self._now_iso()
        with self._connection(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO telegram_logs (
                    created_at, profile_id, level, title, message, delivered, channel_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    profile_id,
                    int(level),
                    title,
                    message,
                    1 if delivered else 0,
                    channel_status,
                ),
            )
            log_id = int(cur.lastrowid)
        return {
            "id": log_id,
            "created_at": created_at,
            "profile_id": profile_id,
            "level": int(level),
            "title": title,
            "message": message,
            "delivered": bool(delivered),
            "channel_status": channel_status,
        }

    def update_telegram_log_status(
        self, log_id: int, delivered: bool, channel_status: str
    ) -> None:
        """Update delivery outcome of an asynchronously dispatched Telegram alert."""
        with self._connection(write=True) as conn:
            conn.execute(
                """
                UPDATE telegram_logs
                SET delivered = ?, channel_status = ?
                WHERE id = ?
                """,
                (1 if delivered else 0, channel_status, int(log_id)),
            )

    def get_telegram_logs(
        self, profile_id: str = "don_manuel", limit: int = 25
    ) -> List[Dict[str, Any]]:
        with self._connection(write=False) as conn:
            rows = conn.execute(
                """
                SELECT * FROM telegram_logs
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
            results: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                item["delivered"] = bool(item["delivered"])
                results.append(item)
            return results

    # ------------------------------------------------------------------
    # Demo Pitch Reset Helper
    # ------------------------------------------------------------------
    def reset_demo_state(self, profile_id: str = "don_manuel") -> None:
        """Reset turns, reviews, telegram logs, and restore clean 21-day seed for pitch rehearsals."""
        with self._connection(write=True) as conn:
            conn.execute("DELETE FROM conversation_turns WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM clinical_reviews WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM telegram_logs WHERE profile_id = ?", (profile_id,))
        self.seed_longitudinal_days(profile_id=profile_id, force=True)
