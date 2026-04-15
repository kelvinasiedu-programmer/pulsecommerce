"""Layer 1 — Business Health KPIs.

Produces the executive-facing KPI bundle used on the landing page:
  * revenue, orders, AOV, conversion rate
  * period-over-period deltas
  * 7/28-day rolling trend
  * channel + category mix
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

import pandas as pd

from pulsecommerce.warehouse import Warehouse


@dataclass
class KPICard:
    label: str
    value: float
    delta_abs: float
    delta_pct: float
    format: str = "number"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HealthReport:
    as_of: date
    window_days: int
    cards: list[KPICard]
    daily: pd.DataFrame
    by_channel: pd.DataFrame
    by_category: pd.DataFrame

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(),
            "window_days": self.window_days,
            "cards": [c.to_dict() for c in self.cards],
        }


def _pct_delta(current: float, prior: float) -> float:
    if prior in (0, 0.0) or pd.isna(prior):
        return 0.0
    return (current - prior) / prior


def _card(label: str, current: float, prior: float, fmt: str = "number") -> KPICard:
    return KPICard(
        label=label,
        value=float(current or 0.0),
        delta_abs=float((current or 0.0) - (prior or 0.0)),
        delta_pct=float(_pct_delta(current or 0.0, prior or 0.0)),
        format=fmt,
    )


class HealthAnalyst:
    """Computes the executive KPI bundle from the warehouse."""

    def __init__(self, warehouse: Warehouse):
        self.wh = warehouse

    def _max_date(self) -> date:
        df = self.wh.query("SELECT MAX(metric_date) AS d FROM daily_kpis")
        return pd.to_datetime(df.loc[0, "d"]).date()

    def report(self, window_days: int = 28, as_of: date | None = None) -> HealthReport:
        as_of = as_of or self._max_date()
        start_cur = as_of - timedelta(days=window_days - 1)
        start_prior = start_cur - timedelta(days=window_days)
        end_prior = start_cur - timedelta(days=1)

        daily = self.wh.query(
            """
            SELECT metric_date, sessions, orders, revenue, margin,
                   avg_order_value, conversion_rate, items_sold, cancelled_orders
            FROM daily_kpis
            WHERE metric_date BETWEEN ? AND ?
            ORDER BY metric_date
            """,
            [start_prior, as_of],
        )
        if daily.empty:
            daily = pd.DataFrame(
                columns=[
                    "metric_date",
                    "sessions",
                    "orders",
                    "revenue",
                    "margin",
                    "avg_order_value",
                    "conversion_rate",
                    "items_sold",
                    "cancelled_orders",
                ]
            )

        daily["metric_date"] = pd.to_datetime(daily["metric_date"])
        cur_mask = daily["metric_date"].dt.date >= start_cur
        prior_mask = (daily["metric_date"].dt.date >= start_prior) & (
            daily["metric_date"].dt.date <= end_prior
        )
        cur = daily.loc[cur_mask]
        prior = daily.loc[prior_mask]

        cards = [
            _card("Revenue", cur["revenue"].sum(), prior["revenue"].sum(), "currency"),
            _card("Gross Margin", cur["margin"].sum(), prior["margin"].sum(), "currency"),
            _card("Orders", cur["orders"].sum(), prior["orders"].sum(), "number"),
            _card("Sessions", cur["sessions"].sum(), prior["sessions"].sum(), "number"),
            _card(
                "AOV",
                cur["revenue"].sum() / max(cur["orders"].sum(), 1),
                prior["revenue"].sum() / max(prior["orders"].sum(), 1),
                "currency",
            ),
            _card(
                "Conversion Rate",
                cur["conversion_rate"].mean(),
                prior["conversion_rate"].mean(),
                "percent",
            ),
            _card(
                "Cancel Rate",
                cur["cancelled_orders"].sum() / max(cur["orders"].sum(), 1),
                prior["cancelled_orders"].sum() / max(prior["orders"].sum(), 1),
                "percent",
            ),
        ]

        by_channel = self.wh.query(
            """
            SELECT channel,
                   COUNT(*)            AS orders,
                   SUM(order_revenue)  AS revenue,
                   AVG(order_revenue)  AS avg_order_value
            FROM fct_orders
            WHERE status NOT IN ('Cancelled', 'Returned')
              AND order_date BETWEEN ? AND ?
            GROUP BY channel
            ORDER BY revenue DESC
            """,
            [start_cur, as_of],
        )

        by_category = self.wh.query(
            """
            SELECT category,
                   SUM(sale_price)   AS revenue,
                   SUM(gross_margin) AS margin,
                   COUNT(*)          AS units
            FROM stg_order_items
            WHERE status NOT IN ('Cancelled', 'Returned')
              AND item_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY revenue DESC
            """,
            [start_cur, as_of],
        )

        return HealthReport(
            as_of=as_of,
            window_days=window_days,
            cards=cards,
            daily=daily.assign(metric_date=daily["metric_date"].dt.date),
            by_channel=by_channel,
            by_category=by_category,
        )
