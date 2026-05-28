"""
persona_config/ — 角色特定參數設定
PersonaConfig dataclass + 各角色設定檔。
Engine 本體不帶任何角色名稱字面量。
"""

from .config import PersonaConfig
from .akane import AKANE

__all__ = ["PersonaConfig", "AKANE", "load_persona_config"]


def load_persona_config(persona_id: str) -> PersonaConfig:
    """
    依 persona_id 回傳對應的 PersonaConfig。
    目前支援 akane；未知 ID 回傳預設值（decay=0.12）。
    """
    if persona_id == "akane":
        return AKANE
    return PersonaConfig(persona_id=persona_id)
