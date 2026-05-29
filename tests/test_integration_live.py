"""
test_integration_live.py — Standalone smoke test for chrono-social-engine
不碰 Hermes/Akane對話記憶，直接呼叫 hooks 驗證功能完整性。

Run:
    python test_integration_live.py
"""

import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.persona_config.akane import AKANE


def test_full_lifecycle_no_crash():
    """pre → post 完整 cycle，不拋錯"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    ctx, block, stress = run_pre_llm_hook(
        persona_id="akane",
        config=AKANE,
        last_msg_ts=None,
        stress=50,
        db_path=db_path,
    )
    assert block, "block should not be empty"
    assert 0 <= stress <= 100, f"stress {stress} out of range"
    assert ctx.persona_id == "akane"

    run_post_llm_hook(ctx, config=AKANE, user_message="沒事啦", db_path=db_path)
    print("[PASS] test_full_lifecycle_no_crash")


def test_new_message_via_telegram():
    """模擬 Telegram 新對話（session reset）"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=8)).isoformat()
    ctx, block, stress = run_pre_llm_hook(
        persona_id="akane",
        config=AKANE,
        last_msg_ts=past,
        stress=30,
        db_path=db_path,
    )
    # 8小時沉默，應觸發 long-silence 逻辑
    assert ctx.silence_hours >= 7.0, f"silence_hours={ctx.silence_hours} too low"
    assert "[CHRONO_SOCIAL_CONTEXT v2.2]" in block, "block missing v2.2 header"
    print(f"[PASS] test_new_message_via_telegram  (silence_hours={ctx.silence_hours:.2f})")


def test_worry_resolution_by_explicit_reassurance():
    """explicit_reassurance 關鍵字 → unresolved_worry 下降"""
    from chrono_social_engine.db import save_carryover_to_db, load_carryover_from_db, init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)

    from chrono_social_engine.core import EmotionalCarryover
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

    run_post_llm_hook(ctx, config=AKANE, user_message="謝謝你擔心，我會注意的", db_path=db_path)

    saved = load_carryover_from_db("akane", db_path)
    assert saved is not None, "carryover should be saved"
    assert saved.unresolved_worry < 0.8, f"worry not reduced: {saved.unresolved_worry}"
    print(f"[PASS] test_worry_resolution  (worry: 0.8 → {saved.unresolved_worry:.2f})")


def test_reassurance_by_user_confirmed_ok():
    """user_confirmed_ok 關鍵字 → worry 下降"""
    from chrono_social_engine.db import save_carryover_to_db, load_carryover_from_db, init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)

    from chrono_social_engine.core import EmotionalCarryover
    carry = EmotionalCarryover(
        intimacy_afterglow=0.3,
        unresolved_worry=0.7,
        emotional_openness_residue=0.3,
        attachment_heat=0.4,
        source_event="test event",
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

    run_post_llm_hook(ctx, config=AKANE, user_message="放心，我沒事了", db_path=db_path)

    saved = load_carryover_from_db("akane", db_path)
    assert saved is not None
    assert saved.unresolved_worry < 0.7, f"worry not reduced: {saved.unresolved_worry}"
    print(f"[PASS] test_user_confirmed_ok  (worry: 0.7 → {saved.unresolved_worry:.2f})")


def test_profile_detection():
    """
    驗證 Hermes hook 的 kwargs 結構。
    模擬 pre_llm_call 的 kwargs（從 hermes_cli/hooks.py 的 spec 取得）。
    """
    # 模擬 Hermes 實際呼叫時的 kwargs
    mock_kwargs = {
        "session_id": "test-session",
        "user_message": "test",
        "conversation_history": [],
        "is_first_turn": True,
        "model": "gpt-4",
        "platform": "telegram",
        # 注意：沒有 "profile" key
    }

    # 測試 plugin 裡的 profile 判断邏輯
    import sys as _sys
    _sys.path.insert(0, r"C:\Users\bbfcc\AppData\Local\hermes\profiles\akane\plugins")
    from akane_behavior import _get_profile_name

    # _get_profile_name() 靠 sys.argv 找 --profile，但 Hermes 沒傳
    profile_from_argv = _get_profile_name()
    print(f"  _get_profile_name() from sys.argv: {repr(profile_from_argv)}")

    # kwargs.get("profile", "") 從 hook kwargs 拿，也沒有
    profile_from_kwargs = mock_kwargs.get("profile", "")
    print(f"  kwargs.get('profile', ''): {repr(profile_from_kwargs)}")

    # platform 是唯一靠譜的 key
    platform = mock_kwargs.get("platform", "")
    print(f"  kwargs.get('platform', ''): {repr(platform)}")

    # 結論：不能用 profile != "akane" 判斷，應該用 platform
    assert platform == "telegram", f"expected telegram, got {platform}"
    print(f"  → 結論：套用於 platform={platform} 的所有 profile")
    print("[PASS] test_profile_detection")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])