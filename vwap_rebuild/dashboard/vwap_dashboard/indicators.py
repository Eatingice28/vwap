"""Pure indicators for educational VWAP and premarket-range context."""
from __future__ import annotations

from datetime import time as dtime
from typing import Optional

import pandas as pd

from . import config as cfg


def empty_bars() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["open", "high", "low", "close", "volume", "vwap"],
        index=pd.DatetimeIndex([], tz=cfg.ET, name="timestamp"),
        dtype="float64",
    )


def slice_between(bars: pd.DataFrame, start: dtime, end: dtime) -> pd.DataFrame:
    if bars.empty:
        return bars
    clock = bars.index.time
    return bars.loc[(clock >= start) & (clock < end)]


def premarket_bars(bars: pd.DataFrame, start: dtime) -> pd.DataFrame:
    return slice_between(bars, start, cfg.PREMARKET_END)


def regular_session_bars(bars: pd.DataFrame) -> pd.DataFrame:
    return slice_between(bars, cfg.MARKET_OPEN, cfg.MARKET_CLOSE)


def compute_vwap(bars: pd.DataFrame) -> pd.Series:
    """Compute cumulative session VWAP, preferring supplied per-bar VWAP when present."""
    if bars.empty:
        return pd.Series(dtype="float64")
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    price = bars.get("vwap", typical).astype(float).fillna(typical)
    volume = bars["volume"].astype(float).clip(lower=0)
    cumulative_volume = volume.cumsum()
    cumulative_price_volume = (price * volume).cumsum()
    return (cumulative_price_volume / cumulative_volume.replace(0, pd.NA)).astype("float64").ffill().fillna(price.expanding().mean())


def vwap_frame(bars: pd.DataFrame, premarket_start: dtime) -> dict:
    regular = regular_session_bars(bars)
    if not regular.empty:
        return {"bars": regular, "vwap": compute_vwap(regular), "session_label": "Regular-session VWAP (from 9:30 AM ET)"}
    premarket = premarket_bars(bars, premarket_start)
    if not premarket.empty:
        return {"bars": premarket, "vwap": compute_vwap(premarket), "session_label": "Premarket VWAP (regular session has not opened yet)"}
    return {"bars": empty_bars(), "vwap": pd.Series(dtype="float64"), "session_label": "No session data yet"}


def vwap_state(bars: pd.DataFrame, vwap: pd.Series) -> dict:
    if bars.empty or vwap.empty:
        return {"state": None, "tone": "neutral", "price": None, "vwap": None, "distance_pct": None}
    price = float(bars["close"].iloc[-1])
    current_vwap = float(vwap.iloc[-1])
    if current_vwap <= 0:
        return {"state": None, "tone": "neutral", "price": price, "vwap": None, "distance_pct": None}
    distance_pct = (price - current_vwap) / current_vwap
    lookback = min(cfg.CROSS_LOOKBACK_BARS, len(bars))
    differences = (bars["close"].iloc[-lookback:] - vwap.iloc[-lookback:]).astype(float)
    prior = differences.iloc[:-1]
    if abs(distance_pct) <= cfg.VWAP_NEUTRAL_BAND_PCT:
        state = cfg.AT_VWAP
    elif distance_pct > 0:
        state = cfg.RECLAIMING_VWAP if (prior < 0).any() else cfg.ABOVE_VWAP
    else:
        state = cfg.REJECTING_VWAP if (prior > 0).any() else cfg.BELOW_VWAP
    return {"state": state, "tone": cfg.VWAP_TONES[state], "price": price, "vwap": current_vwap, "distance_pct": distance_pct}


def premarket_levels(bars: pd.DataFrame, premarket_start: dtime) -> dict:
    premarket = premarket_bars(bars, premarket_start)
    if premarket.empty:
        return {"high": None, "low": None, "bar_count": 0}
    return {"high": float(premarket["high"].max()), "low": float(premarket["low"].min()), "bar_count": int(len(premarket))}


def range_state(price: Optional[float], high: Optional[float], low: Optional[float]) -> dict:
    if price is None or high is None or low is None:
        return {"state": None, "tone": "neutral"}
    if price > high:
        state = cfg.ABOVE_PM_HIGH
    elif price < low:
        state = cfg.BELOW_PM_LOW
    else:
        state = cfg.INSIDE_PM_RANGE
    return {"state": state, "tone": cfg.RANGE_TONES[state]}


def session_change_pct(bars: pd.DataFrame) -> Optional[float]:
    if bars.empty or len(bars) < 2 or float(bars["open"].iloc[0]) <= 0:
        return None
    return (float(bars["close"].iloc[-1]) - float(bars["open"].iloc[0])) / float(bars["open"].iloc[0])
