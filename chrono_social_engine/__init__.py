"""
Chrono-Social Engine
時間-社交感知引擎：為多角色提供長期情感記憶與時間節奏計算。
"""

from .core import (
    TemporalContext,
    EmotionalCarryover,
    MomentumState,
    AnticipatoryState,
    TIME_PERIODS,
    compute_time_period,
    compute_sleep_pressure,
    build_temporal_context,
    merge_carryover,
    decay_carryover,
)
from .persona_config import PersonaConfig

__all__ = [
    "TemporalContext",
    "EmotionalCarryover",
    "MomentumState",
    "AnticipatoryState",
    "PersonaConfig",
    "TIME_PERIODS",
    "compute_time_period",
    "compute_sleep_pressure",
    "build_temporal_context",
    "merge_carryover",
    "decay_carryover",
]