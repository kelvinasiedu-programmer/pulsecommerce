.PHONY: help install install-dev clean generate warehouse pipeline app test lint format typecheck docker-build docker-run ci

PYTHON := python
PIP := $(PYTHON) -m pip

help:
	@echo "PulseCommerce — available targets:"
	@echo "  install       Install runtime dependencies"
	@echo "  install-dev   Install dev dependencies + package in editable mode"
	@echo "  generate      Generate synthetic ecommerce dataset"
	@echo "  warehouse     Build DuckDB warehouse (staging + marts + metrics)"
	@echo "  pipeline      Run the full analytical pipeline (all 5 layers)"
	@echo "  app           Launch the Streamlit dashboard"
	@echo "  test          Run pytest with coverage"
	@echo "  lint          Ruff check"
	@echo "  format        Ruff format"
	@echo "  typecheck     Mypy"
	@echo "  ci            Full CI pipeline (lint + typecheck + test)"
	@echo "  docker-build  Build Docker image"
	@echo "  docker-run    Run dashboard in Docker"
	@echo "  clean         Remove caches and generated data"

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

generate:
	$(PYTHON) -m pulsecommerce.cli generate --seed 42

warehouse:
	$(PYTHON) -m pulsecommerce.cli warehouse

pipeline:
	$(PYTHON) -m pulsecommerce.cli pipeline

app:
	streamlit run dashboard/Home.py

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests

typecheck:
	mypy src

ci: lint typecheck test

docker-build:
	docker build -t pulsecommerce:latest .

docker-run:
	docker run --rm -p 8501:8501 pulsecommerce:latest

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf data/raw/*.parquet data/processed/*.parquet data/warehouse
