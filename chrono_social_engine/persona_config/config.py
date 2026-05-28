"""
config.py — PersonaConfig dataclass definition.
Single source of truth; imported by both __init__.py and per-character config files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo


@dataclass
class PersonaConfig:
    """
    角色特定參數。
    所有數值外部注入，engine 本體零角色假設。
    """
    persona_id: str
    decay_rate: float = 0.12
    vulnerability_hour_start: int = 22   # 深夜區間起點（可跨越午夜）
    vulnerability_hour_end: int = 4        # 深夜區間終點（< start 表示跨午夜）
    vulnerability_inhibition_threshold: float = 0.50
    vulnerability_silence_min: float = 4.0  # 小時
    worry_resolution_delta: float = 0.6
    attachment_heat_bump: float = 0.1
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/New_York"))
