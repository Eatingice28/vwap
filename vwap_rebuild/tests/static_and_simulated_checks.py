"""Offline checks for the rebuild.

These checks deliberately do not connect to Webull, Polygon/Massive, a VPS, or
any external feed. SDK modules are stubbed solely to test feed normalization.
"""
from __future__ import annotations

import ast
import compileall
import importlib
import json
import sys
import tempfile
import types
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "collector"
DASHBOARD = ROOT / "dashboard"


def install_webull_import_stubs() -> None:
    """Provide import-only stand-ins; no SDK call is ever made in these tests."""
    names = [
        "webull", "webull.core", "webull.core.client", "webull.data", "webull.data.common",
        "webull.data.common.category", "webull.data.common.timespan", "webull.data.data_client",
    ]
    for name in names:
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["webull.core.client"].ApiClient = object
    sys.modules["webull.data.common.category"].Category = types.SimpleNamespace(US_STOCK=types.SimpleNamespace(name="US_STOCK"))
    sys.modules["webull.data.common.timespan"].Timespan = types.SimpleNamespace(M1=types.SimpleNamespace(name="M1"))
    sys.modules["webull.data.data_client"].DataClient = object


def assert_collector_has_no_trading_imports() -> None:
    for source in (COLLECTOR / "webull_feed").glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.lower() for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").lower()]
            else:
                continue
            forbidden = [name for name in names if "trade" in name or "order" in name]
            assert not forbidden, f"Forbidden trading import in {source}: {forbidden}"


def check_feed_shape() -> dict:
    sys.path.insert(0, str(COLLECTOR))
    install_webull_import_stubs()
    config = importlib.import_module("webull_feed.config")
    market_data = importlib.import_module("webull_feed.market_data")
    with tempfile.TemporaryDirectory() as temporary_directory:
        settings = config.Settings(
            app_key="test-key",
            app_secret="test-secret",
            region="us",
            endpoint="api.webull.com",
            watchlist=("NVDA", "SPY", "QQQ"),
            poll_seconds=20,
            history_bar_count=800,
            output_path=Path(temporary_directory) / "feed.json",
            bind_host="127.0.0.1",
            port=8088,
            feed_access_token="test-token",
        )
        bars = {
            symbol: [
                {"timestamp": "2026-08-14T08:00:00-04:00", "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5, "volume": 1200.0, "vwap": 100.3},
                {"timestamp": "2026-08-14T09:31:00-04:00", "open": 100.5, "high": 102.0, "low": 100.1, "close": 101.7, "volume": 2200.0, "vwap": 101.0},
            ]
            for symbol in settings.watchlist
        }
        feed = market_data.make_feed(settings, bars)
        serialised = json.loads(json.dumps(feed))
    assert serialised["schema_version"] == 1
    assert serialised["source"] == "webull_openapi_market_data"
    assert set(serialised["symbols"]) == {"NVDA", "SPY", "QQQ"}
    assert all(item["premarket_data_available"] for item in serialised["symbols"].values())
    assert "test-secret" not in json.dumps(serialised)
    assert "app_secret" not in json.dumps(serialised)
    return serialised


def check_dashboard_feed_adapter(feed: dict) -> None:
    sys.path.insert(0, str(DASHBOARD))
    source = importlib.import_module("vwap_dashboard.data_sources")

    class FakeResponse:
        status_code = 200

        def json(self):
            return feed

    original_get = source.requests.get
    source.requests.get = lambda *args, **kwargs: FakeResponse()
    try:
        sessions = source.load_webull_sessions("https://feed.example.com/feed.json", "test-token", ["NVDA", "SPY", "QQQ"])
    finally:
        source.requests.get = original_get
    assert set(sessions) == {"NVDA", "SPY", "QQQ"}
    assert all(len(session["bars"]) == 2 for session in sessions.values())


def check_demo_indicators() -> None:
    demo = importlib.import_module("vwap_dashboard.demo_data")
    indicators = importlib.import_module("vwap_dashboard.indicators")
    context = importlib.import_module("vwap_dashboard.context")
    bars = demo.generate_demo_bars("NVDA", "Bullish context", datetime(2026, 8, 14, 12, 0, tzinfo=UTC))
    frame = indicators.vwap_frame(bars, importlib.import_module("vwap_dashboard.config").PREMARKET_START_CHOICES["4:00 AM ET"])
    state = indicators.vwap_state(frame["bars"], frame["vwap"])
    levels = indicators.premarket_levels(bars, importlib.import_module("vwap_dashboard.config").PREMARKET_START_CHOICES["4:00 AM ET"])
    summary = context.build_summary("NVDA", state, indicators.range_state(state["price"], levels["high"], levels["low"]), indicators.range_state(state["price"], levels["high"], levels["low"]), "4:00 AM ET")
    assert not bars.empty
    assert not frame["bars"].empty
    assert state["vwap"] is not None
    assert levels["high"] is not None
    assert "instruction" not in summary["body"].lower()


def main() -> None:
    assert compileall.compile_dir(ROOT, quiet=1), "Python source did not compile."
    assert_collector_has_no_trading_imports()
    feed = check_feed_shape()
    check_dashboard_feed_adapter(feed)
    check_demo_indicators()
    print("PASS: compilation, no trading imports, simulated collector JSON contract, dashboard feed adapter, and Demo-mode indicators")


if __name__ == "__main__":
    main()
