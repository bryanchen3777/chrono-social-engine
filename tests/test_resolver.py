"""
test_resolver.py — resolver.py 單元測試
"""

import pytest

from chrono_social_engine.core import TemporalContext, EmotionalCarryover, MomentumState, AnticipatoryState
from chrono_social_engine.resolver import detect_resolved_event


# ── Fixtures ──────────────────────────────────────────────────────────────────

def mock_ctx(
    time_period="morning",
    silence_hours=1.0,
    unresolved_worry=0.0,
) -> TemporalContext:
    carry = EmotionalCarryover(
        intimacy_afterglow=0.0,
        unresolved_worry=unresolved_worry,
        emotional_openness_residue=0.0,
        attachment_heat=0.0,
        source_event="test",
        triggered_at="2026-01-01T00:00:00",
        decay_rate=0.12,
    )
    return TemporalContext(
        persona_id="akane",
        current_hour=9,
        time_period=time_period,
        silence_hours=silence_hours,
        carryover=carry,
        momentum=MomentumState(vulnerability_window=False, emotional_amplification=0.0),
        anticipatory=AnticipatoryState(preoccupation_flavor="none", expected_presence_prob=0.6, silence_hours=silence_hours),
        deviation_interpretation="normal",
        emotional_inhibition=0.3,
        stress=30,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDetectResolvedEvent:
    @pytest.mark.parametrize("msg,expected", [
        ("沒事啦放心", "user_confirmed_ok"),
        ("還好，還可以", "user_confirmed_ok"),
        ("好多了，謝謝", "user_confirmed_ok"),
        ("我沒事啦", "user_confirmed_ok"),
        ("fine", "user_confirmed_ok"),
        ("i'm good", "user_confirmed_ok"),
        ("ok", "user_confirmed_ok"),
        ("thanks for worrying", "explicit_reassurance"),
        ("謝謝你擔心", "explicit_reassurance"),
        ("你放心，我會注意", "explicit_reassurance"),
        ("don't worry about me", "explicit_reassurance"),
    ])
    def test_positive_cases(self, msg, expected):
        ctx = mock_ctx()
        assert detect_resolved_event(msg, ctx) == expected

    def test_no_resolution_neutral_message(self):
        ctx = mock_ctx()
        assert detect_resolved_event("你好", ctx) is None
        assert detect_resolved_event("今天天氣怎麼樣", ctx) is None

    def test_user_slept_normally_morning_with_worry(self):
        """早晨 + silence > 5h + unresolved_worry > 0.3 → user_slept_normally"""
        ctx = mock_ctx(time_period="morning", silence_hours=7.0, unresolved_worry=0.5)
        assert detect_resolved_event("hi", ctx) == "user_slept_normally"

    def test_user_slept_normally_dawn(self):
        """dawn + silence > 5h + worry > 0.3 → user_slept_normally"""
        ctx = mock_ctx(time_period="dawn", silence_hours=8.0, unresolved_worry=0.4)
        assert detect_resolved_event("嗨", ctx) == "user_slept_normally"

    def test_user_slept_normally_no_worry_no_trigger(self):
        """有 morning ctx 但 worry < 0.3 → 不觸發"""
        ctx = mock_ctx(time_period="morning", silence_hours=10.0, unresolved_worry=0.2)
        assert detect_resolved_event("嗨", ctx) is None

    def test_user_slept_normally_short_silence(self):
        """morning ctx 但 silence < 5h → 不觸發"""
        ctx = mock_ctx(time_period="morning", silence_hours=3.0, unresolved_worry=0.8)
        assert detect_resolved_event("嗨", ctx) is None

    def test_user_slept_normally_afternoon_not_triggered(self):
        """afternoon + worry > 0.3 + long silence → 不走 user_slept_normally"""
        ctx = mock_ctx(time_period="afternoon", silence_hours=10.0, unresolved_worry=0.6)
        assert detect_resolved_event("嗨", ctx) is None

    def test_user_slept_normally_evening_not_triggered(self):
        """evening + worry > 0.3 + long silence → 不走 user_slept_normally"""
        ctx = mock_ctx(time_period="evening", silence_hours=12.0, unresolved_worry=0.5)
        assert detect_resolved_event("晚上好", ctx) is None

    def test_mixed_ok_keyword(self):
        """同時有 ok 和 worry context，優先用 keyword"""
        ctx = mock_ctx(unresolved_worry=0.8)
        assert detect_resolved_event("沒事啦 ok", ctx) == "user_confirmed_ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])