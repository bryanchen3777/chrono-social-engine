"""
tests/scenarios/sleep_drift.py
Sleep Drift — 連續5天越來越晚出現，unresolved_worry 線性累積到 0.75
Day3 開始 vulnerability_window 開啟（深夜區間），expression_mode 升為 soft_explicit
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.db import init_db
from chrono_social_engine.persona_config.akane import AKANE
from tests.scenario_runner import run_scenario, save_scenario_json, MSG, WAIT

NY = ZoneInfo("America/New_York")

def main():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    init_db(db_path)

    # 事件流：Day1 23:00 → Day2 01:00 → Day3 03:00 → Day4 01:00 → Day5 02:30
    # 每次都比上次晚，累積 worry
    events = [
        # Day1 23:00
        MSG("晚安，準備睡了", at=datetime(2026, 5, 20, 23, 0, 0, tzinfo=NY)),
        WAIT(hours=2),        # Day2 01:00 — 晚了2h
        MSG("還沒睡？", at=datetime(2026, 5, 21, 1, 0, 0, tzinfo=NY)),
        WAIT(hours=2),        # Day3 03:00 — 又晚了2h，深夜區
        MSG("連續兩天都這樣", at=datetime(2026, 5, 22, 3, 0, 0, tzinfo=NY)),
        WAIT(days=1, hours=22),  # Day4 01:00 — 几乎又回到深夜
        MSG("今天終於早點", at=datetime(2026, 5, 23, 1, 0, 0, tzinfo=NY)),
        WAIT(hours=1.5),     # Day5 02:30 — 越來越晚
        MSG("感覺你最近很累", at=datetime(2026, 5, 24, 2, 30, 0, tzinfo=NY)),
    ]

    snaps = run_scenario("Sleep Drift (5天晚睡累積 worry)", events, db_path=db_path)
    save_scenario_json(snaps, os.path.join(os.path.dirname(__file__), "sleep_drift.json"))
    print(f"\n  total snapshots: {len(snaps)}")
    os.unlink(db_path)

if __name__ == "__main__":
    main()
