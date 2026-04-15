"""Demand forecast page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

st.set_page_config(page_title="Forecast — PulseCommerce", page_icon="📈", layout="wide")


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


st.title("📈 Demand Forecast")
st.caption("Weekly revenue forecasts by category — baseline vs ML models, selected by backtest MAPE.")

forecast = load("forecast")
mape = load("forecast_mape")

if forecast.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

forecast["week_start"] = pd.to_datetime(forecast["week_start"])
categories = sorted(forecast["category"].unique())
category = st.selectbox("Category", categories, index=0)

cat_df = forecast[forecast["category"] == category].sort_values("week_start")
hist = cat_df[cat_df["kind"] == "history"]
fc = cat_df[cat_df["kind"] == "forecast"]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=hist["week_start"], y=hist["yhat"],
        mode="lines", name="Actual",
        line=dict(color="#4F46E5", width=2),
    )
)
if not fc.empty:
    fig.add_trace(
        go.Scatter(
            x=fc["week_start"], y=fc["yhat"],
            mode="lines", name="Forecast",
            line=dict(color="#F59E0B", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(fc["week_start"]) + list(fc["week_start"])[::-1],
            y=list(fc["yhat_upper"]) + list(fc["yhat_lower"])[::-1],
            fill="toself", fillcolor="rgba(245,158,11,0.2)",
            line=dict(color="rgba(0,0,0,0)"),
            name="95% interval", showlegend=True,
        )
    )
fig.update_layout(
    template="plotly_dark",
    title=f"{category} — revenue history and {len(fc)}-week forecast",
    height=460, margin=dict(l=20, r=20, t=50, b=20),
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Model backtest (MAPE, lower is better)")
if not mape.empty:
    styled = mape.set_index("category")
    st.dataframe(styled.style.highlight_min(axis=1, color="#0e7c3a"), use_container_width=True)
    winners = mape["chosen_model"].value_counts().rename("wins").reset_index()
    winners.columns = ["model", "categories_won"]
    st.markdown("**Model leaderboard**")
    st.dataframe(winners, use_container_width=True, hide_index=True)

st.subheader("Planner view")
if not fc.empty:
    totals = (
        forecast[forecast["kind"] == "forecast"]
        .groupby("category", as_index=False)[["yhat"]]
        .sum()
        .sort_values("yhat", ascending=False)
    )
    import plotly.express as px

    fig = px.bar(
        totals, x="yhat", y="category", orientation="h",
        title="Next 12-week forecast — total revenue by category",
        template="plotly_dark",
    )
    fig.update_traces(marker_color="#10B981")
    st.plotly_chart(fig, use_container_width=True)
