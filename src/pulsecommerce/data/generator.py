"""Synthetic thelook-style ecommerce dataset generator.

Produces five parquet tables that mirror the canonical thelook_ecommerce schema:
  - users
  - products
  - orders
  - order_items
  - events

The clickstream is the source of truth. Sessions are generated first, walk the
funnel, and every session that reaches the purchase stage emits exactly one
order. That is what makes "241,035 sessions at 3.1% conversion" and "25,000
orders" the same statement instead of two unrelated ones.

The generator injects realistic behaviors that power every downstream layer:
  * seasonality (weekly + annual), applied to sessions so it flows into orders
  * device x channel conversion asymmetry (funnel friction)
  * per-user propensity, which produces the repeat-buyer skew
  * sessions constrained to a user's lifetime, so cohorts mean something
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from pulsecommerce.config import DATA_GEN, RAW_DIR, DataGenConfig, ensure_dirs
from pulsecommerce.logging_utils import get_logger

logger = get_logger(__name__)

#: Ordered funnel stages. A session emits the first `depth` of these.
FUNNEL_STAGES = np.array(
    ["session_start", "product_view", "add_to_cart", "checkout_start", "purchase"]
)

#: Baseline probability of clearing each step, for an average segment. The
#: product is the end-to-end conversion rate (~3%), in the range real ecommerce
#: sites report.
FUNNEL_STEP_PROBS = np.array([0.55, 0.35, 0.50, 0.32])

#: Multipliers on every step. Mobile browses as much but converts worse; paid
#: social and display send cheaper traffic than email or direct.
DEVICE_FRICTION: dict[str, float] = {
    "desktop": 1.15,
    "mobile": 0.90,
    "tablet": 1.00,
}
CHANNEL_FRICTION: dict[str, float] = {
    "Email": 1.25,
    "Direct": 1.20,
    "Organic Search": 1.05,
    "Referral": 1.00,
    "Paid Search": 0.95,
    "Social": 0.80,
    "Display": 0.70,
}

#: Session channel mix, positionally aligned with DataGenConfig.channels.
CHANNEL_MIX = np.array([0.28, 0.18, 0.15, 0.12, 0.14, 0.08, 0.05])

#: Keeps a favourable segment from reaching a certainty of converting.
MAX_STEP_PROB = 0.95

#: Bounds on the per-user activity multiplier, so one customer cannot dominate.
MIN_PROPENSITY = 0.15
MAX_PROPENSITY = 12.0


def _seasonality_multiplier(date: pd.Timestamp) -> float:
    """Yearly + weekly pattern. Peaks in Nov/Dec and on weekends."""
    day_of_year = date.dayofyear
    annual = 1.0 + 0.35 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
    holiday_boost = 1.0
    if date.month == 11 and date.day >= 20:
        holiday_boost = 1.6
    elif date.month == 12 and date.day <= 24:
        holiday_boost = 1.8
    weekly = 1.0 + 0.15 * math.sin(2 * math.pi * date.dayofweek / 7)
    return annual * holiday_boost * weekly


@dataclass
class GeneratedDataset:
    users: pd.DataFrame
    products: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    events: pd.DataFrame

    def write_parquet(self, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {}
        for name, frame in self.tables().items():
            path = out_dir / f"{name}.parquet"
            frame.to_parquet(path, index=False)
            paths[name] = path
        return paths

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "users": self.users,
            "products": self.products,
            "orders": self.orders,
            "order_items": self.order_items,
            "events": self.events,
        }


def _generate_users(cfg: DataGenConfig, rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    start = pd.Timestamp(cfg.start_date)
    end = pd.Timestamp(cfg.end_date)
    span_days = (end - start).days

    created_offsets = rng.integers(0, span_days, size=cfg.n_users)
    created_at = [start + timedelta(days=int(x)) for x in created_offsets]

    countries = rng.choice(
        cfg.countries,
        size=cfg.n_users,
        p=_normalize([0.55, 0.08, 0.12, 0.06, 0.05, 0.05, 0.05, 0.04]),
    )
    traffic_sources = rng.choice(
        cfg.channels,
        size=cfg.n_users,
        p=_normalize(list(CHANNEL_MIX)),
    )
    genders = rng.choice(["F", "M"], size=cfg.n_users, p=[0.56, 0.44])
    ages = rng.integers(18, 72, size=cfg.n_users)

    users = pd.DataFrame(
        {
            "user_id": np.arange(1, cfg.n_users + 1, dtype=np.int64),
            "email": [fake.unique.email() for _ in range(cfg.n_users)],
            "first_name": [fake.first_name() for _ in range(cfg.n_users)],
            "last_name": [fake.last_name() for _ in range(cfg.n_users)],
            "gender": genders,
            "age": ages,
            "country": countries,
            "traffic_source": traffic_sources,
            "created_at": created_at,
            "created_day": created_offsets.astype(np.int64),
        }
    )
    return users


def _generate_products(cfg: DataGenConfig, rng: np.random.Generator) -> pd.DataFrame:
    categories = rng.choice(
        cfg.categories,
        size=cfg.n_products,
        p=_normalize([0.25, 0.15, 0.12, 0.13, 0.12, 0.15, 0.08]),
    )
    cost = np.round(rng.gamma(shape=2.0, scale=12.0, size=cfg.n_products) + 3.0, 2)
    margin = rng.uniform(1.4, 2.6, size=cfg.n_products)
    retail_price = np.round(cost * margin, 2)

    products = pd.DataFrame(
        {
            "product_id": np.arange(1, cfg.n_products + 1, dtype=np.int64),
            "name": [f"Item-{i:04d}" for i in range(1, cfg.n_products + 1)],
            "category": categories,
            "brand": rng.choice(
                ["Aurora", "Northwind", "Halcyon", "Ember", "Loom", "Cascade", "Rift"],
                size=cfg.n_products,
            ),
            "cost": cost,
            "retail_price": retail_price,
        }
    )
    return products


def _expected_session_conversion(cfg: DataGenConfig) -> float:
    """Share of sessions that reach purchase, averaged over the traffic mix.

    Friction multipliers are applied per step and clipped, so the mix-weighted
    average is not the same as the baseline product. Computing it up front is
    what lets the generator back-solve how many sessions it needs to hit the
    target order count.
    """
    device_mix = dict(zip(cfg.devices, cfg.device_weights, strict=True))
    channel_mix = dict(zip(cfg.channels, _normalize(list(CHANNEL_MIX)), strict=True))

    expected = 0.0
    for device, device_p in device_mix.items():
        for channel, channel_p in channel_mix.items():
            friction = DEVICE_FRICTION[device] * CHANNEL_FRICTION[channel]
            reach = float(np.prod(np.clip(FUNNEL_STEP_PROBS * friction, 0.0, MAX_STEP_PROB)))
            expected += device_p * channel_p * reach
    return expected


def _user_propensity(n_users: int, cfg: DataGenConfig, rng: np.random.Generator) -> np.ndarray:
    """Per-user activity multiplier with mean 1, following Zipf-Mandelbrot ranks.

    Weight for rank i is ``1 / (i + q) ** a``. The ``q`` offset is what keeps
    this usable: a plain Zipf law (q=0) concentrates so hard that a handful of
    customers absorb every session, and sampling raw ``rng.zipf`` *variates* as
    weights is worse still - that distribution has no finite mean for a < 2, so
    one freak draw takes essentially the whole mass.

    Now that orders are emitted by the funnel rather than sampled directly, this
    is what produces the repeat-buyer skew: heavy users open more sessions, so
    they buy more often. Ranks are shuffled so propensity is uncorrelated with
    ``user_id``.
    """
    offset = n_users * cfg.buyer_rank_offset_frac
    ranks = np.arange(1, n_users + 1, dtype=float)
    weights = 1.0 / (ranks + offset) ** cfg.buyer_zipf_exponent
    rng.shuffle(weights)
    return np.clip(weights / weights.mean(), MIN_PROPENSITY, MAX_PROPENSITY)


def _generate_sessions(
    cfg: DataGenConfig,
    users: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """One row per session: who, where from, when, and how far down the funnel.

    Session counts scale with both user propensity and the share of the period
    the user existed for, so someone who signed up last month is not credited
    with two years of browsing. Session dates are drawn from the seasonal
    distribution restricted to each user's own lifetime, which is what keeps
    cohort retention meaningful and puts the seasonal shape into orders.
    """
    start = pd.Timestamp(cfg.start_date)
    end = pd.Timestamp(cfg.end_date)
    day_index = pd.date_range(start, end, freq="D")
    total_days = len(day_index)

    seasonal = np.array([_seasonality_multiplier(d) for d in day_index])
    daily_probs = seasonal / seasonal.sum()
    daily_cdf = np.cumsum(daily_probs)

    propensity = _user_propensity(len(users), cfg, rng)
    created_day = users["created_day"].to_numpy()
    active_frac = 1.0 - created_day / total_days

    target_sessions = cfg.n_orders / _expected_session_conversion(cfg)
    weight = propensity * active_frac
    lam = weight * (target_sessions / weight.sum())
    sessions_per_user = rng.poisson(lam)
    n_sessions = int(sessions_per_user.sum())

    session_user_ids = np.repeat(users["user_id"].to_numpy(), sessions_per_user)
    session_created_day = np.repeat(created_day, sessions_per_user)

    devices = rng.choice(cfg.devices, size=n_sessions, p=list(cfg.device_weights))
    channels = rng.choice(cfg.channels, size=n_sessions, p=_normalize(list(CHANNEL_MIX)))

    # Inverse-CDF sample of the seasonal day distribution, truncated to the
    # window that starts on the user's signup day.
    floor = np.where(session_created_day > 0, daily_cdf[session_created_day - 1], 0.0)
    draw = floor + rng.random(n_sessions) * (1.0 - floor)
    session_day = np.clip(
        np.searchsorted(daily_cdf, draw, side="left"), session_created_day, total_days - 1
    )
    session_second = rng.integers(0, 86_400, size=n_sessions)

    friction = np.array([DEVICE_FRICTION[d] for d in devices]) * np.array(
        [CHANNEL_FRICTION[c] for c in channels]
    )

    depth = np.ones(n_sessions, dtype=np.int64)
    alive = np.ones(n_sessions, dtype=bool)
    for step_prob in FUNNEL_STEP_PROBS:
        p = np.clip(step_prob * friction, 0.0, MAX_STEP_PROB)
        advanced = alive & (rng.random(n_sessions) < p)
        depth += advanced
        alive = advanced

    started_at = pd.to_datetime(start) + pd.to_timedelta(
        session_day * 86_400 + session_second, unit="s"
    )

    sessions = pd.DataFrame(
        {
            "session_id": np.arange(1, n_sessions + 1, dtype=np.int64),
            "user_id": session_user_ids,
            "device": devices,
            "channel": channels,
            "started_at": started_at,
            "stage_gap_s": rng.integers(30, 600, size=n_sessions),
            "depth": depth,
        }
    )

    purchases = int((depth == len(FUNNEL_STAGES)).sum())
    logger.info(
        "synthesised %s sessions across %s users -> %s purchases (%.2f%% conversion)",
        f"{n_sessions:,}",
        f"{len(users):,}",
        f"{purchases:,}",
        100.0 * purchases / max(n_sessions, 1),
    )
    return sessions


def _expand_events(sessions: pd.DataFrame) -> pd.DataFrame:
    """Expand each session into one row per funnel stage it reached.

    Stages are properly nested by construction - a session that reached checkout
    necessarily viewed a product - which is what lets stage-to-stage conversion
    mean anything.
    """
    depth = sessions["depth"].to_numpy()
    total_events = int(depth.sum())

    session_idx = np.repeat(np.arange(len(sessions)), depth)
    stage_idx = _within_group_index(depth)

    gap = sessions["stage_gap_s"].to_numpy()[session_idx]
    occurred_at = sessions["started_at"].to_numpy()[session_idx] + (
        stage_idx * gap * np.timedelta64(1, "s")
    )

    events = pd.DataFrame(
        {
            "event_id": np.arange(1, total_events + 1, dtype=np.int64),
            "user_id": sessions["user_id"].to_numpy()[session_idx],
            "session_id": sessions["session_id"].to_numpy()[session_idx],
            "event_type": FUNNEL_STAGES[stage_idx],
            "device": sessions["device"].to_numpy()[session_idx],
            "channel": sessions["channel"].to_numpy()[session_idx],
            "occurred_at": occurred_at,
        }
    )
    logger.info("expanded %s events", f"{total_events:,}")
    return events.sort_values(["user_id", "occurred_at"]).reset_index(drop=True)


def _generate_orders_and_items(
    cfg: DataGenConfig,
    sessions: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Emit exactly one order per session that reached the purchase stage.

    Device, channel, user and timestamp are inherited from the session, so the
    funnel's purchase count and the orders table are the same number by
    construction rather than by coincidence.
    """
    buyers = sessions[sessions["depth"] == len(FUNNEL_STAGES)].sort_values("started_at")
    n_orders = len(buyers)

    # The order lands on the purchase event, which is the last stage of the session.
    purchase_offset = pd.to_timedelta(
        buyers["stage_gap_s"].to_numpy() * (len(FUNNEL_STAGES) - 1), unit="s"
    )

    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, n_orders + 1, dtype=np.int64),
            "user_id": buyers["user_id"].to_numpy(),
            "session_id": buyers["session_id"].to_numpy(),
            "status": rng.choice(
                ["Complete", "Shipped", "Processing", "Cancelled", "Returned"],
                size=n_orders,
                p=[0.58, 0.25, 0.05, 0.07, 0.05],
            ),
            "created_at": buyers["started_at"].to_numpy() + purchase_offset,
            "device": buyers["device"].to_numpy(),
            "channel": buyers["channel"].to_numpy(),
        }
    ).reset_index(drop=True)

    items_per_order = np.clip(rng.poisson(1.7, size=n_orders) + 1, 1, 8)
    total_items = int(items_per_order.sum())

    item_order_ids = np.repeat(orders["order_id"].to_numpy(), items_per_order)
    item_order_dates = np.repeat(orders["created_at"].to_numpy(), items_per_order)
    item_user_ids = np.repeat(orders["user_id"].to_numpy(), items_per_order)
    item_status = np.repeat(orders["status"].to_numpy(), items_per_order)

    product_weights = rng.dirichlet(np.ones(len(products)) * 0.6)
    picked_products = rng.choice(
        products["product_id"].to_numpy(), size=total_items, p=product_weights
    )
    prod_lookup = products.set_index("product_id")
    retail_price = prod_lookup.loc[picked_products, "retail_price"].to_numpy()
    cost = prod_lookup.loc[picked_products, "cost"].to_numpy()
    category = prod_lookup.loc[picked_products, "category"].to_numpy()
    discount = rng.choice([0.0, 0.0, 0.0, 0.10, 0.20, 0.30], size=total_items)
    sale_price = np.round(retail_price * (1.0 - discount), 2)

    order_items = pd.DataFrame(
        {
            "order_item_id": np.arange(1, total_items + 1, dtype=np.int64),
            "order_id": item_order_ids,
            "user_id": item_user_ids,
            "product_id": picked_products,
            "category": category,
            "created_at": item_order_dates,
            "status": item_status,
            "retail_price": retail_price,
            "sale_price": sale_price,
            "cost": cost,
            "discount_pct": np.round(discount, 2),
        }
    )

    logger.info("emitted %s orders / %s line items", f"{n_orders:,}", f"{total_items:,}")
    return orders, order_items


def _within_group_index(counts: np.ndarray) -> np.ndarray:
    """For counts [3, 1, 2] return [0, 1, 2, 0, 0, 1] without a Python loop."""
    total = int(counts.sum())
    group_starts = np.repeat(np.cumsum(counts) - counts, counts)
    return np.arange(total) - group_starts


def _normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    return [w / total for w in weights]


def generate(cfg: DataGenConfig | None = None, seed: int = 42) -> GeneratedDataset:
    cfg = cfg or DATA_GEN
    ensure_dirs()
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    logger.info("generating users (n=%s)", f"{cfg.n_users:,}")
    users = _generate_users(cfg, rng, fake)

    logger.info("generating products (n=%s)", f"{cfg.n_products:,}")
    products = _generate_products(cfg, rng)

    logger.info("generating sessions (target %s orders)", f"{cfg.n_orders:,}")
    sessions = _generate_sessions(cfg, users, rng)

    events = _expand_events(sessions)
    orders, order_items = _generate_orders_and_items(cfg, sessions, products, rng)

    return GeneratedDataset(
        users=users.drop(columns=["created_day"]),
        products=products,
        orders=orders,
        order_items=order_items,
        events=events,
    )


def generate_and_write(cfg: DataGenConfig | None = None, seed: int = 42) -> dict[str, Path]:
    dataset = generate(cfg=cfg, seed=seed)
    paths = dataset.write_parquet(RAW_DIR)
    for name, path in paths.items():
        logger.info("wrote %s -> %s", name, path)
    return paths


if __name__ == "__main__":  # pragma: no cover
    generate_and_write()
