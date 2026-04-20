"""Business Health — executive KPI deep dive with trend, channel, and category views."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from theme import (  # noqa: E402
    CATEGORICAL,
    COLORS,
    SEQ_INDIGO,
    apply_theme,
    hero,
    kpi_row,
    section,
    sidebar_brand,
    style_fig,
)

apply_theme("Business Health", "📊")
sidebar_brand()


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


cards = load("kpi_cards")
daily = load("kpi_daily")
by_channel = load("kpi_channel")
by_category = load("kpi_category")

if cards.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

hero(
    eyebrow="Layer 01 · Business Health",
    title="Is the business healthy?",
    subtitle=(
        "Trailing 28-day KPIs versus the prior equivalent window. Financials, traffic, "
        "and efficiency — grouped for scannability."
    ),
)


def _fmt(value: float, fmt: str) -> str:
    if fmt == "currency":
        return f"${value:,.0f}"
    if fmt == "percent":
        return f"{value * 100:.2f}%"
    return f"{value:,.0f}"


items = [
    {
        "label": row["label"],
        "value": _fmt(row["value"], row["format"]),
        "delta": f"{row['delta_pct'] * 100:+.1f}% vs. Previous Period",
    }
    for _, row in cards.iterrows()
]
kpi_row(items)


st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

tab_trend, tab_channel, tab_category = st.tabs(["📈 Trends", "📡 Channel mix", "🗂️ Category mix"])

daily["metric_date"] = pd.to_datetime(daily["metric_date"])
dd = daily.sort_values("metric_date").copy()
dd["rev_roll"] = dd["revenue"].rolling(7, min_periods=1).mean()
dd["conv_roll"] = dd["conversion_rate"].rolling(7, min_periods=1).mean()
dd["aov_roll"] = dd["avg_order_value"].rolling(7, min_periods=1).mean()


def _trend_fig(y: str, y_roll: str, color: str, y_title: str, tickformat: str | None = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd["metric_date"], y=dd[y], mode="lines", name="Daily",
        line=dict(color=color, width=1), opacity=0.4,
    ))
    fig.add_trace(go.Scatter(
        x=dd["metric_date"], y=dd[y_roll], mode="lines", name="7-day avg",
        line=dict(color=color, width=2.5),
    ))
    style_fig(fig, height=300, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
    fig.update_yaxes(title_text=y_title)
    if tickformat:
        fig.update_yaxes(tickformat=tickformat)
    fig.update_xaxes(title_text=None)
    return fig


with tab_trend:
    section("Revenue & conversion", "Thin daily line under a bold 7-day rolling trend.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Daily revenue**")
        fig = _trend_fig("revenue", "rev_roll", COLORS["primary"], "Revenue ($)")
        fig.update_yaxes(tickprefix="$", separatethousands=True)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Session → purchase conversion**")
        fig = _trend_fig("conversion_rate", "conv_roll", COLORS["success"], "Conversion", tickformat=".2%")
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Daily orders**")
        fig = go.Figure(go.Bar(
            x=dd["metric_date"], y=dd["orders"],
            marker=dict(color=COLORS["primary"], line=dict(width=0)),
            hovertemplate="%{x|%b %d}<br>%{y:,} orders<extra></extra>",
        ))
        style_fig(fig, height=300, margin=dict(l=10, r=10, t=30, b=10))
        fig.update_yaxes(title_text="Orders")
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        st.markdown("**Average order value**")
        fig = _trend_fig("avg_order_value", "aov_roll", COLORS["warning"], "AOV ($)")
        fig.update_yaxes(tickprefix="$", separatethousands=True)
        st.plotly_chart(fig, use_container_width=True)


with tab_channel:
    section("Revenue by acquisition channel", "Last 28 days, sorted by revenue.")
    if by_channel.empty:
        st.info("No channel data yet.")
    else:
        df = by_channel.sort_values("revenue", ascending=True)
        fig = go.Figure(go.Bar(
            x=df["revenue"], y=df["channel"], orientation="h",
            marker=dict(color=COLORS["primary"], line=dict(width=0)),
            text=[f"${v:,.0f}" for v in df["revenue"]],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=11),
            hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
        ))
        style_fig(fig, height=380, margin=dict(l=20, r=60, t=20, b=20))
        fig.update_xaxes(tickprefix="$", separatethousands=True)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Detail**")
        st.dataframe(by_channel, use_container_width=True, hide_index=True)


with tab_category:
    section("Category revenue mix", "Proportional share of trailing 28-day revenue.")
    if by_category.empty:
        st.info("No category data yet.")
    else:
        fig = px.treemap(
            by_category, path=["category"], values="revenue",
            color="revenue", color_continuous_scale=SEQ_INDIGO,
        )
        fig.update_traces(
            textfont=dict(family="Inter", size=13),
            marker=dict(line=dict(color="white", width=2)),
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
        )
        style_fig(fig, height=420, margin=dict(l=10, r=10, t=10, b=10))
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Detail**")
        st.dataframe(by_category, use_container_width=True, hide_index=True)


st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
st.caption(
    "Next — **Funnel Drop-off** localizes where conversion is leaking; "
    "revenue-at-risk is quantified there. All figures sourced from the `daily_kpis` metric table."
)
_ = CATEGORICAL  # re-export for type-check stability
