"""Indicator maths: intraday VWAP, premarket high/low, and state labels.

Every function takes a bars DataFrame with a tz-aware ET DatetimeIndex and
columns: open, high, low, close, volume, vwap (per-bar VWAP, may be NaN).
"""

from __future__ import annotations

from datetime import time as dtime
from typing import Optional

import pandas as pd

from . import config as cfg


# ---------------------------------------------------------------- slicing
def slice_between(bars: pd.DataFrame, start: dtime, end: dtime) -> pd.DataFrame:
    """Return bars whose ET clock time is >= start and < end."""
    if bars.empty:
        return bars
    clock = bars.index.time
    mask = (clock >= start) & (clock < end)
    return bars.loc[mask]


def premarket_bars(bars: pd.DataFrame, start_hm: tuple[int, int]) -> pd.DataFrame:
    return slice_between(bars, dtime(*start_hm), dtime(*cfg.PREMARKET_END))


def regular_session_bars(bars: pd.DataFrame) -> pd.DataFrame:
    return slice_between(bars, dtime(*cfg.MARKET_OPEN), dtime(*cfg.MARKET_CLOSE))


# ------------------------------------------------------------------ VWAP
def _typical_price(bars: pd.DataFrame) -> pd.Series:
    """Per-bar VWAP if the data provider gave one, else (H+L+C)/3."""
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    if "vwap" in bars.columns:
        return bars["vwap"].astype(float).fillna(typical)
    return typical


def compute_vwap(bars: pd.DataFrame) -> pd.Series:
    """Cumulative volume-weighted average price across the given bars.

    VWAP resets each session, so pass in only the bars for one session
    (normally the regular session, 09:30-16:00 ET).
    """
    if bars.empty:
        return pd.Series(dtype="float64")
    price = _typical_price(bars)
    volume = bars["volume"].astype(float).clip(lower=0)
    cum_vol = volume.cumsum()
    cum_pv = (price * volume).cumsum()
    # If a stretch has zero volume, fall back to a plain running mean.
    vwap = cum_pv / cum_vol.replace(0, pd.NA)
    return vwap.astype("float64").ffill().fillna(price.expanding().mean())


def vwap_frame(bars: pd.DataFrame, premarket_start_hm: tuple[int, int]) -> dict:
    """Build the VWAP series for whichever session is currently running.

    Returns a dict with the bars used, the VWAP series, and a label saying
    which session the VWAP covers.
    """
    regular = regular_session_bars(bars)
    if not regular.empty:
        return {
            "bars": regular,
            "vwap": compute_vwap(regular),
            "session": "regular",
            "session_label": "Regular session VWAP (from 9:30 AM ET)",
        }

    pre = premarket_bars(bars, premarket_start_hm)
    if not pre.empty:
        return {
            "bars": pre,
            "vwap": compute_vwap(pre),
            "session": "premarket",
            "session_label": "Premarket VWAP (regular session has not opened yet)",
        }

    return {"bars": bars.iloc[0:0], "vwap": pd.Series(dtype="float64"),
            "session": "none", "session_label": "No session data yet"}


# ------------------------------------------------------------ state logic
def vwap_state(bars: pd.DataFrame, vwap: pd.Series) -> dict:
    """Decide whether price is above, below, reclaiming or rejecting VWAP."""
    if bars.empty or vwap.empty:
        return {"state": None, "price": None, "vwap": None, "distance_pct": None}

    price = float(bars["close"].iloc[-1])
    current_vwap = float(vwap.iloc[-1])
    if current_vwap <= 0:
        return {"state": None, "price": price, "vwap": None, "distance_pct": None}

    distance_pct = (price - current_vwap) / current_vwap
    band = cfg.VWAP_NEUTRAL_BAND_PCT

    # Sign of close-vs-VWAP over the recent lookback window.
    lookback = min(cfg.CROSS_LOOKBACK_BARS, len(bars))
    recent_close = bars["close"].iloc[-lookback:]
    recent_vwap = vwap.iloc[-lookback:]
    diffs = (recent_close - recent_vwap).astype(float)
    prior = diffs.iloc[:-1] if len(diffs) > 1 else diffs.iloc[0:0]

    if abs(distance_pct) <= band:
        state = cfg.AT_VWAP
    elif distance_pct > 0:
        # Above now. Was it below at any point in the recent window?
        state = cfg.RECLAIMING_VWAP if (prior < 0).any() else cfg.ABOVE_VWAP
    else:
        # Below now. Was it above at any point in the recent window?
        state = cfg.REJECTING_VWAP if (prior > 0).any() else cfg.BELOW_VWAP

    return {
        "state": state,
        "price": price,
        "vwap": current_vwap,
        "distance_pct": distance_pct,
        "tone": cfg.VWAP_TONES.get(state, "neutral"),
    }


def premarket_levels(bars: pd.DataFrame, start_hm: tuple[int, int]) -> dict:
    """Premarket high and low for the chosen premarket window."""
    pre = premarket_bars(bars, start_hm)
    if pre.empty:
        return {"high": None, "low": None, "bar_count": 0}
    return {
        "high": float(pre["high"].max()),
        "low": float(pre["low"].min()),
        "bar_count": int(len(pre)),
    }


def range_state(price: Optional[float], high: Optional[float],
                low: Optional[float]) -> dict:
    """Where price sits relative to the premarket range."""
    if price is None or high is None or low is None:
        return {"state": None, "tone": "neutral"}
    if price > high:
        state = cfg.ABOVE_PM_HIGH
    elif price < low:
        state = cfg.BELOW_PM_LOW
    else:
        state = cfg.INSIDE_PM_RANGE
    return {"state": state, "tone": cfg.RANGE_TONES[state]}


def last_price(bars: pd.DataFrame) -> Optional[float]:
    if bars.empty:
        return None
    return float(bars["close"].iloc[-1])


def session_change_pct(bars: pd.DataFrame) -> Optional[float]:
    """Percent move from the first bar of the day to the latest bar."""
    if bars.empty or len(bars) < 2:
        return None
    first = float(bars["open"].iloc[0])
    if first <= 0:
        return None
    return (float(bars["close"].iloc[-1]) - first) / first
