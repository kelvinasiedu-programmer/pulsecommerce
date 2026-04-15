CREATE OR REPLACE VIEW stg_products AS
SELECT
    CAST(product_id AS BIGINT)   AS product_id,
    name,
    category,
    brand,
    CAST(cost AS DOUBLE)         AS cost,
    CAST(retail_price AS DOUBLE) AS retail_price
FROM raw_products;
