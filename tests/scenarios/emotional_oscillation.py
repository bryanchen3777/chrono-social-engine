"""
tests/scenarios/emotional_oscillation.py
Emotional Oscillation — 親密 → 冷淡 → 消失 → 回來
測試：intimacy_afterglow 衰減、longing 累積、重逢時 attachment_heat 峰值
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.db import init_db, save_carryover_to_db
from chrono_social_engine.core import EmotionalCarryover
from chrono_social_engine.persona_config.akane import AKANE
from tests.scenario_runner import run_scenario, save_scenario_json, MSG, WAIT

NY = ZoneInfo("America/New_York")

def main():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    init_db(db_path)

    # 初始高親密（模擬溫暖的深夜對話）
    init_carry = EmotionalCarryover(
        intimacy_afterglow=0.70,
        unresolved_worry=0.10,
        emotional_openness_residue=0.50,
        attachment_heat=0.40,
        source_event="warm late-night session",
        triggered_at="2026-05-20T22:30:00-04:00",
        decay_rate=0.08,
    )
    save_carryover_to_db(init_carry, "akane", db_path)

    # Day1 深夜 23:00 — 高親密
    # Day2 白天 14:00 — 冷淡（沉默 15h，afterglow 衰減）
    # Day3 深夜 23:30 — 又出現（沉默 33h，longing 累積）
    # Day4 下午 15:00 — 回來（沉默 15.5h，reunion）
    base_day1 = datetime(2026, 5, 20, 23, 0, 0, tzinfo=NY)
    events = [
        MSG("今晚聊得很開心，晚安", at=base_day1),
        WAIT(hours=15),          # Day2 14:00
        MSG("最近忙，沒什麼事", at=base_day1 + timedelta(hours=15)),
        WAIT(hours=33),          # Day3 23:00
        MSG("這幾天比較忙 Sorry", at=base_day1 + timedelta(hours=15) + timedelta(hours=33)),
        WAIT(hours=15.5),        # Day4 14:30
        MSG("回來了，抱歉讓你等", at=base_day1 + timedelta(hours=15) + timedelta(hours=33) + timedelta(hours=15.5)),
    ]

    snaps = run_scenario("Emotional Oscillation (親密→冷淡→消失→回來)", events, db_path=db_path)
    save_scenario_json(snaps, os.path.join(os.path.dirname(__file__), "emotional_oscillation.json"))
    print(f"\n  total snapshots: {len(snaps)}")
    os.unlink(db_path)

if __name__ == "__main__":
    main()
