"""
test_db.py — db.py 單元測試
"""

import os
import tempfile

import pytest

from chrono_social_engine.core import EmotionalCarryover
from chrono_social_engine.db import init_db, load_carryover_from_db, save_carryover_to_db


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


class TestInitDb:
    def test_init_creates_table(self, tmp_db):
        init_db(tmp_db)
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='emotional_carryover'"
        )
        assert cur.fetchone() is not None
        conn.close()


class TestLoadSave:
    def test_save_and_load(self, tmp_db):
        init_db(tmp_db)
        carry = EmotionalCarryover(
            intimacy_afterglow=0.6,
            unresolved_worry=0.4,
            emotional_openness_residue=0.3,
            attachment_heat=0.5,
            source_event="test event",
            triggered_at="2026-01-01T12:00:00",
            decay_rate=0.08,
        )
        save_carryover_to_db(carry, "akane", tmp_db)

        loaded = load_carryover_from_db("akane", tmp_db)
        assert loaded is not None
        assert loaded.intimacy_afterglow == 0.6
        assert loaded.unresolved_worry == 0.4
        assert loaded.source_event == "test event"
        assert loaded.decay_rate == 0.08

    def test_load_nonexistent_returns_none(self, tmp_db):
        init_db(tmp_db)
        result = load_carryover_from_db("nonexistent_persona", tmp_db)
        assert result is None

    def test_upsert_replaces(self, tmp_db):
        init_db(tmp_db)
        c1 = EmotionalCarryover(
            intimacy_afterglow=0.5,
            unresolved_worry=0.5,
            emotional_openness_residue=0.5,
            attachment_heat=0.5,
            source_event="first",
            triggered_at="2026-01-01T10:00:00",
            decay_rate=0.12,
        )
        save_carryover_to_db(c1, "akane", tmp_db)

        c2 = EmotionalCarryover(
            intimacy_afterglow=0.8,
            unresolved_worry=0.9,
            emotional_openness_residue=0.7,
            attachment_heat=0.6,
            source_event="second",
            triggered_at="2026-01-01T12:00:00",
            decay_rate=0.08,
        )
        save_carryover_to_db(c2, "akane", tmp_db)

        loaded = load_carryover_from_db("akane", tmp_db)
        assert loaded.intimacy_afterglow == 0.8
        assert loaded.unresolved_worry == 0.9
        assert loaded.source_event == "second"

    def test_corrupted_db_returns_none(self, tmp_db):
        init_db(tmp_db)
        with open(tmp_db, "w") as f:
            f.write("not a valid sqlite file")
        result = load_carryover_from_db("akane", tmp_db)
        assert result is None

    def test_roundtrip_preserves_timezone(self, tmp_db):
        """時區aware datetime寫入後讀回仍保持tzinfo"""
        init_db(tmp_db)
        from zoneinfo import ZoneInfo
        from datetime import datetime

        jst = ZoneInfo("Asia/Tokyo")
        now = datetime.now(jst)
        carry = EmotionalCarryover(
            intimacy_afterglow=0.5,
            unresolved_worry=0.3,
            emotional_openness_residue=0.2,
            attachment_heat=0.1,
            source_event="tz test",
            triggered_at=now.isoformat(),
            decay_rate=0.08,
        )
        save_carryover_to_db(carry, "akane", tmp_db)

        loaded = load_carryover_from_db("akane", tmp_db)
        assert loaded is not None
        # SQLite stores as TEXT ISO 8601; parsing back gives naive str
        # Check the string format is preserved (no data loss)
        assert "T" in loaded.triggered_at  # ISO format
        assert "Asia/Tokyo" in loaded.triggered_at or "+09:00" in loaded.triggered_at

    def test_upsert_does_not_affect_other_persona(self, tmp_db):
        """ON CONFLICT upsert只更新目標角色，不影響其他人的資料"""
        init_db(tmp_db)

        # 先寫入 akari 的 carryover
        akari_carry = EmotionalCarryover(
            intimacy_afterglow=0.7,
            unresolved_worry=0.6,
            emotional_openness_residue=0.5,
            attachment_heat=0.4,
            source_event="akari event",
            triggered_at="2026-01-01T10:00:00",
            decay_rate=0.10,
        )
        save_carryover_to_db(akari_carry, "akari", tmp_db)

        # 再寫入 akane 的 carryover（ upsert 會衝突）
        akane_carry = EmotionalCarryover(
            intimacy_afterglow=0.9,
            unresolved_worry=0.1,
            emotional_openness_residue=0.3,
            attachment_heat=0.2,
            source_event="akane event",
            triggered_at="2026-01-01T12:00:00",
            decay_rate=0.08,
        )
        save_carryover_to_db(akane_carry, "akane", tmp_db)

        # akari 的資料不應該被改變
        akari_loaded = load_carryover_from_db("akari", tmp_db)
        assert akari_loaded is not None
        assert akari_loaded.intimacy_afterglow == 0.7
        assert akari_loaded.unresolved_worry == 0.6
        assert akari_loaded.source_event == "akari event"

        # akane 的資料正確寫入
        akane_loaded = load_carryover_from_db("akane", tmp_db)
        assert akane_loaded.intimacy_afterglow == 0.9
        assert akane_loaded.source_event == "akane event"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])