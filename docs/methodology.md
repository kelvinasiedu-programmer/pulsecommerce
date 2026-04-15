# Methodology

## Data

- **Source**: synthetic thelook-style dataset (`pulsecommerce.data.generator`)
- **Size (default)**: 25k users, 800 products, 95k orders, ~450k events over ~27 months
- **Seed**: `42` — the entire pipeline is deterministic

The generator encodes several business phenomena on purpose so every downstream layer has something to find:

- sinusoidal **annual seasonality** peaking in Nov/Dec
- **weekend lift** in sessions and orders
- **Zipf-distributed repeat buyers** so RFM skew is realistic
- **segment-dependent funnel friction** (mobile converts worse than desktop on most channels)
- **cohort retention decay** so Layer 4's churn labels have real signal

## Warehouse

Three-tier SQL discipline, dbt-style but without the service dependency:

- `staging/` — type casting and renaming only; one view per source table
- `marts/` — business entities with pre-joined context (`fct_orders`, `dim_customers`, `fct_sessions`, `dim_products`)
- `metrics/` — final KPI views consumed by Python layers (`daily_kpis`, `funnel_segmented`, `weekly_category`, `customer_rfm`)

Every Python layer reads from `metrics/` or `marts/` only — never from raw tables directly.

## Forecasting (Layer 3)

- **Unit of forecast**: revenue per category per ISO week
- **Minimum history**: 26 weeks required; categories below that are skipped
- **Models**:
  - *Seasonal-naive*: last-year-same-week (baseline)
  - *Holt-Winters*: additive trend + additive seasonality (period=52) when history ≥ 104 weeks
  - *XGBoost*: lag features (1, 2, 4, 8, 13, 26, 52), rolling stats, and calendar features
- **Backtest**: 3-fold walk-forward, fold size = forecast horizon (12 weeks)
- **Selection**: lowest average MAPE across folds

**Why walk-forward, not random k-fold?** Because leakage through time is the biggest trap in time-series ML. Random k-fold would let the model "see the future" through rolling lags.

## Churn (Layer 4)

- **Label**: `recency_days ≥ inactivity_days (90)` at the snapshot date (= latest order date)
- **Leakage control**: features are computed only on data ≤ `snapshot − 90 days`; customers whose `last_order_date` is inside the window are filtered out
- **Features**: age, tenure, recency, frequency, monetary, AOV, distinct categories, cancel rate, days-between-orders, country, traffic source
- **Models**:
  - *XGBoost* (primary) for signal
  - *Logistic regression* (baseline) for interpretability
- **Validation**: 25% stratified holdout; reported metrics are ROC-AUC and Average Precision
- **Segmentation**: risk deciles via `qcut(churn_risk, q=10)`

## Experiment (Layer 5)

- **Audience**: top-30% risk deciles from Layer 4 (minimum 500 users)
- **Assignment**: 50/50 random with a seed
- **Effect simulation**: treatment receives +8 pp absolute conversion boost and a small negative drift on guardrails — so the readout is realistic, not trivial
- **Tests**: Welch's two-sample t-test for every metric at α = 0.05
- **Decision rules** (see `kpi_dictionary.md`):
  - `ship` requires significant positive lift **and** no significant guardrail regression
  - `reject` on any significant guardrail regression
  - `iterate` on directional-but-not-significant lift

## Limitations

- Synthetic data — the absolute numbers are illustrative; the *method* is what's real
- Forecast intervals use a simple residual-std heuristic (replace with conformal prediction for production)
- Churn label definition is single-threshold; a multi-window or survival model would be stronger in production
- Experiment uses observational proxies (last 60 days) rather than a true concurrent randomisation — real Ship/No-Ship decisions require live randomised exposure
