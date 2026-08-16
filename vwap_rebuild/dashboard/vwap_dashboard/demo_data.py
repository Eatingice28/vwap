"""Deterministic synthetic data for dashboard-only visual and logic testing."""
from __future__ import annotations

import hashlib
from datetime import datetime

import numpy as np
import pandas as pd

from . import config as cfg

SCENARIOS = ("Bullish context", "Bearish context", "Mixed context", "Neutral context")
_BASE_PRICES = {"SPY": 580.0, "QQQ": 500.0, "NVDA": 145.0, "AAPL": 210.0, "TSLA": 320.0, "AMD": 165.0}


def _seed(symbol: str, scenario: str) -> int:
    return int(hashlib.sha256(f"{symbol}:{scenario}".encode()).hexdigest()[:8], 16)


def generate_demo_bars(symbol: str, scenario: str, now: datetime | None = None) -> pd.DataFrame:
    """Return one synthetic day of one-minute OHLCV bars, explicitly not market data."""
    now_et = (now or datetime.now(cfg.ET)).astimezone(cfg.ET)
    session_day = now_et.date()
    index = pd.date_range(
        pd.Timestamp(datetime.combine(session_day, cfg.PREMARKET_START_CHOICES["4:00 AM ET"], tzinfo=cfg.ET)),
        pd.Timestamp(datetime.combine(session_day, cfg.MARKET_CLOSE, tzinfo=cfg.ET)),
        freq="min",
        inclusive="left",
    )
    generator = np.random.default_rng(_seed(symbol, scenario))
    base = _BASE_PRICES.get(symbol, 100.0 + (_seed(symbol, "base") % 200))
    drift_map = {
        "Bullish context": 0.00022,
        "Bearish context": -0.00022,
        "Mixed context": 0.00003 if symbol not in cfg.INDEX_TICKERS else -0.00006,
        "Neutral context": 0.000005,
    }
    volatility = 0.0022
    steps = generator.normal(drift_map[scenario], volatility, len(index))
    closes = base * np.exp(np.cumsum(steps))
    opens = np.r_[base, closes[:-1]]
    spread = np.maximum(closes * generator.uniform(0.0004, 0.0030, len(index)), 0.01)
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    volume = generator.integers(8_000, 100_000, len(index)).astype(float)
    vwap = (highs + lows + closes) / 3.0
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume, "vwap": vwap}, index=index)


def load_demo_session(symbol: str, scenario: str, now: datetime | None = None) -> dict:
    bars = generate_demo_bars(symbol, scenario, now)
    return {
        "bars": bars,
        "session_date": bars.index[-1].date() if not bars.empty else None,
        "is_today": True,
        "source_note": f"Synthetic {scenario.lower()} data for layout and logic testing only.",
    }
