from __future__ import annotations

import importlib
from pathlib import Path


def test_config_respects_data_dir_env(monkeypatch):
    custom_data_dir = Path.cwd() / ".tmp" / "custom-data-root"
    monkeypatch.setenv("PULSECOMMERCE_DATA_DIR", str(custom_data_dir))

    import pulsecommerce.config as config

    config = importlib.reload(config)
    assert config.DATA_DIR == custom_data_dir
    assert config.RAW_DIR == custom_data_dir / "raw"
    assert config.WAREHOUSE_PATH == custom_data_dir / "warehouse" / "pulse.duckdb"

    monkeypatch.delenv("PULSECOMMERCE_DATA_DIR", raising=False)
    importlib.reload(config)
