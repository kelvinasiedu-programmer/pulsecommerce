"""Churn risk page."""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

st.set_page_config(page_title="Churn — PulseCommerce", page_icon="⚠️", layout="wide")


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


st.title("⚠️ Churn Risk")
st.caption("Who's about to stop buying — and where to deploy retention effort.")

scores = load("churn_scores")
cohort = load("cohort_retention")
importance = load("churn_importance")
metrics = load_json("churn_metrics")

if scores.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("ROC-AUC (XGBoost)", f"{metrics.get('roc_auc_xgb', 0):.3f}")
c2.metric("ROC-AUC (Logistic)", f"{metrics.get('roc_auc_logreg', 0):.3f}")
c3.metric("Avg Precision", f"{metrics.get('average_precision_xgb', 0):.3f}")
c4.metric("Baseline churn rate", f"{metrics.get('churn_rate', 0) * 100:.1f}%")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Risk distribution", "Cohort retention", "Feature importance", "Top-at-risk"])

with tab1:
    fig = px.histogram(
        scores, x="churn_risk", nbins=40, template="plotly_dark",
        title="Distribution of predicted churn risk",
    )
    fig.update_traces(marker_color="#EF4444")
    st.plotly_chart(fig, use_container_width=True)
    by_decile = scores.groupby("risk_decile").agg(
        n=("user_id", "count"),
        mean_risk=("churn_risk", "mean"),
        actual_churn=("actual_churn", "mean"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()
    st.dataframe(by_decile, use_container_width=True, hide_index=True)

with tab2:
    if cohort.empty:
        st.info("Not enough history for cohort retention.")
    else:
        cohort["cohort_month"] = pd.to_datetime(cohort["cohort_month"]).dt.strftime("%Y-%m")
        heat = cohort.pivot_table(
            index="cohort_month", columns="month_number",
            values="retention_rate", aggfunc="mean",
        )
        fig = px.imshow(
            heat * 100, text_auto=".0f", aspect="auto",
            color_continuous_scale="Blues",
            labels=dict(color="Retention %"),
            title="Monthly cohort retention heatmap",
            template="plotly_dark",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    if importance.empty:
        st.info("No feature importances computed.")
    else:
        top = importance.head(15).sort_values("importance")
        fig = px.bar(
            top, x="importance", y="feature", orientation="h",
            title="Top features driving churn prediction",
            template="plotly_dark",
        )
        fig.update_traces(marker_color="#A855F7")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    top_at_risk = scores.nlargest(50, "churn_risk").reset_index(drop=True)
    st.dataframe(
        top_at_risk[
            ["user_id", "churn_risk", "recency_days", "frequency", "monetary", "country"]
        ].style.format({"churn_risk": "{:.3f}", "monetary": "${:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "These are the customers the experiment page will target with a retention promotion."
    )
