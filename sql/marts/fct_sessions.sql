-- fct_sessions: collapse events to one row per session with funnel flags
CREATE OR REPLACE TABLE fct_sessions AS
SELECT
    session_id,
    ANY_VALUE(user_id)  AS user_id,
    MIN(occurred_at)    AS session_start,
    MAX(occurred_at)    AS session_end,
    ANY_VALUE(device)   AS device,
    ANY_VALUE(channel)  AS channel,
    MAX(CASE WHEN event_type = 'session_start'  THEN 1 ELSE 0 END) AS has_session_start,
    MAX(CASE WHEN event_type = 'product_view'   THEN 1 ELSE 0 END) AS has_product_view,
    MAX(CASE WHEN event_type = 'add_to_cart'    THEN 1 ELSE 0 END) AS has_add_to_cart,
    MAX(CASE WHEN event_type = 'checkout_start' THEN 1 ELSE 0 END) AS has_checkout_start,
    MAX(CASE WHEN event_type = 'purchase'       THEN 1 ELSE 0 END) AS has_purchase,
    COUNT(*)            AS event_count
FROM stg_events
GROUP BY session_id;
