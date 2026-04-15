-- daily_kpis: the executive-facing daily business pulse
CREATE OR REPLACE VIEW daily_kpis AS
WITH session_day AS (
    SELECT
        CAST(session_start AS DATE) AS metric_date,
        COUNT(*)                    AS sessions,
        SUM(has_purchase)           AS purchase_sessions
    FROM fct_sessions
    GROUP BY CAST(session_start AS DATE)
),
order_day AS (
    SELECT
        order_date AS metric_date,
        COUNT(*)          AS orders,
        SUM(order_revenue) AS revenue,
        SUM(order_margin)  AS margin,
        SUM(item_count)    AS items_sold,
        SUM(is_lost)       AS cancelled_orders,
        AVG(order_revenue) AS avg_order_value
    FROM fct_orders
    WHERE status NOT IN ('Cancelled', 'Returned')
    GROUP BY order_date
)
SELECT
    COALESCE(s.metric_date, o.metric_date)  AS metric_date,
    COALESCE(s.sessions, 0)                 AS sessions,
    COALESCE(s.purchase_sessions, 0)        AS purchase_sessions,
    COALESCE(o.orders, 0)                   AS orders,
    COALESCE(o.revenue, 0.0)                AS revenue,
    COALESCE(o.margin, 0.0)                 AS margin,
    COALESCE(o.items_sold, 0)               AS items_sold,
    COALESCE(o.cancelled_orders, 0)         AS cancelled_orders,
    COALESCE(o.avg_order_value, 0.0)        AS avg_order_value,
    CASE WHEN COALESCE(s.sessions, 0) > 0
         THEN COALESCE(s.purchase_sessions, 0) * 1.0 / s.sessions
         ELSE NULL END                      AS conversion_rate
FROM session_day s
FULL OUTER JOIN order_day o ON s.metric_date = o.metric_date
ORDER BY metric_date;
