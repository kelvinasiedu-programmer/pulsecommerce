"""Shared pytest fixtures — build a tiny warehouse once per session."""

from __future__ import annotations

from pathlib import Path

import pytest

from pulsecommerce.config import SmallDataGenConfig
from pulsecommerce.data.generator import generate
from pulsecommerce.warehouse import Warehouse


@pytest.fixture(scope="session")
def tiny_dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("raw")
    cfg = SmallDataGenConfig(n_users=600, n_products=40, n_orders=1_500, n_events_per_user_mean=6.0)
    dataset = generate(cfg=cfg, seed=7)
    dataset.write_parquet(out)
    return out


@pytest.fixture(scope="session")
def warehouse(tiny_dataset: Path, tmp_path_factory: pytest.TempPathFactory) -> Warehouse:
    db_path = tmp_path_factory.mktemp("wh") / "test.duckdb"
    wh = Warehouse(path=db_path)
    wh.connect()
    wh.build(raw_dir=tiny_dataset)
    yield wh
    wh.close()
