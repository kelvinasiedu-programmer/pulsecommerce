"""Layer 2 — Funnel drop-off & sales efficiency analysis."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pulsecommerce.warehouse import Warehouse

FUNNEL_STAGES: tuple[str, ...] = (
    "session_start",
    "product_view",
    "add_to_cart",
    "checkout_start",
    "purchase",
)


@dataclass
class FunnelInsight:
    biggest_drop_stage: str
    biggest_drop_rate: float
    worst_segment: dict
    best_segment: dict
    estimated_lost_revenue: float


class FunnelAnalyst:
    """Computes overall + segmented funnel metrics and top-loss opportunities."""

    def __init__(self, warehouse: Warehouse):
        self.wh = warehouse

    def overall(self) -> pd.DataFrame:
        df = self.wh.query(
            """
            SELECT
                SUM(has_session_start)  AS session_start,
                SUM(has_product_view)   AS product_view,
                SUM(has_add_to_cart)    AS add_to_cart,
                SUM(has_checkout_start) AS checkout_start,
                SUM(has_purchase)       AS purchase,
                COUNT(*)                AS sessions
            FROM fct_sessions
            """
        )
        row = df.iloc[0].to_dict()
        counts = [int(row[stage]) for stage in FUNNEL_STAGES]
        counts[0] = max(counts[0], int(row["sessions"]))
        rates = [1.0] + [
            counts[i] / counts[i - 1] if counts[i - 1] else 0.0 for i in range(1, len(counts))
        ]
        drop = [0.0] + [1.0 - rates[i] for i in range(1, len(rates))]
        return pd.DataFrame(
            {
                "stage": FUNNEL_STAGES,
                "count": counts,
                "stage_conversion_rate": rates,
                "drop_off_rate": drop,
            }
        )

    def by_segment(self) -> pd.DataFrame:
        df = self.wh.query("SELECT * FROM funnel_segmented ORDER BY sessions DESC")
        return df

    def insights(self, aov: float | None = None) -> FunnelInsight:
        overall = self.overall()
        drops = overall.iloc[1:].copy()
        worst_idx = drops["drop_off_rate"].idxmax()
        biggest_drop_stage = str(drops.loc[worst_idx, "stage"])
        biggest_drop_rate = float(drops.loc[worst_idx, "drop_off_rate"])

        seg = self.by_segment()
        if seg.empty:
            empty = {"device": None, "channel": None, "overall_conversion": 0.0, "sessions": 0}
            return FunnelInsight(biggest_drop_stage, biggest_drop_rate, empty, empty, 0.0)
        seg_filtered = seg[seg["sessions"] >= 50].copy()
        if seg_filtered.empty:
            seg_filtered = seg
        worst = seg_filtered.loc[seg_filtered["overall_conversion"].idxmin()]
        best = seg_filtered.loc[seg_filtered["overall_conversion"].idxmax()]

        if aov is None:
            aov_df = self.wh.query(
                """
                SELECT AVG(order_revenue) AS aov FROM fct_orders
                WHERE status NOT IN ('Cancelled','Returned')
                """
            )
            aov = float(aov_df.loc[0, "aov"] or 0.0)

        gap = float(best["overall_conversion"] - worst["overall_conversion"])
        estimated_lost = gap * float(worst["sessions"]) * aov

        to_dict = lambda row: {  # noqa: E731
            "device": str(row["device"]),
            "channel": str(row["channel"]),
            "overall_conversion": float(row["overall_conversion"]),
            "sessions": int(row["sessions"]),
        }
        return FunnelInsight(
            biggest_drop_stage=biggest_drop_stage,
            biggest_drop_rate=biggest_drop_rate,
            worst_segment=to_dict(worst),
            best_segment=to_dict(best),
            estimated_lost_revenue=max(estimated_lost, 0.0),
        )
