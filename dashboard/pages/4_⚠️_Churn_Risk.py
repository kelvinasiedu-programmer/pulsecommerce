"""Churn Risk — the retention command center."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from theme import (  # noqa: E402
    COLORS,
    SEQ_INDIGO,
    apply_theme,
    hero,
    kpi_row,
    section,
    sidebar_brand,
    style_fig,
)

apply_theme("Churn Risk", "⚠️")
sidebar_brand()


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


scores = load("churn_scores")
cohort = load("cohort_retention")
importance = load("churn_importance")
metrics = load_json("churn_metrics")

if scores.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()


hero(
    eyebrow="Layer 04 · Churn Risk",
    title="Who's about to leave?",
    subtitle=(
        "XGBoost + Logistic baseline trained on RFM and behavioral features. Risk scores feed "
        "directly into the Experiment page — the highest-risk customers are the retention test audience."
    ),
)


# --------------------------------------------------------------------------- #
# KPI strip — Business Reality first, Model Health second
# --------------------------------------------------------------------------- #
churn_rate = metrics.get("churn_rate", 0)
auc_xgb = metrics.get("roc_auc_xgb", 0)
auc_log = metrics.get("roc_auc_logreg", 0)
avg_precision = metrics.get("average_precision_xgb", 0)

high_risk = scores[scores["churn_risk"] >= 0.7]
n_high = len(high_risk)
revenue_at_risk = float(high_risk["monetary"].sum()) if "monetary" in high_risk.columns else 0.0

kpi_row([
    {"label": "Baseline churn rate", "value": f"{churn_rate * 100:.1f}%"},
    {"label": "High-risk customers", "value": f"{n_high:,}", "delta": "risk ≥ 0.70"},
    {"label": "Revenue at risk", "value": f"${revenue_at_risk:,.0f}", "delta": "high-risk LTV sum"},
    {"label": "Model ROC-AUC", "value": f"{auc_xgb:.3f}", "delta": f"Logistic: {auc_log:.3f}"},
])
st.caption(f"Average precision (XGBoost): **{avg_precision:.3f}**")

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_dist, tab_cohort, tab_imp, tab_top = st.tabs([
    "📊 Risk distribution", "🔁 Cohort retention", "🧠 Feature importance", "🎯 Top at-risk",
])


with tab_dist:
    section("Distribution of predicted churn risk",
            "Zones: Safe (< 0.3) · Monitor (0.3–0.7) · High risk (≥ 0.7).")

    hist_data = scores["churn_risk"]
    bins = 40
    counts, edges = pd.cut(hist_data, bins=bins, retbins=True)
    counts_series = counts.value_counts().sort_index()
    centers = (edges[:-1] + edges[1:]) / 2
    y = counts_series.values

    fig = go.Figure()
    # Zone backgrounds
    ymax = float(y.max()) * 1.08 if len(y) else 1
    for x0, x1, color in [
        (0.0, 0.3, "rgba(16,185,129,0.07)"),
        (0.3, 0.7, "rgba(245,158,11,0.08)"),
        (0.7, 1.0, "rgba(239,68,68,0.08)"),
    ]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0, y1=ymax,
                      line=dict(width=0), fillcolor=color, layer="below")

    # Area/step chart
    fig.add_trace(go.Scatter(
        x=centers, y=y, mode="lines",
        line=dict(color=COLORS["primary_dark"], width=2, shape="spline"),
        fill="tozeroy", fillcolor="rgba(79,70,229,0.18)",
        hovertemplate="Risk %{x:.2f}<br>%{y:,} users<extra></extra>",
        name="Users",
    ))

    # Zone labels
    for x, label, color in [
        (0.15, "Safe", COLORS["success"]),
        (0.50, "Monitor", COLORS["warning"]),
        (0.85, "High Risk", COLORS["danger"]),
    ]:
        fig.add_annotation(x=x, y=ymax, text=f"<b>{label}</b>",
                           showarrow=False, font=dict(color=color, size=11), yanchor="top")

    style_fig(fig, height=360, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    fig.update_xaxes(title_text="Predicted churn risk", range=[0, 1])
    fig.update_yaxes(title_text="Customers")
    st.plotly_chart(fig, use_container_width=True)

    # Decile table with inline bars
    section("Risk deciles", "Mean predicted risk, actual churn, and average monetary value per decile.")
    by_decile = scores.groupby("risk_decile").agg(
        n=("user_id", "count"),
        mean_risk=("churn_risk", "mean"),
        actual_churn=("actual_churn", "mean"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()

    styled = by_decile.style.format({
        "n": "{:,}",
        "mean_risk": "{:.1%}",
        "actual_churn": "{:.1%}",
        "avg_monetary": "${:,.0f}",
    }).bar(
        subset=["mean_risk"], color=COLORS["danger_bg"],
        vmin=0, vmax=1,
    ).bar(
        subset=["actual_churn"], color=COLORS["warning_bg"],
        vmin=0, vmax=1,
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


with tab_cohort:
    section("Monthly cohort retention", "% of the cohort still active N months after acquisition.")
    if cohort.empty:
        st.info("Not enough history for cohort retention.")
    else:
        cohort = cohort.copy()
        cohort["cohort_month"] = pd.to_datetime(cohort["cohort_month"]).dt.strftime("%Y-%m")
        heat = cohort.pivot_table(
            index="cohort_month", columns="month_number",
            values="retention_rate", aggfunc="mean",
        )
        fig = px.imshow(
            heat * 100, text_auto=".0f", aspect="auto",
            color_continuous_scale=SEQ_INDIGO,
            labels=dict(color="Retention %", x="Months since acquisition", y="Cohort"),
        )
        fig.update_traces(
            xgap=3, ygap=3,
            textfont=dict(color="white", size=11, family="Inter"),
            hovertemplate="Cohort <b>%{y}</b><br>M%{x}: %{z:.0f}%<extra></extra>",
        )
        style_fig(fig, height=520, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)


with tab_imp:
    section("Top churn drivers", "SHAP-style importance from the XGBoost model.")
    if importance.empty:
        st.info("No feature importances computed.")
    else:
        top = importance.head(15).sort_values("importance")
        fig = go.Figure(go.Bar(
            x=top["importance"], y=top["feature"], orientation="h",
            marker=dict(color=COLORS["primary"], line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>importance: %{x:.4f}<extra></extra>",
        ))
        style_fig(fig, height=max(360, 32 * len(top)), margin=dict(l=10, r=20, t=10, b=10))
        fig.update_xaxes(title_text="Importance", showgrid=False)
        fig.update_yaxes(title_text=None)
        st.plotly_chart(fig, use_container_width=True)


with tab_top:
    section("Top-50 at-risk customers", "These feed the Experiment page's retention audience.")
    top_at_risk = scores.nlargest(50, "churn_risk").reset_index(drop=True)
    display = top_at_risk[[
        "user_id", "churn_risk", "recency_days", "frequency", "monetary", "country"
    ]].copy()

    styled = display.style.format({
        "churn_risk": "{:.1%}",
        "recency_days": "{:.0f}",
        "frequency": "{:.0f}",
        "monetary": "${:,.0f}",
    }).bar(
        subset=["churn_risk"], color=COLORS["danger_bg"], vmin=0, vmax=1,
    ).bar(
        subset=["monetary"], color=COLORS["success_bg"],
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=520)


st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
st.caption(
    "Next — **Experiment Readout** measures whether a retention promo targeted at these high-risk customers "
    "moved the primary metric without breaking any guardrail."
)
