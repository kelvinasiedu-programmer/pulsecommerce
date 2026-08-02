"""Central config: paths, dataset parameters, and model settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parents[3]


REPO_ROOT: Path = _repo_root()
DATA_DIR: Path = REPO_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
WAREHOUSE_DIR: Path = DATA_DIR / "warehouse"
TABLEAU_DIR: Path = DATA_DIR / "tableau"
SQL_DIR: Path = REPO_ROOT / "sql"
SITE_DIR: Path = REPO_ROOT / "site"
DASHBOARD_ASSETS: Path = REPO_ROOT / "dashboard" / "assets"
MODELS_DIR: Path = DATA_DIR / "models"
WAREHOUSE_PATH: Path = WAREHOUSE_DIR / "pulse.duckdb"


@dataclass(frozen=True)
class DataGenConfig:
    """Controls the synthetic dataset size and realism."""

    n_users: int = 25_000
    n_products: int = 800
    n_orders: int = 95_000
    n_events_per_user_mean: float = 18.0
    start_date: str = "2024-01-01"
    end_date: str = "2026-03-31"
    # Repeat-buyer skew (Zipf-Mandelbrot): weight ~ 1 / (rank + offset) ** exponent,
    # where offset = n_users * buyer_rank_offset_frac so the shape holds at any
    # dataset size. Tuned so ~64% of users ever order, the top 20% of buyers drive
    # ~72% of orders, and the busiest customer stays under ~100 orders.
    buyer_zipf_exponent: float = 1.6
    buyer_rank_offset_frac: float = 0.032
    channels: tuple[str, ...] = (
        "Organic Search",
        "Paid Search",
        "Social",
        "Email",
        "Direct",
        "Referral",
        "Display",
    )
    devices: tuple[str, ...] = ("desktop", "mobile", "tablet")
    device_weights: tuple[float, ...] = (0.35, 0.55, 0.10)
    countries: tuple[str, ...] = ("US", "CA", "UK", "DE", "FR", "AU", "BR", "JP")
    categories: tuple[str, ...] = (
        "Apparel",
        "Footwear",
        "Accessories",
        "Home",
        "Beauty",
        "Electronics",
        "Outdoor",
    )


@dataclass(frozen=True)
class SmallDataGenConfig(DataGenConfig):
    """A smaller config used in CI / quick smoke tests."""

    n_users: int = 2_500
    n_products: int = 120
    n_orders: int = 8_000
    n_events_per_user_mean: float = 10.0


@dataclass(frozen=True)
class ForecastConfig:
    horizon_weeks: int = 12
    min_history_weeks: int = 26
    backtest_folds: int = 3


@dataclass(frozen=True)
class ChurnConfig:
    inactivity_days: int = 90
    observation_window_days: int = 180
    test_size: float = 0.25
    random_state: int = 42


@dataclass(frozen=True)
class ExperimentConfig:
    alpha: float = 0.05
    min_sample_size: int = 500
    guardrail_metrics: tuple[str, ...] = field(
        default=(
            "average_order_value",
            "items_per_order",
            "refund_rate_proxy",
        )
    )


DATA_GEN = DataGenConfig()
FORECAST = ForecastConfig()
CHURN = ChurnConfig()
EXPERIMENT = ExperimentConfig()


def ensure_dirs() -> None:
    for p in (
        DATA_DIR,
        RAW_DIR,
        PROCESSED_DIR,
        WAREHOUSE_DIR,
        TABLEAU_DIR,
        MODELS_DIR,
        DASHBOARD_ASSETS,
    ):
        p.mkdir(parents=True, exist_ok=True)
