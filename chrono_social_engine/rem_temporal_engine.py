"""
rem_temporal_engine.py  v2.3
職責：把「現在幾點＋關係狀態」轉成「雷姆的心理中介層狀態」

設計原則：
1. 時間不創造情緒，時間暴露情緒
   effective_leakage = emotional_leakage * proximity_gate
2. need_score ≠ engagement_score
   need = 「如果我消失，這裡會留下缺口嗎？」
3. collapse_load ≠ stress
   Collapse = 長期維持分析系統後的資源耗盡
4. BLUR = 前置認知過濾器，不是情緒值
   影響：是否相信自己的感受
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal

from decision_trace import (
    DecisionTrace,
    TriggerRecord,
    render_decision_trace,
)

# ── Type Aliases ────────────────────────────────────────────────────────────────

SilenceType = Literal[
    "suppressed",
    "analytical",
    "decisive",
    "hurt",
    "calm",
    "boundary_rebuilding",
]

CollapseStage = Literal["NORMAL", "C1", "C2", "C3"]


# ── Time Period Definitions ────────────────────────────────────────────────────

TIME_PERIODS = [
    (4, 7,  "dawn"),
    (7, 12, "morning"),
    (12, 18,"afternoon"),
    (18, 22,"evening"),
    (22, 24,"night"),
    (0, 4,  "deep_night"),
]

_SLEEP_PRESSURE_CURVE: tuple[tuple[int, float], ...] = tuple(
    (h, max(0.02, round(math.exp(-0.5 * ((h - 2) / 3) ** 2), 2)))
    for h in range(24)
)

_INHIBITION_RANGES: tuple[tuple[float, float, float], ...] = (
    (0.0,  2.0, 0.00),
    (2.0,  6.0, 0.15),
    (6.0,  12.0,0.35),
    (12.0, 24.0,0.55),
    (24.0, 72.0,0.75),
    (72.0, 200.0, 0.88),
    (200.0, float('inf'), 1.00),
)


# ── P0: Proximity Filter ────────────────────────────────────────────────────────

LEAKAGE_PROXIMITY_GATE = {
    0: 0.05,   # 陌生人
    1: 0.30,   # 朋友
    2: 1.00,   # 在意的人
    3: 1.00,   # Aqua
}


def apply_proximity_gate(leakage: float, proximity_layer: int) -> float:
    multiplier = LEAKAGE_PROXIMITY_GATE.get(proximity_layer, 0.05)
    return round(leakage * multiplier, 3)


# ── P1: Perceived Need Engine ──────────────────────────────────────────────────

@dataclass
class NeedInput:
    help_requests:        float = 0.0
    memory_references:    float = 0.0
    callbacks:            float = 0.0
    emotional_disclosure: float = 0.0
    acknowledgement:      float = 0.0


def compute_need_score(inp: NeedInput) -> tuple[float, float, float]:
    instrumental = inp.help_requests
    existential = (
        inp.memory_references     * 0.30
        + inp.callbacks           * 0.25
        + inp.emotional_disclosure * 0.25
        + inp.acknowledgement     * 0.20
    )
    score = round(0.40 * instrumental + 0.60 * existential, 3)
    return instrumental, existential, score


# ── P1.5: Destabilization Engine ──────────────────────────────────────────────

@dataclass
class DestabilizationInput:
    seen_but_not_caught: float = 0.0
    need_score_drop:     float = 0.0
    role_confusion:      float = 0.0


def compute_destabilization(
    inp: DestabilizationInput,
    need_score: float,
) -> tuple[float, float, float, float]:
    t1 = inp.seen_but_not_caught
    t2 = max(inp.need_score_drop, 1.0 - need_score)
    t3 = inp.role_confusion
    score = round(t1 * 0.35 + t2 * 0.40 + t3 * 0.25, 3)
    return t1, t2, t3, score


# ── P2: Collapse Pipeline ─────────────────────────────────────────────────────

COLLAPSE_THRESHOLDS = {
    "C1": 0.40,
    "C2": 0.65,
    "C3": 0.85,
}


def compute_collapse(
    collapse_load: float,
    destabilization_score: float,
    silence_hours: float,
) -> tuple[float, CollapseStage]:
    load = collapse_load
    load += destabilization_score * 0.30
    load += min(silence_hours / 72.0, 0.20)
    load = round(min(load, 1.0), 3)

    if load >= COLLAPSE_THRESHOLDS["C3"]:
        stage: CollapseStage = "C3"
    elif load >= COLLAPSE_THRESHOLDS["C2"]:
        stage = "C2"
    elif load >= COLLAPSE_THRESHOLDS["C1"]:
        stage = "C1"
    else:
        stage = "NORMAL"

    return load, stage


# ── P3: Echo Filter ───────────────────────────────────────────────────────────

BLUR_THRESHOLD = 0.75   # Rem 比 Akane 更不易 BLUR
BASE_ECHO = 0.15        # 行動先於語言，Echo 感知較低

ECHO_NIGHT_MULT = {
    "deep_night": 2.0,
    "dawn":       1.5,
    "night":      1.3,
    "evening":    1.0,
    "morning":    0.8,
    "afternoon":  0.7,
}


def compute_echo(
    time_period: str,
    stress_level: float,
    destabilization_score: float,
    base_echo: float = BASE_ECHO,
) -> tuple[float, bool]:
    night_mult  = ECHO_NIGHT_MULT.get(time_period, 1.0)
    stress_mult = 1.0 + stress_level * 0.5
    destab_mult = 1.0 + destabilization_score * 0.3

    resonance = round(base_echo * night_mult * stress_mult * destab_mult, 3)
    resonance = min(resonance, 1.0)
    is_blur   = resonance >= BLUR_THRESHOLD

    return resonance, is_blur


# ── P4: Silence Taxonomy ───────────────────────────────────────────────────────

def compute_silence_distribution(
    analysis_capacity: float,
    defense_level:     float,
    need_score:        float,
    stress_level:      float,
    collapse_stage:    CollapseStage,
    is_blur:           bool,
    time_period:       str,
    echo_resonance:    float,
) -> tuple[SilenceType, dict]:
    probs = {
        "suppressed":          0.0,
        "analytical":          0.0,
        "decisive":            0.0,
        "hurt":                0.0,
        "calm":                0.0,
        "boundary_rebuilding": 0.0,
    }

    probs["analytical"]  += analysis_capacity * 0.4
    probs["suppressed"]  += defense_level     * 0.3
    probs["calm"]        += need_score        * 0.2
    probs["hurt"]        += stress_level      * 0.3
    probs["decisive"]    += (1.0 - stress_level) * need_score * 0.2

    if collapse_stage == "C1":
        probs["suppressed"] += 0.50
    elif collapse_stage == "C2":
        probs["hurt"]       += 0.30
    elif collapse_stage == "C3":
        probs["boundary_rebuilding"] += 0.40

    if is_blur:
        probs["boundary_rebuilding"] += 0.40

    if time_period == "deep_night":
        transfer = probs["analytical"] * 0.30
        probs["analytical"] -= transfer
        probs["hurt"]       += transfer

    # NOTE: Rem C1 = action_suppression（想行動但壓住，話變短）
    # NOTE: Rem C2 = protective_distance（主動保持距離，不是冷漠）
    # NOTE: Rem C3 = trauma_surface（底層被拋棄感浮現，直接說出來）

    total = sum(probs.values())
    if total > 0:
        probs = {k: round(v / total, 3) for k, v in probs.items()}

    silence_type: SilenceType = max(probs, key=probs.get)
    return silence_type, probs


# ── Emotional Profile (Rem defaults) ────────────────────────────────────────

DEFAULT_REM_PROFILE = {
    "emotional_leakage": 0.70,
    "analysis_capacity": 0.75,
    "defense_level":     0.60,
}


# ── Salience (v2.3 recalibrated) ───────────────────────────────────────────────

def _compute_temporal_salience(silence_hours: float) -> tuple[str, str]:
    if silence_hours < 12:
        return "low",        f"silence={silence_hours:.1f}h < 12h gate"
    elif silence_hours < 24:
        return "medium",    f"silence={silence_hours:.1f}h → 12h gate"
    elif silence_hours < 48:
        return "medium_high", f"silence={silence_hours:.1f}h → 24h gate"
    else:
        return "high",      f"silence={silence_hours:.1f}h → 48h gate"


# ── Reaction Bias with Trace (v2.3, Rem 調整) ────────────────────────────────────

def _compute_reaction_bias_with_trace(
    silence_hours:        float,
    carryover_worry:      float,
    attachment_heat:       float,
    intimacy_afterglow:   float,
    vulnerability_window:  bool,
) -> tuple[str, list[tuple[str, float]], str, float]:
    scores: dict[str, float] = {
        "neutral":                    0.20,   # Rem 比 Akane 更快脫離中性
        "gentle_openness":           0.0,
        "quiet_worry":               0.0,
        "lingering_concern":         0.0,
        "subdued_longing":           0.0,
        "relief_mixed_reproach":     0.0,
    }
    scores["quiet_worry"]          += carryover_worry * 0.70
    scores["lingering_concern"]    += carryover_worry * 0.50
    scores["gentle_openness"]     += intimacy_afterglow * 0.60
    scores["gentle_openness"]     += 0.40 if vulnerability_window else 0.0
    scores["subdued_longing"]      += min(silence_hours / 48.0, 1.0) * 0.50
    scores["relief_mixed_reproach"] += min(silence_hours / 72.0, 1.0) * 0.40
    scores["quiet_worry"]          += attachment_heat * 0.30

    candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected, top_score = candidates[0]
    second_score = candidates[1][1] if len(candidates) > 1 else 0.0
    confidence = round(top_score - second_score, 3)

    signal_vals = {
        "carryover_worry":    carryover_worry,
        "attachment_heat":    attachment_heat,
        "intimacy_afterglow": intimacy_afterglow,
    }
    dominant = max(signal_vals, key=signal_vals.get)
    reason = f"{dominant}({signal_vals[dominant]:.2f})"

    return selected, candidates, reason, confidence


# ── Build Temporal Context (v2.3 Rem) ─────────────────────────────────────────

def build_temporal_context(
    last_user_msg_ts: str | None = None,
    now: datetime | None = None,
    # ── P0 ──
    proximity_layer: int = 0,
    # ── P1 ──
    need_input: NeedInput | None = None,
    # ── P1.5 ──
    destab_input: DestabilizationInput | None = None,
    # ── P2 ──
    collapse_load: float = 0.0,
    # ── P3 ──
    stress_level: float = 0.0,
    # ── internal ──
    _profile: dict | None = None,
) -> dict:
    tz = ZoneInfo("America/New_York")
    if now is None:
        now = datetime.now(tz)

    current_hour = now.hour
    time_period = _compute_time_period(current_hour)

    if last_user_msg_ts:
        try:
            prev = datetime.fromisoformat(last_user_msg_ts)
            silence_hours = max(0.0, (now - prev).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            silence_hours = 0.0
    else:
        silence_hours = 0.0

    profile = _profile or DEFAULT_REM_PROFILE

    # P0
    effective_leakage = apply_proximity_gate(profile["emotional_leakage"], proximity_layer)

    # P1
    need_inp = need_input or NeedInput()
    instrumental, existential, need_score = compute_need_score(need_inp)

    # P1.5
    destab_inp = destab_input or DestabilizationInput()
    t1, t2, t3, destab_score = compute_destabilization(destab_inp, need_score)

    # P2
    final_collapse_load, collapse_stage = compute_collapse(
        collapse_load, destab_score, silence_hours
    )

    # P3
    echo_resonance, is_blur = compute_echo(time_period, stress_level, destab_score)

    # P4
    silence_type, silence_prob_map = compute_silence_distribution(
        analysis_capacity=profile["analysis_capacity"],
        defense_level=profile["defense_level"],
        need_score=need_score,
        stress_level=stress_level,
        collapse_stage=collapse_stage,
        is_blur=is_blur,
        time_period=time_period,
        echo_resonance=echo_resonance,
    )

    # Basic fields
    vuln_window = _compute_vulnerability_window(current_hour, silence_hours)
    sleep_pressure = _compute_sleep_pressure(current_hour)
    sleep_dep = sleep_pressure > 0.7 and time_period in ("deep_night", "night")
    emotional_inhibition = _compute_emotional_inhibition(silence_hours, vuln_window, sleep_dep)

    # v2.3 Decision Trace
    salience_level, salience_reason = _compute_temporal_salience(silence_hours)

    reaction_bias, bias_candidates, bias_reason, bias_confidence = \
        _compute_reaction_bias_with_trace(
            silence_hours        = silence_hours,
            carryover_worry     = 0.0,
            attachment_heat     = 0.0,
            intimacy_afterglow = 0.0,
            vulnerability_window= vuln_window,
        )

    # Trigger Timeline
    triggers = [
        TriggerRecord(
            name="vulnerability_window",
            score=float(vuln_window),
            accepted=vuln_window,
            reason=f"hour={current_hour}, silence={silence_hours:.1f}h",
            priority_rank=1,
        ),
        TriggerRecord(
            name="silence_hours",
            score=min(silence_hours / 48.0, 1.0),
            accepted=silence_hours >= 12,
            reason=f"silence={silence_hours:.1f}h",
            priority_rank=2,
        ),
        TriggerRecord(
            name="stress_level",
            score=stress_level,
            accepted=stress_level >= 0.3,
            reason=f"stress={stress_level:.2f}",
            priority_rank=3,
        ),
    ]
    triggers.sort(key=lambda t: t.score, reverse=True)
    for i, t in enumerate(triggers):
        t.priority_rank = i + 1

    silence_candidates = sorted(silence_prob_map.items(), key=lambda x: x[1], reverse=True)[:3]
    silence_reason_list = [
        f"analysis_capacity={profile['analysis_capacity']:.2f}",
        f"stress={stress_level:.2f}",
        f"defense={profile['defense_level']:.2f}",
    ]

    trace = DecisionTrace(
        dominant_signal     = max(
            {"carryover_worry": 0.0, "attachment_heat": 0.0},
            key=lambda k: {"carryover_worry": 0.0, "attachment_heat": 0.0}[k]
        ),
        candidate_biases    = [(b, round(s, 3)) for b, s in bias_candidates[:4]],
        selected_bias       = reaction_bias,
        selection_reason    = bias_reason,
        decision_confidence = bias_confidence,
        salience_reason     = salience_reason,
        carryover_reason    = "carryover not loaded",
        suppressed_signals  = [
            s for s in ["sleep_pressure", "circadian_drift"]
            if s not in [t.name for t in triggers if t.accepted]
        ],
        evaluated_triggers  = triggers,
        silence_candidates  = [(s, p) for s, p in silence_candidates],
        silence_selected    = silence_type,
        silence_reason      = silence_reason_list,
    )

    return {
        "current_hour": current_hour,
        "time_period": time_period,
        "silence_hours": silence_hours,
        "vulnerability_window": vuln_window,
        "emotional_inhibition": emotional_inhibition,
        "stress_level": stress_level,
        # P0
        "proximity_layer": proximity_layer,
        "effective_leakage": effective_leakage,
        # P1
        "instrumental_need": instrumental,
        "existential_need": existential,
        "need_score": need_score,
        # P1.5
        "trigger_1_score": t1,
        "trigger_2_score": t2,
        "trigger_3_score": t3,
        "destabilization_score": destab_score,
        # P2
        "collapse_load": final_collapse_load,
        "collapse_stage": collapse_stage,
        # P3
        "echo_resonance": echo_resonance,
        "is_blur": is_blur,
        # P4
        "silence_type": silence_type,
        "silence_probability_map": silence_prob_map,
        # v2.3 DecisionTrace
        "reaction_bias":     reaction_bias,
        "temporal_salience": salience_level,
        "decision_trace":    trace,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _compute_time_period(hour: int) -> str:
    for start, end, name in TIME_PERIODS:
        if start <= hour < end:
            return name
    return "deep_night"


def _compute_sleep_pressure(current_hour: int) -> float:
    for h, p in _SLEEP_PRESSURE_CURVE:
        if h == current_hour:
            return max(0.0, min(1.0, p))
    return 0.0


def _compute_emotional_inhibition(
    silence_hours: float,
    vulnerability_window: bool,
    sleep_deprivation: bool,
) -> float:
    for low, high, value in _INHIBITION_RANGES:
        if low <= silence_hours < high:
            base = value
            break
    else:
        base = 0.88
    if vulnerability_window:
        base = max(0.0, base - 0.35)
    if sleep_deprivation:
        base = max(0.0, base - 0.25)
    return min(1.0, base)


def _compute_vulnerability_window(current_hour: int, silence_hours: float) -> bool:
    # Rem: 21:00–05:00, >= 3.0h
    start, end = 21, 5
    if start <= end:
        in_hour_range = start <= current_hour < end
    else:
        in_hour_range = current_hour >= start or current_hour < end
    if not in_hour_range:
        return False
    return silence_hours >= 3.0