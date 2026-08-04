-- daily_kpis: the executive-facing daily business pulse
--
-- Three grains feed this, and each is dated by the event it describes:
--   * a session belongs to the day it started
--   * a purchase belongs to the day checkout completed, which for a converting
--     session is its last event
--   * an order belongs to its transaction timestamp
--
-- Dating purchases by session_start instead of session_end used to put a
-- session that started at 23:55 and checked out at 00:10 on different days from
-- its own order, which let `orders` exceed `purchase_sessions` on 6 days.
--
-- The spine is a union rather than a join off sessions: a day with orders but
-- no recorded sessions must still appear, or it silently vanishes from every
-- KPI built on this view.
CREATE OR REPLACE VIEW daily_kpis AS
WITH session_day AS (
    SELECT
        CAST(session_start AS DATE) AS metric_date,
        COUNT(*)                    AS sessions
    FROM fct_sessions
    GROUP BY CAST(session_start AS DATE)
),
purchase_day AS (
    SELECT
        CAST(session_end AS DATE) AS metric_date,
        COUNT(*)                  AS purchase_sessions
    FROM fct_sessions
    WHERE has_purchase = 1
    GROUP BY CAST(session_end AS DATE)
),
order_day AS (
    SELECT
        order_date         AS metric_date,
        COUNT(*)           AS orders,
        SUM(order_revenue) AS revenue,
        SUM(order_margin)  AS margin,
        SUM(item_count)    AS items_sold,
        AVG(order_revenue) AS avg_order_value
    FROM fct_orders
    WHERE status NOT IN ('Cancelled', 'Returned')
    GROUP BY order_date
),
-- Counted separately, and deliberately outside order_day: summing is_lost there
-- always returned zero, because that CTE has already filtered the lost orders
-- out. Cancel Rate read 0% for the life of the project as a result.
lost_day AS (
    SELECT
        order_date AS metric_date,
        COUNT(*)   AS cancelled_orders
    FROM fct_orders
    WHERE is_lost = 1
    GROUP BY order_date
),
spine AS (
    SELECT metric_date FROM session_day
    UNION
    SELECT metric_date FROM purchase_day
    UNION
    SELECT metric_date FROM order_day
    UNION
    SELECT metric_date FROM lost_day
)
SELECT
    d.metric_date                           AS metric_date,
    COALESCE(s.sessions, 0)                 AS sessions,
    COALESCE(p.purchase_sessions, 0)        AS purchase_sessions,
    COALESCE(o.orders, 0)                   AS orders,
    COALESCE(o.revenue, 0.0)                AS revenue,
    COALESCE(o.margin, 0.0)                 AS margin,
    COALESCE(o.items_sold, 0)               AS items_sold,
    COALESCE(l.cancelled_orders, 0)         AS cancelled_orders,
    COALESCE(o.avg_order_value, 0.0)        AS avg_order_value,
    CASE WHEN COALESCE(s.sessions, 0) > 0
         THEN COALESCE(p.purchase_sessions, 0) * 1.0 / s.sessions
         ELSE NULL END                      AS conversion_rate
FROM spine d
LEFT JOIN session_day  s ON d.metric_date = s.metric_date
LEFT JOIN purchase_day p ON d.metric_date = p.metric_date
LEFT JOIN order_day    o ON d.metric_date = o.metric_date
LEFT JOIN lost_day     l ON d.metric_date = l.metric_date
ORDER BY d.metric_date;
