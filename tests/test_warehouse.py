def test_warehouse_has_expected_tables(warehouse):
    expected = [
        "raw_users",
        "raw_orders",
        "raw_order_items",
        "raw_events",
        "raw_products",
        "stg_users",
        "stg_orders",
        "stg_order_items",
        "stg_events",
        "stg_products",
        "fct_orders",
        "dim_customers",
        "fct_sessions",
        "dim_products",
        "daily_kpis",
        "weekly_category",
        "funnel_segmented",
        "customer_rfm",
    ]
    for name in expected:
        assert warehouse.exists(name), f"missing table/view: {name}"


def test_fct_orders_has_rows(warehouse):
    df = warehouse.table("fct_orders")
    assert len(df) > 0
    assert {"order_id", "user_id", "order_revenue", "order_margin"} <= set(df.columns)


def test_daily_kpis_monotonic_dates(warehouse):
    df = warehouse.table("daily_kpis")
    assert df["metric_date"].is_monotonic_increasing
    assert (df["sessions"] >= 0).all()
    assert (df["orders"] >= 0).all()
