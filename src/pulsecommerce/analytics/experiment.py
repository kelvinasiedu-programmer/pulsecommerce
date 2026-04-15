"""Layer 5 — Experiment readout (promotion lift analyzer).

Simulates an A/B test targeting a segment (by default: top-risk churn customers),
computes a primary metric lift with a 2-sample test, checks guardrail metrics,
and emits a ship / iterate / reject recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from pulsecommerce.config import EXPERIMENT
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.warehouse import Warehouse

logger = get_logger(__name__)


@dataclass
class MetricResult:
    name: str
    control_mean: float
    treatment_mean: float
    abs_lift: float
    rel_lift: float
    p_value: float
    is_significant: bool
    is_guardrail: bool
    direction_ok: bool


@dataclass
class ExperimentReport:
    hypothesis: str
    start: date
    end: date
    n_control: int
    n_treatment: int
    primary: MetricResult
    guardrails: list[MetricResult]
    recommendation: str  # ship | iterate | reject
    rationale: str


class PromotionExperiment:
    """Simulated readout: a promo lifts conversion for targeted users without harming AOV/refunds."""

    def __init__(
        self,
        warehouse: Warehouse,
        assignment_seed: int = 7,
        treatment_effect: float = 0.08,
        guardrail_drift: float = -0.015,
    ):
        self.wh = warehouse
        self.assignment_seed = assignment_seed
        self.treatment_effect = treatment_effect
        self.guardrail_drift = guardrail_drift

    def _bootstrap_user_panel(self, window_days: int = 60) -> pd.DataFrame:
        """Collect a per-user, per-experiment-window behavioural snapshot."""
        df = self.wh.query(
            """
            WITH bounds AS (
                SELECT MAX(order_date) AS max_d FROM fct_orders
            )
            SELECT
                u.user_id,
                u.country,
                u.traffic_source,
                COUNT(o.order_id)                                  AS orders,
                COALESCE(SUM(o.order_revenue), 0)                  AS revenue,
                COALESCE(AVG(o.order_revenue), 0)                  AS avg_order_value,
                COALESCE(AVG(o.item_count), 0)                     AS items_per_order,
                COALESCE(AVG(o.is_lost), 0)                        AS refund_rate_proxy,
                CASE WHEN COUNT(o.order_id) > 0 THEN 1 ELSE 0 END  AS converted
            FROM dim_customers u
            LEFT JOIN fct_orders o
              ON u.user_id = o.user_id
             AND o.order_date >= ((SELECT max_d FROM bounds) - INTERVAL '%d days')
            GROUP BY u.user_id, u.country, u.traffic_source
            """
            % window_days
        )
        return df

    def run(
        self,
        audience: pd.DataFrame | None = None,
        window_days: int = 60,
        hypothesis: str = "Targeted 10% off promo lifts conversion on at-risk customers without hurting AOV or refund rate.",
    ) -> ExperimentReport:
        panel = self._bootstrap_user_panel(window_days=window_days)
        if audience is not None and not audience.empty:
            panel = panel.merge(audience[["user_id"]], on="user_id", how="inner")
        if len(panel) < 2 * EXPERIMENT.min_sample_size:
            logger.warning("audience small (%s rows) — results may be unstable", len(panel))

        rng = np.random.default_rng(self.assignment_seed)
        panel = panel.sample(frac=1.0, random_state=self.assignment_seed).reset_index(drop=True)
        panel["arm"] = np.where(rng.random(len(panel)) < 0.5, "control", "treatment")

        # Widen dtypes so assignments don't fail under pandas 2.x strict upcasting.
        panel["converted"] = panel["converted"].astype("int64")
        for col in ("avg_order_value", "items_per_order", "refund_rate_proxy"):
            panel[col] = panel[col].astype("float64")

        # Inject a simulated lift in treatment's primary metric and small drift on guardrails.
        treat_mask = panel["arm"].eq("treatment").to_numpy()
        n_treat = int(treat_mask.sum())
        lift = self.treatment_effect
        base = panel.loc[treat_mask, "converted"].to_numpy(dtype=float)
        boosted = (base + rng.random(n_treat) < 0.5 + lift).astype(np.int64)
        panel.loc[treat_mask, "converted"] = boosted
        panel.loc[treat_mask, "avg_order_value"] = panel.loc[
            treat_mask, "avg_order_value"
        ].to_numpy() * (1 + self.guardrail_drift)
        panel.loc[treat_mask, "items_per_order"] = panel.loc[
            treat_mask, "items_per_order"
        ].to_numpy() * (1 + self.guardrail_drift / 2)
        panel.loc[treat_mask, "refund_rate_proxy"] = panel.loc[
            treat_mask, "refund_rate_proxy"
        ].to_numpy() * (1 + abs(self.guardrail_drift))

        control = panel[panel["arm"] == "control"]
        treatment = panel[panel["arm"] == "treatment"]

        primary = _two_sample_test(
            name="conversion_rate",
            control=control["converted"].to_numpy(),
            treatment=treatment["converted"].to_numpy(),
            guardrail=False,
            lower_is_better=False,
        )

        guardrails = [
            _two_sample_test(
                name="average_order_value",
                control=control["avg_order_value"].to_numpy(),
                treatment=treatment["avg_order_value"].to_numpy(),
                guardrail=True,
                lower_is_better=False,
            ),
            _two_sample_test(
                name="items_per_order",
                control=control["items_per_order"].to_numpy(),
                treatment=treatment["items_per_order"].to_numpy(),
                guardrail=True,
                lower_is_better=False,
            ),
            _two_sample_test(
                name="refund_rate_proxy",
                control=control["refund_rate_proxy"].to_numpy(),
                treatment=treatment["refund_rate_proxy"].to_numpy(),
                guardrail=True,
                lower_is_better=True,
            ),
        ]

        recommendation, rationale = _decide(primary, guardrails)
        bounds = self.wh.query(
            "SELECT MIN(order_date) mn, MAX(order_date) mx FROM fct_orders"
        ).iloc[0]
        end_d = pd.to_datetime(bounds["mx"]).date()
        start_d = end_d - timedelta(days=window_days)
        return ExperimentReport(
            hypothesis=hypothesis,
            start=start_d,
            end=end_d,
            n_control=int(len(control)),
            n_treatment=int(len(treatment)),
            primary=primary,
            guardrails=guardrails,
            recommendation=recommendation,
            rationale=rationale,
        )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _two_sample_test(
    name: str,
    control: np.ndarray,
    treatment: np.ndarray,
    guardrail: bool,
    lower_is_better: bool,
) -> MetricResult:
    control = np.asarray(control, dtype=float)
    treatment = np.asarray(treatment, dtype=float)
    c_mean = float(np.nanmean(control)) if len(control) else 0.0
    t_mean = float(np.nanmean(treatment)) if len(treatment) else 0.0
    abs_lift = t_mean - c_mean
    rel_lift = abs_lift / c_mean if c_mean else 0.0
    if len(control) > 1 and len(treatment) > 1 and np.nanstd(control) + np.nanstd(treatment) > 0:
        _, p = stats.ttest_ind(control, treatment, equal_var=False, nan_policy="omit")
        p = float(p)
    else:
        p = 1.0
    significant = p < EXPERIMENT.alpha
    if lower_is_better:
        direction_ok = abs_lift <= 0
    else:
        direction_ok = abs_lift >= 0
    return MetricResult(
        name=name,
        control_mean=c_mean,
        treatment_mean=t_mean,
        abs_lift=abs_lift,
        rel_lift=rel_lift,
        p_value=p,
        is_significant=significant,
        is_guardrail=guardrail,
        direction_ok=direction_ok,
    )


def _decide(primary: MetricResult, guardrails: list[MetricResult]) -> tuple[str, str]:
    guardrail_breach = [g for g in guardrails if g.is_significant and not g.direction_ok]
    if primary.is_significant and primary.rel_lift > 0 and not guardrail_breach:
        return (
            "ship",
            f"Primary metric {primary.name} improved by {primary.rel_lift:+.2%} (p={primary.p_value:.3f}) "
            f"with no guardrail regressions.",
        )
    if guardrail_breach:
        breaches = ", ".join(g.name for g in guardrail_breach)
        return (
            "reject",
            f"Guardrail regression on {breaches} — do not ship despite primary lift.",
        )
    if primary.rel_lift > 0 and not primary.is_significant:
        return (
            "iterate",
            f"Directional lift of {primary.rel_lift:+.2%} on {primary.name} but not statistically "
            f"significant (p={primary.p_value:.3f}). Extend test or increase sample.",
        )
    return (
        "reject",
        f"No meaningful lift detected (Δ={primary.rel_lift:+.2%}, p={primary.p_value:.3f}).",
    )
