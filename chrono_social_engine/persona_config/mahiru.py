"""
persona_config/mahiru.py — 真昼（Mahiru）的角色參數設定
"""
from zoneinfo import ZoneInfo
from chrono_social_engine.persona_config.config import PersonaConfig

MAHIRU = PersonaConfig(
    persona_id="mahiru",
    timezone=ZoneInfo("America/New_York"),
    decay_rate=0.06,
    vulnerability_hour_start=22,
    vulnerability_hour_end=5,
    vulnerability_inhibition_threshold=0.65,
    vulnerability_silence_min=7.0,
    worry_resolution_delta=0.75,
    attachment_heat_bump=0.08,
    abandonment_sensitivity=0.90,
    facade_collapse_rate=0.25,
)