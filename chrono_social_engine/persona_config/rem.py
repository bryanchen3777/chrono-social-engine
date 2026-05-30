"""
persona_config/rem.py — 雷姆（Rem）的角色參數
Ref: Re:Zero 蕾娜·亞切爾（Rem）
"""
from __future__ import annotations

from chrono_social_engine.persona_config.config import PersonaConfig
from zoneinfo import ZoneInfo

# Rem 的時區：跟隨系統（config.yaml 的 timezone 為空）
# 如果有特定時區需求，在這裡設定
REM_TIMEZONE = ZoneInfo("America/New_York")  # Eastern Time (EDT/EST)

REM = PersonaConfig(
    persona_id="rem",
    timezone=REM_TIMEZONE,
    decay_rate=0.10,
    vulnerability_hour_start=22,
    vulnerability_hour_end=4,
    vulnerability_inhibition_threshold=0.40,
    vulnerability_silence_min=3.0,
    worry_resolution_delta=0.65,
    attachment_heat_bump=0.12,
    abandonment_sensitivity=0.70,
    facade_collapse_rate=0.05,
)
