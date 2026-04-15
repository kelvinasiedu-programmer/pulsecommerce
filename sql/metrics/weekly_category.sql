-- weekly_category: weekly revenue + units by category (feeds forecasting)
CREATE OR REPLACE VIEW weekly_category AS
SELECT
    DATE_TRUNC('week', item_date) AS week_start,
    category,
    SUM(sale_price)               AS revenue,
    SUM(gross_margin)             AS margin,
    COUNT(*)                      AS units_sold
FROM stg_order_items
WHERE status NOT IN ('Cancelled', 'Returned')
GROUP BY 1, 2
ORDER BY 1, 2;
