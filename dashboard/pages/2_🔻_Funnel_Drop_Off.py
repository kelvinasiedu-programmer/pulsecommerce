"""Funnel & Drop-off — session-to-purchase flow, segmented by device × channel."""

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
    insight_card,
    kpi_row,
    section,
    sidebar_brand,
    style_fig,
)

apply_theme("Funnel Drop-off", "🔻")
sidebar_brand()


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


overall = load("funnel_overall")
seg = load("funnel_segmented")
insights = load_json("funnel_insights")

if overall.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()


hero(
    eyebrow="Layer 02 · Funnel & Drop-off",
    title="Where are we losing customers?",
    subtitle=(
        "Five-stage event funnel with segmented conversion by device and channel. "
        "Leakage is quantified in lost revenue — and tied to the highest-friction segment."
    ),
)


# --------------------------------------------------------------------------- #
# KPI strip
# --------------------------------------------------------------------------- #
biggest_stage = insights.get("biggest_drop_stage", "—").replace("_", " ").title()
biggest_rate = insights.get("biggest_drop_rate", 0) * 100
lost = insights.get("estimated_lost_revenue", 0)
total_sessions = int(overall.iloc[0]["count"]) if not overall.empty else 0
final_conv = (overall.iloc[-1]["count"] / max(overall.iloc[0]["count"], 1)) if not overall.empty else 0

kpi_row([
    {"label": "Total Sessions", "value": f"{total_sessions:,}"},
    {"label": "Overall Conversion", "value": f"{final_conv * 100:.2f}%"},
    {"label": "Biggest drop stage", "value": biggest_stage, "delta": f"-{biggest_rate:.1f}% drop"},
    {"label": "Revenue at risk", "value": f"${lost:,.0f}", "delta": "est. recoverable"},
])

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Horizontal step funnel
# --------------------------------------------------------------------------- #
section("Conversion flow", "Step funnel — stage volume and % of previous stage.")

stages = overall["stage"].str.replace("_", " ").str.title().tolist()
counts = overall["count"].tolist()
prev_pct = [1.0] + [counts[i] / counts[i - 1] if counts[i - 1] else 0 for i in range(1, len(counts))]
drop_pct = [0] + [1 - p for p in prev_pct[1:]]

palette = ["#3730A3", "#4338CA", "#4F46E5", "#6366F1", "#818CF8"]

fig = go.Figure()
for i, (stage, cnt, p, d) in enumerate(zip(stages, counts, prev_pct, drop_pct, strict=True)):
    fig.add_trace(go.Bar(
        y=[stage], x=[cnt], orientation="h",
        marker=dict(color=palette[i % len(palette)], line=dict(width=0)),
        text=f"<b>{cnt:,}</b>  ·  {p * 100:.1f}% of prev"
             + (f"  ·  <span style='color:#EF4444'>-{d * 100:.1f}%</span>" if i > 0 else ""),
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=12),
        hovertemplate=f"<b>{stage}</b><br>{cnt:,} users<extra></extra>",
        showlegend=False,
    ))
fig.update_layout(barmode="overlay")
style_fig(fig, height=max(260, 56 * len(stages)), margin=dict(l=20, r=200, t=10, b=10))
fig.update_yaxes(categoryorder="array", categoryarray=stages[::-1], autorange="reversed")
fig.update_xaxes(showticklabels=False, showgrid=False)
st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Segmented view: table + heatmap
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
section("Segmented conversion", "Filter by sample size, then inspect the device × channel grid.")

min_sessions = st.slider("Min sessions per segment", 0, 500, 100, step=25)
view = seg[seg["sessions"] >= min_sessions].copy()

left, right = st.columns([5, 5])

with left:
    st.markdown("**Segment table** — sortable, with progress bars")
    view["conversion"] = view["overall_conversion"]
    cols_to_show = ["device", "channel", "sessions", "overall_conversion"]
    opt_cols = [c for c in ("view_rate", "cart_rate", "purchase_rate") if c in view.columns]
    cols_to_show.extend(opt_cols)

    table = view[cols_to_show].sort_values("overall_conversion", ascending=False).reset_index(drop=True)
    styled = table.style.format({
        "sessions": "{:,}",
        "overall_conversion": "{:.2%}",
        **{c: "{:.2%}" for c in opt_cols},
    }).bar(
        subset=["overall_conversion"],
        color=COLORS["primary_light"],
        vmin=0, vmax=float(table["overall_conversion"].max()) if not table.empty else 1,
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

with right:
    st.markdown("**Device × channel heatmap** — single-hue indigo, darker = stronger conversion")
    if not view.empty:
        heat = view.pivot_table(
            index="device", columns="channel", values="overall_conversion", aggfunc="mean"
        )
        fig = px.imshow(
            heat * 100,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale=SEQ_INDIGO,
            labels=dict(color="Conv %"),
        )
        fig.update_traces(
            textfont=dict(color="white", size=13, family="Inter"),
            xgap=3, ygap=3,
            hovertemplate="<b>%{y} · %{x}</b><br>%{z:.2f}% conversion<extra></extra>",
        )
        style_fig(fig, height=420, margin=dict(l=10, r=10, t=10, b=10))
        fig.update_xaxes(side="top", title_text=None)
        fig.update_yaxes(title_text=None)
        st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Actionable recommendations
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
section("Recommended actions", "Each card ties a diagnosis to an owner and a dollar-denominated move.")

worst = insights.get("worst_segment", {})
best = insights.get("best_segment", {})
worst_dev = worst.get("device", "—")
worst_ch = worst.get("channel", "—")
worst_conv = worst.get("overall_conversion", 0) * 100
best_dev = best.get("device", "—")
best_ch = best.get("channel", "—")
best_conv = best.get("overall_conversion", 0) * 100

c1, c2 = st.columns(2)
with c1:
    insight_card(
        "🔍 Diagnose — worst-performing segment",
        f"<b>{worst_dev} / {worst_ch}</b> converts at <b>{worst_conv:.2f}%</b> "
        f"vs. <b>{best_conv:.2f}%</b> for <b>{best_dev} / {best_ch}</b>. "
        f"That's a <b>{(best_conv - worst_conv):.2f} pp</b> gap.",
        tone="warning",
    )
    insight_card(
        "📍 Localize — stage-level friction",
        f"Biggest drop occurs at <b>{biggest_stage}</b> (-{biggest_rate:.1f}%). "
        f"Investigate UX there before optimizing earlier stages.",
    )
with c2:
    insight_card(
        "💰 Quantify — revenue opportunity",
        f"Closing half the gap on the worst segment recovers roughly "
        f"<b>${lost / 2:,.0f}</b> over the analysis window.",
        tone="success",
    )
    insight_card(
        "🎯 Act — targeted experiment",
        f"Route <b>{worst_dev} / {worst_ch}</b> into a retention-focused A/B test. "
        f"See the <b>Experiment Readout</b> page for the live result.",
        tone="success",
    )


st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
st.caption(
    "Next — **Demand Forecast** answers *what's coming*, converting funnel signal into forward revenue."
)
