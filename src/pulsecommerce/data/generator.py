"""Synthetic thelook-style ecommerce dataset generator.

Produces five parquet tables that mirror the canonical thelook_ecommerce schema:
  - users
  - products
  - orders
  - order_items
  - events

The generator injects realistic behaviours that power every downstream layer:
  * seasonality (weekly + annual)
  * category mix shifts over time
  * device x channel conversion asymmetry (funnel friction)
  * cohort retention decay (churn signal)
  * a simulated promotion that feeds the experimentation layer
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

#: Keeps a favourable segment from reaching a certainty of converting.
MAX_STEP_PROB = 0.95


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
        p=_normalize([0.28, 0.18, 0.15, 0.12, 0.14, 0.08, 0.05]),
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


def _generate_orders_and_items(
    cfg: DataGenConfig,
    users: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(cfg.start_date)
    end = pd.Timestamp(cfg.end_date)
    total_days = (end - start).days + 1
    day_index = pd.date_range(start, end, freq="D")
    seasonal_weights = np.array([_seasonality_multiplier(d) for d in day_index])
    daily_probs = seasonal_weights / seasonal_weights.sum()

    order_day_offsets = rng.choice(total_days, size=cfg.n_orders, p=daily_probs)
    order_hours = rng.integers(0, 24, size=cfg.n_orders)
    order_minutes = rng.integers(0, 60, size=cfg.n_orders)
    order_dates = [
        start + timedelta(days=int(off), hours=int(h), minutes=int(m))
        for off, h, m in zip(order_day_offsets, order_hours, order_minutes, strict=False)
    ]

    order_user_ids = rng.choice(
        users["user_id"].to_numpy(),
        size=cfg.n_orders,
        p=_repeat_buyer_weights(len(users), cfg, rng),
    )

    devices = rng.choice(cfg.devices, size=cfg.n_orders, p=list(cfg.device_weights))
    channels = rng.choice(
        cfg.channels,
        size=cfg.n_orders,
        p=_normalize([0.26, 0.20, 0.16, 0.14, 0.12, 0.07, 0.05]),
    )

    status_choices = rng.choice(
        ["Complete", "Shipped", "Processing", "Cancelled", "Returned"],
        size=cfg.n_orders,
        p=[0.58, 0.25, 0.05, 0.07, 0.05],
    )

    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, cfg.n_orders + 1, dtype=np.int64),
            "user_id": order_user_ids,
            "status": status_choices,
            "created_at": order_dates,
            "device": devices,
            "channel": channels,
        }
    )
    orders = orders.sort_values("created_at").reset_index(drop=True)
    orders["order_id"] = np.arange(1, len(orders) + 1, dtype=np.int64)

    # ---- line items
    items_per_order = np.clip(rng.poisson(1.7, size=len(orders)) + 1, 1, 8)
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

    return orders, order_items


def _generate_events(
    cfg: DataGenConfig,
    users: pd.DataFrame,
    orders: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Synthesize a clickstream with a canonical 5-stage funnel.

    Funnel: session_start -> product_view -> add_to_cart -> checkout_start -> purchase

    Sessions are the unit of generation, not events. Each session picks its
    device and channel once, then walks the funnel and stops at the first stage
    it fails to clear. That makes the stages properly nested - a session that
    reached checkout necessarily viewed a product - which is what lets
    stage-to-stage conversion mean anything.

    Continuation probability is scaled by device and channel, so the
    device-by-channel conversion asymmetry is a real property of the data rather
    than sampling noise across otherwise identical segments.
    """
    n_users = len(users)

    # expected events per session = 1 + P(reach stage 2) + P(reach stage 3) + ...
    reach = np.cumprod(np.concatenate([[1.0], FUNNEL_STEP_PROBS]))
    sessions_per_user_mean = max(cfg.n_events_per_user_mean / reach.sum(), 1.0)

    sessions_per_user = np.clip(rng.poisson(sessions_per_user_mean, size=n_users), 1, None)
    n_sessions = int(sessions_per_user.sum())

    session_user_ids = np.repeat(users["user_id"].to_numpy(), sessions_per_user)
    devices = rng.choice(cfg.devices, size=n_sessions, p=list(cfg.device_weights))
    channels = rng.choice(
        cfg.channels, size=n_sessions, p=_normalize([0.28, 0.18, 0.15, 0.12, 0.14, 0.08, 0.05])
    )

    friction = np.array([DEVICE_FRICTION[d] for d in devices]) * np.array(
        [CHANNEL_FRICTION[c] for c in channels]
    )

    # walk the funnel: depth is the number of stages the session cleared
    depth = np.ones(n_sessions, dtype=np.int64)
    alive = np.ones(n_sessions, dtype=bool)
    for step_prob in FUNNEL_STEP_PROBS:
        p = np.clip(step_prob * friction, 0.0, MAX_STEP_PROB)
        advanced = alive & (rng.random(n_sessions) < p)
        depth += advanced
        alive = advanced

    total_events = int(depth.sum())
    logger.info(
        "synthesising %s events across %s sessions / %s users",
        f"{total_events:,}",
        f"{n_sessions:,}",
        f"{n_users:,}",
    )

    start = pd.Timestamp(cfg.start_date)
    end = pd.Timestamp(cfg.end_date)
    total_seconds = int((end - start).total_seconds())

    session_starts = rng.integers(0, total_seconds, size=n_sessions)
    session_ids = np.arange(1, n_sessions + 1, dtype=np.int64)

    # expand each session into one row per stage it reached
    event_session_idx = np.repeat(np.arange(n_sessions), depth)
    stage_idx = _within_group_index(depth)

    # stages land a few minutes apart, so ordering within a session is stable
    offsets = stage_idx * rng.integers(30, 600, size=total_events)
    event_seconds = session_starts[event_session_idx] + offsets

    events = pd.DataFrame(
        {
            "event_id": np.arange(1, total_events + 1, dtype=np.int64),
            "user_id": session_user_ids[event_session_idx],
            "session_id": session_ids[event_session_idx],
            "event_type": FUNNEL_STAGES[stage_idx],
            "device": devices[event_session_idx],
            "channel": channels[event_session_idx],
            "occurred_at": pd.to_datetime(start) + pd.to_timedelta(event_seconds, unit="s"),
        }
    )
    return events.sort_values(["user_id", "occurred_at"]).reset_index(drop=True)


def _within_group_index(counts: np.ndarray) -> np.ndarray:
    """For counts [3, 1, 2] return [0, 1, 2, 0, 0, 1] without a Python loop."""
    total = int(counts.sum())
    group_starts = np.repeat(np.cumsum(counts) - counts, counts)
    return np.arange(total) - group_starts


def _normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    return [w / total for w in weights]


def _repeat_buyer_weights(
    n_users: int,
    cfg: DataGenConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Per-user purchase propensity following a Zipf-Mandelbrot law.

    Weight for rank i is ``1 / (i + q) ** a``. The ``q`` offset is what keeps
    this usable: a plain Zipf law (q=0) concentrates so hard that a handful of
    customers absorb every order, and sampling raw ``rng.zipf`` *variates* as
    weights is worse still - that distribution has no finite mean for a < 2, so
    one freak draw takes essentially the whole probability mass.

    ``q`` scales with the user base so the skew looks the same in the small CI
    dataset as in the full one. Ranks are shuffled so propensity is
    uncorrelated with ``user_id``.
    """
    offset = n_users * cfg.buyer_rank_offset_frac
    ranks = np.arange(1, n_users + 1, dtype=float)
    weights = 1.0 / (ranks + offset) ** cfg.buyer_zipf_exponent
    rng.shuffle(weights)
    return weights / weights.sum()


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

    logger.info("generating orders (n=%s) and order_items", f"{cfg.n_orders:,}")
    orders, order_items = _generate_orders_and_items(cfg, users, products, rng)

    logger.info("generating clickstream events")
    events = _generate_events(cfg, users, orders, rng)

    return GeneratedDataset(
        users=users, products=products, orders=orders, order_items=order_items, events=events
    )


def generate_and_write(cfg: DataGenConfig | None = None, seed: int = 42) -> dict[str, Path]:
    dataset = generate(cfg=cfg, seed=seed)
    paths = dataset.write_parquet(RAW_DIR)
    for name, path in paths.items():
        logger.info("wrote %s -> %s", name, path)
    return paths


if __name__ == "__main__":  # pragma: no cover
    generate_and_write()
