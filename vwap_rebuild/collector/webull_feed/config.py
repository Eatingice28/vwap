"""Configuration for the read-only Webull market-data collector.

Credentials are deliberately read only from environment variables on the VPS.
This module never writes, prints, or returns the app secret.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


class ConfigError(ValueError):
    """Raised when a required non-secret configuration value is invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required. Add it to the collector environment file.")
    return value


def _positive_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number.") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _csv_symbols(raw: str) -> Tuple[str, ...]:
    symbols = tuple(dict.fromkeys(item.strip().upper() for item in raw.split(",") if item.strip()))
    if not symbols:
        raise ConfigError("WEBULL_WATCHLIST must contain at least one ticker symbol.")
    if len(symbols) > 100:
        raise ConfigError("WEBULL_WATCHLIST supports at most 100 symbols per collector instance.")
    if any(not symbol.replace(".", "").replace("-", "").isalnum() for symbol in symbols):
        raise ConfigError("WEBULL_WATCHLIST may contain only letters, digits, periods, hyphens, and commas.")
    return symbols


@dataclass(frozen=True)
class Settings:
    """Runtime settings for a collector that only retrieves market data."""

    app_key: str
    app_secret: str
    region: str
    endpoint: str
    watchlist: Tuple[str, ...]
    poll_seconds: int
    history_bar_count: int
    output_path: Path
    bind_host: str
    port: int
    feed_access_token: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            app_key=_required("WEBULL_APP_KEY"),
            app_secret=_required("WEBULL_APP_SECRET"),
            region=os.getenv("WEBULL_REGION", "us").strip() or "us",
            endpoint=os.getenv("WEBULL_API_ENDPOINT", "api.webull.com").strip() or "api.webull.com",
            watchlist=_csv_symbols(os.getenv("WEBULL_WATCHLIST", "NVDA,SPY,QQQ")),
            poll_seconds=_positive_int("WEBULL_POLL_SECONDS", 20, 10, 300),
            history_bar_count=_positive_int("WEBULL_HISTORY_BAR_COUNT", 800, 50, 1200),
            output_path=Path(os.getenv("WEBULL_OUTPUT_PATH", "/var/lib/webull-feed/feed.json")).expanduser(),
            bind_host=os.getenv("WEBULL_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_positive_int("WEBULL_PORT", 8088, 1, 65535),
            feed_access_token=os.getenv("WEBULL_FEED_ACCESS_TOKEN", "").strip() or None,
        )

    def public_config(self) -> dict:
        """Return diagnostics that are safe to include in the feed/status endpoint."""
        return {
            "region": self.region,
            "endpoint": self.endpoint,
            "watchlist": list(self.watchlist),
            "poll_seconds": self.poll_seconds,
            "history_bar_count": self.history_bar_count,
        }
