"""
core.py — 時間-社交感知引擎核心資料結構與計算邏輯
Engine core: data structures and computation logic for temporal-emotional state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Literal

# ── Time Period Definitions ──────────────────────────────────────────────────

"""
TIME_PERIODS — 每條：(start_hour, end_hour, name)
end_hour 不包含在區間內。
注意：沒有覆蓋 (0, 1) 的 midnight 段，落在 deep_night。
"""
TIME_PERIODS = [
    (4, 7,  "dawn"),       # 04:00–06:59
    (7, 12, "morning"),    # 07:00–11:59
    (12, 18,"afternoon"),  # 12:00–17:59
    (18, 22,"evening"),    # 18:00–21:59
    (22, 24,"night"),      # 22:00–23:59
    (0, 4,  "deep_night"), # 00:00–03:59
]

# ── Sleep Pressure Curve ──────────────────────────────────────────────────────

"""
鐘形曲線資料：hour → sleep_pressure (0.0~1.0)
凌晨最高，下午最低，晚上回升。
每小時一筆，24 小時。
"""
_SLEEP_PRESSURE_CURVE: tuple[tuple[int, float], ...] = tuple(
    (h, max(0.02, round(math.exp(-0.5 * ((h - 2) / 3) ** 2), 2)))
    for h in range(24)
)

# ── Emotional Inhibition Range ───────────────────────────────────────────────

"""
emotional_inhibition 的計算区间：
silence_hours → inhibition_level 的 mapping。
"""
_INHIBITION_RANGES: tuple[tuple[float, float, float], ...] = (
    (0.0,  2.0, 0.00),
    (2.0,  6.0, 0.15),
    (6.0,  12.0,0.35),
    (12.0, 24.0,0.55),
    (24.0, 72.0,0.75),
    (72.0, 200.0, 0.88),
    (200.0, float('inf'), 1.00),
)


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class EmotionalCarryover:
    """
    跨 session 攜帶的情感狀態。
    所有 float 欄位範圍：0.0 ~ 1.0。
    """
    intimacy_afterglow: float = 0.0          # 親密餘溫（會自然衰減）
    unresolved_worry: float = 0.0            # 未解除的擔心（衰退較慢，有 floor）
    emotional_openness_residue: float = 0.0  # 情感開放殘留
    attachment_heat: float = 0.0            # 依戀熱度
    source_event: str = ""                  # 觸發的事件描述
    triggered_at: str = ""                  # ISO 8601 timestamp
    decay_rate: float = 0.12                 # 從 PersonaConfig 帶入

    def apply_decay(self, elapsed_hours: float) -> EmotionalCarryover:
        """對所有欄位套用指數衰減，unresolved_worry 有 floor (original * 0.25)。"""
        factor = (1 - self.decay_rate) ** elapsed_hours
        new_worry_floor = self.unresolved_worry * 0.25 if self.unresolved_worry > 0 else 0.0
        new_worry = max(new_worry_floor, self.unresolved_worry * factor)
        return EmotionalCarryover(
            intimacy_afterglow=max(0.0, self.intimacy_afterglow * factor),
            unresolved_worry=new_worry,
            emotional_openness_residue=max(0.0, self.emotional_openness_residue * factor),
            attachment_heat=max(0.0, self.attachment_heat * factor),
            source_event=self.source_event,
            triggered_at=self.triggered_at,
            decay_rate=self.decay_rate,
        )


@dataclass
class MomentumState:
    """當前對話中的即時狀態。"""
    vulnerability_window: bool = False        # 是否在深夜脆弱窗口
    emotional_amplification: float = 0.0     # <0 抑制, >0 放大


@dataclass
class AnticipatoryState:
    """對用戶未來行為的預期。"""
    preoccupation_flavor: Literal["none", "longing", "worried", "anxious"] = "none"
    expected_presence_prob: float = 0.5      # 靜態預設，v3 改為動態計算
    silence_hours: float = 0.0
    is_overdue: bool = False                 # True when silence_hours > 48


@dataclass
class TemporalContext:
    """
    完整時間-社交上下文。
    這是 render.py 和 hooks.py 的主要輸入。
    """
    persona_id: str
    current_hour: int
    time_period: str
    silence_hours: float
    carryover: EmotionalCarryover
    momentum: MomentumState
    anticipatory: AnticipatoryState
    deviation_interpretation: str  # normal/sleep_deprivation/longing/missing
    emotional_inhibition: float    # 0.0~1.0，越大越不會說心裡話
    stress: int                     # 0~100


@dataclass
class PersonaConfig:
    """
    角色特定參數。
    Engine 本體不帶任何角色假設，所有數值從這裡注入。
    """
    persona_id: str
    decay_rate: float = 0.12
    vulnerability_hour_start: int = 22  # 深夜區間 start（可跨越午夜）
    vulnerability_hour_end: int = 4      # 深夜區間 end
    vulnerability_inhibition_threshold: float = 0.50
    vulnerability_silence_min: float = 4.0  # 小時
    worry_resolution_delta: float = 0.6
    attachment_heat_bump: float = 0.1
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("Asia/Tokyo"))


# ── Computation Functions ──────────────────────────────────────────────────────

def compute_time_period(hour: int) -> str:
    """
    根據 hour 回傳 TIME_PERIODS 中對應的時間區間名稱。
    預設（不在任何區間）："deep_night"。
    """
    for start, end, name in TIME_PERIODS:
        if start <= hour < end:
            return name
    return "deep_night"


def compute_sleep_pressure(current_hour: int) -> float:
    """
    鐘形曲線：凌晨最高 (~1.0)，下午最低 (~0.0)。
    用 _SLEEP_PRESSURE_CURVE tuple 查表，無需每次重建。
    """
    for h, p in _SLEEP_PRESSURE_CURVE:
        if h == current_hour:
            return max(0.0, min(1.0, p))
    return 0.0


def _get_inhibition_for_silence(silence_hours: float) -> float:
    """根據沉默時長查表回傳 inhibition 等級。"""
    for low, high, value in _INHIBITION_RANGES:
        if low <= silence_hours < high:
            return value
    return 0.88  # 72h+


def compute_emotional_inhibition(
    silence_hours: float,
    vulnerability_window: bool,
    sleep_deprivation: bool,
) -> float:
    """
    計算情緒抑制程度 (0.0~1.0)。
    - silence_hours 越長 → 抑制越高
    - vulnerability_window 開啟 → 抑制降低
    - sleep_deprivation → 抑制降低（對方說話可能不經大腦）
    """
    base = _get_inhibition_for_silence(silence_hours)
    if vulnerability_window:
        base = max(0.0, base - 0.35)
    if sleep_deprivation:
        base = max(0.0, base - 0.25)
    return min(1.0, base)


def compute_vulnerability_window(
    current_hour: int,
    silence_hours: float,
    config: PersonaConfig,
) -> bool:
    """
    深夜脆弱窗口判定。
    條件：當前時間在角色設定的深夜區間內
          且沉默時長 >= 角色設定的門檻
    支援跨越午夜的區間（如 22:00 ~ 04:00）。
    """
    start = config.vulnerability_hour_start
    end = config.vulnerability_hour_end

    if start <= end:
        in_hour_range = start <= current_hour < end
    else:
        # 跨越午夜：22~04 → 22<=hour<24 或 0<=hour<4
        in_hour_range = current_hour >= start or current_hour < end

    if not in_hour_range:
        return False
    return silence_hours >= config.vulnerability_silence_min


def build_temporal_context(
    persona_id: str,
    last_msg_ts: str | None,
    current_stress: int,
    carryover: EmotionalCarryover,
    config: PersonaConfig,
    now: datetime | None = None,
) -> TemporalContext:
    """
    根據狀態建立完整 TemporalContext。
    """
    if now is None:
        now = datetime.now(config.timezone)
    current_hour = now.hour
    time_period = compute_time_period(current_hour)

    # 計算沉默時長
    if last_msg_ts:
        try:
            prev = datetime.fromisoformat(last_msg_ts)
            silence_hours = (now - prev).total_seconds() / 3600.0
            silence_hours = max(0.0, silence_hours)
        except (ValueError, TypeError):
            silence_hours = 0.0
    else:
        silence_hours = 0.0

    # Momentum
    vuln_window = compute_vulnerability_window(current_hour, silence_hours, config)
    sleep_pressure = compute_sleep_pressure(current_hour)
    sleep_dep = sleep_pressure > 0.7 and time_period in ("deep_night", "night")
    emotional_inhibition = compute_emotional_inhibition(silence_hours, vuln_window, sleep_dep)

    amplification = 0.0
    if vuln_window:
        amplification += 0.20
    if sleep_dep:
        amplification += 0.15
    if carryover.intimacy_afterglow > 0.6:
        amplification += 0.10
    if carryover.unresolved_worry > 0.5:
        amplification -= 0.15

    momentum = MomentumState(
        vulnerability_window=vuln_window,
        emotional_amplification=max(-0.5, min(0.5, amplification)),
    )

    # Anticipatory
    if silence_hours > 24:
        flavor: Literal["none", "longing", "worried", "anxious"] = "longing"
        expected_prob = 0.3
    elif silence_hours > 8:
        flavor = "worried"
        expected_prob = 0.4
    else:
        flavor = "none"
        expected_prob = 0.6

    anticipatory = AnticipatoryState(
        preoccupation_flavor=flavor,
        expected_presence_prob=expected_prob,
        silence_hours=silence_hours,
        is_overdue=silence_hours > 48,
    )

    # Deviation interpretation
    if time_period in ("deep_night", "night") and sleep_pressure > 0.7:
        deviation = "sleep_deprivation"
    elif silence_hours > 48:
        deviation = "longing"
    elif silence_hours > 24:
        deviation = "missing"
    else:
        deviation = "normal"

    return TemporalContext(
        persona_id=persona_id,
        current_hour=current_hour,
        time_period=time_period,
        silence_hours=silence_hours,
        carryover=carryover,
        momentum=momentum,
        anticipatory=anticipatory,
        deviation_interpretation=deviation,
        emotional_inhibition=emotional_inhibition,
        stress=current_stress,
    )


def merge_carryover(
    existing: EmotionalCarryover | None,
    new: EmotionalCarryover,
) -> EmotionalCarryover:
    """
    合併兩個 carryover：
    - 取最高值（不做平均，避免稀釋重要情緒）
    - source_event 保留較新的
    """
    if existing is None:
        return new

    def mx(a: float, b: float) -> float:
        return max(a, b)

    return EmotionalCarryover(
        intimacy_afterglow=mx(existing.intimacy_afterglow, new.intimacy_afterglow),
        unresolved_worry=mx(existing.unresolved_worry, new.unresolved_worry),
        emotional_openness_residue=mx(existing.emotional_openness_residue, new.emotional_openness_residue),
        attachment_heat=mx(existing.attachment_heat, new.attachment_heat),
        source_event=new.source_event if new.triggered_at >= existing.triggered_at else existing.source_event,
        triggered_at=max(existing.triggered_at, new.triggered_at),
        decay_rate=new.decay_rate,
    )


def decay_carryover(carryover: EmotionalCarryover, elapsed_hours: float) -> EmotionalCarryover:
    """套用衰減。delegate 到 carryover 自身的方法。"""
    return carryover.apply_decay(elapsed_hours)