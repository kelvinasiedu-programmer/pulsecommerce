-- dim_customers: one row per user with lifetime KPIs
CREATE OR REPLACE TABLE dim_customers AS
WITH order_stats AS (
    SELECT
        user_id,
        COUNT(*)                  AS lifetime_orders,
        SUM(order_revenue)        AS lifetime_revenue,
        SUM(order_margin)         AS lifetime_margin,
        MIN(order_date)           AS first_order_date,
        MAX(order_date)           AS last_order_date,
        SUM(is_lost)              AS cancelled_or_returned_orders
    FROM fct_orders
    WHERE status NOT IN ('Cancelled', 'Returned')
    GROUP BY user_id
)
SELECT
    u.user_id,
    u.email,
    u.gender,
    u.age,
    u.country,
    u.traffic_source,
    u.created_at          AS signed_up_at,
    COALESCE(o.lifetime_orders, 0)   AS lifetime_orders,
    COALESCE(o.lifetime_revenue, 0.0) AS lifetime_revenue,
    COALESCE(o.lifetime_margin, 0.0)  AS lifetime_margin,
    o.first_order_date,
    o.last_order_date,
    COALESCE(o.cancelled_or_returned_orders, 0) AS cancelled_or_returned_orders,
    CASE WHEN o.lifetime_orders IS NULL THEN 'prospect'
         WHEN o.lifetime_orders = 1 THEN 'one_time'
         WHEN o.lifetime_orders BETWEEN 2 AND 4 THEN 'repeat'
         ELSE 'loyal'
    END AS customer_segment
FROM stg_users u
LEFT JOIN order_stats o ON u.user_id = o.user_id;
