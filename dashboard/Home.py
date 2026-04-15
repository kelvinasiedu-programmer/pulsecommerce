"""PulseCommerce — Streamlit landing page.

The 5 analytical deep-dives live in dashboard/pages/. This Home page is
the executive summary: one glance at the state of the business.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Make `pulsecommerce` importable whether the app is launched from repo root
# (Streamlit Cloud) or from /dashboard locally.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from pulsecommerce.config import PROCESSED_DIR  # noqa: E402

st.set_page_config(
    page_title="PulseCommerce",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Cold-start bootstrap: if no processed artifacts exist, run the pipeline.
# --------------------------------------------------------------------------- #
def _ensure_bootstrapped() -> None:
    if (PROCESSED_DIR / "kpi_cards.parquet").exists():
        return
    with st.spinner("First-time setup — generating data and running the full 5-layer pipeline…"):
        from pulsecommerce.cli import main

        main(["all", "--small"])


_ensure_bootstrapped()


# --------------------------------------------------------------------------- #
# Data loaders
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_parquet(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


cards = load_parquet("kpi_cards")
daily = load_parquet("kpi_daily")
funnel_overall = load_parquet("funnel_overall")
experiment = load_json("experiment")
churn_metrics = load_json("churn_metrics")
funnel_insights = load_json("funnel_insights")


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.markdown("# 📈")
with col_title:
    st.title("PulseCommerce")
    st.caption(
        "One warehouse · five analytical layers · one story — "
        "**health → funnel → forecast → churn → experiment**"
    )

st.divider()

# --------------------------------------------------------------------------- #
# Exec KPI strip
# --------------------------------------------------------------------------- #
if cards.empty:
    st.error("Pipeline artifacts not found. Run `python -m pulsecommerce.cli all` first.")
    st.stop()


def _format(value: float, fmt: str) -> str:
    if fmt == "currency":
        return f"${value:,.0f}"
    if fmt == "percent":
        return f"{value * 100:.2f}%"
    return f"{value:,.0f}"


st.markdown("### Trailing 28-day business pulse")
kpi_cols = st.columns(len(cards))
for col, (_, row) in zip(kpi_cols, cards.iterrows(), strict=False):
    col.metric(
        row["label"],
        _format(row["value"], row["format"]),
        f"{row['delta_pct'] * 100:+.1f}% vs prior 28d",
    )

st.divider()

# --------------------------------------------------------------------------- #
# Top-line chart + snapshot
# --------------------------------------------------------------------------- #
left, right = st.columns([3, 2])

with left:
    st.markdown("#### Daily revenue & conversion")
    if not daily.empty:
        daily["metric_date"] = pd.to_datetime(daily["metric_date"])
        fig = px.area(
            daily, x="metric_date", y="revenue",
            template="plotly_dark",
            title=None,
        )
        fig.update_traces(line_color="#4F46E5", fillcolor="rgba(79,70,229,0.25)")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300,
                          xaxis_title=None, yaxis_title="Revenue ($)")
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("#### The 5-layer story")
    biggest = funnel_insights.get("biggest_drop_stage", "—")
    lost = funnel_insights.get("estimated_lost_revenue", 0)
    auc = churn_metrics.get("roc_auc_xgb", 0)
    churn_rate = churn_metrics.get("churn_rate", 0)
    rec = (experiment.get("recommendation") or "").upper() or "—"
    emoji = {"SHIP": "🟢", "ITERATE": "🟡", "REJECT": "🔴"}.get(rec, "⚪")

    st.markdown(
        f"""
- **Health** — revenue trend shown left, full KPI bundle on the Business Health page.
- **Funnel** — biggest drop at **{biggest}**; closing the segment gap worth **${lost:,.0f}**.
- **Forecast** — 12-week forecasts per category on the Demand Forecast page.
- **Churn** — XGBoost ROC-AUC **{auc:.3f}** at **{churn_rate * 100:.1f}%** baseline churn.
- **Experiment** — targeted retention promo → {emoji} **{rec}**.
"""
    )

st.divider()

# --------------------------------------------------------------------------- #
# Overall funnel + experiment readout snapshots
# --------------------------------------------------------------------------- #
left2, right2 = st.columns(2)

with left2:
    st.markdown("#### Overall funnel")
    if not funnel_overall.empty:
        import plotly.graph_objects as go

        fig = go.Figure(
            go.Funnel(
                y=funnel_overall["stage"].str.replace("_", " ").str.title(),
                x=funnel_overall["count"],
                textinfo="value+percent previous",
                marker=dict(color=["#4F46E5", "#6366F1", "#8B5CF6", "#A855F7", "#D946EF"]),
            )
        )
        fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=340)
        st.plotly_chart(fig, use_container_width=True)

with right2:
    st.markdown("#### Experiment readout")
    if experiment:
        primary = experiment.get("primary", {})
        guardrails = experiment.get("guardrails", [])
        g1, g2 = st.columns(2)
        g1.metric(
            primary.get("name", "primary"),
            f"{primary.get('treatment_mean', 0):.4f}",
            f"{primary.get('rel_lift', 0) * 100:+.2f}%",
        )
        g2.metric("p-value", f"{primary.get('p_value', 1):.4f}")
        st.write(experiment.get("rationale", ""))
        rows = []
        for g in guardrails:
            rows.append(
                {
                    "guardrail": g.get("name"),
                    "lift %": g.get("rel_lift", 0) * 100,
                    "p": g.get("p_value", 1),
                    "ok?": "✅" if g.get("direction_ok") else "⚠️",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

st.markdown(
    """
**Navigate deeper:**

1. 📊 Business Health &nbsp; · &nbsp; 2. 🔻 Funnel Drop-off &nbsp; · &nbsp;
3. 📈 Demand Forecast &nbsp; · &nbsp; 4. ⚠️ Churn Risk &nbsp; · &nbsp;
5. 🧪 Experiment Readout

Repo: [github.com/kelvinasiedu/pulsecommerce](https://github.com/kelvinasiedu/pulsecommerce) ·
Methodology: `docs/methodology.md` ·
KPI dictionary: `docs/kpi_dictionary.md`
"""
)
