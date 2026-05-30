"""
persona_config/hinami.py — 日南日向（Hinami）的角色參數
"""
from zoneinfo import ZoneInfo
from chrono_social_engine.persona_config.config import PersonaConfig

HINAMI = PersonaConfig(
    persona_id="hinami",
    timezone=ZoneInfo("America/New_York"),
    decay_rate=0.06,
    vulnerability_hour_start=23,
    vulnerability_hour_end=5,
    vulnerability_inhibition_threshold=0.35,
    vulnerability_silence_min=5.0,
    worry_resolution_delta=0.70,
    attachment_heat_bump=0.09,
    abandonment_sensitivity=0.40,
    facade_collapse_rate=0.20,
)
