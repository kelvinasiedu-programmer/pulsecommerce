"""Tableau Public export layer.

Tableau Public cannot connect to DuckDB, so the contract between the Python
side and the viz side is a small set of tidy CSVs with stable column names.

Grain is deliberately left low enough that Tableau does its own aggregation -
the workbooks stay interactive instead of rendering numbers Python already
decided. The one exception is `cohort_retention`, which is already at its
natural grain coming out of the churn layer.

Metric definitions match `docs/kpi_dictionary.md`: revenue, margin and order
counts exclude Cancelled/Returned rows, and `orders_fact` applies that
exclusion in SQL rather than leaving it to a Tableau data source filter. The
filter approach was tried first and Tableau Public Desktop failed with an
internal error twice while applying it. Doing it here also makes `orders_fact`
and `kpi_daily` agree on revenue by construction, which a test asserts.
Cancellation volume is still available as `cancelled_orders` on `kpi_daily`.

Usage:
    python -m pulsecommerce.cli tableau
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pulsecommerce.config import PROCESSED_DIR, SITE_DIR, TABLEAU_DIR, ensure_dirs
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.warehouse import Warehouse

logger = get_logger(__name__)

#: Funnel stages in order, mapped to their flag column on `fct_sessions`.
FUNNEL_STAGES: tuple[tuple[int, str, str], ...] = (
    (1, "Session Start", "has_session_start"),
    (2, "Product View", "has_product_view"),
    (3, "Add to Cart", "has_add_to_cart"),
    (4, "Checkout Start", "has_checkout_start"),
    (5, "Purchase", "has_purchase"),
)

KPI_DAILY_SQL = """
SELECT
    metric_date,
    sessions,
    purchase_sessions,
    orders,
    revenue,
    margin,
    items_sold,
    cancelled_orders,
    avg_order_value,
    conversion_rate
FROM daily_kpis
ORDER BY metric_date
"""

ORDERS_FACT_SQL = """
SELECT
    oi.order_id,
    oi.user_id,
    o.order_date,
    o.device,
    o.channel,
    u.country,
    c.customer_segment,
    oi.category,
    p.brand,
    oi.status,
    oi.sale_price      AS revenue,
    oi.cost            AS cost,
    oi.gross_margin    AS margin,
    oi.discount_pct
FROM stg_order_items oi
JOIN stg_orders o          ON o.order_id = oi.order_id
LEFT JOIN stg_users u      ON u.user_id = oi.user_id
LEFT JOIN dim_customers c  ON c.user_id = oi.user_id
LEFT JOIN dim_products p   ON p.product_id = oi.product_id
WHERE oi.status NOT IN ('Cancelled', 'Returned')
ORDER BY o.order_date, oi.order_id
"""

FUNNEL_SEGMENTS_SQL = """
SELECT
    device,
    channel,
    sessions,
    product_views,
    add_to_carts,
    checkout_starts,
    purchases,
    view_rate,
    cart_rate,
    checkout_rate,
    purchase_rate,
    overall_conversion
FROM funnel_segmented
ORDER BY overall_conversion DESC
"""


def _funnel_stages_sql() -> str:
    """Unpivot the five session flags into one row per week x segment x stage."""
    blocks = [
        f"""
        SELECT
            DATE_TRUNC('week', session_start) AS week_start,
            device,
            channel,
            {order}                           AS stage_order,
            '{label}'                         AS stage,
            SUM({flag})                       AS sessions_reached
        FROM fct_sessions
        GROUP BY 1, 2, 3
        """
        for order, label, flag in FUNNEL_STAGES
    ]
    return "\nUNION ALL\n".join(blocks) + "\nORDER BY week_start, device, channel, stage_order"


@dataclass(frozen=True)
class ExportedTable:
    """One CSV handed to Tableau."""

    name: str
    path: Path
    rows: int
    columns: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.path.name,
            "rows": self.rows,
            "columns": list(self.columns),
            "size_kb": round(self.path.stat().st_size / 1024, 1),
        }


def _write_csv(df: pd.DataFrame, name: str, out_dir: Path) -> ExportedTable:
    path = out_dir / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("wrote %s (%s rows)", path.name, f"{len(df):,}")
    return ExportedTable(name=name, path=path, rows=len(df), columns=tuple(df.columns))


def _read_cohort_retention(processed_dir: Path) -> pd.DataFrame:
    """Cohort retention is produced by the churn layer, not recomputed here."""
    path = processed_dir / "cohort_retention.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path}. Run `python -m pulsecommerce.cli all` first - the "
            f"cohort table is written by the churn layer."
        )
    df = pd.read_parquet(path)
    return df.assign(cohort_month=pd.to_datetime(df["cohort_month"]).dt.date)


def export_tableau(
    out_dir: Path = TABLEAU_DIR,
    processed_dir: Path = PROCESSED_DIR,
    site_dir: Path | None = SITE_DIR,
    warehouse: Warehouse | None = None,
) -> dict[str, Path]:
    """Write the Tableau Public CSV bundle and its manifest.

    The CSVs are gitignored working files for Tableau Desktop. The manifest is
    also copied into `site/data/` - it is small, it belongs in version control,
    and it is what lets the published site state its own data coverage instead
    of hardcoding a date that goes stale.

    Pass `warehouse` to export from an existing connection; otherwise the
    default warehouse is opened and closed here.
    """
    ensure_dirs()
    out_dir.mkdir(parents=True, exist_ok=True)

    owned = warehouse is None
    wh = warehouse or Warehouse()
    try:
        if owned:
            wh.connect()
        tables = [
            _write_csv(wh.query(KPI_DAILY_SQL), "kpi_daily", out_dir),
            _write_csv(wh.query(ORDERS_FACT_SQL), "orders_fact", out_dir),
            _write_csv(wh.query(_funnel_stages_sql()), "funnel_stages", out_dir),
            _write_csv(wh.query(FUNNEL_SEGMENTS_SQL), "funnel_segments", out_dir),
            _write_csv(_read_cohort_retention(processed_dir), "cohort_retention", out_dir),
        ]
    finally:
        if owned:
            wh.close()

    manifest_path = _write_manifest(tables, out_dir)
    logger.info("tableau bundle ready in %s", out_dir)

    paths = {t.name: t.path for t in tables}
    paths["manifest"] = manifest_path

    if site_dir is not None:
        site_manifest = site_dir / "data" / "manifest.json"
        site_manifest.parent.mkdir(parents=True, exist_ok=True)
        site_manifest.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
        logger.info("copied manifest to %s", site_manifest)
        paths["site_manifest"] = site_manifest

    return paths


def _write_manifest(tables: list[ExportedTable], out_dir: Path) -> Path:
    """A manifest so the site can state what the data covers without guessing."""
    kpi = next((t for t in tables if t.name == "kpi_daily"), None)
    coverage: dict[str, str] = {}
    if kpi is not None:
        daily = pd.read_csv(kpi.path, usecols=["metric_date"])
        coverage = {
            "start": str(daily["metric_date"].min()),
            "end": str(daily["metric_date"].max()),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage": coverage,
        "tables": [t.to_dict() for t in tables],
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
