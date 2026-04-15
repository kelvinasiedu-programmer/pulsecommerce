CREATE OR REPLACE VIEW stg_events AS
SELECT
    CAST(event_id AS BIGINT)     AS event_id,
    CAST(user_id AS BIGINT)      AS user_id,
    CAST(session_id AS BIGINT)   AS session_id,
    event_type,
    device,
    channel,
    CAST(occurred_at AS TIMESTAMP) AS occurred_at,
    CAST(occurred_at AS DATE)    AS event_date
FROM raw_events;
