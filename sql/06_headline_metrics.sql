-- =====================================================================
-- 06_headline_metrics.sql - the official metric definitions from the brief, in one view.
-- Use it to validate the dashboard numbers (Power BI measures must reproduce these).
-- =====================================================================
CREATE OR REPLACE VIEW dw.v_headline_metrics AS
SELECT
    SUM(gross_amount)                                                        AS gross_sales,
    SUM(net_amount)            FILTER (WHERE NOT is_cancelled)               AS nmv,
    SUM(net_amount)  FILTER (WHERE NOT is_cancelled)
      - SUM(returned_amount) FILTER (WHERE NOT is_cancelled)                 AS net_revenue,
    SUM(cost_amount) FILTER (WHERE is_kept)                                  AS cost_of_goods_kept,
    SUM(net_amount)  FILTER (WHERE NOT is_cancelled)
      - SUM(returned_amount) FILTER (WHERE NOT is_cancelled)
      - SUM(cost_amount) FILTER (WHERE is_kept)                              AS margin,
    COUNT(DISTINCT order_id)                                                 AS all_orders,
    COUNT(DISTINCT order_id) FILTER (WHERE is_cancelled)                     AS cancelled_orders,
    ROUND(100.0 * COUNT(DISTINCT order_id) FILTER (WHERE is_cancelled) / COUNT(DISTINCT order_id), 2) AS cancellation_rate_pct,
    COUNT(DISTINCT order_id) FILTER (WHERE NOT is_cancelled)                 AS non_cancelled_orders,
    ROUND(SUM(net_amount) FILTER (WHERE NOT is_cancelled)
          / COUNT(DISTINCT order_id) FILTER (WHERE NOT is_cancelled), 2)     AS aov,
    SUM(quantity)    FILTER (WHERE NOT is_cancelled)                         AS units,
    COUNT(DISTINCT customer_key) FILTER (WHERE NOT is_cancelled AND customer_key <> -1) AS active_customers,
    COUNT(*) FILTER (WHERE is_delivered)                                     AS delivered_lines,
    COUNT(*) FILTER (WHERE is_delivered AND is_returned)                     AS returned_lines,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_delivered AND is_returned)
          / NULLIF(COUNT(*) FILTER (WHERE is_delivered),0), 2)               AS return_rate_pct,
    -- extra (NOT in the official margin formula): what the courier cost NexusMart
    SUM(shipping_fee)                                                        AS shipping_cost_all_orders,
    SUM(shipping_fee) FILTER (WHERE is_cancelled)                            AS shipping_cost_on_cancelled_orders
FROM dw.fact_sales;
