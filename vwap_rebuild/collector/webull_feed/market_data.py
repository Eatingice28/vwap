"""Read-only Webull market-data access and JSON feed normalization.

This module intentionally imports no order, account, portfolio, or trading client.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from webull.core.client import ApiClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from webull.data.data_client import DataClient

from .config import Settings

LOG = logging.getLogger(__name__)
EASTERN = ZoneInfo("America/New_York")


class MarketDataError(RuntimeError):
    """A safe, non-secret description of a market-data problem."""


def _coerce_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_field(source: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in source and source[name] is not None:
            return source[name]
    return None


def _timestamp_to_eastern(value: Any) -> str | None:
    """Normalize a provider timestamp to an offset-aware ISO 8601 ET string."""
    if value is None:
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        raw = float(value)
        # The Webull HTTP API uses millisecond timestamps; also tolerate seconds.
        if raw > 10_000_000_000:
            raw /= 1000
        return datetime.fromtimestamp(raw, tz=UTC).astimezone(EASTERN).isoformat()
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=EASTERN)
        return parsed.astimezone(EASTERN).isoformat()
    return None


def _normalise_bar(raw: dict[str, Any]) -> dict[str, float | str | None] | None:
    timestamp = _timestamp_to_eastern(_read_field(raw, "timestamp", "time", "ts", "t"))
    open_ = _coerce_number(_read_field(raw, "open", "o"))
    high = _coerce_number(_read_field(raw, "high", "h"))
    low = _coerce_number(_read_field(raw, "low", "l"))
    close = _coerce_number(_read_field(raw, "close", "c"))
    volume = _coerce_number(_read_field(raw, "volume", "v"))
    vwap = _coerce_number(_read_field(raw, "vwap", "vw"))
    if timestamp is None or any(value is None for value in (open_, high, low, close, volume)):
        return None
    return {
        "timestamp": timestamp,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "vwap": vwap,
    }


def _find_records(payload: Any, symbol: str) -> list[dict[str, Any]]:
    """Accept common documented/observed response layouts without exposing raw payloads."""
    if not isinstance(payload, dict):
        return []
    containers: list[Any] = [payload, payload.get("data"), payload.get("result")]
    symbol_upper = symbol.upper()
    for container in containers:
        if isinstance(container, dict):
            direct = container.get(symbol) or container.get(symbol_upper)
            if isinstance(direct, list):
                return [row for row in direct if isinstance(row, dict)]
            for key in ("bars", "items", "list", "data"):
                candidate = container.get(key)
                if isinstance(candidate, list):
                    rows = [row for row in candidate if isinstance(row, dict)]
                    tagged = [row for row in rows if str(_read_field(row, "symbol", "ticker", "s") or "").upper() == symbol_upper]
                    return tagged or rows
        elif isinstance(container, list):
            rows = [row for row in container if isinstance(row, dict)]
            tagged = [row for row in rows if str(_read_field(row, "symbol", "ticker", "s") or "").upper() == symbol_upper]
            return tagged or rows
    return []


def _safe_http_error(response: Any) -> MarketDataError:
    status = getattr(response, "status_code", "unknown")
    if status == 401:
        return MarketDataError("Webull authentication failed (HTTP 401). Check the app key, app secret, region, and API endpoint.")
    if status == 403:
        return MarketDataError("Webull denied market-data access (HTTP 403). Check the market-data entitlement and extended-hours permission.")
    if status == 429:
        return MarketDataError("Webull rate limit reached (HTTP 429). Increase the poll interval or reduce the watchlist.")
    return MarketDataError(f"Webull market-data request failed (HTTP {status}). Check the service logs and configuration.")


class WebullMarketData:
    """A narrow adapter exposing only the Webull market-data API needed here."""

    def __init__(self, settings: Settings):
        api_client = ApiClient(settings.app_key, settings.app_secret, settings.region)
        api_client.add_endpoint(settings.region, settings.endpoint)
        self._client = DataClient(api_client)
        self._settings = settings

    def fetch_bars(self) -> dict[str, list[dict[str, float | str | None]]]:
        """Fetch recent 1-minute PRE/RTH bars for all configured symbols."""
        response = self._client.market_data.get_batch_history_bar(
            list(self._settings.watchlist),
            Category.US_STOCK.name,
            Timespan.M1.name,
            count=str(self._settings.history_bar_count),
            real_time_required=True,
            trading_sessions=["PRE", "RTH"],
        )
        if getattr(response, "status_code", None) != 200:
            raise _safe_http_error(response)
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MarketDataError("Webull returned an unreadable market-data response.") from exc

        output: dict[str, list[dict[str, float | str | None]]] = {}
        for symbol in self._settings.watchlist:
            bars = [_normalise_bar(row) for row in _find_records(payload, symbol)]
            clean = [bar for bar in bars if bar is not None]
            clean.sort(key=lambda bar: str(bar["timestamp"]))
            output[symbol] = clean
        return output


def has_premarket_bar(bars: Iterable[dict[str, Any]]) -> bool:
    for bar in bars:
        raw = bar.get("timestamp")
        if not isinstance(raw, str):
            continue
        try:
            stamp = datetime.fromisoformat(raw).astimezone(EASTERN)
        except ValueError:
            continue
        if (stamp.hour, stamp.minute) >= (4, 0) and (stamp.hour, stamp.minute) < (9, 30):
            return True
    return False


def make_feed(settings: Settings, bars_by_symbol: dict[str, list[dict[str, Any]]], error: str | None = None) -> dict[str, Any]:
    """Create the stable, credential-free JSON document consumed by the dashboard."""
    now = datetime.now(tz=UTC).isoformat()
    symbols: dict[str, Any] = {}
    for symbol in settings.watchlist:
        bars = bars_by_symbol.get(symbol, [])
        premarket_available = has_premarket_bar(bars)
        note = None
        if not bars:
            note = "No 1-minute bars were returned for this symbol."
        elif not premarket_available:
            note = "No premarket bars were returned. Extended-hours data may be unavailable for this entitlement or session."
        symbols[symbol] = {
            "symbol": symbol,
            "status": "ok" if bars else "no_data",
            "note": note,
            "bar_count": len(bars),
            "latest_bar_timestamp": bars[-1]["timestamp"] if bars else None,
            "premarket_data_available": premarket_available,
            "bars": bars,
        }
    return {
        "schema_version": 1,
        "source": "webull_openapi_market_data",
        "generated_at": now,
        "status": "error" if error else ("degraded" if any(not item["bars"] for item in symbols.values()) else "ok"),
        "error": error,
        "config": settings.public_config(),
        "symbols": symbols,
    }
