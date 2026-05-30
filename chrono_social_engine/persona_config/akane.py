"""
akane.py — 黒川あかね 的角色參數設定
"""

from zoneinfo import ZoneInfo
from .config import PersonaConfig

AKANE = PersonaConfig(
    persona_id="akane",
    timezone=ZoneInfo("America/New_York"),
    decay_rate=0.08,
    vulnerability_hour_start=22,
    vulnerability_hour_end=4,
    vulnerability_inhibition_threshold=0.45,
    vulnerability_silence_min=4.5,
    worry_resolution_delta=0.65,
    attachment_heat_bump=0.12,
    abandonment_sensitivity=0.50,
    facade_collapse_rate=0.10,
)
