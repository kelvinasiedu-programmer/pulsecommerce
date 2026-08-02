from pulsecommerce.config import SmallDataGenConfig
from pulsecommerce.data.generator import FUNNEL_STAGES, generate


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


def test_orders_spread_across_the_user_base():
    """Guards the repeat-buyer weighting.

    Sampling raw zipf variates as weights collapsed 95k orders onto ~130 users,
    which made every customer-level metric (cohorts, churn, RFM) meaningless.
    The skew should be heavy but not degenerate.
    """
    cfg = SmallDataGenConfig(
        n_users=2_000, n_products=40, n_orders=6_000, n_events_per_user_mean=3.0
    )
    ds = generate(cfg=cfg, seed=7)

    counts = ds.orders["user_id"].value_counts()
    buyer_share = len(counts) / cfg.n_users
    top20_share = counts.head(max(1, len(counts) // 5)).sum() / counts.sum()

    assert 0.40 <= buyer_share <= 0.90, f"{buyer_share:.1%} of users placed an order"
    assert 0.50 <= top20_share <= 0.85, f"top 20% of buyers drive {top20_share:.1%} of orders"
    assert counts.max() < cfg.n_orders * 0.02, "a single customer absorbed too many orders"


def test_funnel_stages_are_nested_within_a_session():
    """A session that reached stage N must have emitted every stage before it.

    Events used to be drawn independently per event with a random session_id, so
    16% of sessions added to cart having never viewed a product and every
    stage-to-stage conversion rate was meaningless.
    """
    cfg = SmallDataGenConfig(n_users=800, n_products=30, n_orders=1_200, n_events_per_user_mean=6.0)
    ds = generate(cfg=cfg, seed=3)

    reached = (
        ds.events.assign(hit=1)
        .pivot_table(index="session_id", columns="event_type", values="hit", aggfunc="max")
        .reindex(columns=FUNNEL_STAGES)
        .fillna(0)
        .astype(int)
    )

    for earlier, later in zip(FUNNEL_STAGES, FUNNEL_STAGES[1:], strict=False):
        violations = int(((reached[later] == 1) & (reached[earlier] == 0)).sum())
        assert violations == 0, f"{violations} sessions reached {later} without {earlier}"


def test_session_attributes_are_stable_within_a_session():
    cfg = SmallDataGenConfig(n_users=400, n_products=20, n_orders=600, n_events_per_user_mean=6.0)
    ds = generate(cfg=cfg, seed=4)

    per_session = ds.events.groupby("session_id")[["device", "channel", "user_id"]].nunique()
    assert (per_session == 1).all().all(), "device/channel/user drifts inside a session"


def test_conversion_differs_by_segment():
    """Device x channel asymmetry should be a property of the data, not noise."""
    cfg = SmallDataGenConfig(
        n_users=6_000, n_products=40, n_orders=2_000, n_events_per_user_mean=6.0
    )
    ds = generate(cfg=cfg, seed=5)

    per_session = ds.events.groupby("session_id").agg(
        device=("device", "first"),
        channel=("channel", "first"),
        purchased=("event_type", lambda s: int("purchase" in set(s))),
    )
    by_device = per_session.groupby("device")["purchased"].mean()
    by_channel = per_session.groupby("channel")["purchased"].mean()

    assert by_device["desktop"] > by_device["mobile"], "desktop should out-convert mobile"
    assert by_channel["Email"] > by_channel["Display"], "email should out-convert display"


def test_seed_is_deterministic():
    cfg = SmallDataGenConfig(n_users=120, n_products=10, n_orders=220, n_events_per_user_mean=3.0)
    a = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    b = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    assert a == b
