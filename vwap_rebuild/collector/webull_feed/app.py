"""Executable service for the read-only Webull market-data collector.

It has exactly two public HTTP routes: `/healthz` and `/feed.json`.
The service binds to localhost by default; use a TLS reverse proxy for public access.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, Response, request, send_file

from .config import ConfigError, Settings
from .market_data import MarketDataError, WebullMarketData, make_feed

LOG = logging.getLogger(__name__)


class Collector:
    """Periodic, read-only collection with last-known-good feed retention."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.market_data = WebullMarketData(settings)
        self._lock = threading.Lock()
        self._last_feed: dict[str, Any] | None = None
        self._last_success_at: str | None = None

    def _write_atomically(self, payload: dict[str, Any]) -> None:
        target = self.settings.output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, temporary_name = tempfile.mkstemp(prefix=".feed-", suffix=".json", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def poll_once(self) -> dict[str, Any]:
        """Fetch a new feed. On failure publish a safe degraded status, never secrets."""
        try:
            bars = self.market_data.fetch_bars()
            feed = make_feed(self.settings, bars)
            self._last_success_at = datetime.now(tz=UTC).isoformat()
            LOG.info("Collected %s symbols; feed status=%s", len(bars), feed["status"])
        except MarketDataError as exc:
            # The adapter only emits safe messages; do not log raw response bodies.
            error = str(exc)
            LOG.warning("Market-data collection failed: %s", error)
            with self._lock:
                previous_symbols = (self._last_feed or {}).get("symbols", {})
            previous_bars = {
                symbol: list(item.get("bars", []))
                for symbol, item in previous_symbols.items()
                if isinstance(item, dict)
            }
            feed = make_feed(self.settings, previous_bars, error=error)
            feed["status"] = "stale" if previous_bars else "error"
        except Exception:
            # A client/library failure can be diagnosed from a local traceback without printing secrets.
            LOG.exception("Unexpected collector failure; no raw request or credential values were logged.")
            with self._lock:
                previous_symbols = (self._last_feed or {}).get("symbols", {})
            previous_bars = {
                symbol: list(item.get("bars", []))
                for symbol, item in previous_symbols.items()
                if isinstance(item, dict)
            }
            feed = make_feed(self.settings, previous_bars, error="Unexpected collector failure. Inspect the local service log.")
            feed["status"] = "stale" if previous_bars else "error"

        feed["last_success_at"] = self._last_success_at
        try:
            self._write_atomically(feed)
        except OSError:
            LOG.exception("Could not write the feed JSON; check WEBULL_OUTPUT_PATH permissions and free disk space.")
            raise
        with self._lock:
            self._last_feed = feed
        return feed

    def run_forever(self) -> None:
        """Run collection indefinitely. Designed to be supervised by systemd."""
        while True:
            self.poll_once()
            threading.Event().wait(self.settings.poll_seconds)


def create_app(settings: Settings, collector: Collector) -> Flask:
    app = Flask(__name__)

    def authorised() -> bool:
        expected = settings.feed_access_token
        return expected is None or request.headers.get("X-Feed-Token", "") == expected

    @app.get("/healthz")
    def healthz() -> Response:
        if not authorised():
            return Response("Not found.\n", status=404, mimetype="text/plain")
        with collector._lock:
            feed = collector._last_feed
        if feed is None:
            return Response("collector starting\n", status=503, mimetype="text/plain")
        if feed.get("status") == "error":
            return Response("collector error\n", status=503, mimetype="text/plain")
        return Response("ok\n", mimetype="text/plain")

    @app.get("/feed.json")
    def feed_json() -> Response:
        if not authorised():
            return Response("Not found.\n", status=404, mimetype="text/plain")
        path: Path = settings.output_path
        if not path.exists():
            return Response("Feed is not available yet.\n", status=503, mimetype="text/plain")
        response = send_file(path, mimetype="application/json", conditional=True, max_age=0)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    return app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Webull market-data JSON collector")
    parser.add_argument("--once", action="store_true", help="Fetch once, write JSON, and exit.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=os.getenv("WEBULL_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_environment()
    except ConfigError as exc:
        LOG.error("Collector configuration error: %s", exc)
        return 2

    collector = Collector(settings)
    if _parse_args().once:
        collector.poll_once()
        return 0

    # Fetch before serving so a healthy endpoint always has an initial file.
    collector.poll_once()
    worker = threading.Thread(target=collector.run_forever, name="market-data-poller", daemon=True)
    worker.start()
    app = create_app(settings, collector)
    LOG.info("Serving read-only feed on http://%s:%s/feed.json", settings.bind_host, settings.port)
    app.run(host=settings.bind_host, port=settings.port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
