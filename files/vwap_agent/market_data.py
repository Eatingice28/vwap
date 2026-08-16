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


class AuthError(MarketDataError):
    """The key itself is missing, wrong or malformed (HTTP 401)."""


class EntitlementError(MarketDataError):
    """The key is valid but the plan does not cover this data (HTTP 403).

    On free plans this is normal for the current day, so the caller can
    keep looking at earlier sessions instead of giving up.
    """


class RateLimitError(MarketDataError):
    """Too many requests in the last minute (HTTP 429)."""


def empty_bars() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz=cfg.ET, name="timestamp")
    return pd.DataFrame(columns=BARS_COLUMNS, index=idx, dtype="float64")


def mask_key(api_key: str) -> str:
    """Describe a key without revealing it, for the diagnostics panel."""
    key = (api_key or "").strip()
    if not key:
        return "not set"
    if len(key) <= 8:
        return f"{len(key)} characters (looks too short)"
    return f"{len(key)} characters, starts {key[:4]}, ends {key[-4:]}"


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
    if not str(api_key).strip():
        raise AuthError(
            "No API key found. Add polygon_api_key to your Streamlit secrets, "
            "or switch the sidebar to Demo mode."
        )

    url = f"{base_url}/v2/aggs/ticker/{ticker}/range/1/minute/{day}/{day}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000,
              "apiKey": str(api_key).strip()}

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

    if response.status_code == 401:
        raise AuthError(
            "The data provider did not recognise your API key (HTTP 401). "
            "Copy the key again from your dashboard and update "
            "polygon_api_key in Streamlit secrets."
        )
    if response.status_code == 403:
        raise EntitlementError(
            f"Your plan does not cover {ticker} data for {day} (HTTP 403). "
            "On free plans this is normal for today's data."
        )
    if response.status_code == 429:
        raise RateLimitError(
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

    status = str(payload.get("status", "")).upper()
    if status == "NOT_AUTHORIZED":
        raise EntitlementError(
            f"Your plan does not cover {ticker} data for {day}. "
            "On free plans this is normal for today's data."
        )
    if status == "ERROR":
        message = str(payload.get("error") or "")
        if "not entitled" in message.lower() or "upgrade" in message.lower():
            raise EntitlementError(message)
        raise MarketDataError(message or "The data provider reported an error.")

    return _parse_results(payload.get("results") or [])


def load_session_bars(ticker: str, api_key: str, today: date,
                      base_url: str = cfg.POLYGON_BASE_URL,
                      max_lookback_days: int = 6) -> dict:
    """Get the most recent session that actually has bars.

    Weekends, holidays and delayed-data plans all mean today may be
    unavailable. A 401 is fatal because the key is wrong, but an empty
    day or a 403 just means "look further back", which is exactly what
    a free plan does with recent dates.
    """
    day = today
    attempts: list[str] = []
    blocked_days = 0

    for _ in range(max_lookback_days + 1):
        try:
            bars = fetch_minute_bars(ticker, day, api_key, base_url=base_url)
        except EntitlementError:
            attempts.append(f"{day}: not covered by your plan")
            blocked_days += 1
            day -= timedelta(days=1)
            continue

        if not bars.empty:
            attempts.append(f"{day}: {len(bars)} bars")
            return {
                "bars": bars,
                "session_date": day,
                "is_today": day == today,
                "attempts": attempts,
            }

        attempts.append(f"{day}: no data")
        day -= timedelta(days=1)

    if blocked_days:
        raise EntitlementError(
            f"Your plan did not allow any of the last {max_lookback_days} "
            f"days of {ticker.upper()} minute data. Free plans usually cover "
            "older sessions only. Check what your plan includes, or use "
            "Demo mode."
        )

    raise MarketDataError(
        f"No price data came back for '{ticker.upper()}' in the last "
        f"{max_lookback_days} days. Check the ticker spelling. "
        "Demo mode always works for testing."
    )


def connection_test(ticker: str, api_key: str, today: date,
                    base_url: str = cfg.POLYGON_BASE_URL,
                    days: int = 5) -> list[dict]:
    """Try several days one at a time and report what happened to each.

    Used by the sidebar's connection test so problems are visible
    instead of hidden behind one generic error.
    """
    results = []
    day = today
    for _ in range(days):
        entry = {"date": str(day)}
        try:
            bars = fetch_minute_bars(ticker, day, api_key, base_url=base_url)
            entry["result"] = f"{len(bars)} bars" if len(bars) else "no data"
            entry["ok"] = bool(len(bars))
        except MarketDataError as exc:
            entry["result"] = str(exc)
            entry["ok"] = False
        results.append(entry)
        day -= timedelta(days=1)
    return results


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
