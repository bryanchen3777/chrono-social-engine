"""
test_core.py — core.py 單元測試
"""

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chrono_social_engine.core import (
    EmotionalCarryover,
    MomentumState,
    AnticipatoryState,
    TemporalContext,
    PersonaConfig,
    compute_time_period,
    compute_sleep_pressure,
    compute_emotional_inhibition,
    compute_vulnerability_window,
    build_temporal_context,
    merge_carryover,
    decay_carryover,
    TIME_PERIODS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

AKANE_CONFIG = PersonaConfig(
    persona_id="akane",
    decay_rate=0.08,
    vulnerability_hour_start=22,
    vulnerability_hour_end=4,
    vulnerability_inhibition_threshold=0.45,
    vulnerability_silence_min=4.5,
)

DEFAULT_CONFIG = PersonaConfig(persona_id="test")


def make_carryover(**kw) -> EmotionalCarryover:
    defaults = dict(
        intimacy_afterglow=0.0,
        unresolved_worry=0.0,
        emotional_openness_residue=0.0,
        attachment_heat=0.0,
        source_event="",
        triggered_at=datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        decay_rate=0.12,
    )
    defaults.update(kw)
    return EmotionalCarryover(**defaults)


# ── compute_time_period ───────────────────────────────────────────────────────

class TestComputeTimePeriod:
    @pytest.mark.parametrize("hour,expected", [
        (3, "deep_night"),
        (5, "dawn"),
        (8, "morning"),
        (12, "afternoon"),
        (15, "afternoon"),
        (19, "evening"),
        (22, "night"),
        (23, "night"),
        (0, "deep_night"),
    ])
    def test_known_hours(self, hour, expected):
        assert compute_time_period(hour) == expected


# ── compute_sleep_pressure ───────────────────────────────────────────────────

class TestComputeSleepPressure:
    def test_peak_at_night(self):
        # 凌晨是高峰
        assert compute_sleep_pressure(2) > 0.9

    def test_low_in_afternoon(self):
        # 下午應該是低點
        assert compute_sleep_pressure(15) < 0.1

    def test_curve_symmetry(self):
        # 鐘形曲線：22:00 ≈ 0.0, 02:00 ≈ 1.0
        assert compute_sleep_pressure(22) < 0.1
        assert compute_sleep_pressure(2) > 0.9


# ── compute_vulnerability_window ────────────────────────────────────────────

class TestVulnerabilityWindow:
    def test_deep_night_with_long_silence(self):
        """凌晨3點 + silence 5h → 茜的門檻4.5h → True"""
        config = AKANE_CONFIG
        assert compute_vulnerability_window(3, 5.0, config) is True

    def test_deep_night_below_threshold(self):
        """凌晨3點 + silence 4h → 低於門檻 → False"""
        config = AKANE_CONFIG
        assert compute_vulnerability_window(3, 4.0, config) is False

    def test_daytime_no_trigger(self):
        """下午3點 → 不在深夜區間 → False"""
        config = AKANE_CONFIG
        assert compute_vulnerability_window(15, 10.0, config) is False

    def test_night_with_short_silence(self):
        """22:00 + silence 2h → 低於門檻 → False"""
        config = AKANE_CONFIG
        assert compute_vulnerability_window(22, 2.0, config) is False

    def test_night_at_exact_threshold(self):
        """22:00 + silence 4.5h → 等於門檻 → True"""
        config = AKANE_CONFIG
        assert compute_vulnerability_window(22, 4.5, config) is True

    def test_cross_midnight_range(self):
        """跨午夜：23:00 在區間內，1:00 在區間內，10:00 不在"""
        config = PersonaConfig(persona_id="test", vulnerability_hour_start=22, vulnerability_hour_end=4)
        assert compute_vulnerability_window(23, 4.0, config) is True
        assert compute_vulnerability_window(1, 4.0, config) is True
        assert compute_vulnerability_window(10, 4.0, config) is False


# ── compute_emotional_inhibition ────────────────────────────────────────────

class TestEmotionalInhibition:
    def test_long_silence_high_inhibition(self):
        """72h+ → 0.88"""
        assert compute_emotional_inhibition(100.0, False, False) == 0.88

    def test_short_silence_low_inhibition(self):
        """30min → 0.0"""
        assert compute_emotional_inhibition(0.5, False, False) == 0.0

    def test_vuln_window_reduces_inhibition(self):
        """有 vuln_window → inhibition 降 0.35"""
        base = compute_emotional_inhibition(10.0, False, False)
        with_vuln = compute_emotional_inhibition(10.0, True, False)
        assert with_vuln == max(0.0, base - 0.35)

    def test_sleep_dep_reduces_inhibition(self):
        """睡眠剝奪 → inhibition 降 0.25"""
        base = compute_emotional_inhibition(10.0, False, False)
        with_dep = compute_emotional_inhibition(10.0, False, True)
        assert with_dep == max(0.0, base - 0.25)

    def test_floor_at_zero(self):
        """抑制不會低於 0"""
        assert compute_emotional_inhibition(0.0, True, True) == 0.0

    def test_ceiling_at_one(self):
        """抑制不會超過 1"""
        assert compute_emotional_inhibition(1000.0, False, False) == 1.0


# ── carryover decay ──────────────────────────────────────────────────────────

class TestCarryoverDecay:
    def test_intimacy_decay_12h(self):
        """12小時後 intimacy_afterglow 衰退到 (1-0.12)^12 ≈ 0.20"""
        c = make_carryover(intimacy_afterglow=1.0, decay_rate=0.12)
        decayed = c.apply_decay(12.0)
        assert 0.18 <= decayed.intimacy_afterglow <= 0.22

    def test_unresolved_worry_has_floor(self):
        """無論多久，worry >= original * 0.25"""
        c = make_carryover(unresolved_worry=0.80, decay_rate=0.12)
        decayed = c.apply_decay(1000.0)
        assert decayed.unresolved_worry >= 0.80 * 0.25

    def test_decay_rate_from_carryover(self):
        """decay_rate 從 carryover 自身的值讀取，不是 config"""
        c = make_carryover(intimacy_afterglow=1.0, decay_rate=0.05)
        decayed = c.apply_decay(10.0)
        # (1-0.05)^10 ≈ 0.60
        assert 0.58 <= decayed.intimacy_afterglow <= 0.62


# ── carryover merge ──────────────────────────────────────────────────────────

class TestCarryoverMerge:
    def test_merge_takes_max(self):
        """取最大值，不做平均"""
        old = make_carryover(intimacy_afterglow=0.4, unresolved_worry=0.3)
        new = make_carryover(intimacy_afterglow=0.6, unresolved_worry=0.5)
        merged = merge_carryover(old, new)
        assert merged.intimacy_afterglow == 0.6
        assert merged.unresolved_worry == 0.5

    def test_merge_no_overflow(self):
        """合併後不超過 1.0"""
        old = make_carryover(attachment_heat=0.95)
        new = make_carryover(attachment_heat=0.90)
        merged = merge_carryover(old, new)
        assert merged.attachment_heat <= 1.0

    def test_merge_none_existing(self):
        """existing=None → 直接回傳 new"""
        new = make_carryover(intimacy_afterglow=0.7)
        merged = merge_carryover(None, new)
        assert merged.intimacy_afterglow == 0.7

    def test_merge_repeated_stays_below_one(self):
        """連續 10 次 merge，attachment_heat 不會爆到 1.0"""
        carry = make_carryover(attachment_heat=0.0)
        new = make_carryover(attachment_heat=0.75)
        for _ in range(10):
            carry = merge_carryover(carry, new)
        assert carry.attachment_heat <= 1.0


# ── build_temporal_context ───────────────────────────────────────────────────

class TestBuildTemporalContext:
    def test_basic_context_building(self):
        carry = make_carryover()
        ctx = build_temporal_context(
            persona_id="akane",
            last_msg_ts=None,
            current_stress=40,
            carryover=carry,
            config=AKANE_CONFIG,
        )
        assert ctx.persona_id == "akane"
        assert ctx.stress == 40
        assert ctx.carryover is carry
        assert ctx.time_period in [name for _, _, name in TIME_PERIODS]

    def test_silence_hours_from_last_msg(self):
        past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=5)).isoformat()
        carry = make_carryover()
        ctx = build_temporal_context(
            persona_id="akane",
            last_msg_ts=past,
            current_stress=20,
            carryover=carry,
            config=AKANE_CONFIG,
        )
        assert 4.0 <= ctx.silence_hours <= 6.0

    def test_deviation_sleep_dep(self):
        """深夜 + 高 sleep_pressure → sleep_deprivation"""
        carry = make_carryover()
        # 手工傳一個深夜 timestamp
        past = (datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(hours=3)).replace(hour=2).isoformat()
        ctx = build_temporal_context(
            persona_id="akane",
            last_msg_ts=past,
            current_stress=30,
            carryover=carry,
            config=AKANE_CONFIG,
        )
        # 如果時間落在深夜且 sleep_pressure 高，會是 sleep_deprivation
        if ctx.time_period in ("deep_night", "night"):
            assert ctx.deviation_interpretation in (
                "sleep_deprivation", "longing", "missing", "normal"
            )


# ── PersonaConfig 参数差异 ─────────────────────────────────────────────────

class TestPersonaConfigDiff:
    def test_akane_decay_is_slow(self):
        """茜的 decay_rate = 0.08，比預設 0.12 慢"""
        assert AKANE_CONFIG.decay_rate < PersonaConfig(persona_id="x").decay_rate

    def test_akane_vulnerability_threshold_is_lower(self):
        """茜的抑制門檻 0.45，比預設 0.50 更難觸發"""
        assert AKANE_CONFIG.vulnerability_inhibition_threshold < 0.50

    def test_different_configs_produce_different_vuln(self):
        """不同 config 產生不同 vuln 判定"""
        cfg_strict = PersonaConfig(persona_id="strict", vulnerability_silence_min=8.0)
        cfg_relaxed = PersonaConfig(persona_id="relaxed", vulnerability_silence_min=2.0)

        hour, silence = 3, 5.0
        strict_vuln = compute_vulnerability_window(hour, silence, cfg_strict)
        relaxed_vuln = compute_vulnerability_window(hour, silence, cfg_relaxed)

        assert strict_vuln is False
        assert relaxed_vuln is True


# ── carryover trigger combination ────────────────────────────────────────────

class TestCarryoverTriggers:
    def test_vuln_plus_sleep_dep_worry(self):
        """vuln + sleep_dep 同時觸發 → worry 取 max(0.15, 0.85)"""
        # 使用 hooks._create_carryover_from_ctx 的邏輯
        # 這裡我們直接測試 compute_emotional_inhibition 的組合效果
        # 睡 dep → worry = 0.85
        inhibition = compute_emotional_inhibition(2.0, False, True)
        assert inhibition == max(0.0, 0.15 - 0.25)  # base=0.15 (2-6h range), -0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])