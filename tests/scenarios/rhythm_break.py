"""
tests/scenarios/rhythm_break.py
Rhythm Break — 30小時沉默 → 深夜脆弱窗口觸發 → 重逢 → 再次消失48h
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.db import save_carryover_to_db, load_carryover_from_db, init_db
from chrono_social_engine.core import EmotionalCarryover
from chrono_social_engine.persona_config.akane import AKANE
from tests.scenario_runner import run_scenario, save_scenario_json, MSG, WAIT

NY = ZoneInfo("America/New_York")

def main():
    # 使用 temp file db 以保留 carryover 跨 turn
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    init_db(db_path)

    # 預填初始 carryover（模擬之前有過一段溫暖對話）
    init_carry = EmotionalCarryover(
        intimacy_afterglow=0.40,
        unresolved_worry=0.10,
        emotional_openness_residue=0.20,
        attachment_heat=0.25,
        source_event="warm prior session",
        triggered_at="2026-05-20T21:00:00-04:00",
        decay_rate=0.08,
    )
    save_carryover_to_db(init_carry, "akane", db_path)
    print(f"  pre-filled carryover: worry={init_carry.unresolved_worry}, heat={init_carry.attachment_heat}")

    # 事件流
    base = datetime(2026, 5, 20, 21, 0, 0, tzinfo=NY)   # Day1 21:00
    events = [
        MSG("偶爾晚睡也沒關係啦", at=base),
        WAIT(hours=30),         # Day3 03:00 — 30h沉默，應觸發 vulnerability_window
        MSG("還在嗎？", at=base + timedelta(hours=30)),
        WAIT(days=1.5),         # Day4 15:00 — 重逢
        MSG("回來了，今天比較忙", at=base + timedelta(hours=30) + timedelta(days=1.5)),
        WAIT(hours=48),         # Day6 15:00 — 再次消失48h（衰退）
        MSG("抱歉讓你等了", at=base + timedelta(hours=30) + timedelta(days=1.5) + timedelta(hours=48)),
    ]

    snaps = run_scenario("Rhythm Break (30h沉默 → 重逢 → 48h衰退)", events, db_path=db_path)
    save_scenario_json(snaps, os.path.join(os.path.dirname(__file__), "rhythm_break.json"))
    print(f"\n  total snapshots: {len(snaps)}")
    os.unlink(db_path)

if __name__ == "__main__":
    main()
