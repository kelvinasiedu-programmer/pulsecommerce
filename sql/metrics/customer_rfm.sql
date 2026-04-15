-- customer_rfm: recency / frequency / monetary snapshot (feeds churn)
CREATE OR REPLACE VIEW customer_rfm AS
WITH last_obs AS (
    SELECT MAX(order_date) AS max_date FROM fct_orders
)
SELECT
    c.user_id,
    c.country,
    c.traffic_source,
    c.customer_segment,
    c.lifetime_orders,
    c.lifetime_revenue,
    c.lifetime_margin,
    c.cancelled_or_returned_orders,
    c.first_order_date,
    c.last_order_date,
    DATE_DIFF('day', c.last_order_date, (SELECT max_date FROM last_obs)) AS recency_days,
    c.lifetime_orders           AS frequency,
    c.lifetime_revenue          AS monetary
FROM dim_customers c
WHERE c.lifetime_orders > 0;
