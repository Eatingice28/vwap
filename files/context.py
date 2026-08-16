"""Turns the numbers into a plain-English context summary.

Wording rules for this file:
  - Describe context only. Never say buy, sell, enter, exit or target.
  - Never predict a price or promise an outcome.
  - Prefer phrases like "bullish context", "watch area", "confirmation needed".
"""

from __future__ import annotations

from typing import Optional

from . import config as cfg

_TONE_SCORE = {"bullish": 1, "bearish": -1, "mixed": 0, "neutral": 0}

_HEADLINES = {
    "bullish": "Bullish context",
    "bearish": "Bearish context",
    "mixed": "Mixed context - caution",
    "neutral": "Neutral context - confirmation needed",
}


def _index_phrase(name: str, state: Optional[str]) -> str:
    if state is None:
        return f"{name} premarket levels are not available yet"
    if state == cfg.ABOVE_PM_HIGH:
        return f"{name} is trading above its premarket high"
    if state == cfg.BELOW_PM_LOW:
        return f"{name} is trading below its premarket low"
    return f"{name} is still inside its premarket range"


def _stock_phrase(ticker: str, state: Optional[str],
                  distance_pct: Optional[float]) -> str:
    if state is None:
        return f"{ticker} does not have enough data to place it against VWAP yet"
    gap = ""
    if distance_pct is not None:
        gap = f" ({distance_pct * 100:+.2f}% from VWAP)"
    if state == cfg.ABOVE_VWAP:
        return f"{ticker} is holding above intraday VWAP{gap}"
    if state == cfg.BELOW_VWAP:
        return f"{ticker} is holding below intraday VWAP{gap}"
    if state == cfg.RECLAIMING_VWAP:
        return f"{ticker} has crossed back above VWAP in the last few minutes{gap}"
    if state == cfg.REJECTING_VWAP:
        return f"{ticker} has slipped back below VWAP in the last few minutes{gap}"
    return f"{ticker} is sitting right on VWAP{gap} - a watch area rather than a decided one"


def overall_tone(stock_tone: str, spy_tone: str, qqq_tone: str) -> str:
    """Combine one stock reading and two index readings into a tone."""
    stock_score = _TONE_SCORE.get(stock_tone, 0)
    index_score = _TONE_SCORE.get(spy_tone, 0) + _TONE_SCORE.get(qqq_tone, 0)

    if stock_score == 0 and index_score == 0:
        return "neutral"
    # Stock and indices pointing opposite ways is the classic mixed case.
    if stock_score > 0 and index_score < 0:
        return "mixed"
    if stock_score < 0 and index_score > 0:
        return "mixed"
    total = stock_score * 2 + index_score
    if total >= 3:
        return "bullish"
    if total <= -3:
        return "bearish"
    if total == 0:
        return "neutral"
    return "mixed"


def build_summary(ticker: str, stock: dict, spy: dict, qqq: dict,
                  premarket_label: str, session_note: str = "") -> dict:
    """Return the headline, tone and body paragraph for the summary card."""
    stock_tone = stock.get("tone") or "neutral"
    spy_tone = spy.get("tone") or "neutral"
    qqq_tone = qqq.get("tone") or "neutral"
    tone = overall_tone(stock_tone, spy_tone, qqq_tone)

    lines = [
        _stock_phrase(ticker, stock.get("state"), stock.get("distance_pct")) + ".",
        _index_phrase("SPY", spy.get("state")) + ", and "
        + _index_phrase("QQQ", qqq.get("state")) + ".",
    ]

    if tone == "bullish":
        lines.append(
            f"Taken together this reads as a bullish context: {ticker} and the "
            "broad market are leaning the same way. Continuation is not "
            "guaranteed - confirmation is still needed, and losing VWAP would "
            "change the picture."
        )
    elif tone == "bearish":
        lines.append(
            f"Taken together this reads as a bearish context: {ticker} and the "
            "broad market are leaning the same way. Reclaiming VWAP would "
            "change the picture, so confirmation is still needed."
        )
    elif tone == "mixed":
        lines.append(
            f"{ticker} and the index backdrop disagree, which is a mixed "
            "context. Mixed conditions are usually where false moves happen, "
            "so treat these levels as a watch area and wait for confirmation."
        )
    else:
        lines.append(
            "Nothing here is leaning strongly in either direction yet. This is "
            "a neutral context - the premarket levels and VWAP are the areas "
            "to watch until one of them gives way."
        )

    lines.append(f"Premarket range measured from {premarket_label}.")
    if session_note:
        lines.append(session_note)

    return {
        "tone": tone,
        "headline": _HEADLINES[tone],
        "body": " ".join(lines),
    }


def build_alerts(ticker: str, previous: dict, current: dict) -> list[str]:
    """Compare the last reading with this one and describe what changed."""
    if not previous:
        return []
    events = []

    def changed(key: str) -> bool:
        return previous.get(key) is not None and previous.get(key) != current.get(key)

    if changed("stock_state"):
        events.append(
            f"{ticker}: {previous['stock_state']} -> {current['stock_state']}"
        )
    for name in ("SPY", "QQQ"):
        key = f"{name.lower()}_state"
        if changed(key):
            events.append(f"{name}: {previous[key]} -> {current[key]}")
    if changed("tone"):
        events.append(
            f"Overall context: {previous['tone']} -> {current['tone']}"
        )
    return events
