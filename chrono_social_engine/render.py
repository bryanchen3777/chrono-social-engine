"""
render.py — render_temporal_block + situation_hint
Templating for Hermes Agent system prompts.
"""

from __future__ import annotations

from typing import Callable

from .core import TemporalContext

# ── Hint Configuration ─────────────────────────────────────────────────────────

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


# ── Public API ─────────────────────────────────────────────────────────────────

def render_temporal_block(ctx: TemporalContext) -> str:
    """
    將 TemporalContext 渲染為可插入 system prompt 的字串區塊。
    包含時間狀態、情感狀態、suggesstion hints。
    """
    lines = ["[Temporal Context]"]

    # Time period
    period_label = {
        "dawn": "清晨（04–07）",
        "morning": "上午（07–12）",
        "afternoon": "下午（12–18）",
        "evening": "傍晚（18–22）",
        "night": "深夜（22–24）",
        "deep_night": "凌晨（00–04）",
    }.get(ctx.time_period, ctx.time_period)

    lines.append(f"- 時間區間：{period_label}")
    lines.append(f"- 沉默時長：{ctx.silence_hours:.1f}h")

    # Emotional state summary
    carry = ctx.carryover
    if carry.intimacy_afterglow > 0.3:
        lines.append(f"- 親密餘溫：{carry.intimacy_afterglow:.0%}（warm afterglow）")
    if carry.unresolved_worry > 0.2:
        lines.append(f"- 未解除的掛念：{carry.unresolved_worry:.0%}")
    if carry.emotional_openness_residue > 0.2:
        lines.append(f"- 情感開放殘留：{carry.emotional_openness_residue:.0%}")
    if carry.attachment_heat > 0.2:
        lines.append(f"- 依戀熱度：{carry.attachment_heat:.0%}")

    # Vulnerability window
    if ctx.momentum.vulnerability_window:
        lines.append("- ⚠️ 深夜脆弱窗口：抑制降低，真實情感可能外洩")

    # Deviation interpretation
    dev_map = {
        "normal": "作息正常",
        "sleep_deprivation": "⚠️ 對方未獲充足睡眠",
        "longing": "⚠️ 對方有濃厚的思念情緒",
        "missing": "⚠️ 對方感覺被忽略",
    }
    if ctx.deviation_interpretation != "normal":
        lines.append(f"- 解讀偏離：{dev_map.get(ctx.deviation_interpretation, ctx.deviation_interpretation)}")

    # Stress indicator
    if ctx.stress > 60:
        lines.append(f"- 情緒壓力：高（{ctx.stress}）")
    elif ctx.stress > 30:
        lines.append(f"- 情緒壓力：中（{ctx.stress}）")

    # Situation hints
    hints = _generate_situation_hint(ctx)
    if hints:
        lines.append("- 情境提示：")
        for hint in hints:
            lines.append(f"  · {hint}")

    return "\n".join(lines)


def _generate_situation_hint(ctx: TemporalContext) -> list[str]:
    """
    依優先序回傳最多 2 條 situation hints。
    Hint 可以是靜態字串，也可以是接收 ctx 的 callable。
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