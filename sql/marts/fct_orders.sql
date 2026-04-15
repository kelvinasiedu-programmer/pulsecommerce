-- fct_orders: one row per order, enriched with revenue/margin/item counts
CREATE OR REPLACE TABLE fct_orders AS
WITH items_agg AS (
    SELECT
        order_id,
        COUNT(*)              AS item_count,
        SUM(sale_price)       AS order_revenue,
        SUM(cost)              AS order_cost,
        SUM(gross_margin)     AS order_margin,
        AVG(discount_pct)     AS avg_discount_pct
    FROM stg_order_items
    GROUP BY order_id
)
SELECT
    o.order_id,
    o.user_id,
    o.status,
    o.created_at,
    o.order_date,
    o.order_week,
    o.order_month,
    o.device,
    o.channel,
    i.item_count,
    i.order_revenue,
    i.order_cost,
    i.order_margin,
    i.avg_discount_pct,
    CASE WHEN o.status IN ('Cancelled', 'Returned') THEN 1 ELSE 0 END AS is_lost
FROM stg_orders o
LEFT JOIN items_agg i ON o.order_id = i.order_id;
