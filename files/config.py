"""Central settings for the VWAP Market Context Agent.

Nothing here places trades or talks to a broker. This file only holds
constants used for reading market data and describing context.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

APP_NAME = "VWAP Market Context Agent"
APP_TAGLINE = "Educational market context only - no trade signals, no order placement."

# All market logic runs in US Eastern Time, regardless of where you are.
ET = ZoneInfo("America/New_York")

# Index tickers used for broad-market context.
INDEX_TICKERS = ("SPY", "QQQ")

# Premarket start options shown in the sidebar.
PREMARKET_START_CHOICES = {
    "4:00 AM ET (full premarket)": (4, 0),
    "7:00 AM ET (late premarket)": (7, 0),
}

PREMARKET_END = (9, 30)
MARKET_OPEN = (9, 30)
MARKET_CLOSE = (16, 0)

# API endpoints. Polygon.io rebranded to Massive.com in Oct 2025.
# Both hosts accept the same API key.
POLYGON_BASE_URL = "https://api.polygon.io"
MASSIVE_BASE_URL = "https://api.massive.com"

# --- Colour scheme -------------------------------------------------------
GREEN = "#15803d"
RED = "#b91c1c"
YELLOW = "#a16207"
GRAY = "#4b5563"

GREEN_BG = "#dcfce7"
RED_BG = "#fee2e2"
YELLOW_BG = "#fef9c3"
GRAY_BG = "#f3f4f6"

TONE_COLORS = {
    "bullish": (GREEN, GREEN_BG),
    "bearish": (RED, RED_BG),
    "mixed": (YELLOW, YELLOW_BG),
    "neutral": (GRAY, GRAY_BG),
}

# --- VWAP state labels ---------------------------------------------------
ABOVE_VWAP = "Above VWAP"
BELOW_VWAP = "Below VWAP"
RECLAIMING_VWAP = "Reclaiming VWAP"
REJECTING_VWAP = "Rejecting VWAP"
AT_VWAP = "At VWAP (watch area)"

VWAP_TONES = {
    ABOVE_VWAP: "bullish",
    RECLAIMING_VWAP: "bullish",
    BELOW_VWAP: "bearish",
    REJECTING_VWAP: "bearish",
    AT_VWAP: "neutral",
}

# --- Premarket range state labels ---------------------------------------
ABOVE_PM_HIGH = "Above premarket high"
BELOW_PM_LOW = "Below premarket low"
INSIDE_PM_RANGE = "Inside premarket range"

RANGE_TONES = {
    ABOVE_PM_HIGH: "bullish",
    BELOW_PM_LOW: "bearish",
    INSIDE_PM_RANGE: "neutral",
}

# How close to VWAP counts as "at VWAP" instead of above/below (0.10%).
VWAP_NEUTRAL_BAND_PCT = 0.0010

# How many recent minutes to look back when deciding reclaim vs reject.
CROSS_LOOKBACK_BARS = 10

# Refresh interval bounds (seconds) shown in the sidebar.
MIN_REFRESH_SECONDS = 30
MAX_REFRESH_SECONDS = 60
DEFAULT_REFRESH_SECONDS = 45
