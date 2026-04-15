"""Experiment readout page."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

st.set_page_config(page_title="Experiment — PulseCommerce", page_icon="🧪", layout="wide")


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


st.title("🧪 Experiment Readout")
st.caption("Did the targeted retention promotion move the needle — without hurting anything else?")

exp = load_json("experiment")
if not exp:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

rec = exp.get("recommendation", "—").lower()
emoji = {"ship": "🟢", "iterate": "🟡", "reject": "🔴"}.get(rec, "⚪")

st.markdown(f"### Recommendation: {emoji} **{rec.upper()}**")
st.info(exp.get("rationale", ""))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Control sample", f"{exp.get('n_control', 0):,}")
c2.metric("Treatment sample", f"{exp.get('n_treatment', 0):,}")
c3.metric("Start", exp.get("start", "—"))
c4.metric("End", exp.get("end", "—"))

st.divider()

primary = exp.get("primary", {})
guardrails = exp.get("guardrails", [])

st.subheader("Primary metric")
g1, g2, g3, g4 = st.columns(4)
g1.metric(primary.get("name", "—"), f"{primary.get('treatment_mean', 0):.4f}",
          f"{primary.get('rel_lift', 0) * 100:+.2f}% vs control")
g2.metric("Control mean", f"{primary.get('control_mean', 0):.4f}")
g3.metric("p-value", f"{primary.get('p_value', 1):.4f}")
g4.metric("Significant?", "Yes" if primary.get("is_significant") else "No")

st.subheader("Guardrail metrics")
rows = []
for g in guardrails:
    rows.append(
        {
            "metric": g.get("name"),
            "control": g.get("control_mean"),
            "treatment": g.get("treatment_mean"),
            "abs_lift": g.get("abs_lift"),
            "rel_lift": g.get("rel_lift"),
            "p_value": g.get("p_value"),
            "significant": g.get("is_significant"),
            "direction_ok": g.get("direction_ok"),
        }
    )
guardrail_df = pd.DataFrame(rows)
st.dataframe(
    guardrail_df.style.format(
        {
            "control": "{:.4f}",
            "treatment": "{:.4f}",
            "abs_lift": "{:+.4f}",
            "rel_lift": "{:+.2%}",
            "p_value": "{:.4f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

# Lift waterfall
fig = go.Figure(
    go.Bar(
        x=[primary.get("name")] + [g.get("name") for g in guardrails],
        y=[primary.get("rel_lift", 0)] + [g.get("rel_lift", 0) for g in guardrails],
        marker_color=["#10B981"]
        + ["#10B981" if g.get("direction_ok") else "#EF4444" for g in guardrails],
        text=[f"{primary.get('rel_lift', 0) * 100:+.2f}%"]
        + [f"{g.get('rel_lift', 0) * 100:+.2f}%" for g in guardrails],
        textposition="outside",
    )
)
fig.update_layout(
    template="plotly_dark",
    title="Relative lift: primary vs guardrails",
    yaxis_tickformat=".2%",
    height=360,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Hypothesis")
st.write(exp.get("hypothesis", "—"))
