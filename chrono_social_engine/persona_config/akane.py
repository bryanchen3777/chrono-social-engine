"""
akane.py — 黒川あかね 的角色參數設定
"""

from .config import PersonaConfig

AKANE = PersonaConfig(
    persona_id="akane",
    decay_rate=0.08,                          # 記性好，衰退慢
    vulnerability_hour_start=22,               # 22:00 開始
    vulnerability_hour_end=4,                  # 04:00 結束（跨越午夜）
    vulnerability_inhibition_threshold=0.45,  # 比較難打開
    vulnerability_silence_min=4.5,             # 需要 4.5 小時沉默才觸發
    worry_resolution_delta=0.65,              # 解除時下降幅度稍大
    attachment_heat_bump=0.12,
)
