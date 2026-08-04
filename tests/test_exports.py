"""Tests for the Tableau Public export bundle."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pulsecommerce.exports.tableau import export_tableau


@pytest.fixture(scope="module")
def bundle(warehouse, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out = tmp_path_factory.mktemp("tableau")
    processed = tmp_path_factory.mktemp("processed")

    # cohort_retention normally comes from the churn layer; stub the shape it
    # produces so the export does not have to train a model to be tested.
    pd.DataFrame(
        {
            "cohort_month": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-02-01"]),
            "month_number": [0, 1, 0],
            "active_users": [50, 22, 61],
            "cohort_size": [50, 50, 61],
            "retention_rate": [1.0, 0.44, 1.0],
        }
    ).to_parquet(processed / "cohort_retention.parquet", index=False)

    return export_tableau(
        out_dir=out,
        processed_dir=processed,
        site_dir=None,
        warehouse=warehouse,
    )


def test_writes_every_expected_table(bundle):
    expected = {
        "kpi_daily",
        "orders_fact",
        "funnel_stages",
        "funnel_segments",
        "cohort_retention",
        "manifest",
    }
    assert expected <= set(bundle)
    for path in bundle.values():
        assert path.exists(), f"{path.name} was not written"


def test_orders_fact_excludes_cancellations(bundle):
    df = pd.read_csv(bundle["orders_fact"])

    assert not df["status"].isin({"Cancelled", "Returned"}).any()
    assert "status_group" not in df.columns, "the tagging column is no longer exported"


def test_orders_fact_revenue_agrees_with_kpi_daily(bundle):
    """The two sources a Tableau dashboard shows side by side must not disagree.

    Business Health puts KPI tiles from `kpi_daily` next to channel and category
    breakdowns from `orders_fact`. If these totals drift, the dashboard
    contradicts itself on screen.
    """
    orders = pd.read_csv(bundle["orders_fact"])
    daily = pd.read_csv(bundle["kpi_daily"])

    assert orders["revenue"].sum() == pytest.approx(daily["revenue"].sum(), rel=1e-6)
    assert orders["margin"].sum() == pytest.approx(daily["margin"].sum(), rel=1e-6)
    assert orders["order_id"].nunique() == daily["orders"].sum()


def test_funnel_stages_is_long_and_ordered(bundle):
    df = pd.read_csv(bundle["funnel_stages"])

    assert {"week_start", "device", "channel", "stage", "stage_order", "sessions_reached"} == set(
        df.columns
    )
    assert df["stage_order"].between(1, 5).all()

    # the funnel only makes sense if it narrows
    by_stage = df.groupby("stage_order")["sessions_reached"].sum()
    assert by_stage.is_monotonic_decreasing, f"funnel widens: {by_stage.to_dict()}"


def test_funnel_segment_rates_are_proportions(bundle):
    df = pd.read_csv(bundle["funnel_segments"])
    rates = ["view_rate", "cart_rate", "checkout_rate", "purchase_rate", "overall_conversion"]
    for col in rates:
        finite = df[col].dropna()
        assert finite.between(0, 1).all(), f"{col} outside [0, 1]"


def test_manifest_reports_coverage_and_rows(bundle):
    payload = json.loads(bundle["manifest"].read_text(encoding="utf-8"))

    assert payload["coverage"]["start"] <= payload["coverage"]["end"]
    names = {t["name"] for t in payload["tables"]}
    assert "kpi_daily" in names

    kpi = next(t for t in payload["tables"] if t["name"] == "kpi_daily")
    assert kpi["rows"] == len(pd.read_csv(bundle["kpi_daily"]))
