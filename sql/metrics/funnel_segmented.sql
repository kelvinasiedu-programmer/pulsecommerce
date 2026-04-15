-- funnel_segmented: stage-to-stage conversion by device x channel
CREATE OR REPLACE VIEW funnel_segmented AS
SELECT
    device,
    channel,
    COUNT(*)                                             AS sessions,
    SUM(has_product_view)                                AS product_views,
    SUM(has_add_to_cart)                                 AS add_to_carts,
    SUM(has_checkout_start)                              AS checkout_starts,
    SUM(has_purchase)                                    AS purchases,
    SUM(has_product_view)   * 1.0 / NULLIF(COUNT(*), 0)              AS view_rate,
    SUM(has_add_to_cart)    * 1.0 / NULLIF(SUM(has_product_view), 0) AS cart_rate,
    SUM(has_checkout_start) * 1.0 / NULLIF(SUM(has_add_to_cart), 0)  AS checkout_rate,
    SUM(has_purchase)       * 1.0 / NULLIF(SUM(has_checkout_start), 0) AS purchase_rate,
    SUM(has_purchase)       * 1.0 / NULLIF(COUNT(*), 0)              AS overall_conversion
FROM fct_sessions
GROUP BY device, channel;
