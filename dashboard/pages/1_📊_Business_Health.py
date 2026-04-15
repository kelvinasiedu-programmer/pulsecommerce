"""Business Health page — the executive KPI deep dive."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

st.set_page_config(page_title="Business Health — PulseCommerce", page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


st.title("📊 Business Health")
st.caption("Executive KPIs — revenue, orders, conversion, and mix — vs the prior equivalent window.")

cards = load("kpi_cards")
daily = load("kpi_daily")
by_channel = load("kpi_channel")
by_category = load("kpi_category")

if cards.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

# KPI cards row
cols = st.columns(len(cards))
for col, (_, row) in zip(cols, cards.iterrows(), strict=False):
    fmt = row["format"]
    val = row["value"]
    if fmt == "currency":
        text = f"${val:,.0f}"
    elif fmt == "percent":
        text = f"{val * 100:.2f}%"
    else:
        text = f"{val:,.0f}"
    col.metric(row["label"], text, f"{row['delta_pct'] * 100:+.1f}% vs prior")

st.divider()

daily["metric_date"] = pd.to_datetime(daily["metric_date"])
tab1, tab2, tab3 = st.tabs(["Trends", "Channel mix", "Category mix"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.line(daily, x="metric_date", y="revenue", template="plotly_dark",
                      title="Daily revenue")
        fig.update_traces(line_color="#4F46E5")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.line(daily, x="metric_date", y="conversion_rate", template="plotly_dark",
                      title="Session → purchase conversion")
        fig.update_traces(line_color="#10B981")
        fig.update_yaxes(tickformat=".2%")
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig = px.bar(daily, x="metric_date", y="orders", template="plotly_dark",
                     title="Daily orders")
        fig.update_traces(marker_color="#6366F1")
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        fig = px.line(daily, x="metric_date", y="avg_order_value", template="plotly_dark",
                      title="Average order value")
        fig.update_traces(line_color="#F59E0B")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if by_channel.empty:
        st.info("No channel data yet.")
    else:
        fig = px.bar(
            by_channel.sort_values("revenue", ascending=True),
            x="revenue", y="channel", orientation="h",
            title="Revenue by acquisition channel (last 28 days)",
            template="plotly_dark",
        )
        fig.update_traces(marker_color="#4F46E5")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(by_channel, use_container_width=True)

with tab3:
    if by_category.empty:
        st.info("No category data yet.")
    else:
        fig = px.treemap(
            by_category, path=["category"], values="revenue",
            title="Revenue share by category (last 28 days)",
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(by_category, use_container_width=True)
