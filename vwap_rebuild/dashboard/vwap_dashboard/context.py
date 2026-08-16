"""Educational, non-instructional contextual wording for the dashboard."""
from __future__ import annotations

from typing import Optional

from . import config as cfg

_SCORE = {"bullish": 1, "bearish": -1, "mixed": 0, "neutral": 0}
_HEADLINES = {
    "bullish": "Bullish context",
    "bearish": "Bearish context",
    "mixed": "Mixed context — confirmation needed",
    "neutral": "Neutral context — watch area",
}


def _stock_phrase(symbol: str, state: Optional[str], distance_pct: Optional[float]) -> str:
    if state is None:
        return f"{symbol} does not have enough data to place it against VWAP yet"
    distance = f" ({distance_pct * 100:+.2f}% from VWAP)" if distance_pct is not None else ""
    phrases = {
        cfg.ABOVE_VWAP: f"{symbol} is holding above intraday VWAP{distance}",
        cfg.BELOW_VWAP: f"{symbol} is holding below intraday VWAP{distance}",
        cfg.RECLAIMING_VWAP: f"{symbol} has moved back above VWAP in the recent bars{distance}",
        cfg.REJECTING_VWAP: f"{symbol} has moved back below VWAP in the recent bars{distance}",
        cfg.AT_VWAP: f"{symbol} is sitting near VWAP{distance}, a watch area where confirmation is needed",
    }
    return phrases.get(state, f"{symbol} has an unclassified VWAP reading")


def _index_phrase(symbol: str, state: Optional[str]) -> str:
    if state is None:
        return f"{symbol} premarket levels are not available yet"
    if state == cfg.ABOVE_PM_HIGH:
        return f"{symbol} is above its premarket high"
    if state == cfg.BELOW_PM_LOW:
        return f"{symbol} is below its premarket low"
    return f"{symbol} remains inside its premarket range"


def overall_tone(stock_tone: str, spy_tone: str, qqq_tone: str) -> str:
    stock_score = _SCORE.get(stock_tone, 0)
    index_score = _SCORE.get(spy_tone, 0) + _SCORE.get(qqq_tone, 0)
    if stock_score == 0 and index_score == 0:
        return "neutral"
    if (stock_score > 0 and index_score < 0) or (stock_score < 0 and index_score > 0):
        return "mixed"
    combined = stock_score * 2 + index_score
    if combined >= 3:
        return "bullish"
    if combined <= -3:
        return "bearish"
    return "mixed" if combined else "neutral"


def build_summary(symbol: str, stock: dict, spy: dict, qqq: dict, premarket_label: str, note: str = "") -> dict:
    tone = overall_tone(stock.get("tone", "neutral"), spy.get("tone", "neutral"), qqq.get("tone", "neutral"))
    body = [
        _stock_phrase(symbol, stock.get("state"), stock.get("distance_pct")) + ".",
        _index_phrase("SPY", spy.get("state")) + ", and " + _index_phrase("QQQ", qqq.get("state")) + ".",
    ]
    if tone == "bullish":
        body.append("Together, these readings describe bullish context only; confirmation is still needed and the context can change.")
    elif tone == "bearish":
        body.append("Together, these readings describe bearish context only; confirmation is still needed and the context can change.")
    elif tone == "mixed":
        body.append("The symbol and broad-market backdrop disagree, creating mixed context and a watch area rather than a decided reading.")
    else:
        body.append("Nothing is leaning strongly in either direction yet, so this is a watch area where confirmation is needed.")
    body.append(f"Premarket range measured from {premarket_label}.")
    if note:
        body.append(note)
    return {"tone": tone, "headline": _HEADLINES[tone], "body": " ".join(body)}
