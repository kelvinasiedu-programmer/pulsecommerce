# KPI Dictionary

Every chart in PulseCommerce traces back to a metric defined here. When two layers disagree, this document wins.

## Health (Layer 1)

| Metric | Definition | SQL source | Owner |
|---|---|---|---|
| **Revenue** | Sum of `order_revenue` from `fct_orders` where `status NOT IN ('Cancelled','Returned')` | `daily_kpis.revenue` | Finance / Commercial |
| **Gross Margin** | Sum of `sale_price − cost` per line item, aggregated per order | `daily_kpis.margin` | Finance |
| **Orders** | Count of distinct `order_id` in `fct_orders`, excluding cancels/returns | `daily_kpis.orders` | Ops |
| **Sessions** | Count of distinct `session_id` in `fct_sessions` | `daily_kpis.sessions` | Marketing |
| **Average Order Value (AOV)** | Revenue ÷ Orders | Computed in Health layer | Commercial |
| **Conversion Rate** | Sessions with a purchase event ÷ total sessions | `daily_kpis.conversion_rate` | Growth |
| **Cancel Rate** | Cancelled orders ÷ total orders (excluding cancels) | Computed in Health layer | Ops |

## Funnel (Layer 2)

| Metric | Definition | SQL source |
|---|---|---|
| Stage conversion rate | Stage N sessions ÷ Stage N-1 sessions | `FunnelAnalyst.overall()` |
| Segment conversion | Purchases ÷ sessions within device × channel | `funnel_segmented.overall_conversion` |
| Lost revenue opportunity | (Best-segment conv − worst-segment conv) × worst-segment sessions × AOV | `FunnelAnalyst.insights()` |

## Forecast (Layer 3)

| Metric | Definition |
|---|---|
| MAPE | `mean(|y_true − y_pred| / y_true)` computed on the held-out fold |
| Walk-forward folds | 3 × 12-week folds, each trained on all history up to the fold start |
| Chosen model | Minimum average backtest MAPE across folds |
| 95% interval | `yhat ± 1.96 × σ(Δy)` (quick heuristic; replace with conformal in production) |

## Churn (Layer 4)

| Term | Definition |
|---|---|
| **Churn label** | `recency_days ≥ 90` as of snapshot = `max(order_date)` |
| **Recency** | Days since last non-cancelled order |
| **Frequency** | Lifetime count of non-cancelled orders |
| **Monetary** | Lifetime non-cancelled revenue |
| **Feature cutoff** | `snapshot − 90 days`: features are computed on data *before* the churn window to prevent leakage |
| **ROC-AUC** | Area under the receiver operating characteristic curve on a 25% stratified holdout |
| **Risk decile** | `qcut(churn_risk, q=10)` — decile 10 = top 10% highest risk |

## Experiment (Layer 5)

| Term | Definition |
|---|---|
| **Primary metric** | `conversion_rate` on the targeted audience |
| **Guardrail metrics** | `average_order_value`, `items_per_order`, `refund_rate_proxy` |
| **Significance test** | Welch's two-sample t-test (unequal variances) at α = 0.05 |
| **Recommendation rules** | `ship` = primary significant & positive **and** no guardrail regressions · `reject` = guardrail regression or no lift · `iterate` = directional lift but not significant |
