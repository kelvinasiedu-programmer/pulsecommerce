CREATE OR REPLACE VIEW stg_order_items AS
SELECT
    CAST(order_item_id AS BIGINT) AS order_item_id,
    CAST(order_id AS BIGINT)      AS order_id,
    CAST(user_id AS BIGINT)       AS user_id,
    CAST(product_id AS BIGINT)    AS product_id,
    category,
    status,
    CAST(retail_price AS DOUBLE)  AS retail_price,
    CAST(sale_price AS DOUBLE)    AS sale_price,
    CAST(cost AS DOUBLE)          AS cost,
    CAST(discount_pct AS DOUBLE)  AS discount_pct,
    sale_price - cost             AS gross_margin,
    CAST(created_at AS TIMESTAMP) AS created_at,
    CAST(created_at AS DATE)      AS item_date
FROM raw_order_items;
