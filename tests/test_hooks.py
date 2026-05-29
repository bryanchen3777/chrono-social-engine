"""
test_hooks.py — hooks.py 整合測試
"""

import os
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chrono_social_engine.core import EmotionalCarryover, PersonaConfig, TemporalContext, MomentumState, AnticipatoryState
from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.persona_config import AKANE


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


AKANE_CFG = AKANE


class TestRunPreLlMHook:
    def test_returns_tuple_of_three(self, tmp_db):
        ctx, block, stress = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE_CFG,
            last_msg_ts=None,
            stress=50,
            db_path=tmp_db,
        )
        assert isinstance(ctx, TemporalContext)
        assert isinstance(block, str)
        assert isinstance(stress, int)
        assert 0 <= stress <= 100

    def test_block_contains_temporal_context(self, tmp_db):
        _, block, _ = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE_CFG,
            last_msg_ts=None,
            stress=40,
            db_path=tmp_db,
        )
        assert "[CHRONO_SOCIAL_CONTEXT v2.2]" in block

    def test_silence_hours_calculated(self, tmp_db):
        past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=7)).isoformat()
        ctx, _, _ = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE_CFG,
            last_msg_ts=past,
            stress=20,
            db_path=tmp_db,
        )
        assert ctx.silence_hours >= 6.0

    def test_carryover_loaded_from_db(self, tmp_db):
        # 先寫入 carryover
        carry = EmotionalCarryover(
            intimacy_afterglow=0.7,
            unresolved_worry=0.5,
            emotional_openness_residue=0.4,
            attachment_heat=0.3,
            source_event="test carryover",
            triggered_at=datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            decay_rate=0.08,
        )
        from chrono_social_engine.db import save_carryover_to_db, init_db
        init_db(tmp_db)
        save_carryover_to_db(carry, "akane", tmp_db)

        ctx, _, _ = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE_CFG,
            last_msg_ts=None,
            stress=30,
            db_path=tmp_db,
        )
        assert ctx.carryover.intimacy_afterglow == 0.7

    def test_decays_carryover_on_load(self, tmp_db):
        from chrono_social_engine.db import save_carryover_to_db, init_db
        init_db(tmp_db)
        old_carry = EmotionalCarryover(
            intimacy_afterglow=1.0,
            unresolved_worry=1.0,
            emotional_openness_residue=0.5,
            attachment_heat=0.5,
            source_event="old",
            triggered_at=(datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=12)).isoformat(),
            decay_rate=0.12,
        )
        save_carryover_to_db(old_carry, "akane", tmp_db)

        past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=12)).isoformat()
        ctx, _, _ = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE_CFG,
            last_msg_ts=past,
            stress=30,
            db_path=tmp_db,
        )
        # (1-0.12)^12 ≈ 0.20, 所以 intimacy ≈ 0.20
        assert ctx.carryover.intimacy_afterglow < 0.5


class TestRunPostLlMHook:
    def test_creates_carryover_and_saves(self, tmp_db):
        from chrono_social_engine.db import init_db
        init_db(tmp_db)

        past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=5)).isoformat()
        carry = EmotionalCarryover(
            intimacy_afterglow=0.6,
            unresolved_worry=0.8,
            emotional_openness_residue=0.3,
            attachment_heat=0.4,
            source_event="worry event",
            triggered_at=past,
            decay_rate=0.08,
        )
        from chrono_social_engine.db import save_carryover_to_db
        save_carryover_to_db(carry, "akane", tmp_db)

        ctx = TemporalContext(
            persona_id="akane",
            current_hour=2,
            time_period="deep_night",
            silence_hours=5.0,
            carryover=carry,
            momentum=MomentumState(vulnerability_window=True, emotional_amplification=0.2),
            anticipatory=AnticipatoryState(preoccupation_flavor="none", expected_presence_prob=0.4, silence_hours=5.0),
            deviation_interpretation="sleep_deprivation",
            emotional_inhibition=0.2,
            stress=50,
        )

        run_post_llm_hook(ctx, config=AKANE_CFG, user_message="我沒事", db_path=tmp_db)

        from chrono_social_engine.db import load_carryover_from_db
        saved = load_carryover_from_db("akane", tmp_db)
        assert saved is not None
        assert saved.intimacy_afterglow > 0

    def test_resolution_reduces_worry(self, tmp_db):
        from chrono_social_engine.db import init_db, save_carryover_to_db
        init_db(tmp_db)

        carry = EmotionalCarryover(
            intimacy_afterglow=0.3,
            unresolved_worry=0.8,
            emotional_openness_residue=0.3,
            attachment_heat=0.4,
            source_event="test",
            triggered_at=datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            decay_rate=0.08,
        )
        save_carryover_to_db(carry, "akane", tmp_db)

        ctx = TemporalContext(
            persona_id="akane",
            current_hour=9,
            time_period="morning",
            silence_hours=3.0,
            carryover=carry,
            momentum=MomentumState(vulnerability_window=False, emotional_amplification=0.0),
            anticipatory=AnticipatoryState(preoccupation_flavor="none", expected_presence_prob=0.6, silence_hours=3.0),
            deviation_interpretation="normal",
            emotional_inhibition=0.3,
            stress=30,
        )

        run_post_llm_hook(ctx, config=AKANE_CFG, user_message="放心我沒事", db_path=tmp_db)

        from chrono_social_engine.db import load_carryover_from_db
        saved = load_carryover_from_db("akane", tmp_db)
        assert saved.unresolved_worry < 0.8  # worry 被降低了


if __name__ == "__main__":
    pytest.main([__file__, "-v"])