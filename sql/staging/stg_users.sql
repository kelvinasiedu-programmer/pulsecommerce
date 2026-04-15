-- stg_users: typed, renamed, null-cleaned copy of raw.users
CREATE OR REPLACE VIEW stg_users AS
SELECT
    CAST(user_id AS BIGINT)      AS user_id,
    LOWER(email)                 AS email,
    first_name,
    last_name,
    gender,
    CAST(age AS INTEGER)         AS age,
    country,
    traffic_source,
    CAST(created_at AS TIMESTAMP) AS created_at
FROM raw_users;
