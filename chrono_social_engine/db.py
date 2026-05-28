"""
db.py — SQLite 持久化層
"""

from __future__ import annotations

import json
from pathlib import Path

from .core import EmotionalCarryover

DB_PATH = Path(__file__).parent.parent / "data" / "chrono_memory.db"


def init_db(db_path: str | Path = DB_PATH) -> None:
    """初始化資料庫 schema。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotional_carryover (
            persona_id                  TEXT PRIMARY KEY,
            intimacy_afterglow          REAL DEFAULT 0.0,
            unresolved_worry            REAL DEFAULT 0.0,
            emotional_openness_residue  REAL DEFAULT 0.0,
            attachment_heat             REAL DEFAULT 0.0,
            source_event               TEXT DEFAULT '',
            triggered_at               TEXT NOT NULL,
            decay_rate                 REAL DEFAULT 0.12
        )
    """)
    conn.commit()
    conn.close()


def load_carryover_from_db(persona_id: str, db_path: str | Path = DB_PATH) -> EmotionalCarryover | None:
    """
    從 DB 載入指定角色的 carryover。
    任何錯誤回傳 None，不 raise。
    """
    import sqlite3
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM emotional_carryover WHERE persona_id = ?",
            (persona_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return EmotionalCarryover(
            intimacy_afterglow=row["intimacy_afterglow"],
            unresolved_worry=row["unresolved_worry"],
            emotional_openness_residue=row["emotional_openness_residue"],
            attachment_heat=row["attachment_heat"],
            source_event=row["source_event"],
            triggered_at=row["triggered_at"],
            decay_rate=row["decay_rate"],
        )
    except Exception:
        return None


def save_carryover_to_db(carryover: EmotionalCarryover, persona_id: str, db_path: str | Path = DB_PATH) -> None:
    """Upsert carryover 到 DB。"""
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("""
        INSERT INTO emotional_carryover
            (persona_id, intimacy_afterglow, unresolved_worry,
             emotional_openness_residue, attachment_heat,
             source_event, triggered_at, decay_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(persona_id) DO UPDATE SET
            intimacy_afterglow = excluded.intimacy_afterglow,
            unresolved_worry = excluded.unresolved_worry,
            emotional_openness_residue = excluded.emotional_openness_residue,
            attachment_heat = excluded.attachment_heat,
            source_event = excluded.source_event,
            triggered_at = excluded.triggered_at,
            decay_rate = excluded.decay_rate
    """, (
        persona_id,
        carryover.intimacy_afterglow,
        carryover.unresolved_worry,
        carryover.emotional_openness_residue,
        carryover.attachment_heat,
        carryover.source_event,
        carryover.triggered_at,
        carryover.decay_rate,
    ))
    conn.commit()
    conn.close()