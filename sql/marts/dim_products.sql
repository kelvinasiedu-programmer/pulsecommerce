CREATE OR REPLACE TABLE dim_products AS
WITH sales AS (
    SELECT
        product_id,
        SUM(sale_price)    AS lifetime_revenue,
        SUM(gross_margin)  AS lifetime_margin,
        COUNT(*)           AS units_sold
    FROM stg_order_items
    WHERE status NOT IN ('Cancelled', 'Returned')
    GROUP BY product_id
)
SELECT
    p.product_id,
    p.name,
    p.category,
    p.brand,
    p.cost,
    p.retail_price,
    COALESCE(s.units_sold, 0)       AS units_sold,
    COALESCE(s.lifetime_revenue, 0) AS lifetime_revenue,
    COALESCE(s.lifetime_margin, 0)  AS lifetime_margin
FROM stg_products p
LEFT JOIN sales s ON p.product_id = s.product_id;
