"""
tests/scenario_runner.py
Synthetic Timeline Testing — 不需要真實對話，直接餵事件流觀察狀態演化
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import json

from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.render import render_temporal_block
from chrono_social_engine.persona_config.akane import AKANE

NY = ZoneInfo("America/New_York")


# ── DSL ────────────────────────────────────────────────────────

@dataclass
class MSG:
    text: str
    at: datetime           # 絕對時間

@dataclass
class WAIT:
    hours: float = 0.0
    days: float = 0.0

    def as_delta(self) -> timedelta:
        return timedelta(hours=self.hours, days=self.days)


# ── Snapshot ───────────────────────────────────────────────────

@dataclass
class StateSnapshot:
    timestamp: str
    message: str
    time_period: str
    silence_hours: float
    vulnerability_window: bool
    carryover_worry: float
    attachment_heat: float
    intimacy_afterglow: float
    reaction_bias: str
    temporal_salience: str
    expression_mode: str
    deviation: str
    stress: int

    def display(self) -> str:
        vw = "[VW!] " if self.vulnerability_window else "       "
        return (
            f"[{self.timestamp}] '{self.message}'\n"
            f"  {vw}period={self.time_period:<12} silence={self.silence_hours:>5.1f}h\n"
            f"     worry={self.carryover_worry:.2f}  heat={self.attachment_heat:.2f}"
            f"  afterglow={self.intimacy_afterglow:.2f}\n"
            f"     bias={self.reaction_bias:<22} salience={self.temporal_salience}"
            f"  mode={self.expression_mode}\n"
            f"     deviation={self.deviation:<20} stress={self.stress}"
        )


# ── Scenario Runner ──────────────────────────────────────────────

def run_scenario(title: str, events: list, db_path: str = ":memory:") -> list[StateSnapshot]:
    """
    依序執行 events，回傳每個狀態快照。
    events 成員：MSG(text, at) 或 WAIT(hours=N)
    """
    snapshots = []

    print(f"\n{'='*60}")
    print(f" SCENARIO: {title}")
    print(f"{'='*60}")

    # 初始狀態
    prev_ts = None   # 上一次 MSG 的時間（用於 last_msg_ts）
    last_msg = "(init)"

    for i, event in enumerate(events):
        if isinstance(event, WAIT):
            print(f"\n  [+ WAIT {event.hours:.1f}h / {event.days:.1f}d]")
            continue

        if isinstance(event, MSG):
            ts = event.at
            text = event.text
            last_msg = text

        # ── pre-hook ──────────────────────────────────────────
        # prev_ts = 上一次說話的時間（用於計算沉默）
        # ts = 這次評估的「現在」時間
        ts_str = prev_ts.isoformat() if prev_ts else None
        ctx, block, stress = run_pre_llm_hook(
            persona_id="akane",
            config=AKANE,
            last_msg_ts=ts_str,
            stress=50,
            db_path=db_path,
            now=ts,
        )

        # ── snapshot ─────────────────────────────────────────
        snap = StateSnapshot(
            timestamp=ts.strftime("%m-%d %H:%M") if ts else "init",
            message=last_msg[:40],
            time_period=ctx.time_period,
            silence_hours=ctx.silence_hours,
            vulnerability_window=ctx.momentum.vulnerability_window,
            carryover_worry=ctx.carryover.unresolved_worry,
            attachment_heat=ctx.carryover.attachment_heat,
            intimacy_afterglow=ctx.carryover.intimacy_afterglow,
            reaction_bias=render_temporal_block(ctx).split("reaction_bias=")[1].split("\n")[0] if "reaction_bias=" in render_temporal_block(ctx) else "unknown",
            temporal_salience=render_temporal_block(ctx).split("temporal_salience=")[1].split("\n")[0] if "temporal_salience=" in render_temporal_block(ctx) else "unknown",
            expression_mode=render_temporal_block(ctx).split("expression_mode=")[1].split("\n")[0] if "expression_mode=" in render_temporal_block(ctx) else "unknown",
            deviation=ctx.deviation_interpretation,
            stress=stress,
        )
        snapshots.append(snap)
        print(f"\n{snap.display()}")

        # ── post-hook ─────────────────────────────────────────
        if isinstance(event, MSG):
            run_post_llm_hook(ctx=ctx, config=AKANE, user_message=text, db_path=db_path, now=ts)
            prev_ts = ts  # 更新上一次說話時間

    return snapshots


def save_scenario_json(snapshots: list[StateSnapshot], filename: str) -> None:
    records = [asdict(s) for s in snapshots]
    Path(filename).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → JSON saved: {filename}")


# ── Diff Tool ────────────────────────────────────────────────────────────────

def diff_against_baseline(
    current: list[StateSnapshot],
    baseline_path: str,
    fields: list[str] = ["reaction_bias", "expression_mode", "carryover_worry",
                           "attachment_heat", "temporal_salience", "deviation"],
) -> None:
    """
    Compare current run snapshots against a stored baseline JSON.
    Usage:
        snaps = run_scenario(...)
        diff_against_baseline(snaps, "tests/scenarios/baseline/rhythm_break_v2.2.json")
    """
    import json
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))

    print(f"\n{'='*60}")
    print(f"DIFF vs {Path(baseline_path).name}")
    print(f"{'='*60}")

    found_diff = False
    for i, (cur, old) in enumerate(zip(current, baseline)):
        diffs = {}
        for k in fields:
            cur_val = getattr(cur, k, None)
            old_val = old.get(k)
            if str(old_val) != str(cur_val):
                diffs[k] = (old_val, cur_val)
        if diffs:
            found_diff = True
            print(f"\nSnapshot {i+1} [{cur.timestamp}] '{cur.message}'")
            for k, (before, after) in diffs.items():
                print(f"  {k}: {before}  →  {after}")

    if not found_diff:
        print("\n  [OK] No differences found — engine behavior unchanged")
    else:
        print(f"\n  [!] {sum(1 for c, b in zip(current, baseline) for k in fields if str(getattr(c, k)) != str(b.get(k)))} differences found")
