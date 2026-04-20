"""Shared design system for PulseCommerce — a professional BI platform.

Light, card-based UI inspired by Stripe / Shopify analytics. Every page imports
`apply_theme()` at the top and uses the helpers below for consistent visuals.
"""

from __future__ import annotations

from typing import Any, Sequence

import plotly.graph_objects as go
import streamlit as st

COLORS = {
    # Brand
    "primary": "#4F46E5",          # Indigo
    "primary_dark": "#3730A3",
    "primary_light": "#EEF2FF",
    "accent": "#0EA5E9",            # Sky
    # Neutrals
    "bg": "#F8FAFC",
    "surface": "#FFFFFF",
    "border": "#E5E7EB",
    "border_strong": "#D1D5DB",
    "text": "#0F172A",
    "text_muted": "#475569",
    "text_subtle": "#64748B",
    # Status
    "success": "#10B981",
    "success_bg": "#ECFDF5",
    "warning": "#F59E0B",
    "warning_bg": "#FFFBEB",
    "danger": "#EF4444",
    "danger_bg": "#FEF2F2",
    "info": "#3B82F6",
    "info_bg": "#EFF6FF",
}

SEQ_INDIGO = ["#EEF2FF", "#C7D2FE", "#A5B4FC", "#818CF8", "#6366F1", "#4F46E5", "#4338CA", "#3730A3"]
SEQ_TEAL = ["#F0FDFA", "#CCFBF1", "#99F6E4", "#5EEAD4", "#2DD4BF", "#14B8A6", "#0D9488", "#0F766E"]

CATEGORICAL = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6", "#14B8A6", "#F97316"]


def apply_theme(page_title: str, page_icon: str) -> None:
    """Call once at the top of every page."""
    st.set_page_config(
        page_title=f"{page_title} · PulseCommerce",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


_GLOBAL_CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"]  {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {COLORS['text']};
  }}

  /* Page background */
  .stApp {{
    background: {COLORS['bg']};
  }}

  /* Main block — fluid width so content expands when the sidebar is collapsed */
  .main .block-container {{
    padding-top: 1.5rem;
    padding-bottom: 4rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
    max-width: 100%;
  }}
  @media (min-width: 1600px) {{
    .main .block-container {{
      padding-left: 4rem;
      padding-right: 4rem;
    }}
  }}

  /* Hide only the three-dot menu, Deploy button, and footer. */
  #MainMenu {{ display: none !important; }}
  footer {{ display: none !important; }}
  .stDeployButton {{ display: none !important; }}
  header[data-testid="stHeader"] {{
    background: transparent;
    z-index: 100;
  }}
  /* Hide only the toolbar actions (deploy/menu), NOT the sidebar toggle */
  [data-testid="stToolbarActions"] {{ display: none !important; }}

  /* Force the "re-open sidebar" button to always be visible and prominent
     so users are never stranded after collapsing the sidebar. */
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],
  button[kind="header"][data-testid="baseButton-headerNoPadding"] {{
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    z-index: 999 !important;
  }}
  [data-testid="stSidebarCollapsedControl"] button,
  [data-testid="collapsedControl"] button {{
    background: {COLORS['primary']} !important;
    color: white !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(79,70,229,0.35) !important;
  }}
  [data-testid="stSidebarCollapsedControl"] button svg,
  [data-testid="collapsedControl"] button svg {{
    color: white !important;
    fill: white !important;
  }}
  /* Sidebar's own collapse chevron — keep obvious */
  [data-testid="stSidebarCollapseButton"] {{
    visibility: visible !important;
    display: flex !important;
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{
    background: #FFFFFF;
    border-right: 1px solid {COLORS['border']};
  }}
  /* Only pin width when the sidebar is actually expanded, so it can
     collapse to 0 and let main content flush left. */
  section[data-testid="stSidebar"][aria-expanded="true"] {{
    min-width: 260px !important;
  }}
  /* Ensure the collapsed sidebar has no visible footprint */
  section[data-testid="stSidebar"][aria-expanded="false"] {{
    min-width: 0 !important;
    width: 0 !important;
    border-right: none !important;
  }}
  /* Streamlit's auto page-navigation list */
  [data-testid="stSidebarNav"] {{
    padding-top: 8px;
  }}
  [data-testid="stSidebarNav"] ul {{ padding: 0 8px; }}
  [data-testid="stSidebarNav"] a {{
    color: {COLORS['text']} !important;
    font-weight: 500;
    border-radius: 8px;
    padding: 6px 10px;
  }}
  [data-testid="stSidebarNav"] a:hover {{
    background: {COLORS['primary_light']};
  }}

  section[data-testid="stSidebar"] .stRadio label,
  section[data-testid="stSidebar"] p {{
    color: {COLORS['text']} !important;
  }}

  /* Typography */
  h1 {{
    font-weight: 700 !important;
    font-size: 1.75rem !important;
    letter-spacing: -0.02em;
    color: {COLORS['text']} !important;
    margin-bottom: 0.25rem !important;
  }}
  h2 {{
    font-weight: 600 !important;
    font-size: 1.25rem !important;
    letter-spacing: -0.01em;
    color: {COLORS['text']} !important;
  }}
  h3, h4 {{
    font-weight: 600 !important;
    color: {COLORS['text']} !important;
  }}

  /* KPI metric override */
  [data-testid="stMetric"] {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
  }}
  [data-testid="stMetricLabel"] {{
    font-size: 0.8rem !important;
    color: {COLORS['text_muted']} !important;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  [data-testid="stMetricValue"] {{
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: {COLORS['text']} !important;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  [data-testid="stMetricDelta"] {{
    font-size: 0.8rem !important;
    font-weight: 500 !important;
  }}

  /* Divider */
  hr {{ border-top: 1px solid {COLORS['border']} !important; }}

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 1px solid {COLORS['border']};
  }}
  .stTabs [data-baseweb="tab"] {{
    background: transparent;
    border: none;
    color: {COLORS['text_muted']};
    font-weight: 500;
    padding: 10px 16px;
  }}
  .stTabs [aria-selected="true"] {{
    color: {COLORS['primary']} !important;
    border-bottom: 2px solid {COLORS['primary']} !important;
  }}

  /* DataFrame */
  .stDataFrame {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    overflow: hidden;
  }}

  /* Plotly chart containers */
  .js-plotly-plot {{ border-radius: 8px; }}

  /* Buttons */
  .stButton > button {{
    background: {COLORS['primary']};
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    padding: 8px 16px;
    transition: all 0.15s;
  }}
  .stButton > button:hover {{
    background: {COLORS['primary_dark']};
    transform: translateY(-1px);
  }}

  /* Selectbox / slider labels */
  .stSelectbox label, .stSlider label {{
    color: {COLORS['text_muted']} !important;
    font-weight: 500;
    font-size: 0.85rem;
  }}

  /* Caption */
  .stCaption, [data-testid="stCaptionContainer"] {{
    color: {COLORS['text_muted']} !important;
  }}

  /* Card container helper */
  .pc-card {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 20px 22px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    margin-bottom: 16px;
  }}
  .pc-card-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {COLORS['text']};
    margin-bottom: 4px;
  }}
  .pc-card-sub {{
    font-size: 0.8rem;
    color: {COLORS['text_muted']};
    margin-bottom: 14px;
  }}

  /* Page hero */
  .pc-hero {{
    background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 22px;
  }}
  .pc-hero-eyebrow {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: {COLORS['primary']};
    text-transform: uppercase;
  }}
  .pc-hero-title {{
    font-size: 1.65rem;
    font-weight: 700;
    color: {COLORS['text']};
    margin: 4px 0 6px 0;
    letter-spacing: -0.02em;
  }}
  .pc-hero-sub {{
    font-size: 0.95rem;
    color: {COLORS['text_muted']};
    max-width: 780px;
  }}

  /* Insight card */
  .pc-insight {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-left: 3px solid {COLORS['primary']};
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
  }}
  .pc-insight.success {{ border-left-color: {COLORS['success']}; }}
  .pc-insight.warning {{ border-left-color: {COLORS['warning']}; }}
  .pc-insight.danger  {{ border-left-color: {COLORS['danger']}; }}
  .pc-insight-title {{
    font-weight: 600;
    font-size: 0.9rem;
    color: {COLORS['text']};
    margin-bottom: 2px;
  }}
  .pc-insight-body {{
    color: {COLORS['text_muted']};
    font-size: 0.88rem;
    line-height: 1.5;
  }}

  /* Badges */
  .pc-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }}
  .pc-badge.success {{ background: {COLORS['success_bg']}; color: #065F46; }}
  .pc-badge.warning {{ background: {COLORS['warning_bg']}; color: #92400E; }}
  .pc-badge.danger  {{ background: {COLORS['danger_bg']};  color: #991B1B; }}
  .pc-badge.info    {{ background: {COLORS['info_bg']};    color: #1E40AF; }}
  .pc-badge.neutral {{ background: #F1F5F9; color: {COLORS['text_muted']}; }}

  /* Verdict banner */
  .pc-verdict {{
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 22px;
    border: 1px solid transparent;
  }}
  .pc-verdict .label {{
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 700;
    opacity: 0.8;
  }}
  .pc-verdict .title {{
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 2px 0 6px 0;
  }}
  .pc-verdict .sub {{
    font-size: 0.95rem;
    opacity: 0.85;
  }}
  .pc-verdict.ship    {{ background: {COLORS['success_bg']}; border-color: #A7F3D0; color: #064E3B; }}
  .pc-verdict.iterate {{ background: {COLORS['warning_bg']}; border-color: #FDE68A; color: #78350F; }}
  .pc-verdict.reject  {{ background: {COLORS['danger_bg']};  border-color: #FECACA; color: #7F1D1D; }}

  /* Nav pills (Home) */
  .pc-navgrid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
    margin-top: 10px;
  }}
  .pc-navcard {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 16px 18px;
    transition: all 0.15s;
  }}
  .pc-navcard:hover {{
    border-color: {COLORS['primary']};
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(79,70,229,0.08);
  }}
  .pc-navcard .n {{
    font-size: 0.7rem;
    font-weight: 700;
    color: {COLORS['primary']};
    letter-spacing: 0.12em;
  }}
  .pc-navcard .t {{
    font-weight: 600;
    font-size: 1rem;
    margin: 2px 0 4px 0;
    color: {COLORS['text']};
  }}
  .pc-navcard .d {{
    font-size: 0.82rem;
    color: {COLORS['text_muted']};
    line-height: 1.4;
  }}

  /* Section header (title + subtitle) */
  .pc-section-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: {COLORS['text']};
    margin-top: 18px;
    margin-bottom: 2px;
  }}
  .pc-section-sub {{
    font-size: 0.85rem;
    color: {COLORS['text_muted']};
    margin-bottom: 14px;
  }}
</style>
"""


def plotly_layout(**overrides: Any) -> dict[str, Any]:
    """Return a clean white-theme layout dict for Plotly figures."""
    base: dict[str, Any] = dict(
        template="plotly_white",
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color=COLORS["text"]),
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            showgrid=False,
            showline=False,
            linecolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_muted"], size=11),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            gridwidth=1,
            showline=False,
            tickfont=dict(color=COLORS["text_muted"], size=11),
        ),
        colorway=CATEGORICAL,
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter",
                        bordercolor=COLORS["border"]),
        legend=dict(bgcolor="rgba(255,255,255,0)", bordercolor=COLORS["border"],
                    font=dict(color=COLORS["text_muted"], size=11)),
    )
    base.update(overrides)
    return base


def style_fig(fig: go.Figure, **overrides: Any) -> go.Figure:
    fig.update_layout(**plotly_layout(**overrides))
    return fig


def hero(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="pc-hero">
          <div class="pc-hero-eyebrow">{eyebrow}</div>
          <div class="pc-hero-title">{title}</div>
          <div class="pc-hero-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="pc-section-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="pc-section-title">{title}</div>{sub}',
        unsafe_allow_html=True,
    )


def insight_card(title: str, body: str, tone: str = "") -> None:
    cls = f"pc-insight {tone}" if tone else "pc-insight"
    st.markdown(
        f'<div class="{cls}"><div class="pc-insight-title">{title}</div>'
        f'<div class="pc-insight-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="pc-badge {tone}">{text}</span>'


def verdict_banner(recommendation: str, rationale: str) -> None:
    rec = (recommendation or "").lower()
    mapping = {
        "ship": ("ship", "✓ SHIP", "Clear win on primary metric with guardrails intact."),
        "iterate": ("iterate", "◐ ITERATE", "Directional but not conclusive. Needs more data or refinement."),
        "reject": ("reject", "✕ REJECT", "Primary metric did not move, or a guardrail was breached."),
    }
    tone, title, default_sub = mapping.get(rec, ("iterate", rec.upper() or "—", ""))
    st.markdown(
        f"""
        <div class="pc-verdict {tone}">
          <div class="label">Experiment Verdict</div>
          <div class="title">{title}</div>
          <div class="sub">{rationale or default_sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(items: Sequence[dict[str, Any]]) -> None:
    """Render a row of KPI cards.

    Each item: {label, value, delta (optional), delta_tone (optional: 'success'/'danger'/'neutral')}.
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items, strict=False):
        delta = item.get("delta")
        if delta is None:
            col.metric(item["label"], item["value"])
        else:
            col.metric(item["label"], item["value"], delta)


def sidebar_brand() -> None:
    """Brand mark at the top of the sidebar."""
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding: 8px 4px 16px 4px; border-bottom: 1px solid {COLORS['border']}; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 34px; height: 34px; border-radius: 9px;
                            background: linear-gradient(135deg, #4F46E5, #7C3AED);
                            display:flex; align-items:center; justify-content:center;
                            color:white; font-weight:700; font-size:18px;">P</div>
                <div>
                  <div style="font-weight:700; font-size:1.02rem; color:{COLORS['text']}; line-height:1.1;">PulseCommerce</div>
                  <div style="font-size:0.72rem; color:{COLORS['text_muted']};">Commerce Intelligence</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
