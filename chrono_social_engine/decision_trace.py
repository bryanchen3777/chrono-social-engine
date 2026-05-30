"""
decision_trace.py — DecisionTrace v2.3
職責：記錄每次 build_temporal_context 的決策過程
原則：只進 Log，絕對不進 LLM Prompt
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TriggerRecord:
    name:          str
    score:         float
    accepted:      bool
    reason:        str = ""
    priority_rank: int = 0   # 1=主導，數字越大越次要


@dataclass
class DecisionTrace:
    # Bias 決策
    dominant_signal:     str = ""
    candidate_biases:    list = field(default_factory=list)  # [(str, float)]
    selected_bias:       str = ""
    selection_reason:    str = ""
    decision_confidence: float = 0.0   # <0.60 = 邊界案例

    # Salience 決策
    salience_reason:     str = ""

    # Carryover 決策
    carryover_reason:    str = ""

    # 被壓制的訊號
    suppressed_signals:  list = field(default_factory=list)  # [str]

    # Trigger Timeline
    evaluated_triggers:  list = field(default_factory=list)  # [TriggerRecord]

    # Silence 決策
    silence_candidates:  list = field(default_factory=list)  # [(str, float)]
    silence_selected:    str = ""
    silence_reason:      list = field(default_factory=list)  # [str]


CONFIDENCE_WARN_THRESHOLD = 0.60


def render_decision_trace(trace: DecisionTrace) -> str:
    lines = ["[DECISION_TRACE]", "─" * 45]

    conf = trace.decision_confidence
    warn = "  ← ⚠️ 邊界案例" if conf < CONFIDENCE_WARN_THRESHOLD else ""
    candidates_str = " | ".join(
        f"{name}({score:.2f})" for name, score in trace.candidate_biases
    )
    lines += [
        "BIAS",
        f"  selected    : {trace.selected_bias}",
        f"  confidence  : {conf:.2f}{warn}",
        f"  candidates  : {candidates_str}",
        f"  reason      : {trace.selection_reason}",
        f"  dominant    : {trace.dominant_signal}",
    ]

    lines.append("\nTRIGGERS (#rank score accepted)")
    for t in sorted(trace.evaluated_triggers, key=lambda x: x.priority_rank):
        mark = "✓" if t.accepted else "✗"
        lines.append(f"  #{t.priority_rank}  {t.name:<24} {t.score:.2f}  {mark}  {t.reason}")

    silence_cands = " | ".join(
        f"{name}({score:.2f})" for name, score in trace.silence_candidates
    )
    lines += [
        "\nSILENCE",
        f"  selected    : {trace.silence_selected}",
        f"  candidates  : {silence_cands}",
        f"  reason      : {' | '.join(trace.silence_reason)}",
    ]

    lines += [
        f"\nSALIENCE    : {trace.salience_reason}",
        f"SUPPRESSED  : {', '.join(trace.suppressed_signals) or 'none'}",
        "─" * 45,
    ]

    return "\n".join(lines)