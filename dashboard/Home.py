"""PulseCommerce — executive landing page.

Professional BI platform landing: at-a-glance health strip, unified narrative,
and deep-link navigation into the five analytical layers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from pulsecommerce.config import PROCESSED_DIR  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import COLORS, apply_theme, hero, insight_card, kpi_row, section, sidebar_brand, style_fig  # noqa: E402

apply_theme("Overview", "📈")
sidebar_brand()


# --------------------------------------------------------------------------- #
# Cold-start bootstrap
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
# Hero
# --------------------------------------------------------------------------- #
hero(
    eyebrow="Commerce Intelligence Platform",
    title="PulseCommerce — the full story, one screen",
    subtitle=(
        "One warehouse, five analytical layers. From business health to targeted experiments — "
        "every number traces back to a single source of truth."
    ),
)

if cards.empty:
    st.error("Pipeline artifacts not found. Run `python -m pulsecommerce.cli all` first.")
    st.stop()


# --------------------------------------------------------------------------- #
# Executive KPI strip
# --------------------------------------------------------------------------- #
def _fmt(value: float, fmt: str) -> str:
    if fmt == "currency":
        return f"${value:,.0f}"
    if fmt == "percent":
        return f"{value * 100:.2f}%"
    return f"{value:,.0f}"


section("Trailing 28-day business pulse", "All metrics compared to the prior equivalent 28-day window.")
kpi_items = [
    {
        "label": row["label"],
        "value": _fmt(row["value"], row["format"]),
        "delta": f"{row['delta_pct'] * 100:+.1f}% vs. Previous Period",
    }
    for _, row in cards.iterrows()
]
kpi_row(kpi_items)


# --------------------------------------------------------------------------- #
# Revenue trend + narrative
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 22px;'></div>", unsafe_allow_html=True)
left, right = st.columns([3, 2])

with left:
    section("Daily revenue", "Gradient area with 7-day rolling average overlay.")
    if not daily.empty:
        daily["metric_date"] = pd.to_datetime(daily["metric_date"])
        dd = daily.sort_values("metric_date").copy()
        dd["rolling"] = dd["revenue"].rolling(window=7, min_periods=1).mean()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dd["metric_date"], y=dd["revenue"],
            mode="lines", name="Daily",
            line=dict(color=COLORS["primary"], width=1.2),
            fill="tozeroy", fillcolor="rgba(79,70,229,0.10)",
        ))
        fig.add_trace(go.Scatter(
            x=dd["metric_date"], y=dd["rolling"],
            mode="lines", name="7-day avg",
            line=dict(color=COLORS["primary_dark"], width=2.5),
        ))
        style_fig(fig, height=320, margin=dict(l=10, r=10, t=10, b=10))
        fig.update_yaxes(title_text="Revenue ($)", tickprefix="$", separatethousands=True)
        fig.update_xaxes(title_text=None)
        st.plotly_chart(fig, use_container_width=True)

with right:
    section("The five-layer narrative", "Each number below deep-links to its dedicated page.")
    biggest = funnel_insights.get("biggest_drop_stage", "—").replace("_", " ").title()
    lost = funnel_insights.get("estimated_lost_revenue", 0)
    auc = churn_metrics.get("roc_auc_xgb", 0)
    churn_rate = churn_metrics.get("churn_rate", 0)
    rec = (experiment.get("recommendation") or "").lower()
    rec_label = {"ship": "SHIP", "iterate": "ITERATE", "reject": "REJECT"}.get(rec, "—")
    rec_tone = {"ship": "success", "iterate": "warning", "reject": "danger"}.get(rec, "")

    insight_card("Health", "28-day KPIs in the strip above — revenue area chart tracks the full series.")
    insight_card(
        "Funnel",
        f"Biggest drop at <b>{biggest}</b>. Closing the worst-segment gap is worth <b>${lost:,.0f}</b>.",
    )
    insight_card("Forecast", "12-week revenue projections per category, backtested via walk-forward MAPE.")
    insight_card(
        "Churn",
        f"XGBoost ROC-AUC <b>{auc:.3f}</b> · baseline churn <b>{churn_rate * 100:.1f}%</b>.",
    )
    insight_card(
        f"Experiment — {rec_label}",
        experiment.get("rationale", "Retention promo result — see the Experiment page."),
        tone=rec_tone,
    )


# --------------------------------------------------------------------------- #
# Funnel + experiment summary
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    section("Conversion funnel", "Session → purchase — stage counts and drop-offs.")
    if not funnel_overall.empty:
        labels = funnel_overall["stage"].str.replace("_", " ").str.title()
        fig = go.Figure(go.Funnel(
            y=labels, x=funnel_overall["count"],
            textinfo="value+percent previous",
            textfont=dict(color="white", size=12),
            marker=dict(
                color=["#3730A3", "#4F46E5", "#6366F1", "#818CF8", "#A5B4FC"],
                line=dict(color="white", width=1),
            ),
            connector=dict(line=dict(color=COLORS["border"], width=1)),
        ))
        style_fig(fig, height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

with c2:
    section("Experiment readout", "Primary metric + guardrail snapshot.")
    if experiment:
        primary = experiment.get("primary", {})
        guardrails = experiment.get("guardrails", [])

        g1, g2 = st.columns(2)
        g1.metric(
            primary.get("name", "primary").replace("_", " ").title(),
            f"{primary.get('treatment_mean', 0):.4f}",
            f"{primary.get('rel_lift', 0) * 100:+.2f}% vs control",
        )
        g2.metric(
            "Statistical p-value",
            f"{primary.get('p_value', 1):.3f}",
            "Significant" if primary.get("is_significant") else "Not significant",
            delta_color="normal" if primary.get("is_significant") else "off",
        )

        rows = []
        for g in guardrails:
            rows.append({
                "Metric": g.get("name", "").replace("_", " ").title(),
                "Lift": f"{g.get('rel_lift', 0) * 100:+.2f}%",
                "p": f"{g.get('p_value', 1):.3f}",
                "Status": "PASS" if g.get("direction_ok") else "FAIL",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Navigation grid
# --------------------------------------------------------------------------- #
st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
section("Jump into a layer", "The five analytical surfaces that make up the platform.")

nav_items = [
    ("01", "📊", "Business Health", "Revenue, AOV, conversion — period vs. period with channel/category mix."),
    ("02", "🔻", "Funnel Drop-off", "Five-stage event funnel with segmented device × channel heatmap."),
    ("03", "📈", "Demand Forecast", "Seasonal-naive vs Holt-Winters vs XGBoost, selected by backtest MAPE."),
    ("04", "⚠️", "Churn Risk", "RFM + behavioral features, ROC-AUC leaderboard, top at-risk list."),
    ("05", "🧪", "Experiment Readout", "Welch t-test primary metric with guardrails and verdict."),
]
html = '<div class="pc-navgrid">'
for n, icon, title, desc in nav_items:
    html += (
        f'<div class="pc-navcard">'
        f'<div class="n">{n} · {icon}</div>'
        f'<div class="t">{title}</div>'
        f'<div class="d">{desc}</div>'
        f'</div>'
    )
html += "</div>"
st.markdown(html, unsafe_allow_html=True)

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div style="display:flex; justify-content:space-between; font-size:0.78rem;
                color:{COLORS['text_muted']}; padding-top:14px; border-top:1px solid {COLORS['border']};">
      <div>PulseCommerce · synthetic dataset · {len(daily) if not daily.empty else 0} days of history</div>
      <div>
        <a href="https://github.com/kelvinasiedu-programmer/pulsecommerce" target="_blank"
           style="color:{COLORS['text_muted']}; text-decoration:none;">GitHub</a>
        &nbsp;·&nbsp; Methodology &nbsp;·&nbsp; KPI Dictionary
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
