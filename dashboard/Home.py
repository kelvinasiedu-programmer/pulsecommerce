"""PulseCommerce — overview dashboard.

Summarizes the trailing-28-day state of the synthetic store across the five
analytical layers, with drill-through links into each page.
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
from theme import COLORS, apply_theme, sidebar_brand, style_fig  # noqa: E402

apply_theme("Overview", "📈")
sidebar_brand()


def _ensure_bootstrapped() -> None:
    if (PROCESSED_DIR / "kpi_cards.parquet").exists():
        return
    with st.spinner("First-time setup — generating data and running the full 5-layer pipeline…"):
        from pulsecommerce.cli import main

        main(["all", "--small"])


_ensure_bootstrapped()


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
by_category = load_parquet("kpi_category")
funnel_overall = load_parquet("funnel_overall")
experiment = load_json("experiment")
churn_metrics = load_json("churn_metrics")
funnel_insights = load_json("funnel_insights")

if cards.empty:
    st.error("Pipeline artifacts not found. Run `python -m pulsecommerce.cli all` first.")
    st.stop()


st.markdown(
    f"""
    <style>
      .hp-welcome {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 4px 2px 20px 2px; gap: 16px; flex-wrap: wrap;
      }}
      .hp-eyebrow {{
        font-size: 0.72rem; font-weight: 600; color: {COLORS['primary']};
        text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;
      }}
      .hp-hi {{ font-size: 1.6rem; font-weight: 700; color: {COLORS['text']};
                letter-spacing: -0.02em; margin-bottom: 4px; }}
      .hp-sub {{ font-size: 0.9rem; color: {COLORS['text_muted']}; max-width: 56ch; }}
      .hp-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}

      /* Pills: both variants meet WCAG 2.5.5 AA (44px minimum touch target) */
      .hp-pill {{
        background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
        border-radius: 10px; padding: 10px 14px; font-size: 0.82rem;
        font-weight: 500; color: {COLORS['text']};
        display: inline-flex; align-items: center; gap: 8px;
        min-height: 44px; box-sizing: border-box;
      }}
      .hp-pill-link {{
        text-decoration: none; transition: border-color 0.15s, background 0.15s;
      }}
      .hp-pill-link:hover {{
        border-color: {COLORS['primary']};
        background: {COLORS['primary_light']};
      }}
      .hp-pill-link:focus-visible {{
        outline: 2px solid {COLORS['primary']};
        outline-offset: 2px;
      }}

      .hp-kpigrid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px; margin-bottom: 22px;
      }}
      .hp-kpi {{
        background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
        border-radius: 14px; padding: 18px 20px;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
        display: flex; gap: 14px; align-items: flex-start;
        margin: 0;
      }}
      .hp-kpi dt, .hp-kpi dd {{ margin: 0; }}
      .hp-kpi .ic {{
        width: 44px; height: 44px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
      }}
      .hp-kpi .ic svg {{ width: 22px; height: 22px; }}
      /* Icon tones — derived palette; kept as a documented secondary scale */
      .hp-kpi .ic.indigo  {{ background: {COLORS['primary_light']}; color: {COLORS['primary_dark']}; }}
      .hp-kpi .ic.emerald {{ background: {COLORS['success_bg']}; color: #047857; }}
      .hp-kpi .ic.amber   {{ background: {COLORS['warning_bg']}; color: #B45309; }}
      .hp-kpi .ic.sky     {{ background: {COLORS['info_bg']}; color: #1D4ED8; }}
      .hp-kpi .ic.pink    {{ background: #FDF2F8; color: #BE185D; }}
      .hp-kpi .ic.violet  {{ background: #F5F3FF; color: #6D28D9; }}
      .hp-kpi .ic.slate   {{ background: #F1F5F9; color: #334155; }}
      .hp-kpi .lbl {{
        font-size: 0.75rem; font-weight: 600; color: {COLORS['text_muted']};
        text-transform: uppercase; letter-spacing: 0.06em;
      }}
      .hp-kpi .val {{
        font-size: 1.5rem; font-weight: 700; color: {COLORS['text']};
        letter-spacing: -0.02em; margin: 2px 0 6px 0; line-height: 1.1;
      }}
      /* Delta chip: direction communicated via three redundant channels — color,
         arrow glyph, and the word "up"/"down" — so color-blind users and
         screen-reader users get the same information. */
      .hp-kpi .chip {{
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 0.75rem; font-weight: 700; padding: 3px 9px;
        border-radius: 999px;
      }}
      .hp-kpi .chip .arrow {{ font-size: 0.9rem; line-height: 1; }}
      .hp-kpi .chip.up   {{ background: {COLORS['success_bg']}; color: #047857; }}
      .hp-kpi .chip.down {{ background: {COLORS['danger_bg']}; color: #B91C1C; }}
      .hp-kpi .vs {{
        font-size: 0.72rem; color: {COLORS['text_muted']}; margin-left: 6px;
      }}

      .hp-panel {{
        background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
        border-radius: 14px; padding: 18px 20px; margin-bottom: 16px;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
      }}
      .hp-panel h4 {{
        font-size: 0.98rem; font-weight: 600; color: {COLORS['text']};
        margin: 0 0 4px 0;
      }}
      .hp-panel .sub {{ font-size: 0.82rem; color: {COLORS['text_muted']}; }}

      .hp-cat-stripe {{
        display: flex; border-radius: 12px; overflow: hidden; height: 38px;
        border: 1px solid {COLORS['border']};
      }}
      .hp-cat-seg {{
        display: flex; align-items: center; justify-content: center;
        color: white; font-size: 0.78rem; font-weight: 600;
        padding: 0 8px; white-space: nowrap; overflow: hidden;
        text-overflow: ellipsis;
      }}
      .hp-cat-legend {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(170px,1fr));
        gap: 10px; margin-top: 12px;
      }}
      .hp-cat-leg-item {{
        display: flex; align-items: center; gap: 8px;
        font-size: 0.82rem; color: {COLORS['text_muted']};
      }}
      .hp-cat-leg-dot {{
        width: 10px; height: 10px; border-radius: 3px;
      }}
      .hp-cat-leg-val {{ color: {COLORS['text']}; font-weight: 600; }}

      .hp-verdict-pill {{
        display: inline-flex; align-items: center; gap: 8px;
        padding: 6px 12px; border-radius: 999px; font-weight: 600;
        font-size: 0.82rem;
      }}
      .hp-verdict-pill.ship    {{ background: {COLORS['success_bg']}; color: #065F46; }}
      .hp-verdict-pill.iterate {{ background: {COLORS['warning_bg']}; color: #92400E; }}
      .hp-verdict-pill.reject  {{ background: {COLORS['danger_bg']}; color: #991B1B; }}

      .hp-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 2px; border-bottom: 1px solid {COLORS['border']};
      }}
      .hp-row:last-child {{ border-bottom: none; }}
      .hp-row .nm {{ font-weight: 500; color: {COLORS['text']}; font-size: 0.88rem; }}
      .hp-row .su {{ font-size: 0.76rem; color: {COLORS['text_muted']}; }}
      .hp-row .vl {{ font-weight: 600; color: {COLORS['text']}; font-size: 0.88rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


days_of_history = len(daily) if not daily.empty else 0

st.markdown(
    f"""
    <div class="hp-welcome">
      <div>
        <div class="hp-eyebrow">Portfolio project · synthetic dataset</div>
        <div class="hp-hi">PulseCommerce Overview</div>
        <div class="hp-sub">Trailing 28-day state of the store, summarized across the five analytical layers.</div>
      </div>
      <div class="hp-actions">
        <span class="hp-pill" aria-label="Data window">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round"
               stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
          {days_of_history} days of history
        </span>
        <a class="hp-pill hp-pill-link" href="https://github.com/kelvinasiedu-programmer/pulsecommerce"
           target="_blank" rel="noopener noreferrer" aria-label="Open source repository on GitHub">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 .5C5.73.5.5 5.73.5 12a11.5 11.5 0 0 0 7.86 10.93c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.36-3.88-1.36-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.24 3.34.95.1-.74.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.18-3.1-.12-.3-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.97 10.97 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.62 1.59.23 2.75.11 3.05.74.81 1.18 1.84 1.18 3.1 0 4.43-2.69 5.4-5.26 5.69.41.35.78 1.05.78 2.12v3.14c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5z"/>
          </svg>
          GitHub
        </a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _fmt(value: float, fmt: str) -> str:
    if fmt == "currency":
        return f"${value:,.0f}"
    if fmt == "percent":
        return f"{value * 100:.2f}%"
    return f"{value:,.0f}"


_SVG = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">{}</svg>'
)
kpi_icons = {
    "revenue": (_SVG.format('<line x1="12" y1="1" x2="12" y2="23"/>'
                            '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'),
                "indigo"),
    "gross_margin": (_SVG.format('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
                                 '<polyline points="17 6 23 6 23 12"/>'), "emerald"),
    "orders": (_SVG.format('<path d="M16.5 9.4l-9-5.19"/>'
                           '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
                           '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>'
                           '<line x1="12" y1="22.08" x2="12" y2="12"/>'), "sky"),
    "sessions": (_SVG.format('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
                             '<circle cx="9" cy="7" r="4"/>'
                             '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
                             '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'), "violet"),
    "aov": (_SVG.format('<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>'
                        '<line x1="1" y1="10" x2="23" y2="10"/>'), "amber"),
    "conversion_rate": (_SVG.format('<circle cx="12" cy="12" r="10"/>'
                                    '<circle cx="12" cy="12" r="6"/>'
                                    '<circle cx="12" cy="12" r="2"/>'), "pink"),
    "cancel_rate": (_SVG.format('<circle cx="12" cy="12" r="10"/>'
                                '<line x1="12" y1="8" x2="12" y2="12"/>'
                                '<line x1="12" y1="16" x2="12.01" y2="16"/>'), "slate"),
}

# Pick the 4 headline KPIs
headline_keys = ["revenue", "orders", "conversion_rate", "aov"]
id_col = "metric" if "metric" in cards.columns else ("id" if "id" in cards.columns else None)
if id_col:
    cards_by_key = {row[id_col]: row for _, row in cards.iterrows()}
    headline = [cards_by_key[k] for k in headline_keys if k in cards_by_key]
    if len(headline) < 4:
        headline = [cards.iloc[i] for i in range(min(4, len(cards)))]
else:
    headline = [cards.iloc[i] for i in range(min(4, len(cards)))]

kpi_html = '<div class="hp-kpigrid" role="list">'
for row in headline:
    key = row[id_col] if id_col else row["label"].lower().replace(" ", "_")
    icon, tone = kpi_icons.get(key, (_SVG.format('<circle cx="12" cy="12" r="10"/>'), "indigo"))
    val = _fmt(row["value"], row["format"])
    delta = row["delta_pct"]
    chip_cls = "up" if delta >= 0 else "down"
    arrow = "↑" if delta >= 0 else "↓"
    direction = "up" if delta >= 0 else "down"
    kpi_html += (
        f'<dl class="hp-kpi" role="listitem" aria-label="{row["label"]}: {val}">'
        f'  <div class="ic {tone}" aria-hidden="true">{icon}</div>'
        f'  <div style="flex:1; min-width:0;">'
        f'    <dt class="lbl">{row["label"]}</dt>'
        f'    <dd class="val">{val}</dd>'
        f'    <dd>'
        f'      <span class="chip {chip_cls}">'
        f'        <span class="arrow" aria-hidden="true">{arrow}</span> '
        f'{direction} {abs(delta) * 100:.1f}%'
        f'      </span>'
        f'      <span class="vs">vs. prior period</span>'
        f'    </dd>'
        f'  </div>'
        f'</dl>'
    )
kpi_html += "</div>"
st.markdown(kpi_html, unsafe_allow_html=True)


left, right = st.columns([7, 5])

with left:
    st.markdown(
        """
        <div class="hp-panel">
          <h4>Revenue insights</h4>
          <div class="sub">Daily revenue with the peak-performing day highlighted.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not daily.empty:
        dd = daily.copy()
        dd["metric_date"] = pd.to_datetime(dd["metric_date"])
        dd = dd.sort_values("metric_date")
        peak_idx = dd["revenue"].idxmax()
        peak_date = dd.loc[peak_idx, "metric_date"]
        peak_rev = dd.loc[peak_idx, "revenue"]
        colors = [
            COLORS["primary"] if d == peak_date else "#C7D2FE"
            for d in dd["metric_date"]
        ]
        fig = go.Figure(go.Bar(
            x=dd["metric_date"], y=dd["revenue"],
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="%{x|%b %d}<br>$%{y:,.0f}<extra></extra>",
        ))
        fig.add_annotation(
            x=peak_date, y=peak_rev, yshift=18,
            text=f"<b>Peak day</b><br>${peak_rev:,.0f}",
            showarrow=False, font=dict(size=10, color="white"),
            bgcolor=COLORS["primary"],
            bordercolor=COLORS["primary"],
            borderpad=6,
        )
        style_fig(fig, height=320, margin=dict(l=10, r=10, t=40, b=10),
                  bargap=0.3)
        fig.update_yaxes(tickprefix="$", separatethousands=True, title_text=None)
        fig.update_xaxes(title_text=None)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown(
        """
        <div class="hp-panel">
          <h4>Sales performance</h4>
          <div class="sub">Session-to-purchase conversion, last 28 days.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Donut gauge for conversion rate
    conv_row = None
    if id_col and "conversion_rate" in cards_by_key:
        conv_row = cards_by_key["conversion_rate"]
    conv_val = float(conv_row["value"]) if conv_row is not None else 0.0
    conv_pct = conv_val * 100
    target = 3.5  # visual target for the gauge backing
    gauge_filled = min(conv_pct / target, 1.0) if target > 0 else 0.0

    fig_d = go.Figure(go.Pie(
        values=[gauge_filled, 1 - gauge_filled],
        hole=0.78,
        sort=False,
        direction="clockwise",
        rotation=180,
        marker=dict(colors=[COLORS["primary"], COLORS["primary_light"]],
                    line=dict(color="white", width=0)),
        textinfo="none", hoverinfo="skip",
    ))
    fig_d.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=COLORS["surface"], plot_bgcolor=COLORS["surface"],
        height=220,
        annotations=[
            dict(text=f"<b>{conv_pct:.2f}%</b>", x=0.5, y=0.55, showarrow=False,
                 font=dict(size=28, color=COLORS["text"], family="Inter")),
            dict(text="Conversion", x=0.5, y=0.38, showarrow=False,
                 font=dict(size=12, color=COLORS["text_muted"], family="Inter")),
        ],
    )
    st.plotly_chart(fig_d, use_container_width=True)

    # Mini stats under gauge
    orders_row = cards_by_key.get("orders") if id_col else None
    sessions_row = cards_by_key.get("sessions") if id_col else None
    aov_row = cards_by_key.get("aov") if id_col else None
    orders_v = _fmt(orders_row["value"], orders_row["format"]) if orders_row is not None else "—"
    sessions_v = _fmt(sessions_row["value"], sessions_row["format"]) if sessions_row is not None else "—"
    aov_v = _fmt(aov_row["value"], aov_row["format"]) if aov_row is not None else "—"
    st.markdown(
        f"""
        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top:-10px;">
          <div style="text-align:center; padding:10px 4px; background:#F8FAFC;
                      border-radius:10px; border:1px solid {COLORS['border']};">
            <div style="font-size:0.72rem; color:{COLORS['text_muted']}; text-transform:uppercase;
                        letter-spacing:0.06em;">Orders</div>
            <div style="font-size:1rem; font-weight:700; color:{COLORS['text']};">{orders_v}</div>
          </div>
          <div style="text-align:center; padding:10px 4px; background:#F8FAFC;
                      border-radius:10px; border:1px solid {COLORS['border']};">
            <div style="font-size:0.72rem; color:{COLORS['text_muted']}; text-transform:uppercase;
                        letter-spacing:0.06em;">Sessions</div>
            <div style="font-size:1rem; font-weight:700; color:{COLORS['text']};">{sessions_v}</div>
          </div>
          <div style="text-align:center; padding:10px 4px; background:#F8FAFC;
                      border-radius:10px; border:1px solid {COLORS['border']};">
            <div style="font-size:0.72rem; color:{COLORS['text_muted']}; text-transform:uppercase;
                        letter-spacing:0.06em;">AOV</div>
            <div style="font-size:1rem; font-weight:700; color:{COLORS['text']};">{aov_v}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if not by_category.empty:
    cat = by_category.sort_values("revenue", ascending=False).copy()
    total = float(cat["revenue"].sum())
    palette = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EC4899",
               "#8B5CF6", "#14B8A6", "#F97316", "#6366F1", "#EF4444"]
    cat["color"] = [palette[i % len(palette)] for i in range(len(cat))]
    cat["share"] = cat["revenue"] / total

    stripe_segs = "".join([
        f'<div class="hp-cat-seg" style="flex:{r["share"]:.4f}; background:{r["color"]};" '
        f'title="{r["category"]}: ${r["revenue"]:,.0f} ({r["share"] * 100:.1f}%)">'
        f'{r["category"] if r["share"] > 0.08 else ""}</div>'
        for _, r in cat.iterrows()
    ])
    legend = "".join([
        f'<div class="hp-cat-leg-item">'
        f'<span class="hp-cat-leg-dot" style="background:{r["color"]};"></span>'
        f'<span>{r["category"]}</span>'
        f'<span class="hp-cat-leg-val" style="margin-left:auto;">${r["revenue"]:,.0f}</span>'
        f'</div>'
        for _, r in cat.iterrows()
    ])
    st.markdown(
        f"""
        <div class="hp-panel">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px;">
            <div>
              <h4>Category revenue mix</h4>
              <div class="sub">Proportional share of trailing 28-day revenue · total ${total:,.0f}</div>
            </div>
          </div>
          <div class="hp-cat-stripe">{stripe_segs}</div>
          <div class="hp-cat-legend">{legend}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


bottom_left, bottom_right = st.columns([7, 5])

with bottom_left:
    st.markdown('<div class="hp-panel">', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <div>
            <h4>Top performing days</h4>
            <div class="sub">Your best-converting days in the trailing 28-day window.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not daily.empty:
        top_days = (
            daily.assign(metric_date=pd.to_datetime(daily["metric_date"]))
            .nlargest(7, "revenue")
            .sort_values("metric_date", ascending=False)
        )
        target_rev = daily["revenue"].median()
        for _, row in top_days.iterrows():
            status_ok = row["revenue"] >= target_rev
            status_cls = "up" if status_ok else "down"
            status_label = "Above median" if status_ok else "Below median"
            chip_bg, chip_fg = (
                (COLORS["success_bg"], "#065F46") if status_ok
                else (COLORS["danger_bg"], "#991B1B")
            )
            st.markdown(
                f"""
                <div class="hp-row">
                  <div style="display:flex; gap:12px; align-items:center;">
                    <div style="width:36px; height:36px; border-radius:10px;
                                background:{COLORS['primary_light']};
                                display:flex; align-items:center; justify-content:center;
                                font-weight:700; color:{COLORS['primary_dark']};
                                font-size:0.78rem;">
                      {row['metric_date'].strftime('%d')}
                    </div>
                    <div>
                      <div class="nm">{row['metric_date'].strftime('%A · %b %d, %Y')}</div>
                      <div class="su">{int(row['orders']):,} orders · {int(row['sessions']):,} sessions</div>
                    </div>
                  </div>
                  <div style="display:flex; gap:16px; align-items:center;">
                    <span style="background:{chip_bg}; color:{chip_fg}; padding:3px 10px;
                                 border-radius:999px; font-size:0.72rem; font-weight:600;">
                      {status_label}
                    </span>
                    <div class="vl" style="min-width:90px; text-align:right;">
                      ${row['revenue']:,.0f}
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _ = status_cls  # variable referenced for style completeness
    st.markdown("</div>", unsafe_allow_html=True)

with bottom_right:
    # Funnel snapshot
    st.markdown('<div class="hp-panel">', unsafe_allow_html=True)
    st.markdown(
        """
        <h4>Funnel snapshot</h4>
        <div class="sub">Session → purchase, five stages.</div>
        """,
        unsafe_allow_html=True,
    )
    if not funnel_overall.empty:
        labels = funnel_overall["stage"].str.replace("_", " ").str.title()
        fig_f = go.Figure(go.Funnel(
            y=labels, x=funnel_overall["count"],
            textinfo="value+percent previous",
            textfont=dict(color="white", size=11),
            marker=dict(
                color=["#3730A3", "#4F46E5", "#6366F1", "#818CF8", "#A5B4FC"],
                line=dict(color="white", width=1),
            ),
            connector=dict(line=dict(color=COLORS["border"], width=1)),
        ))
        style_fig(fig_f, height=260, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_f, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Experiment verdict card
    rec = (experiment.get("recommendation") or "").lower()
    rec_cls = {"ship": "ship", "iterate": "iterate", "reject": "reject"}.get(rec, "iterate")
    rec_label = {"ship": "✓ SHIP", "iterate": "◐ ITERATE", "reject": "✕ REJECT"}.get(rec, "—")
    auc = churn_metrics.get("roc_auc_xgb", 0)
    biggest = funnel_insights.get("biggest_drop_stage", "—").replace("_", " ").title()
    lost = funnel_insights.get("estimated_lost_revenue", 0)

    st.markdown(
        f"""
        <div class="hp-panel" style="margin-bottom:0;">
          <h4>Signals</h4>
          <div style="margin-top:10px; display:flex; flex-direction:column; gap:10px;">
            <div class="hp-row">
              <div>
                <div class="nm">Experiment verdict</div>
                <div class="su">Targeted retention promo</div>
              </div>
              <span class="hp-verdict-pill {rec_cls}">{rec_label}</span>
            </div>
            <div class="hp-row">
              <div>
                <div class="nm">Churn model (XGBoost)</div>
                <div class="su">ROC-AUC</div>
              </div>
              <div class="vl">{auc:.3f}</div>
            </div>
            <div class="hp-row">
              <div>
                <div class="nm">Biggest funnel leak</div>
                <div class="su">{biggest}</div>
              </div>
              <div class="vl">${lost:,.0f}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="pc-section-title">Jump into a layer</div>
    <div class="pc-section-sub">The five analytical surfaces that make up the platform.</div>
    """,
    unsafe_allow_html=True,
)
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

st.markdown("<div style='height: 22px;'></div>", unsafe_allow_html=True)
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
