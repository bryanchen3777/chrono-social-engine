"""
test_integration_smoke.py — Phase 8 整合冒煙測試
"""

import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.persona_config.akane import AKANE


def test_full_lifecycle_akane():
    """模擬完整 pre → post 循環，確認不 crash"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    ctx, block, stress = run_pre_llm_hook(
        persona_id="akane",
        config=AKANE,
        last_msg_ts=None,
        stress=50,
        db_path=db_path,
    )
    assert "[Temporal Context]" in block or ctx.persona_id == "akane"
    assert 0 <= stress <= 100

    run_post_llm_hook(ctx, config=AKANE, user_message="沒事啦", db_path=db_path)


def test_pre_hook_with_silence():
    """有 long silence 的情境"""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=8)).isoformat()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    ctx, block, stress = run_pre_llm_hook(
        persona_id="akane",
        config=AKANE,
        last_msg_ts=past,
        stress=30,
        db_path=db_path,
    )
    assert ctx.silence_hours >= 7.0


def test_reassurance_reduces_worry():
    """確認 explicit_reassurance 關鍵字路徑正確降低 worry"""
    from chrono_social_engine.core import EmotionalCarryover
    from chrono_social_engine.db import save_carryover_to_db, load_carryover_from_db, init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)

    carry = EmotionalCarryover(
        intimacy_afterglow=0.3,
        unresolved_worry=0.8,
        emotional_openness_residue=0.3,
        attachment_heat=0.4,
        source_event="worry event",
        triggered_at="2026-01-01T00:00:00",
        decay_rate=0.08,
    )
    save_carryover_to_db(carry, "akane", db_path)

    ctx, _, _ = run_pre_llm_hook(
        persona_id="akane",
        config=AKANE,
        last_msg_ts=None,
        stress=50,
        db_path=db_path,
    )

    # Use keyword-based resolution (explicit_reassurance) which doesn't depend on time_period
    run_post_llm_hook(ctx, config=AKANE, user_message="謝謝你擔心，我會注意的", db_path=db_path)

    saved = load_carryover_from_db("akane", db_path)
    assert saved is not None
    # explicit_reassurance → worry -= 0.65, from 0.8 → 0.15
    assert saved.unresolved_worry < 0.8


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])