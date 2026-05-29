"""tests/test_render.py — render 層行為測試"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chrono_social_engine.core import (
    build_temporal_context,
    TemporalContext,
    EmotionalCarryover,
    MomentumState,
    AnticipatoryState,
)
from chrono_social_engine.render import (
    render_temporal_block,
    _compute_reaction_bias,
    _compute_temporal_salience,
    _compute_expression_mode,
)
from chrono_social_engine.persona_config.akane import AKANE

NY = ZoneInfo("America/New_York")


def make_ctx(hour: int = 15, silence_hours: float = 1.0, **extra_fields) -> TemporalContext:
    """Helper: build a minimal TemporalContext for testing."""
    now = datetime(2026, 5, 28, hour, 0, 0, tzinfo=NY)
    last_ts = (now - timedelta(hours=silence_hours)).isoformat()

    carry = EmotionalCarryover(
        intimacy_afterglow=0.1,
        unresolved_worry=0.1,
        emotional_openness_residue=0.1,
        attachment_heat=0.1,
        source_event="test",
        triggered_at=now.isoformat(),
        decay_rate=0.08,
    )
    momentum = MomentumState(vulnerability_window=False, emotional_amplification=0.0)
    anticipatory = AnticipatoryState(
        preoccupation_flavor="none",
        expected_presence_prob=0.6,
        silence_hours=silence_hours,
        is_overdue=silence_hours > 48,
    )
    ctx = TemporalContext(
        persona_id="akane",
        current_hour=hour,
        time_period="evening",
        silence_hours=silence_hours,
        carryover=carry,
        momentum=momentum,
        anticipatory=anticipatory,
        deviation_interpretation="normal",
        emotional_inhibition=0.3,
        stress=50,
    )
    # Allow overriding fields for targeted tests
    for key, val in extra_fields.items():
        setattr(ctx, key, val)
    return ctx


# ── salience tests ────────────────────────────────────────────────────────────

def test_low_salience_casual_chat():
    """日常閒聊：silence < 6h，不是深夜，salience 應為 low"""
    ctx = make_ctx(hour=15, silence_hours=1.0)
    assert _compute_temporal_salience(ctx) == "low"


def test_medium_salience_long_silence():
    """沉默超過 6 小時：salience 應為 medium"""
    ctx = make_ctx(hour=15, silence_hours=7.0)
    assert _compute_temporal_salience(ctx) == "medium"


def test_high_salience_overdue():
    """消失超過 48 小時：salience 應為 high"""
    ctx = make_ctx(hour=15, silence_hours=50.0)
    assert _compute_temporal_salience(ctx) == "high"


def test_high_salience_vulnerability_window():
    """深夜 + silence > 4h：vulnerability_window=True → salience=high"""
    ctx = make_ctx(hour=2, silence_hours=5.0)
    ctx.momentum.vulnerability_window = True
    assert _compute_temporal_salience(ctx) == "high"


# ── expression_mode tests ────────────────────────────────────────────────────

def test_implicit_by_default():
    """低顯著度時，expression_mode 預設為 implicit"""
    ctx = make_ctx(hour=15, silence_hours=1.0)
    assert _compute_expression_mode(ctx) == "implicit"


def test_soft_explicit_when_overdue():
    """消失超過 48h → expression_mode=soft_explicit"""
    ctx = make_ctx(hour=15, silence_hours=50.0)
    assert _compute_expression_mode(ctx) == "soft_explicit"


# ── render output tests ─────────────────────────────────────────────────────

def test_render_no_clock_time():
    """render 輸出不應包含 current_time 或 weekday 等時鐘字串"""
    ctx = make_ctx(hour=10, silence_hours=2.0)
    block = render_temporal_block(ctx)
    assert "current_time" not in block
    assert "weekday" not in block
    assert "Thursday" not in block
    assert "木曜日" not in block


def test_render_contains_reaction_bias():
    """render 輸出應包含 reaction_bias 欄位"""
    ctx = make_ctx(hour=15, silence_hours=1.0)
    block = render_temporal_block(ctx)
    assert "reaction_bias=" in block
    assert "expression_mode=" in block
    assert "temporal_salience=" in block
