"""
雷姆的心理中介層狀態引擎
Rem Psych Mediation Layer State Engine
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


# === 狀態閾值 ===
BLUR_THRESHOLD = 0.75
BASE_ECHO = 0.15
COLLAPSE_THRESHOLDS = {"C1": 0.40, "C2": 0.65, "C3": 0.85}

# === 預設 Profile（茜） ===
DEFAULT_REM_PROFILE = {
    "emotional_leakage": 0.70,
    "analysis_capacity": 0.75,
    "defense_level": 0.60,
}
# abandonment_sensitivity = 0.60  # 行動型，不縮，但有被拋棄底層
# facade_collapse_rate    = 0.05  # 沒有人設要崩，情感直接轉行為


def _profile_default():
    return DEFAULT_REM_PROFILE.copy()


def compute_blur_intensity(
    emotional_payload: float,
    echo_depth: float,
    profile: Optional[Dict[str, float]] = None
) -> float:
    """
    計算模糊強度（0.0–1.0）。
    Rem 採用較低的 blur threshold（0.75），更傾向保持情緒清晰度。
    """
    p = profile or _profile_default()
    leakage = p.get("emotional_leakage", 0.70)
    analysis = p.get("analysis_capacity", 0.75)

    raw = emotional_payload * (1 - echo_depth * BASE_ECHO)
    decay = (leakage + analysis) / 2
    blur = raw * (1 - decay * 0.5)

    if blur > BLUR_THRESHOLD:
        return min(blur / BLUR_THRESHOLD, 1.0)
    return blur


def compute_collapse_probability(
    state_vector: Dict[str, float],
    profile: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    評估各層級崩潰機率。C1=淺層模糊，C2=中層波動，C3=深層創傷。
    """
    p = profile or _profile_default()
    defense = p.get("defense_level", 0.60)

    probs = {}
    for level, threshold in COLLAPSE_THRESHOLDS.items():
        raw_score = state_vector.get(level, 0.0)
        # 防御係數
        adjusted = raw_score * (1 - defense * 0.3)
        probs[level] = max(0.0, min(adjusted / threshold, 1.0))

    return probs


def _compute_vulnerability_window(
    current_hour: int,
    silence_hours: float,
    profile: Optional[Dict[str, float]] = None
) -> bool:
    """
    深夜 21:00–05:00 為高脆弱時段。
    Rem 在此時段若沉默 >= 3 小時，進入創傷掃描模式。
    """
    start = 21
    end = 5
    if start <= current_hour < 24 or 0 <= current_hour < end:
        return silence_hours >= 3.0
    return False


def build_temporal_context(
    turn_index: int,
    emotional_payload: float,
    echo_depth: float,
    silence_hours: float = 0.0,
    last_collapse_level: Optional[str] = None,
    profile: Optional[Dict[str, float]] = None,
    custom_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    建構完整的中介層上下文（Rem 版）。
    包含：狀態向量、崩潰閾值、脆弱時段標記、個人 Profile。
    """
    profile = profile or DEFAULT_REM_PROFILE
    current_hour = datetime.now().hour

    # 計算模糊強度
    blur = compute_blur_intensity(emotional_payload, echo_depth, profile)

    # 構建狀態向量
    state_vector = {
        "C1": emotional_payload * 0.3 + echo_depth * 0.1,
        "C2": emotional_payload * 0.5 + echo_depth * 0.2,
        "C3": emotional_payload * 0.7 + echo_depth * 0.3,
    }
    if last_collapse_level is not None:
        decay = 0.85 ** (turn_index + 1)
        state_vector[last_collapse_level] *= decay

    # 崩潰機率
    collapse = compute_collapse_probability(state_vector, profile)

    # 脆弱時段
    vulnerable = _compute_vulnerability_window(current_hour, silence_hours, profile)

    context = {
        "turn_index": turn_index,
        "blur_intensity": blur,
        "state_vector": state_vector,
        "collapse_probabilities": collapse,
        "is_vulnerable_window": vulnerable,
        "profile": profile,
        "timestamp": datetime.now().isoformat(),
        "hour": current_hour,
    }

    if custom_state:
        context["custom_state"] = custom_state

    return context


def should_trigger_deep_processing(
    context: Dict[str, Any],
    threshold_override: Optional[float] = None
) -> bool:
    """
    根據模糊強度與脆弱時段判斷是否進入深層處理模式。
    """
    blur = context.get("blur_intensity", 0.0)
    vulnerable = context.get("is_vulnerable_window", False)
    threshold = threshold_override or (BLUR_THRESHOLD * 0.8)

    # 脆弱時段門檻降低
    effective = threshold * (0.9 if vulnerable else 1.0)
    return blur >= effective


def reset_temporal_state(profile: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    重置狀態向量（測試或對話終結時調用）。
    """
    profile = profile or DEFAULT_REM_PROFILE.copy()
    return {
        "turn_index": 0,
        "last_collapse_level": None,
        "silence_hours": 0.0,
        "state_vector": {"C1": 0.0, "C2": 0.0, "C3": 0.0},
        "profile": profile,
    }