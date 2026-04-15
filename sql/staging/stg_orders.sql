CREATE OR REPLACE VIEW stg_orders AS
SELECT
    CAST(order_id AS BIGINT)      AS order_id,
    CAST(user_id AS BIGINT)       AS user_id,
    status,
    CAST(created_at AS TIMESTAMP) AS created_at,
    device,
    channel,
    CAST(created_at AS DATE)      AS order_date,
    DATE_TRUNC('week', created_at)  AS order_week,
    DATE_TRUNC('month', created_at) AS order_month
FROM raw_orders;
