"""Educational-only multi-ticker VWAP and premarket-context dashboard.

This dashboard reads price history or a sanitized collector feed. It has no
brokerage SDK, no Webull app credential, and no order-placement capability.
"""
from __future__ import annotations

import hmac
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from vwap_dashboard import config as cfg
from vwap_dashboard import context, data_sources, demo_data, indicators

st.set_page_config(page_title=cfg.APP_NAME, page_icon="📊", layout="wide", initial_sidebar_state="expanded")


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name.upper(), default)


def password_ok() -> bool:
    expected = get_secret("app_password")
    if not expected:
        st.session_state["password_notice"] = True
        return True
    if st.session_state.get("password_ok"):
        return True
    st.title(cfg.APP_NAME)
    st.caption(cfg.APP_TAGLINE)
    supplied = st.text_input("Dashboard password", type="password", label_visibility="collapsed", placeholder="Password")
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(supplied, expected):
            st.session_state["password_ok"] = True
            st.rerun()
        else:
            st.error("That password is not correct.")
    st.caption("This is a lightweight privacy lock. Do not store sensitive information in the dashboard.")
    return False


def parse_watchlist(raw: str) -> list[str]:
    symbols = list(dict.fromkeys(part.strip().upper() for part in raw.split(",") if part.strip()))
    invalid = [symbol for symbol in symbols if not symbol.replace(".", "").replace("-", "").isalnum()]
    if invalid:
        raise ValueError("Ticker symbols may contain only letters, digits, periods, hyphens, and commas.")
    main = [symbol for symbol in symbols if symbol not in cfg.INDEX_TICKERS]
    if not main:
        raise ValueError("Add at least one symbol other than SPY and QQQ to the watchlist.")
    if len(main) > 10:
        raise ValueError("This layout supports up to ten watched symbols at a time.")
    return main


def analyse(symbol: str, session: dict, premarket_start) -> dict:
    bars = session["bars"]
    frame = indicators.vwap_frame(bars, premarket_start)
    stock_state = indicators.vwap_state(frame["bars"], frame["vwap"])
    levels = indicators.premarket_levels(bars, premarket_start)
    price = stock_state["price"] if stock_state["price"] is not None else (float(bars["close"].iloc[-1]) if not bars.empty else None)
    return {
        "symbol": symbol,
        "bars": bars,
        "frame": frame,
        "vwap_state": stock_state,
        "levels": levels,
        "price": price,
        "range_state": indicators.range_state(price, levels["high"], levels["low"]),
        "change_pct": indicators.session_change_pct(bars),
        "session_date": session.get("session_date"),
        "is_today": session.get("is_today", False),
        "source_note": session.get("source_note"),
        "premarket_data_available": session.get("premarket_data_available", True),
    }


def tone_class(tone: str) -> str:
    return {"bullish": "positive", "bearish": "negative", "mixed": "mixed", "neutral": "neutral"}.get(tone, "neutral")


def inject_css() -> None:
    st.markdown("""
    <style>
      .context-card {border-radius: 14px; padding: 1rem 1.1rem; border: 1px solid #D6DCE5; margin-bottom: .8rem;}
      .context-card.positive {background: #EAF8EF; border-color: #79C78C;}
      .context-card.negative {background: #FFF0F0; border-color: #E99A9A;}
      .context-card.mixed {background: #FFF8E2; border-color: #E7C967;}
      .context-card.neutral {background: #F3F5F8; border-color: #B8C0CC;}
      .metric-note {color: #56616F; font-size: .86rem; min-height: 2.4rem;}
    </style>
    """, unsafe_allow_html=True)


def metric_card(item: dict) -> None:
    state = item["vwap_state"]
    with st.container(border=True):
        st.caption(f"{item['symbol']} — latest price")
        st.metric(item["symbol"], data_sources.format_price(item["price"]), data_sources.format_pct(item["change_pct"]))
        st.markdown(f"**{state.get('state') or 'No VWAP reading'}**")
        st.caption(f"VWAP {data_sources.format_price(state.get('vwap'))} · {item['frame']['session_label']}")
        if item["source_note"]:
            st.caption(item["source_note"])


def schedule_refresh(seconds: int) -> None:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=seconds * 1000, key="vwap_context_refresh")
    except Exception:
        st.caption(f"Refresh the page periodically; optional auto-refresh helper is unavailable (requested interval: {seconds}s).")


if not password_ok():
    st.stop()

inject_css()
with st.sidebar:
    st.header("Settings")
    raw_watchlist = st.text_input("Watchlist", value="NVDA,AMD", help="Use commas to separate watched symbols. SPY and QQQ are included automatically for shared context.")
    mode = st.radio("Data mode", ["Demo mode", "Live mode (Polygon/Massive)", "Live mode (Webull real-time)"], index=0)
    demo_scenario = "Neutral context"
    if mode == "Demo mode":
        demo_scenario = st.selectbox("Demo scenario", list(demo_data.SCENARIOS), index=3)
    premarket_label = st.selectbox("Premarket range begins", list(cfg.PREMARKET_START_CHOICES), index=0)
    refresh_seconds = st.slider("Auto-refresh interval (seconds)", cfg.MIN_REFRESH_SECONDS, cfg.MAX_REFRESH_SECONDS, cfg.DEFAULT_REFRESH_SECONDS, step=5)
    show_chart = st.toggle("Show selected-symbol chart", value=True)
    st.divider()
    st.caption("Demo mode uses made-up data. Live modes provide educational market context only and do not provide instructions or forecasts.")
    if mode == "Live mode (Polygon/Massive)":
        st.caption("Polygon/Massive mode makes one request per watched symbol plus SPY and QQQ. Longer intervals help with lower API limits.")
    if mode == "Live mode (Webull real-time)":
        st.caption("This dashboard receives only the collector's sanitized JSON feed. It never holds your Webull app credentials.")
    if st.button("Refresh now"):
        st.rerun()

try:
    main_symbols = parse_watchlist(raw_watchlist)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
all_symbols = main_symbols + list(cfg.INDEX_TICKERS)
premarket_start = cfg.PREMARKET_START_CHOICES[premarket_label]
now_et = datetime.now(cfg.ET)

try:
    if mode == "Demo mode":
        sessions = {symbol: demo_data.load_demo_session(symbol, demo_scenario, now_et) for symbol in all_symbols}
    elif mode == "Live mode (Polygon/Massive)":
        api_key = get_secret("polygon_api_key")
        use_massive = get_secret("use_massive_host", "false").strip().lower() in {"1", "true", "yes", "on"}
        sessions = {symbol: data_sources.load_polygon_session(symbol, api_key, use_massive, now_et.date()) for symbol in all_symbols}
    else:
        sessions = data_sources.load_webull_sessions(get_secret("webull_feed_url"), get_secret("webull_feed_token"), all_symbols)
except data_sources.DataSourceError as exc:
    st.title(cfg.APP_NAME)
    st.error(str(exc))
    st.info("Demo mode remains available for checking the dashboard layout and calculations without any external connection.")
    st.stop()

analysis = {symbol: analyse(symbol, session, premarket_start) for symbol, session in sessions.items()}
focus_symbol = main_symbols[0]
focus = analysis[focus_symbol]
spy = analysis["SPY"]
qqq = analysis["QQQ"]
summary = context.build_summary(focus_symbol, focus["vwap_state"], spy["range_state"], qqq["range_state"], premarket_label, focus["source_note"] or "")

st.title(cfg.APP_NAME)
st.caption(cfg.APP_TAGLINE)
st.caption(f"Mode: **{mode}** · Updated: {now_et.strftime('%Y-%m-%d %H:%M:%S ET')} · Focus: **{focus_symbol}**")
if st.session_state.get("password_notice"):
    st.warning("No app_password is configured, so anyone with the link can view this dashboard. Add one in Streamlit secrets if privacy is needed.")
if mode == "Demo mode":
    st.info(f"Demo mode is active. Every displayed price in this view is synthetic **{demo_scenario.lower()}** data.")
if not focus["is_today"]:
    st.warning(f"The focus symbol is showing its latest available session ({focus['session_date']}), not today.")
if not focus["premarket_data_available"]:
    st.warning("No premarket bars were supplied for the focus symbol. Premarket levels are unavailable; check the collector entitlement and session configuration.")

st.markdown(f"<div class='context-card {tone_class(summary['tone'])}'><strong>{summary['headline']}</strong><br>{summary['body']}</div>", unsafe_allow_html=True)

st.subheader("Watched-symbol VWAP context")
for start in range(0, len(main_symbols), 3):
    columns = st.columns(min(3, len(main_symbols) - start))
    for column, symbol in zip(columns, main_symbols[start:start + 3]):
        with column:
            metric_card(analysis[symbol])

st.subheader("Shared SPY and QQQ premarket context")
left, right = st.columns(2)
for column, item in ((left, spy), (right, qqq)):
    with column:
        with st.container(border=True):
            st.caption(f"{item['symbol']} — shared index context")
            st.metric(item["symbol"], data_sources.format_price(item["price"]))
            st.markdown(f"**{item['range_state'].get('state') or 'Premarket level unavailable'}**")
            st.caption(f"Premarket high {data_sources.format_price(item['levels']['high'])} · low {data_sources.format_price(item['levels']['low'])}")
            if item["source_note"]:
                st.caption(item["source_note"])

st.subheader(f"{focus_symbol} detail")
details = [
    ("Latest price", data_sources.format_price(focus["price"])),
    ("Intraday VWAP", data_sources.format_price(focus["vwap_state"].get("vwap"))),
    ("Distance from VWAP", data_sources.format_pct(focus["vwap_state"].get("distance_pct"))),
    ("Move since session start", data_sources.format_pct(focus["change_pct"])),
    ("Premarket high", data_sources.format_price(focus["levels"]["high"])),
    ("Premarket low", data_sources.format_price(focus["levels"]["low"])),
    ("VWAP state", focus["vwap_state"].get("state") or "--"),
    ("Premarket range state", focus["range_state"].get("state") or "--"),
]
st.dataframe(pd.DataFrame(details, columns=["Measure", "Reading"]), hide_index=True, use_container_width=True)

if show_chart:
    chart_bars = focus["frame"]["bars"]
    if chart_bars.empty:
        st.caption("There are not enough session bars to draw this chart.")
    else:
        st.subheader(f"{focus_symbol} price versus VWAP")
        st.line_chart(pd.DataFrame({"Price": chart_bars["close"], "VWAP": focus["frame"]["vwap"]}), use_container_width=True)
        st.caption(focus["frame"]["session_label"])

with st.expander("Definitions and limitations"):
    st.markdown("""
    **VWAP** is the cumulative average price in the selected session, weighted by each bar's volume. It resets each session.

    **Above VWAP**, **below VWAP**, **reclaiming VWAP**, and **rejecting VWAP** are descriptive labels based on the latest bars. **Watch area** means price is near VWAP and confirmation is needed. **Premarket high** and **premarket low** are the highest and lowest bar prices before the 9:30 AM ET regular-session open, measured from the selected start time.

    This dashboard is educational context only. It does not place, modify, or cancel trades; it does not provide forecasts; and it does not provide instructions for action.
    """)

schedule_refresh(refresh_seconds)
