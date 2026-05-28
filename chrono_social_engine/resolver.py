"""
resolver.py — resolved_event 自動偵測
Automatic detection of emotional resolution events from user messages.
"""

from __future__ import annotations

from typing import Optional

from .core import TemporalContext

# ── Keyword patterns ──────────────────────────────────────────────────────────

_RESOLUTION_PATTERNS = {
    "user_confirmed_ok": [
        # 中文
        "沒事", "還好", "好多了", "不用擔心", "我沒事", "還可以", "沒關係",
        # English
        "fine", "ok", "okay", "better", "i'm good", "i'm fine", "all good",
    ],
    "explicit_reassurance": [
        # 中文
        "謝謝你擔心", "知道了", "會注意", "你放心", "不用操心", "我會注意",
        # English
        "thanks for worrying", "i'll be careful", "don't worry about me",
    ],
}


def _matches_any(text: str, keywords: list[str]) -> bool:
    """大小寫不敏感，子字串匹配。"""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def detect_resolved_event(user_message: str, ctx: TemporalContext) -> Optional[str]:
    """
    根據 user_message 與 ctx 自動偵測情緒是否已被解除。
    回傳：'user_confirmed_ok' | 'explicit_reassurance' | 'user_slept_normally' | None

    Logic：
    1. 先試 keyword match（user_confirmed_ok / explicit_reassurance）
    2. 再看 user_slept_normally（不看 keyword，看 ctx）
    """
    # 1. Keyword-based detection
    for event_type, keywords in _RESOLUTION_PATTERNS.items():
        if _matches_any(user_message, keywords):
            return event_type

    # 2. Sleep-based resolution
    # 條件：早晨/morning 且上次有未解除的 worry 且沉默 > 5 小時
    if (
        ctx.time_period in ("morning", "dawn")
        and ctx.carryover.unresolved_worry > 0.3
        and ctx.silence_hours > 5
    ):
        return "user_slept_normally"

    return None