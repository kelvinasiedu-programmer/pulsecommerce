import pandas as pd

from pulsecommerce.config import SmallDataGenConfig
from pulsecommerce.data.generator import FUNNEL_STAGES, generate


def test_generate_returns_all_tables():
    cfg = SmallDataGenConfig(n_users=200, n_products=20, n_orders=400)
    ds = generate(cfg=cfg, seed=0)

    assert len(ds.users) == 200
    assert len(ds.products) == 20
    assert len(ds.orders) > 0
    assert len(ds.order_items) >= len(ds.orders)
    assert len(ds.events) > 0


def test_referential_integrity():
    cfg = SmallDataGenConfig(n_users=150, n_products=15, n_orders=300)
    ds = generate(cfg=cfg, seed=1)

    assert ds.order_items["order_id"].isin(ds.orders["order_id"]).all()
    assert ds.order_items["product_id"].isin(ds.products["product_id"]).all()
    assert ds.events["user_id"].isin(ds.users["user_id"]).all()


def test_every_order_traces_back_to_a_purchase_event():
    """The clickstream and the orders table must describe one business.

    They used to be generated independently: the funnel reported 9,879 purchases
    while the orders table held 83,542 rows, so conversion rate and order count
    on the same dashboard contradicted each other by 8.5x.
    """
    cfg = SmallDataGenConfig(n_users=900, n_products=30, n_orders=1_200)
    ds = generate(cfg=cfg, seed=11)

    purchase_events = ds.events[ds.events["event_type"] == "purchase"]

    assert len(ds.orders) == len(purchase_events), "order count must equal purchase count"
    assert set(ds.orders["session_id"]) == set(purchase_events["session_id"])
    assert ds.orders["session_id"].is_unique, "a session cannot produce two orders"


def test_no_session_predates_the_user_signup():
    """Cohort retention is meaningless if customers shop before they exist."""
    cfg = SmallDataGenConfig(n_users=700, n_products=25, n_orders=900)
    ds = generate(cfg=cfg, seed=12)

    joined = ds.events.merge(ds.users[["user_id", "created_at"]], on="user_id", how="left")
    early = joined[joined["occurred_at"] < joined["created_at"].dt.normalize()]

    assert len(early) == 0, f"{len(early)} events happened before the user signed up"


def test_orders_carry_seasonality():
    """Q4 has to be visibly busier or the forecasting layer has nothing to find."""
    cfg = SmallDataGenConfig(n_users=4_000, n_products=40, n_orders=8_000)
    ds = generate(cfg=cfg, seed=13)

    by_month = ds.orders.groupby(pd.to_datetime(ds.orders["created_at"]).dt.month).size()
    q4 = by_month.reindex([11, 12]).mean()
    rest = by_month.drop([11, 12], errors="ignore").mean()

    assert q4 > rest * 1.15, f"Q4 {q4:.0f} vs baseline {rest:.0f} is not a seasonal peak"


def test_orders_spread_across_the_user_base():
    """Guards the repeat-buyer weighting.

    Sampling raw zipf variates as weights collapsed 95k orders onto ~130 users,
    which made every customer-level metric (cohorts, churn, RFM) meaningless.
    The skew should be heavy but not degenerate.
    """
    cfg = SmallDataGenConfig(n_users=2_000, n_products=40, n_orders=6_000)
    ds = generate(cfg=cfg, seed=7)

    counts = ds.orders["user_id"].value_counts()
    buyer_share = len(counts) / cfg.n_users
    top20_share = counts.head(max(1, len(counts) // 5)).sum() / counts.sum()

    assert 0.30 <= buyer_share <= 0.90, f"{buyer_share:.1%} of users placed an order"
    assert 0.35 <= top20_share <= 0.85, f"top 20% of buyers drive {top20_share:.1%} of orders"
    assert counts.max() < counts.sum() * 0.02, "a single customer absorbed too many orders"


def test_funnel_stages_are_nested_within_a_session():
    """A session that reached stage N must have emitted every stage before it.

    Events used to be drawn independently per event with a random session_id, so
    16% of sessions added to cart having never viewed a product and every
    stage-to-stage conversion rate was meaningless.
    """
    cfg = SmallDataGenConfig(n_users=800, n_products=30, n_orders=1_200)
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
    cfg = SmallDataGenConfig(n_users=400, n_products=20, n_orders=600)
    ds = generate(cfg=cfg, seed=4)

    per_session = ds.events.groupby("session_id")[["device", "channel", "user_id"]].nunique()
    assert (per_session == 1).all().all(), "device/channel/user drifts inside a session"


def test_conversion_differs_by_segment():
    """Device x channel asymmetry should be a property of the data, not noise."""
    cfg = SmallDataGenConfig(n_users=6_000, n_products=40, n_orders=2_000)
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
    cfg = SmallDataGenConfig(n_users=120, n_products=10, n_orders=220)
    a = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    b = generate(cfg=cfg, seed=42).orders["order_id"].sum()
    assert a == b
