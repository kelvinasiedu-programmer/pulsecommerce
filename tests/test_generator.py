from pulsecommerce.config import SmallDataGenConfig
from pulsecommerce.data.generator import generate


def test_generate_returns_all_tables():
    cfg = SmallDataGenConfig(n_users=200, n_products=20, n_orders=400, n_events_per_user_mean=4.0)
    ds = generate(cfg=cfg, seed=0)

    assert len(ds.users) == 200
    assert len(ds.products) == 20
    assert len(ds.orders) > 0
    assert len(ds.order_items) >= len(ds.orders)
    assert len(ds.events) > 0


def test_referential_integrity():
    cfg = SmallDataGenConfig(n_users=150, n_products=15, n_orders=300, n_events_per_user_mean=3.0)
    ds = generate(cfg=cfg, seed=1)

    assert ds.order_items["order_id"].isin(ds.orders["order_id"]).all()
    assert ds.order_items["product_id"].isin(ds.products["product_id"]).all()
    assert ds.events["user_id"].isin(ds.users["user_id"]).all()


def test_seed_is_deterministic():
    cfg = SmallDataGenConfig(n_users=120, n_products=10, n_orders=220, n_events_per_user_mean=3.0)
    a = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    b = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    assert a == b
