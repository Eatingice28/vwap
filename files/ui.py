"""Reusable display pieces. All layout is responsive so it works on phones."""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from . import config as cfg

CSS = """
<style>
.vmca-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 0.75rem;
  margin: 0.25rem 0 1rem 0;
}
.vmca-card {
  border-radius: 12px;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(0,0,0,0.08);
  border-left-width: 7px;
  border-left-style: solid;
}
.vmca-card .label {
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.75;
  margin-bottom: 0.15rem;
}
.vmca-card .value {
  font-size: 1.45rem;
  font-weight: 700;
  line-height: 1.2;
}
.vmca-card .state {
  font-size: 1.0rem;
  font-weight: 600;
  margin-top: 0.2rem;
}
.vmca-card .detail {
  font-size: 0.85rem;
  opacity: 0.85;
  margin-top: 0.35rem;
  line-height: 1.35;
}
.vmca-summary {
  border-radius: 12px;
  padding: 1.1rem 1.2rem;
  border: 1px solid rgba(0,0,0,0.08);
  border-left-width: 9px;
  border-left-style: solid;
  margin-bottom: 1rem;
}
.vmca-summary h3 { margin: 0 0 0.4rem 0; font-size: 1.3rem; }
.vmca-summary p { margin: 0; font-size: 0.98rem; line-height: 1.5; }
.vmca-legend { font-size: 0.85rem; opacity: 0.85; }
.vmca-dot {
  display: inline-block; width: 0.7rem; height: 0.7rem;
  border-radius: 50%; margin-right: 0.3rem; vertical-align: middle;
}
.vmca-note {
  font-size: 0.85rem; opacity: 0.8; margin-top: 0.2rem;
}
@media (max-width: 640px) {
  .vmca-card .value { font-size: 1.25rem; }
  .vmca-summary h3 { font-size: 1.15rem; }
}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _colors(tone: str) -> tuple[str, str]:
    return cfg.TONE_COLORS.get(tone, cfg.TONE_COLORS["neutral"])


def status_cards(cards: list[dict]) -> None:
    """Render a responsive row of colour-coded status cards.

    Each card dict: label, value, state, detail, tone.
    """
    blocks = []
    for card in cards:
        fg, bg = _colors(card.get("tone", "neutral"))
        blocks.append(
            f'<div class="vmca-card" style="background:{bg};border-left-color:{fg};">'
            f'<div class="label">{html.escape(str(card.get("label", "")))}</div>'
            f'<div class="value" style="color:{fg};">'
            f'{html.escape(str(card.get("value", "--")))}</div>'
            f'<div class="state" style="color:{fg};">'
            f'{html.escape(str(card.get("state", "")))}</div>'
            f'<div class="detail">{card.get("detail", "")}</div>'
            f"</div>"
        )
    st.markdown(
        f'<div class="vmca-grid">{"".join(blocks)}</div>', unsafe_allow_html=True
    )


def summary_card(headline: str, body: str, tone: str) -> None:
    fg, bg = _colors(tone)
    st.markdown(
        f'<div class="vmca-summary" style="background:{bg};border-left-color:{fg};">'
        f'<h3 style="color:{fg};">{html.escape(headline)}</h3>'
        f"<p>{html.escape(body)}</p></div>",
        unsafe_allow_html=True,
    )


def legend() -> None:
    items = [
        (cfg.GREEN, "Green - bullish context"),
        (cfg.RED, "Red - bearish context"),
        (cfg.YELLOW, "Yellow - mixed / caution"),
        (cfg.GRAY, "Gray - neutral"),
    ]
    dots = "&nbsp;&nbsp;".join(
        f'<span><span class="vmca-dot" style="background:{colour};"></span>'
        f"{label}</span>"
        for colour, label in items
    )
    st.markdown(f'<div class="vmca-legend">{dots}</div>', unsafe_allow_html=True)


def disclaimer() -> None:
    st.caption(
        "This dashboard is for education and market context only. It does not "
        "place trades, does not connect to any brokerage, and does not give "
        "buy or sell instructions. Nothing here is financial advice and no "
        "outcome or profit is implied. Data may be delayed depending on your "
        "data plan."
    )


def note(text: str) -> None:
    st.markdown(f'<div class="vmca-note">{html.escape(text)}</div>',
                unsafe_allow_html=True)


def format_level(value: Optional[float]) -> str:
    return "--" if value is None else f"${value:,.2f}"
