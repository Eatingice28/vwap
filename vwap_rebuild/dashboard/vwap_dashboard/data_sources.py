"""Read-only dashboard data adapters.

The Webull adapter accepts only the collector's sanitized JSON feed. It never
imports a brokerage SDK and never receives Webull app credentials.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from . import config as cfg
from .indicators import empty_bars


class DataSourceError(RuntimeError):
    """A plain-English error suitable for showing in the dashboard."""


def format_price(value: float | None) -> str:
    return "--" if value is None else f"${value:,.2f}"


def format_pct(value: float | None) -> str:
    return "--" if value is None else f"{value * 100:+.2f}%"


def _bars_from_records(records: list[dict[str, Any]], timestamp_field: str = "timestamp") -> pd.DataFrame:
    if not records:
        return empty_bars()
    frame = pd.DataFrame(records)
    required = {timestamp_field, "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return empty_bars()
    frame["timestamp"] = pd.to_datetime(frame[timestamp_field], utc=True, errors="coerce").dt.tz_convert(cfg.ET)
    frame = frame.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
    output = pd.DataFrame(index=frame.index)
    for column in ("open", "high", "low", "close", "volume", "vwap"):
        output[column] = pd.to_numeric(frame[column], errors="coerce") if column in frame else float("nan")
    return output.dropna(subset=["open", "high", "low", "close", "volume"]).astype("float64")


def _parse_polygon_results(results: list[dict[str, Any]]) -> pd.DataFrame:
    records = [{
        "timestamp": item.get("t"), "open": item.get("o"), "high": item.get("h"), "low": item.get("l"),
        "close": item.get("c"), "volume": item.get("v", 0), "vwap": item.get("vw"),
    } for item in results]
    # Polygon timestamps are millisecond epoch values; convert them before shared parsing.
    for record in records:
        raw = record["timestamp"]
        if raw is not None:
            record["timestamp"] = datetime.fromtimestamp(float(raw) / 1000, tz=cfg.ET).astimezone(cfg.ET).isoformat()
    return _bars_from_records(records)


def _polygon_bars(symbol: str, day: date, api_key: str, base_url: str) -> pd.DataFrame:
    if not api_key.strip():
        raise DataSourceError("No Polygon/Massive API key is configured. Add polygon_api_key to Streamlit secrets or select Demo mode.")
    url = f"{base_url}/v2/aggs/ticker/{symbol}/range/1/minute/{day}/{day}"
    try:
        response = requests.get(url, params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": api_key}, timeout=20)
    except requests.Timeout as exc:
        raise DataSourceError("The Polygon/Massive request timed out. Try again shortly.") from exc
    except requests.RequestException as exc:
        raise DataSourceError("The dashboard could not reach Polygon/Massive. Check the network connection.") from exc
    if response.status_code == 401:
        raise DataSourceError("Polygon/Massive did not recognize the configured API key (HTTP 401).")
    if response.status_code == 403:
        raise DataSourceError(f"Your Polygon/Massive plan does not cover {symbol} for {day} (HTTP 403).")
    if response.status_code == 429:
        raise DataSourceError("Polygon/Massive rate limit reached (HTTP 429). Increase the refresh interval and try later.")
    if response.status_code == 404:
        raise DataSourceError(f"'{symbol}' was not found by Polygon/Massive.")
    if response.status_code >= 400:
        raise DataSourceError(f"Polygon/Massive returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise DataSourceError("Polygon/Massive returned an unreadable response.") from exc
    if str(payload.get("status", "")).upper() == "NOT_AUTHORIZED":
        raise DataSourceError(f"Your Polygon/Massive plan does not cover {symbol} for {day}.")
    return _parse_polygon_results(payload.get("results") or [])


def load_polygon_session(symbol: str, api_key: str, use_massive_host: bool, today: date) -> dict:
    """Fetch the latest usable session, preserving free-plan fallback behavior."""
    base_url = cfg.MASSIVE_BASE_URL if use_massive_host else cfg.POLYGON_BASE_URL
    blocked_days = 0
    last_error: DataSourceError | None = None
    for offset in range(7):
        day = today - timedelta(days=offset)
        try:
            bars = _polygon_bars(symbol, day, api_key, base_url)
        except DataSourceError as exc:
            last_error = exc
            if "HTTP 403" in str(exc) or "does not cover" in str(exc):
                blocked_days += 1
                continue
            raise
        if not bars.empty:
            return {"bars": bars, "session_date": day, "is_today": day == today, "source_note": None}
    if blocked_days:
        raise DataSourceError(f"No usable Polygon/Massive data was returned for {symbol} in the last seven days; the plan may not cover these sessions.")
    raise last_error or DataSourceError(f"No recent Polygon/Massive data was returned for {symbol}.")


def _parse_generated_at(feed: dict[str, Any]) -> datetime | None:
    raw = feed.get("generated_at")
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value if value.tzinfo else value.replace(tzinfo=cfg.ET)
    except ValueError:
        return None


def load_webull_feed(feed_url: str, feed_token: str, symbol: str, timeout_seconds: int = 15) -> dict:
    """Load one normalized symbol session from the collector's read-only HTTPS feed."""
    if not feed_url.strip():
        raise DataSourceError("No Webull collector URL is configured. Add webull_feed_url to Streamlit secrets or select Demo mode.")
    headers = {"X-Feed-Token": feed_token} if feed_token else {}
    try:
        response = requests.get(feed_url.strip(), headers=headers, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise DataSourceError("The Webull collector feed timed out. Check the collector and HTTPS proxy.") from exc
    except requests.RequestException as exc:
        raise DataSourceError("The dashboard could not reach the Webull collector feed. Check its URL and HTTPS proxy.") from exc
    if response.status_code in (401, 403, 404):
        raise DataSourceError("The Webull collector feed rejected this request. Check webull_feed_url and webull_feed_token.")
    if response.status_code >= 400:
        raise DataSourceError(f"The Webull collector feed returned HTTP {response.status_code}.")
    try:
        feed = response.json()
    except ValueError as exc:
        raise DataSourceError("The Webull collector feed returned unreadable JSON.") from exc
    if feed.get("schema_version") != 1 or not isinstance(feed.get("symbols"), dict):
        raise DataSourceError("The Webull collector feed has an unsupported format. Update dashboard and collector together.")
    item = feed["symbols"].get(symbol.upper())
    if not isinstance(item, dict):
        raise DataSourceError(f"The Webull collector is not watching {symbol.upper()}. Add it to WEBULL_WATCHLIST on the VPS.")
    bars = _bars_from_records(item.get("bars") if isinstance(item.get("bars"), list) else [])
    generated_at = _parse_generated_at(feed)
    note_parts = [part for part in (item.get("note"), feed.get("error")) if isinstance(part, str) and part]
    status = str(feed.get("status", "unknown"))
    if status in {"stale", "error"}:
        note_parts.insert(0, f"Collector status is {status}; prices may not be current.")
    if generated_at is not None:
        age_seconds = (datetime.now(generated_at.tzinfo) - generated_at).total_seconds()
        if age_seconds > 120:
            note_parts.insert(0, f"Collector feed is {int(age_seconds)} seconds old; it may be stale.")
    if bars.empty:
        message = "; ".join(note_parts) or f"The collector returned no usable bars for {symbol.upper()}."
        raise DataSourceError(message)
    session_date = bars.index[-1].date()
    return {
        "bars": bars,
        "session_date": session_date,
        "is_today": session_date == datetime.now(cfg.ET).date(),
        "source_note": " ".join(note_parts) or None,
        "feed_generated_at": generated_at.isoformat() if generated_at else None,
        "premarket_data_available": bool(item.get("premarket_data_available")),
    }


def load_webull_sessions(feed_url: str, feed_token: str, symbols: list[str], timeout_seconds: int = 15) -> dict[str, dict]:
    """Load every requested symbol from one collector feed request."""
    if not feed_url.strip():
        raise DataSourceError("No Webull collector URL is configured. Add webull_feed_url to Streamlit secrets or select Demo mode.")
    headers = {"X-Feed-Token": feed_token} if feed_token else {}
    try:
        response = requests.get(feed_url.strip(), headers=headers, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise DataSourceError("The Webull collector feed timed out. Check the collector and HTTPS proxy.") from exc
    except requests.RequestException as exc:
        raise DataSourceError("The dashboard could not reach the Webull collector feed. Check its URL and HTTPS proxy.") from exc
    if response.status_code in (401, 403, 404):
        raise DataSourceError("The Webull collector feed rejected this request. Check webull_feed_url and webull_feed_token.")
    if response.status_code >= 400:
        raise DataSourceError(f"The Webull collector feed returned HTTP {response.status_code}.")
    try:
        feed = response.json()
    except ValueError as exc:
        raise DataSourceError("The Webull collector feed returned unreadable JSON.") from exc
    if feed.get("schema_version") != 1 or not isinstance(feed.get("symbols"), dict):
        raise DataSourceError("The Webull collector feed has an unsupported format. Update dashboard and collector together.")

    generated_at = _parse_generated_at(feed)
    general_notes: list[str] = []
    status = str(feed.get("status", "unknown"))
    if status in {"stale", "error"}:
        general_notes.append(f"Collector status is {status}; prices may not be current.")
    if isinstance(feed.get("error"), str) and feed["error"]:
        general_notes.append(feed["error"])
    if generated_at is not None:
        age_seconds = (datetime.now(generated_at.tzinfo) - generated_at).total_seconds()
        if age_seconds > 120:
            general_notes.append(f"Collector feed is {int(age_seconds)} seconds old; it may be stale.")

    sessions: dict[str, dict] = {}
    unavailable: list[str] = []
    for requested_symbol in symbols:
        symbol = requested_symbol.upper()
        item = feed["symbols"].get(symbol)
        if not isinstance(item, dict):
            unavailable.append(symbol)
            continue
        bars = _bars_from_records(item.get("bars") if isinstance(item.get("bars"), list) else [])
        notes = list(general_notes)
        if isinstance(item.get("note"), str) and item["note"]:
            notes.append(item["note"])
        if bars.empty:
            unavailable.append(symbol)
            continue
        session_date = bars.index[-1].date()
        sessions[symbol] = {
            "bars": bars,
            "session_date": session_date,
            "is_today": session_date == datetime.now(cfg.ET).date(),
            "source_note": " ".join(notes) or None,
            "feed_generated_at": generated_at.isoformat() if generated_at else None,
            "premarket_data_available": bool(item.get("premarket_data_available")),
        }
    if unavailable:
        missing = ", ".join(unavailable)
        raise DataSourceError(f"The Webull collector returned no usable bars for: {missing}. Add missing symbols to WEBULL_WATCHLIST or check the collector entitlement.")
    return sessions
