"""
hooks.py — run_pre_llm_hook / run_post_llm_hook
Hermes Agent 整合層。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .core import (
    EmotionalCarryover,
    PersonaConfig,
    build_temporal_context,
    merge_carryover,
    decay_carryover,
)
from .db import init_db, load_carryover_from_db, save_carryover_to_db
from .resolver import detect_resolved_event
from .render import render_temporal_block


# ── Pre-LLM Hook ──────────────────────────────────────────────────────────────

def run_pre_llm_hook(
    persona_id: str,
    config: PersonaConfig,
    last_msg_ts: str | None,
    stress: int,
    db_path: Path | None = None,
) -> tuple[object, str, int]:
    """
    回傳：(ctx, temporal_block_string, adjusted_stress)

    - 從 DB 載入 carryover，套用衰減
    - 建立 TemporalContext
    - 渲染 prompt block
    - 調整 stress（根据 emotional_inhibition）
    """
    db = db_path or Path(__file__).parent.parent / "data" / "chrono_memory.db"

    init_db(db)
    raw = load_carryover_from_db(persona_id, db)

    # 套用衰減
    if raw and last_msg_ts:
        try:
            prev = datetime.fromisoformat(last_msg_ts)
            elapsed = (datetime.now(config.timezone) - prev).total_seconds() / 3600.0
            elapsed = max(0.0, elapsed)
            carryover = raw.apply_decay(elapsed)
        except Exception:
            carryover = raw
    else:
        carryover = raw or EmotionalCarryover(decay_rate=config.decay_rate)

    ctx = build_temporal_context(
        persona_id=persona_id,
        last_msg_ts=last_msg_ts,
        current_stress=stress,
        carryover=carryover,
        config=config,
    )

    block = render_temporal_block(ctx)

    # stress 調整：情緒抑制越高，感受到的 stress 越低（壓抑了）
    adjusted_stress = int(stress * (1.0 - ctx.emotional_inhibition * 0.3))
    adjusted_stress = max(0, min(100, adjusted_stress))

    return ctx, block, adjusted_stress


# ── Post-LLM Hook ─────────────────────────────────────────────────────────────

def run_post_llm_hook(
    ctx: object,
    config: PersonaConfig,
    user_message: str,
    db_path: Path | None = None,
) -> None:
    """
    自動偵測 resolved_event，更新 carryover，寫入 DB。

    流程：
    1. detect_resolved_event(user_message, ctx)
    2. create_carryover_if_needed
    3. merge / replace
    4. resolve_worry_if_applicable
    5. save_carryover_to_db
    """
    db = db_path or Path(__file__).parent.parent / "data" / "chrono_memory.db"
    now_iso = datetime.now(config.timezone).isoformat()

    # 取出 ctx 實際型別（TemporalContext）
    # mypy narrowing via cast not needed at runtime
    tctx = ctx

    # 1. Detect resolution
    resolved = detect_resolved_event(user_message, tctx)

    # 2. Build new_carryover from momentum / ctx state
    new_carryover = _create_carryover_from_ctx(tctx, now_iso, config)

    # 3. Load existing from DB
    existing = load_carryover_from_db(config.persona_id, db)

    # 4. Merge
    if existing:
        merged = merge_carryover(existing, new_carryover)
    else:
        merged = new_carryover

    # 5. Resolve worry if applicable
    if resolved in ("user_confirmed_ok", "explicit_reassurance"):
        delta = config.worry_resolution_delta
        merged = EmotionalCarryover(
            intimacy_afterglow=merged.intimacy_afterglow,
            unresolved_worry=max(0.0, merged.unresolved_worry - delta),
            emotional_openness_residue=merged.emotional_openness_residue,
            attachment_heat=merged.attachment_heat,
            source_event=merged.source_event,
            triggered_at=merged.triggered_at,
            decay_rate=merged.decay_rate,
        )
    elif resolved == "user_slept_normally":
        # 部分解除（睡過了，worry 降一半）
        merged = EmotionalCarryover(
            intimacy_afterglow=merged.intimacy_afterglow,
            unresolved_worry=max(0.0, merged.unresolved_worry * 0.5),
            emotional_openness_residue=merged.emotional_openness_residue,
            attachment_heat=merged.attachment_heat,
            source_event=merged.source_event,
            triggered_at=merged.triggered_at,
            decay_rate=merged.decay_rate,
        )

    # 6. Cap all values at 1.0
    merged.intimacy_afterglow = min(1.0, merged.intimacy_afterglow)
    merged.unresolved_worry = min(1.0, merged.unresolved_worry)
    merged.emotional_openness_residue = min(1.0, merged.emotional_openness_residue)
    merged.attachment_heat = min(1.0, merged.attachment_heat)

    # 7. Save
    save_carryover_to_db(merged, config.persona_id, db)


def _create_carryover_from_ctx(ctx: object, now_iso: str, config: PersonaConfig) -> EmotionalCarryover:
    """
    從 TemporalContext 的狀態建立新的 EmotionalCarryover。
    根據 momentum 和 carryover 欄位計算。
    """
    # runtime type check — ctx is always TemporalContext from build_temporal_context
    tctx = ctx  # type: ignore

    intimacy = 0.0
    worry = 0.0
    openness = 0.0
    attachment = 0.0
    source = ""

    if tctx.momentum.vulnerability_window:
        openness = max(openness, 0.40)
        source = f"深夜脆弱窗口觸發 @ {now_iso}"

    if tctx.deviation_interpretation == "sleep_deprivation":
        worry = max(worry, 0.85)
        source = f"睡眠剝奪解讀 @ {now_iso}"

    if tctx.carryover.unresolved_worry > 0.5 and tctx.silence_hours > 5:
        worry = max(worry, 0.70)
        if not source:
            source = f"持續未解除的 worry @ {now_iso}"

    if tctx.anticipatory.preoccupation_flavor == "longing":
        attachment = max(attachment, 0.50)
        source = f"思念情緒 @ {now_iso}"

    if tctx.carryover.intimacy_afterglow > 0:
        intimacy = max(intimacy, tctx.carryover.intimacy_afterglow * 0.6)

    return EmotionalCarryover(
        intimacy_afterglow=min(1.0, intimacy),
        unresolved_worry=min(1.0, worry),
        emotional_openness_residue=min(1.0, openness),
        attachment_heat=min(1.0, attachment),
        source_event=source,
        triggered_at=now_iso,
        decay_rate=config.decay_rate,
    )