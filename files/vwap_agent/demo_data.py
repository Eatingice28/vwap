"""Sample data so the dashboard can be tested without an API key.

Demo bars are generated from a fixed random seed, so the same ticker and
scenario always produce the same chart. Nothing here touches the internet.

Shape of a demo day:
  04:00-09:30 ET  a bounded premarket wander, which creates a clean
                  premarket high and low
  09:30 onwards   a session that moves toward a target for the chosen
                  scenario, so the colours and wording are easy to test
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

import numpy as np
import pandas as pd

from . import config as cfg

SCENARIOS = ("Bullish", "Bearish", "Mixed", "Neutral")

# Rough starting prices so demo numbers look sensible.
_BASE_PRICES = {
    "SPY": 545.0, "QQQ": 470.0, "NVDA": 128.0, "TSLA": 245.0,
    "AAPL": 225.0, "AMD": 158.0, "MSFT": 425.0, "AMZN": 185.0,
    "META": 505.0, "GOOGL": 178.0,
}

# Per scenario: total move by the end of the session for the main ticker
# and for the indices, plus a noise multiplier.
_SCENARIOS = {
    "Bullish": {"main": 0.018, "index": 0.009, "noise": 1.0},
    "Bearish": {"main": -0.018, "index": -0.009, "noise": 1.0},
    "Mixed": {"main": 0.018, "index": -0.009, "noise": 1.0},
    "Neutral": {"main": 0.0005, "index": 0.0003, "noise": 0.45},
}

# Half-width of the premarket wander, as a fraction of price.
_PREMARKET_AMPLITUDE = {"main": 0.0045, "index": 0.0025}


def _base_price(ticker: str) -> float:
    ticker = ticker.upper()
    if ticker in _BASE_PRICES:
        return _BASE_PRICES[ticker]
    # Stable pseudo-price for any other symbol, between $40 and $340.
    seed = sum(ord(char) for char in ticker)
    return 40.0 + (seed % 300)


def _seed_for(ticker: str, scenario: str, day: str) -> int:
    text = f"{ticker.upper()}|{scenario}|{day}"
    value = 0
    for char in text:  # stable across runs, unlike hash()
        value = (value * 131 + ord(char)) % (2**31 - 1)
    return value


def _demo_end_time(now_et: datetime) -> datetime:
    """Where the synthetic day should stop.

    On weekends, or early in the day, show a complete-looking mid-morning
    session so there is always post-open action to look at.
    """
    close_of_day = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    mid_morning = now_et.replace(hour=11, minute=30, second=0, microsecond=0)
    if now_et.weekday() >= 5 or now_et < mid_morning:
        return mid_morning
    return min(now_et.replace(second=0, microsecond=0), close_of_day)


def _ou_path(rng: np.random.Generator, n: int, amplitude: float) -> np.ndarray:
    """A bounded wander (Ornstein-Uhlenbeck style) centred on zero."""
    if n <= 0:
        return np.zeros(0)
    theta, path, level = 0.045, np.empty(n), 0.0
    step_sd = amplitude * 0.30
    for i in range(n):
        level = level * (1 - theta) + rng.normal(0.0, step_sd)
        path[i] = level
    peak = float(np.max(np.abs(path))) or 1.0
    return path / peak * amplitude  # scale so the range is predictable


def generate_demo_bars(ticker: str, scenario: str, now_et: datetime,
                       is_index: bool = False) -> pd.DataFrame:
    """Build one day of synthetic 1-minute bars from 04:00 ET."""
    scenario = scenario if scenario in _SCENARIOS else "Neutral"
    settings = _SCENARIOS[scenario]
    role = "index" if is_index else "main"

    end = _demo_end_time(now_et)
    start = end.replace(hour=4, minute=0, second=0, microsecond=0)
    if end <= start:
        end = start + timedelta(minutes=180)

    index = pd.date_range(start=start, end=end, freq="1min", tz=cfg.ET)
    n = len(index)
    rng = np.random.default_rng(_seed_for(ticker, scenario, str(end.date())))
    price0 = _base_price(ticker)

    is_premarket = np.array([ts.time() < dtime(*cfg.MARKET_OPEN) for ts in index])
    n_pre = int(is_premarket.sum())
    n_post = n - n_pre

    # --- premarket: bounded wander, so the high/low are meaningful ---------
    premarket_path = _ou_path(rng, n_pre, _PREMARKET_AMPLITUDE[role])

    # --- regular session: walk toward the scenario target -----------------
    if n_post > 0:
        progress = np.linspace(0.0, 1.0, n_post) ** 0.75
        target = settings[role]
        session_noise_sd = (0.0006 if role == "main" else 0.0003) * settings["noise"]
        wobble = np.cumsum(rng.normal(0.0, session_noise_sd, size=n_post))
        wobble = wobble - np.linspace(0, wobble[-1], n_post) * 0.5  # keep it tame
        start_level = float(premarket_path[-1]) if n_pre else 0.0
        session_path = start_level + target * progress + wobble
    else:
        session_path = np.zeros(0)

    path = np.concatenate([premarket_path, session_path])
    closes = price0 * (1.0 + path)

    opens = np.concatenate([[price0], closes[:-1]])
    tick = np.abs(rng.normal(0.0, 0.0004, size=n)) * closes
    highs = np.maximum(opens, closes) + tick
    lows = np.minimum(opens, closes) - tick

    base_volume = 40000 if is_index else 4000
    session_weight = np.where(is_premarket, 0.2, 1.0)
    volumes = (rng.gamma(3.0, base_volume / 3.0, size=n) * session_weight).round() + 1

    typical = (highs + lows + closes) / 3.0

    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "vwap": typical,
        },
        index=index,
    ).astype("float64")


def load_demo_session(ticker: str, scenario: str, now_et: datetime,
                      is_index: bool = False) -> dict:
    bars = generate_demo_bars(ticker, scenario, now_et, is_index=is_index)
    return {
        "bars": bars,
        "session_date": bars.index[-1].date(),
        "is_today": True,
    }
