"""Shared pytest fixtures - build a tiny warehouse once per session."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from pulsecommerce.config import SmallDataGenConfig
from pulsecommerce.data.generator import generate
from pulsecommerce.warehouse import Warehouse


@pytest.fixture(scope="session")
def repo_tmp_dir() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp" / "pytest"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="session")
def tiny_dataset(repo_tmp_dir: Path) -> Path:
    out = repo_tmp_dir / f"raw-{uuid4().hex}"
    out.mkdir(parents=True, exist_ok=True)
    cfg = SmallDataGenConfig(n_users=600, n_products=40, n_orders=1_500, n_events_per_user_mean=6.0)
    dataset = generate(cfg=cfg, seed=7)
    dataset.write_parquet(out)
    return out


@pytest.fixture(scope="session")
def warehouse(tiny_dataset: Path, repo_tmp_dir: Path) -> Warehouse:
    db_dir = repo_tmp_dir / f"wh-{uuid4().hex}"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "test.duckdb"
    wh = Warehouse(path=db_path)
    wh.connect()
    wh.build(raw_dir=tiny_dataset)
    yield wh
    wh.close()
