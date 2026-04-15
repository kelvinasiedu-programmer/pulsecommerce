"""Demand Forecast — baseline vs ML, selected per category by walk-forward MAPE."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from theme import (  # noqa: E402
    COLORS,
    apply_theme,
    hero,
    kpi_row,
    section,
    sidebar_brand,
    style_fig,
)

apply_theme("Demand Forecast", "📈")
sidebar_brand()


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


forecast = load("forecast")
mape = load("forecast_mape")

if forecast.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()


hero(
    eyebrow="Layer 03 · Demand Forecast",
    title="What's coming next?",
    subtitle=(
        "Per-category 12-week revenue forecasts. Three models compete — Seasonal-Naive, "
        "Holt-Winters, XGBoost — and the one with the lowest backtest MAPE wins."
    ),
)


# --------------------------------------------------------------------------- #
# KPI strip
# --------------------------------------------------------------------------- #
forecast["week_start"] = pd.to_datetime(forecast["week_start"])
forecast_only = forecast[forecast["kind"] == "forecast"]
total_forecast_rev = forecast_only["yhat"].sum() if not forecast_only.empty else 0
horizon_weeks = forecast_only["week_start"].nunique() if not forecast_only.empty else 0
n_categories = forecast["category"].nunique()
best_mape = mape[[c for c in mape.columns if c not in ("category", "chosen_model")]].min().min() if not mape.empty else 0

kpi_row([
    {"label": "Forecast horizon", "value": f"{horizon_weeks} wk"},
    {"label": "Categories modeled", "value": f"{n_categories}"},
    {"label": "Total projected revenue", "value": f"${total_forecast_rev:,.0f}"},
    {"label": "Best model MAPE", "value": f"{best_mape * 100:.1f}%"},
])

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Category selector + forecast chart
# --------------------------------------------------------------------------- #
categories = sorted(forecast["category"].unique())

col_sel, _ = st.columns([3, 7])
with col_sel:
    category = st.selectbox("Category", categories, index=0, label_visibility="visible")

section(f"{category} — revenue history and forecast", "Shaded band is the 95% prediction interval.")

cat_df = forecast[forecast["category"] == category].sort_values("week_start")
hist = cat_df[cat_df["kind"] == "history"]
fc = cat_df[cat_df["kind"] == "forecast"]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=hist["week_start"], y=hist["yhat"],
    mode="lines", name="Actual",
    line=dict(color=COLORS["primary"], width=2.5),
    fill="tozeroy", fillcolor="rgba(79,70,229,0.08)",
))
if not fc.empty:
    fig.add_trace(go.Scatter(
        x=list(fc["week_start"]) + list(fc["week_start"])[::-1],
        y=list(fc["yhat_upper"]) + list(fc["yhat_lower"])[::-1],
        fill="toself",
        fillcolor="rgba(245,158,11,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% interval",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=fc["week_start"], y=fc["yhat"],
        mode="lines", name="Forecast",
        line=dict(color=COLORS["warning"], width=2.5, dash="dot"),
    ))
    # Vertical "forecast starts" guide
    if not hist.empty:
        last_hist = hist["week_start"].max()
        fig.add_vline(x=last_hist, line=dict(color=COLORS["border_strong"], width=1, dash="dash"))

style_fig(fig, height=420, margin=dict(l=10, r=10, t=20, b=10))
fig.update_yaxes(title_text="Weekly revenue ($)", tickprefix="$", separatethousands=True)
fig.update_xaxes(title_text=None)
st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Backtest + leaderboard (side by side)
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

if not mape.empty:
    left, right = st.columns([6, 4])

    with left:
        section("Model backtest — MAPE by category", "Lower is better. The lowest value per row is highlighted.")
        mape_cols = [c for c in mape.columns if c not in ("category", "chosen_model")]
        display = mape.set_index("category")
        styled = display.style.format(
            {c: "{:.1%}" for c in mape_cols}
        ).highlight_min(subset=mape_cols, axis=1, color=COLORS["success_bg"])
        st.dataframe(styled, use_container_width=True, height=min(420, 48 + 36 * len(display)))

    with right:
        section("Leaderboard", "Categories won per model.")
        winners = mape["chosen_model"].value_counts().rename_axis("Model").reset_index(name="Wins")
        fig = go.Figure(go.Bar(
            y=winners["Model"], x=winners["Wins"], orientation="h",
            marker=dict(color=COLORS["primary"], line=dict(width=0)),
            text=winners["Wins"],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=12),
        ))
        style_fig(fig, height=min(300, 60 + 40 * len(winners)),
                  margin=dict(l=10, r=40, t=10, b=10))
        fig.update_xaxes(showticklabels=False, showgrid=False)
        fig.update_yaxes(title_text=None)
        st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Planner view
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
section("Planner view", f"Total projected revenue across the next {horizon_weeks} weeks, by category.")

if not forecast_only.empty:
    totals = (
        forecast_only.groupby("category", as_index=False)[["yhat"]]
        .sum()
        .sort_values("yhat", ascending=True)
    )
    fig = go.Figure(go.Bar(
        x=totals["yhat"], y=totals["category"], orientation="h",
        marker=dict(color=COLORS["primary_dark"], line=dict(width=0)),
        text=[f"${v:,.0f}" for v in totals["yhat"]],
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=11),
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
    ))
    style_fig(fig, height=max(320, 44 * len(totals)), margin=dict(l=20, r=110, t=10, b=10))
    fig.update_xaxes(tickprefix="$", separatethousands=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)


st.caption(
    "Next — **Churn Risk** identifies which customers are most likely to stop buying, so demand signal "
    "can be converted into retention spend."
)
