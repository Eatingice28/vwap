"""Read-only market data client for Polygon.io (now Massive.com).

This module only ever performs HTTP GET requests for price history.
It cannot place orders and never talks to a brokerage.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

from . import config as cfg

BARS_COLUMNS = ["open", "high", "low", "close", "volume", "vwap"]


class MarketDataError(Exception):
    """Raised with a plain-English message the app can show the user."""


def empty_bars() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz=cfg.ET, name="timestamp")
    return pd.DataFrame(columns=BARS_COLUMNS, index=idx, dtype="float64")


def _parse_results(results: list[dict]) -> pd.DataFrame:
    if not results:
        return empty_bars()
    frame = pd.DataFrame(results)
    frame["timestamp"] = (
        pd.to_datetime(frame["t"], unit="ms", utc=True).dt.tz_convert(cfg.ET)
    )
    frame = frame.set_index("timestamp").sort_index()
    out = pd.DataFrame(index=frame.index)
    out["open"] = frame.get("o")
    out["high"] = frame.get("h")
    out["low"] = frame.get("l")
    out["close"] = frame.get("c")
    out["volume"] = frame.get("v", 0)
    out["vwap"] = frame.get("vw")
    return out.astype("float64")


def fetch_minute_bars(ticker: str, day: date, api_key: str,
                      base_url: str = cfg.POLYGON_BASE_URL,
                      timeout: int = 20) -> pd.DataFrame:
    """Fetch 1-minute bars for one ticker on one calendar day.

    Minute aggregates include premarket and after-hours bars.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise MarketDataError("Please enter a ticker symbol.")
    if not api_key:
        raise MarketDataError(
            "No API key found. Add polygon_api_key to your Streamlit secrets, "
            "or switch the sidebar to Demo mode."
        )

    url = f"{base_url}/v2/aggs/ticker/{ticker}/range/1/minute/{day}/{day}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": api_key}

    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise MarketDataError(
            "The data provider took too long to answer. Try again in a moment."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise MarketDataError(
            "Could not reach the data provider. Check your internet connection."
        ) from exc

    if response.status_code in (401, 403):
        raise MarketDataError(
            "The data provider rejected your API key. Check that "
            "polygon_api_key in Streamlit secrets is correct, and that your "
            "plan covers this data."
        )
    if response.status_code == 429:
        raise MarketDataError(
            "Rate limit reached. The free plan allows about 5 requests per "
            "minute and this dashboard uses 3 per refresh. Increase the "
            "refresh interval in the sidebar and wait a minute."
        )
    if response.status_code == 404:
        raise MarketDataError(
            f"'{ticker}' was not found. Check the spelling of the ticker."
        )
    if response.status_code >= 400:
        raise MarketDataError(
            f"The data provider returned an error (HTTP {response.status_code}). "
            "Try again shortly."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataError("The data provider sent an unreadable reply.") from exc

    if payload.get("status") == "ERROR":
        raise MarketDataError(
            payload.get("error") or "The data provider reported an error."
        )

    return _parse_results(payload.get("results") or [])


def load_session_bars(ticker: str, api_key: str, today: date,
                      base_url: str = cfg.POLYGON_BASE_URL,
                      max_lookback_days: int = 6) -> dict:
    """Get the most recent session that actually has bars.

    Weekends, holidays and delayed data plans mean today may be empty.
    Rather than showing an error, walk back a few days and clearly label
    which session is on screen.
    """
    day = today
    checked = 0
    while checked <= max_lookback_days:
        bars = fetch_minute_bars(ticker, day, api_key, base_url=base_url)
        if not bars.empty:
            return {"bars": bars, "session_date": day, "is_today": day == today}
        day -= timedelta(days=1)
        checked += 1

    raise MarketDataError(
        f"No price data came back for '{ticker.upper()}' in the last "
        f"{max_lookback_days} days. Check the ticker, or your plan may not "
        "include intraday data. Demo mode always works for testing."
    )


def resolve_base_url(use_massive_host: bool) -> str:
    return cfg.MASSIVE_BASE_URL if use_massive_host else cfg.POLYGON_BASE_URL


def format_price(value: Optional[float]) -> str:
    if value is None:
        return "--"
    return f"${value:,.2f}"


def format_pct(value: Optional[float]) -> str:
    if value is None:
        return "--"
    return f"{value * 100:+.2f}%"
