"""VWAP Market Context Agent - a read-only market context dashboard.

Safety notes, on purpose and by design:
  * This app never places a trade.
  * This app never connects to a brokerage.
  * This app never tells you to buy or sell anything.
It reads price history, works out VWAP and premarket levels, and describes
the resulting context in plain English for educational use only.
"""

from __future__ import annotations

import hmac
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from vwap_agent import config as cfg
from vwap_agent import context as ctx
from vwap_agent import demo_data, indicators, market_data, ui

# --------------------------------------------------------------- page setup
st.set_page_config(
    page_title=cfg.APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)


# ------------------------------------------------------------------ secrets
def get_secret(name: str, default=None):
    """Read a value from Streamlit secrets, then environment variables."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name.upper(), default)


# ----------------------------------------------------------- password gate
def check_password() -> bool:
    """Show a simple password screen. Returns True once unlocked."""
    expected = get_secret("app_password")

    if not expected:
        # No password configured: allow access, but say so clearly.
        st.session_state["no_password_set"] = True
        return True

    if st.session_state.get("password_ok"):
        return True

    st.title(cfg.APP_NAME)
    st.caption(cfg.APP_TAGLINE)
    st.subheader("Enter password")

    entered = st.text_input("Password", type="password",
                            label_visibility="collapsed",
                            placeholder="Password")
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(str(entered), str(expected)):
            st.session_state["password_ok"] = True
            st.rerun()
        else:
            st.error("That password is not correct. Please try again.")
    st.caption(
        "This is a light lock to keep the page private, not bank-grade "
        "security. Do not put sensitive information in this app."
    )
    return False


if not check_password():
    st.stop()


# ----------------------------------------------------------------- sidebar
ui.inject_css()

with st.sidebar:
    st.header("Settings")

    ticker = st.text_input(
        "Ticker you are watching", value="NVDA",
        help="Examples: NVDA, TSLA, AAPL, AMD",
    ).strip().upper()

    mode = st.radio(
        "Data mode", ["Demo mode", "Live mode"], index=0,
        help="Demo mode uses built-in sample data and needs no API key.",
    )
    demo = mode == "Demo mode"

    demo_scenario = "Mixed"
    if demo:
        demo_scenario = st.selectbox(
            "Demo scenario", list(demo_data.SCENARIOS), index=2,
            help="Try each one to see how the colours and wording change.",
        )

    premarket_label = st.selectbox(
        "Premarket window starts at", list(cfg.PREMARKET_START_CHOICES.keys()),
        index=0,
    )
    premarket_start = cfg.PREMARKET_START_CHOICES[premarket_label]

    refresh_seconds = st.slider(
        "Auto-refresh every (seconds)",
        min_value=cfg.MIN_REFRESH_SECONDS,
        max_value=cfg.MAX_REFRESH_SECONDS,
        value=cfg.DEFAULT_REFRESH_SECONDS,
        step=5,
    )

    alerts_on = st.toggle(
        "Show change alerts", value=True,
        help="Highlights when a VWAP or premarket-range state changes.",
    )

    show_chart = st.toggle("Show price vs VWAP chart", value=True)

    st.divider()
    st.caption(
        "Free data plans allow about 5 requests per minute. This dashboard "
        "uses 3 per refresh, so keep the interval at 45-60 seconds if you "
        "are on the free plan."
    )
    if st.button("Refresh now"):
        st.rerun()

    with st.expander("Connection test"):
        st.caption(
            "Checks your API key against the last few days, one day at a "
            "time, and shows exactly what the data provider said."
        )
        if st.button("Run connection test"):
            st.session_state["run_conn_test"] = True

if st.session_state.pop("run_conn_test", False):
    st.subheader("Connection test")
    test_key = str(get_secret("polygon_api_key", "") or "")
    test_base = market_data.resolve_base_url(bool(get_secret("use_massive_host", False)))
    st.write(f"**Key in secrets:** {market_data.mask_key(test_key)}")
    st.write(f"**Endpoint:** {test_base}")
    if not test_key:
        st.error("No polygon_api_key found in Streamlit secrets.")
    else:
        with st.spinner("Testing..."):
            rows = market_data.connection_test(
                ticker or "AAPL", test_key, datetime.now(cfg.ET).date(),
                base_url=test_base,
            )
        st.dataframe(
            pd.DataFrame(rows)[["date", "result"]],
            hide_index=True, width="stretch",
        )
        if any(row["ok"] for row in rows):
            st.success(
                "Your key works. Any day marked 'not covered by your plan' "
                "is normal on a free plan - the app will use the most recent "
                "day that does work."
            )
        else:
            st.error("No day returned data. See the messages above.")
    st.divider()

if not ticker:
    st.warning("Enter a ticker in the sidebar to begin.")
    st.stop()


# ------------------------------------------------------------- data loading
@st.cache_data(ttl=600, show_spinner=False)
def load_live(symbol: str, day_str: str, cache_bucket: int, api_key: str,
              base_url: str) -> dict:
    """Cached live fetch. cache_bucket changes once per refresh interval."""
    day = datetime.strptime(day_str, "%Y-%m-%d").date()
    return market_data.load_session_bars(symbol, api_key, day, base_url=base_url)


now_et = datetime.now(cfg.ET)
cache_bucket = int(time.time() // max(refresh_seconds, 15))
symbols = [ticker, "SPY", "QQQ"]

sessions: dict[str, dict] = {}
load_error = None

if demo:
    for symbol in symbols:
        sessions[symbol] = demo_data.load_demo_session(
            symbol, demo_scenario, now_et, is_index=symbol in cfg.INDEX_TICKERS
        )
else:
    api_key = get_secret("polygon_api_key", "")
    use_massive = bool(get_secret("use_massive_host", False))
    base_url = market_data.resolve_base_url(use_massive)
    try:
        for symbol in symbols:
            sessions[symbol] = load_live(
                symbol, now_et.date().isoformat(), cache_bucket,
                str(api_key), base_url,
            )
    except market_data.MarketDataError as exc:
        load_error = str(exc)
        st.session_state["last_error_kind"] = type(exc).__name__

if load_error:
    st.title(cfg.APP_NAME)
    st.error(load_error)
    st.info(
        "Switch the sidebar to **Demo mode** to keep using the dashboard "
        "while you sort the data connection out."
    )
    st.stop()


# --------------------------------------------------------------- indicators
def analyse(symbol: str) -> dict:
    session = sessions[symbol]
    bars = session["bars"]
    frame = indicators.vwap_frame(bars, premarket_start)
    state = indicators.vwap_state(frame["bars"], frame["vwap"])
    levels = indicators.premarket_levels(bars, premarket_start)
    price = state["price"] if state["price"] is not None else indicators.last_price(bars)
    return {
        "symbol": symbol,
        "bars": bars,
        "frame": frame,
        "vwap_state": state,
        "levels": levels,
        "price": price,
        "range_state": indicators.range_state(price, levels["high"], levels["low"]),
        "change_pct": indicators.session_change_pct(bars),
        "session_date": session["session_date"],
        "is_today": session["is_today"],
    }


main = analyse(ticker)
spy = analyse("SPY")
qqq = analyse("QQQ")

session_note = ""
if not main["is_today"]:
    session_note = (
        f"Showing the last available session ({main['session_date']}), not "
        "today - your data plan or the market calendar did not return "
        "today's bars."
    )

summary = ctx.build_summary(
    ticker,
    main["vwap_state"],
    spy["range_state"],
    qqq["range_state"],
    premarket_label,
    session_note,
)


# ------------------------------------------------------------------ alerts
current_states = {
    "stock_state": main["vwap_state"]["state"],
    "spy_state": spy["range_state"]["state"],
    "qqq_state": qqq["range_state"]["state"],
    "tone": summary["tone"],
}
alert_key = f"prev_states::{ticker}::{'demo' if demo else 'live'}"
previous_states = st.session_state.get(alert_key, {})
new_events = ctx.build_alerts(ticker, previous_states, current_states)
st.session_state[alert_key] = current_states

if alerts_on and new_events:
    log = st.session_state.get("alert_log", [])
    stamp = now_et.strftime("%H:%M:%S ET")
    log = [f"{stamp} - {event}" for event in new_events] + log
    st.session_state["alert_log"] = log[:12]


# ------------------------------------------------------------------ header
st.title(cfg.APP_NAME)
st.caption(cfg.APP_TAGLINE)

top_left, top_right = st.columns([3, 2])
with top_left:
    mode_label = "Demo data" if demo else "Live data"
    st.markdown(
        f"**{ticker}** &nbsp;·&nbsp; {mode_label} &nbsp;·&nbsp; "
        f"session {main['session_date']} &nbsp;·&nbsp; "
        f"updated {now_et.strftime('%H:%M:%S')} ET"
    )
with top_right:
    ui.legend()

if st.session_state.get("no_password_set"):
    st.warning(
        "No password is set, so anyone with the link can open this "
        "dashboard. Add app_password to your Streamlit secrets to lock it."
    )

if demo:
    st.info(
        f"Demo mode is on - these are made-up '{demo_scenario}' prices for "
        "testing the layout. Switch to Live mode in the sidebar for real data."
    )
if session_note:
    st.warning(session_note)

ui.summary_card(summary["headline"], summary["body"], summary["tone"])


# ------------------------------------------------------------------- cards
def index_detail(item: dict) -> str:
    return (
        f"Premarket high {ui.format_level(item['levels']['high'])}<br>"
        f"Premarket low {ui.format_level(item['levels']['low'])}"
    )


stock_state = main["vwap_state"]
stock_detail = (
    f"VWAP {ui.format_level(stock_state.get('vwap'))}<br>"
    f"{main['frame']['session_label']}"
)

ui.status_cards([
    {
        "label": f"{ticker} price",
        "value": market_data.format_price(main["price"]),
        "state": stock_state.get("state") or "No data yet",
        "detail": stock_detail,
        "tone": stock_state.get("tone", "neutral"),
    },
    {
        "label": "SPY vs premarket range",
        "value": market_data.format_price(spy["price"]),
        "state": spy["range_state"].get("state") or "No premarket data",
        "detail": index_detail(spy),
        "tone": spy["range_state"].get("tone", "neutral"),
    },
    {
        "label": "QQQ vs premarket range",
        "value": market_data.format_price(qqq["price"]),
        "state": qqq["range_state"].get("state") or "No premarket data",
        "detail": index_detail(qqq),
        "tone": qqq["range_state"].get("tone", "neutral"),
    },
])


# -------------------------------------------------------- details and chart
detail_col, alert_col = st.columns([3, 2])

with detail_col:
    st.subheader(f"{ticker} detail")
    rows = [
        ("Last price", market_data.format_price(main["price"])),
        ("Intraday VWAP", market_data.format_price(stock_state.get("vwap"))),
        ("Distance from VWAP", market_data.format_pct(stock_state.get("distance_pct"))),
        ("Move since session start", market_data.format_pct(main["change_pct"])),
        ("Premarket high", ui.format_level(main["levels"]["high"])),
        ("Premarket low", ui.format_level(main["levels"]["low"])),
        ("VWAP state", stock_state.get("state") or "--"),
        ("Premarket range state", main["range_state"].get("state") or "--"),
    ]
    st.dataframe(
        pd.DataFrame(rows, columns=["Measure", "Value"]),
        hide_index=True, width="stretch",
    )

with alert_col:
    st.subheader("Recent changes")
    if not alerts_on:
        st.caption("Alerts are switched off in the sidebar.")
    else:
        log = st.session_state.get("alert_log", [])
        if log:
            for entry in log:
                st.write(f"- {entry}")
        else:
            st.caption(
                "No state changes seen yet in this session. Changes appear "
                "here as they happen."
            )

if show_chart:
    st.subheader(f"{ticker} price vs VWAP")
    chart_bars = main["frame"]["bars"]
    if chart_bars.empty:
        st.caption("Not enough bars yet to draw a chart.")
    else:
        chart_df = pd.DataFrame(
            {"Price": chart_bars["close"], "VWAP": main["frame"]["vwap"]}
        )
        st.line_chart(chart_df, width="stretch")
        ui.note(main["frame"]["session_label"])

with st.expander("What do these words mean?"):
    st.markdown(
        """
- **VWAP** - volume weighted average price. The average price paid so far
  today, weighted by how much volume traded at each price. It resets every
  session.
- **Above VWAP** - price is trading above that average, often read as a
  bullish context.
- **Below VWAP** - price is trading below that average, often read as a
  bearish context.
- **Reclaiming VWAP** - price was below VWAP recently and has crossed back
  above it.
- **Rejecting VWAP** - price was above VWAP recently and has slipped back
  below it.
- **Watch area** - price is sitting on the level, so the context is not
  decided yet and confirmation is needed.
- **Premarket high / low** - the highest and lowest prices traded before the
  9:30 AM ET open, measured from the start time you chose in the sidebar.
- **Inside the premarket range** - price has not broken out either way,
  usually read as a neutral context.
"""
    )

ui.disclaimer()


# ------------------------------------------------------------ auto refresh
def schedule_refresh(seconds: int) -> None:
    """Re-run the app on a timer, using whichever method is available."""
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=seconds * 1000, key="vmca_autorefresh")
        return
    except Exception:
        pass

    # Fallback: reload the browser tab if the helper package is missing.
    import streamlit.components.v1 as components

    components.html(
        f"<script>setTimeout(function(){{window.parent.location.reload();}},"
        f"{seconds * 1000});</script>",
        height=0,
    )


schedule_refresh(refresh_seconds)
