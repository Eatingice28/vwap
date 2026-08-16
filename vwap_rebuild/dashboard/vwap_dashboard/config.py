"""Dashboard constants. All timing is evaluated in US Eastern time."""
from __future__ import annotations

from datetime import time as dtime
from zoneinfo import ZoneInfo

APP_NAME = "VWAP & Premarket Context"
APP_TAGLINE = "Educational market context only — never trading instructions"
ET = ZoneInfo("America/New_York")
INDEX_TICKERS = ("SPY", "QQQ")
MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
PREMARKET_END = dtime(9, 30)
PREMARKET_START_CHOICES = {
    "4:00 AM ET": dtime(4, 0),
    "7:00 AM ET": dtime(7, 0),
    "8:00 AM ET": dtime(8, 0),
}
VWAP_NEUTRAL_BAND_PCT = 0.0008
CROSS_LOOKBACK_BARS = 8
MIN_REFRESH_SECONDS = 15
MAX_REFRESH_SECONDS = 300
DEFAULT_REFRESH_SECONDS = 30
POLYGON_BASE_URL = "https://api.polygon.io"
MASSIVE_BASE_URL = "https://api.massive.com"

ABOVE_VWAP = "Above VWAP"
BELOW_VWAP = "Below VWAP"
RECLAIMING_VWAP = "Reclaiming VWAP"
REJECTING_VWAP = "Rejecting VWAP"
AT_VWAP = "At VWAP — watch area"
ABOVE_PM_HIGH = "Above premarket high"
BELOW_PM_LOW = "Below premarket low"
INSIDE_PM_RANGE = "Inside premarket range"

VWAP_TONES = {
    ABOVE_VWAP: "bullish",
    BELOW_VWAP: "bearish",
    RECLAIMING_VWAP: "bullish",
    REJECTING_VWAP: "bearish",
    AT_VWAP: "neutral",
}
RANGE_TONES = {
    ABOVE_PM_HIGH: "bullish",
    BELOW_PM_LOW: "bearish",
    INSIDE_PM_RANGE: "neutral",
}
