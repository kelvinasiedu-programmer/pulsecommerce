"""DuckDB warehouse adapter.

Builds the three-tier SQL layer (raw → staging → marts → metrics) directly from
the parquet files emitted by `pulsecommerce.data.generator`.

Usage:
    with Warehouse() as wh:
        wh.build()
        df = wh.query("SELECT * FROM daily_kpis LIMIT 10")
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from pulsecommerce.config import RAW_DIR, SQL_DIR, WAREHOUSE_PATH, ensure_dirs
from pulsecommerce.logging_utils import get_logger

logger = get_logger(__name__)


RAW_TABLES: tuple[str, ...] = ("users", "products", "orders", "order_items", "events")

STAGING_FILES: tuple[str, ...] = (
    "stg_users.sql",
    "stg_products.sql",
    "stg_orders.sql",
    "stg_order_items.sql",
    "stg_events.sql",
)
MART_FILES: tuple[str, ...] = (
    "fct_orders.sql",
    "dim_customers.sql",
    "fct_sessions.sql",
    "dim_products.sql",
)
METRIC_FILES: tuple[str, ...] = (
    "daily_kpis.sql",
    "weekly_category.sql",
    "funnel_segmented.sql",
    "customer_rfm.sql",
)


class Warehouse:
    """Thin DuckDB wrapper that owns the lifecycle of the analytics warehouse."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else WAREHOUSE_PATH
        self.conn: duckdb.DuckDBPyConnection | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def connect(self) -> duckdb.DuckDBPyConnection:
        if self.conn is None:
            ensure_dirs()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(str(self.path))
        return self.conn

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "Warehouse":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self, raw_dir: Path | None = None, sql_dir: Path | None = None) -> None:
        """(Re)build the warehouse from the raw parquet files."""
        raw_dir = raw_dir or RAW_DIR
        sql_dir = sql_dir or SQL_DIR
        conn = self.connect()

        self._load_raw(raw_dir)
        logger.info("staging views …")
        self._run_sql_dir(sql_dir / "staging", STAGING_FILES)
        logger.info("marts …")
        self._run_sql_dir(sql_dir / "marts", MART_FILES)
        logger.info("metrics …")
        self._run_sql_dir(sql_dir / "metrics", METRIC_FILES)
        conn.commit()
        logger.info("warehouse ready at %s", self.path)

    def _load_raw(self, raw_dir: Path) -> None:
        conn = self.connect()
        for name in RAW_TABLES:
            parquet = raw_dir / f"{name}.parquet"
            if not parquet.exists():
                raise FileNotFoundError(
                    f"missing raw parquet: {parquet}. "
                    f"Run `python -m pulsecommerce.cli generate` first."
                )
            conn.execute(
                f"CREATE OR REPLACE TABLE raw_{name} AS SELECT * FROM read_parquet(?)",
                [str(parquet)],
            )
            rows = conn.execute(f"SELECT COUNT(*) FROM raw_{name}").fetchone()[0]
            logger.info("raw_%s loaded (%s rows)", name, f"{rows:,}")

    def _run_sql_dir(self, folder: Path, files: Iterable[str]) -> None:
        conn = self.connect()
        for fname in files:
            sql_path = folder / fname
            if not sql_path.exists():
                raise FileNotFoundError(sql_path)
            sql = sql_path.read_text(encoding="utf-8")
            try:
                conn.execute(sql)
            except Exception as exc:  # pragma: no cover
                logger.error("failed running %s: %s", sql_path, exc)
                raise

    # ------------------------------------------------------------------ #
    # Querying helpers
    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        conn = self.connect()
        if params is None:
            return conn.execute(sql).fetchdf()
        return conn.execute(sql, list(params)).fetchdf()

    def table(self, name: str) -> pd.DataFrame:
        return self.query(f"SELECT * FROM {name}")

    def exists(self, name: str) -> bool:
        conn = self.connect()
        row = conn.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE LOWER(table_name) = LOWER(?)
            """,
            [name],
        ).fetchone()
        return bool(row and row[0] > 0)
