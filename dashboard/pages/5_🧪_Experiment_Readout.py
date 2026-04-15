"""Experiment Readout — ship / iterate / reject verdict with guardrails."""

from __future__ import annotations

import json
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
    badge,
    hero,
    kpi_row,
    section,
    sidebar_brand,
    style_fig,
    verdict_banner,
)

apply_theme("Experiment Readout", "🧪")
sidebar_brand()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


exp = load_json("experiment")
if not exp:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()


hero(
    eyebrow="Layer 05 · Experiment Readout",
    title="Did the intervention work?",
    subtitle=(
        "Targeted retention promotion on high-churn-risk customers. Primary metric tested via Welch's t-test, "
        "with guardrails to catch collateral damage."
    ),
)


# --------------------------------------------------------------------------- #
# Verdict banner
# --------------------------------------------------------------------------- #
verdict_banner(exp.get("recommendation", ""), exp.get("rationale", ""))


# --------------------------------------------------------------------------- #
# Experiment setup strip
# --------------------------------------------------------------------------- #
kpi_row([
    {"label": "Control sample", "value": f"{exp.get('n_control', 0):,}"},
    {"label": "Treatment sample", "value": f"{exp.get('n_treatment', 0):,}"},
    {"label": "Start", "value": exp.get("start", "—")[:10]},
    {"label": "End", "value": exp.get("end", "—")[:10]},
])

st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Primary metric + lift visualization
# --------------------------------------------------------------------------- #
primary = exp.get("primary", {})
guardrails = exp.get("guardrails", [])

left, right = st.columns([5, 7])

with left:
    section("Primary metric", "The single metric the experiment was powered for.")

    pname = primary.get("name", "primary").replace("_", " ").title()
    lift_pct = primary.get("rel_lift", 0) * 100
    lift_tone = "success" if lift_pct > 0 else "danger"
    sig = primary.get("is_significant", False)
    sig_tone = "success" if sig else "neutral"
    sig_label = "Significant" if sig else "Not significant"

    st.markdown(
        f"""
        <div class="pc-card" style="padding:22px 24px;">
          <div class="pc-card-title" style="font-size:0.8rem; text-transform:uppercase;
                letter-spacing:0.08em; color:{COLORS['text_muted']};">{pname}</div>
          <div style="font-size:2.4rem; font-weight:700; color:{COLORS['text']};
                letter-spacing:-0.02em; margin:4px 0;">{primary.get('treatment_mean', 0):.4f}</div>
          <div style="display:flex; gap:8px; align-items:center; margin-top:6px;">
            {badge(f"{lift_pct:+.2f}% vs control", lift_tone)}
            {badge(f"p = {primary.get('p_value', 1):.3f}", sig_tone)}
            {badge(sig_label, sig_tone)}
          </div>
          <div style="font-size:0.85rem; color:{COLORS['text_muted']}; margin-top:14px;">
            Control mean: <b style="color:{COLORS['text']};">{primary.get('control_mean', 0):.4f}</b>
            &nbsp;·&nbsp; Absolute lift: <b style="color:{COLORS['text']};">
                {primary.get('abs_lift', 0):+.4f}</b>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    section("Relative lift — primary vs. guardrails", "Green = direction OK. Red = guardrail breach.")

    labels = [primary.get("name", "primary").replace("_", " ").title()] + [
        g.get("name", "").replace("_", " ").title() for g in guardrails
    ]
    lifts = [primary.get("rel_lift", 0) * 100] + [g.get("rel_lift", 0) * 100 for g in guardrails]
    colors = [COLORS["primary"]] + [
        COLORS["success"] if g.get("direction_ok") else COLORS["danger"] for g in guardrails
    ]

    fig = go.Figure(go.Bar(
        x=lifts, y=labels, orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:+.2f}%" for v in lifts],
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=12),
        hovertemplate="<b>%{y}</b><br>lift: %{x:+.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line=dict(color=COLORS["border_strong"], width=1.5))
    style_fig(fig, height=max(260, 52 * len(labels)), margin=dict(l=10, r=80, t=10, b=10))
    fig.update_xaxes(ticksuffix="%", zeroline=False)
    fig.update_yaxes(title_text=None, autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Guardrail table
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
section("Guardrail metrics", "Secondary metrics monitored to catch unintended harm.")


def _status(g: dict) -> str:
    if g.get("direction_ok"):
        return "✅ PASS"
    return "⚠️ FAIL"


rows = []
for g in guardrails:
    rows.append({
        "Metric": g.get("name", "").replace("_", " ").title(),
        "Control": g.get("control_mean", 0),
        "Treatment": g.get("treatment_mean", 0),
        "Abs lift": g.get("abs_lift", 0),
        "Rel lift": g.get("rel_lift", 0),
        "p-value": g.get("p_value", 1),
        "Status": _status(g),
    })

if rows:
    df = pd.DataFrame(rows)

    def _row_color(row: pd.Series) -> list[str]:
        ok = "PASS" in str(row["Status"])
        color = COLORS["success_bg"] if ok else COLORS["danger_bg"]
        return [f"background-color: {color}" if col == "Status" else "" for col in row.index]

    styled = df.style.format({
        "Control": "{:.4f}",
        "Treatment": "{:.4f}",
        "Abs lift": "{:+.4f}",
        "Rel lift": "{:+.2%}",
        "p-value": "{:.3f}",
    }).apply(_row_color, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Context
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
section("Hypothesis & context", "The original prediction being tested.")
st.markdown(
    f"""
    <div class="pc-card">
      <div style="font-size:0.9rem; color:{COLORS['text']}; line-height:1.6;">
        {exp.get('hypothesis', '—')}
      </div>
      <div style="font-size:0.8rem; color:{COLORS['text_muted']}; margin-top:12px;
                  padding-top:12px; border-top:1px solid {COLORS['border']};">
        Method: Welch's two-sample t-test (unequal variance) · α = 0.05 ·
        Audience: top-30% churn-risk customers from the Churn Risk model.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
st.caption(
    "End of the five-layer story. The verdict closes the loop: funnel → forecast → churn → "
    "intervention → measurable outcome."
)
