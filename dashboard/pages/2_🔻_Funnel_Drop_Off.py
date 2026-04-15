"""Funnel drop-off page."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulsecommerce.config import PROCESSED_DIR

st.set_page_config(page_title="Funnel — PulseCommerce", page_icon="🔻", layout="wide")


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


st.title("🔻 Funnel & Drop-off")
st.caption("Where we lose customers between session and purchase — and which segments leak most.")

overall = load("funnel_overall")
seg = load("funnel_segmented")
insights = load_json("funnel_insights")

if overall.empty:
    st.warning("Run `python -m pulsecommerce.cli pipeline` to populate this page.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Biggest drop-off stage", insights.get("biggest_drop_stage", "—"))
col2.metric("Drop-off at that stage", f"{insights.get('biggest_drop_rate', 0) * 100:.1f}%")
col3.metric("Est. lost-revenue opportunity", f"${insights.get('estimated_lost_revenue', 0):,.0f}")

st.divider()

fig = go.Figure(
    go.Funnel(
        y=overall["stage"].str.replace("_", " ").str.title(),
        x=overall["count"],
        textinfo="value+percent previous",
        marker=dict(color=["#4F46E5", "#6366F1", "#8B5CF6", "#A855F7", "#D946EF"]),
    )
)
fig.update_layout(template="plotly_dark", title="Overall funnel", height=420)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Segmented funnel")
c1, c2 = st.columns([2, 3])
with c1:
    min_sessions = st.slider("Min sessions per segment", 0, 500, 100, step=25)
    view = seg[seg["sessions"] >= min_sessions].copy()
    view["conversion_%"] = (view["overall_conversion"] * 100).round(3)
    st.dataframe(
        view.sort_values("conversion_%", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
with c2:
    if not view.empty:
        heat = view.pivot_table(
            index="device", columns="channel", values="overall_conversion", aggfunc="mean"
        )
        import plotly.express as px

        fig = px.imshow(
            heat * 100,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale="Viridis",
            labels=dict(color="Conversion %"),
            title="Overall conversion by device × channel",
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Recommendations")
worst = insights.get("worst_segment", {})
best = insights.get("best_segment", {})
st.markdown(
    f"""
- **Diagnose**: The **{worst.get('device', '-')} / {worst.get('channel', '-')}** segment converts at
  **{worst.get('overall_conversion', 0) * 100:.2f}%** vs **{best.get('overall_conversion', 0) * 100:.2f}%**
  for the best segment ({best.get('device', '-')} / {best.get('channel', '-')}).
- **Localize**: Stage-level drop-off peaks at **{insights.get('biggest_drop_stage', '-')}** — investigate UX friction there first.
- **Quantify**: Closing half the gap on the worst segment would recover roughly
  **${insights.get('estimated_lost_revenue', 0) / 2:,.0f}** over the analysis window.
- **Act**: Route the worst segment into a targeted A/B test (see the Experiment page).
"""
)
