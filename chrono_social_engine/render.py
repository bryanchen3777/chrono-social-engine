"""
render.py — render_temporal_block + situation_hint
Templating for Hermes Agent system prompts.
v2.2: time fields removed from prompt output; replaced with behavior-bias layer.
"""

from __future__ import annotations

from typing import Callable

from .core import TemporalContext

# ── Hint Configuration (debug / hook use only, not rendered to LLM) ───────────

_HINT_PRIORITY: list[tuple[Callable[[TemporalContext], bool], str | Callable[[TemporalContext], str]]] = [
    (
        lambda ctx: ctx.momentum.vulnerability_window,
        "深夜防衛低落，容易說出平時不會說的話",
    ),
    (
        lambda ctx: ctx.carryover.unresolved_worry > 0.5,
        lambda ctx: f"仍在擔心上次對話（{ctx.carryover.source_event}）",
    ),
    (
        lambda ctx: ctx.deviation_interpretation == "sleep_deprivation",
        "對方這時間仍在線，推測睡眠不足",
    ),
    (
        lambda ctx: ctx.anticipatory.preoccupation_flavor == "longing",
        "對方消失超過一天，有明顯思念",
    ),
    (
        lambda ctx: ctx.anticipatory.preoccupation_flavor == "worried",
        "正在等待對方，有擔心傾向",
    ),
]


# ── Behavior-Bias Computations ─────────────────────────────────────────────────

def _compute_reaction_bias(ctx: TemporalContext) -> str:
    """把時間狀態翻譯成行為傾向，不暴露時鐘資訊"""
    if ctx.carryover.unresolved_worry > 0.5:
        return "lingering_concern"
    if ctx.momentum.vulnerability_window:
        return "gentle_openness"
    if ctx.deviation_interpretation == "sleep_deprivation":
        return "quiet_worry"
    if ctx.anticipatory.preoccupation_flavor == "longing" and ctx.silence_hours > 24:
        return "subdued_longing"
    if ctx.anticipatory.is_overdue:
        return "relief_mixed_reproach"
    return "neutral"


def _compute_temporal_salience(ctx: TemporalContext) -> str:
    """決定這次對話時間感應該有多顯著"""
    if ctx.anticipatory.is_overdue:
        return "high"
    if ctx.momentum.vulnerability_window:
        return "high"
    if ctx.deviation_interpretation is not None and ctx.deviation_interpretation != "normal":
        return "medium"
    if ctx.silence_hours > 6:
        return "medium"
    return "low"


def _compute_expression_mode(ctx: TemporalContext) -> str:
    """
    預設 implicit。
    salience=high → soft_explicit（可模糊提及時間感）
    explicit 永遠不由系統觸發，只由使用者問時間時在 system prompt 層覆蓋。
    """
    salience = _compute_temporal_salience(ctx)
    if salience == "high":
        return "soft_explicit"
    return "implicit"


# ── Public API ─────────────────────────────────────────────────────────────────

def render_temporal_block(ctx: TemporalContext) -> str:
    """
    將 TemporalContext 渲染為可插入 system prompt 的字串區塊（v2.2）。
    不再輸出 current_time / weekday 等時鐘資訊，改為 behavior-bias 欄位。
    """
    return f"""[CHRONO_SOCIAL_CONTEXT v2.2]
time_period={ctx.time_period}
silence={ctx.silence_hours:.1f}h
arrival_deviation={ctx.deviation_interpretation or 'none'}
vulnerability_window={ctx.momentum.vulnerability_window}
carryover_worry={ctx.carryover.unresolved_worry:.2f}
attachment_heat={ctx.carryover.attachment_heat:.2f}
reaction_bias={_compute_reaction_bias(ctx)}
temporal_salience={_compute_temporal_salience(ctx)}
expression_mode={_compute_expression_mode(ctx)}
[/CHRONO_SOCIAL_CONTEXT]
"""


def _generate_situation_hint(ctx: TemporalContext) -> list[str]:
    """
    依優先序回傳最多 2 條 situation hints。
    Hint 可以是靜態字串，也可以是接收 ctx 的 callable。
    (保留給 debug / hook 層使用，不出現在 LLM prompt 裡)
    """
    results = []
    for predicate, hint in _HINT_PRIORITY:
        try:
            trigger = predicate(ctx)
        except Exception:
            trigger = False
        if trigger:
            if callable(hint) and not isinstance(hint, str):
                results.append(hint(ctx))
            elif isinstance(hint, str):
                results.append(hint)
            if len(results) >= 2:
                break
    return results
