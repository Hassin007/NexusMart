-- =====================================================================
-- 03_build_fact.sql - FactSales, grain = ONE ROW PER ORDER LINE ITEM.
-- Rebuilt from scratch inside one transaction => re-running never duplicates rows (idempotent).
--
-- Rules implemented here (each one is a documented design decision):
--  * Returns are aggregated PER LINE using VALID returns only (is_valid_return), so the grain holds.
--  * Shipping fee is one charge per ORDER: allocated to lines in proportion to gross value, last
--    rounding cent pushed onto the first line, so lines add up to the order fee EXACTLY (no double count).
--  * LocationKey = SHIP-TO city (orders.ship_city_id), not the customer's home city.
--  * ReturnDateKey = Unknown(-1) when a valid return has an impossible date (before the order).
--  * Cost = cost_price x quantity. Lines of Unknown products have no cost: estimated from the
--    overall median cost/price ratio and flagged (cost_estimated).
-- =====================================================================
BEGIN;
TRUNCATE dw.fact_sales;

INSERT INTO dw.fact_sales (
    order_item_id, order_id, date_key, customer_key, product_key, seller_key, location_key,
    quantity, unit_price, gross_amount, discount_amount, net_amount, discount_pct,
    cost_amount, cost_estimated, shipping_fee, shipping_fee_estimated, has_shipment, shipping_days,
    is_cancelled, is_in_transit, is_delivered, is_returned, is_kept,
    returned_amount, return_date_key, return_reason, return_status,
    order_status, payment_method, channel)
WITH cost_ratio AS (
    SELECT (percentile_cont(0.5) WITHIN GROUP (ORDER BY cost_price / NULLIF(list_price,0)))::numeric AS r
    FROM staging.products WHERE cost_price > 0 AND list_price > 0
),
ret_sum AS (                                  -- all VALID returns of a line, summed
    SELECT order_item_id, SUM(refund_amount) AS returned_amount
    FROM staging.returns WHERE is_valid_return GROUP BY order_item_id
),
ret_last AS (                                 -- return details = latest VALID return of the line
    SELECT DISTINCT ON (order_item_id) order_item_id, return_date, return_reason, return_status
    FROM staging.returns WHERE is_valid_return
    ORDER BY order_item_id, return_date DESC NULLS LAST, return_id DESC
),
lines AS (
    SELECT oi.*, o.customer_id, o.order_date, o.order_status, o.ship_city_id, o.channel, o.discount_pct,
           op.primary_payment_method,
           sh.shipping_fee AS order_fee, sh.fee_imputed AS fee_imputed, sh.shipping_days,
           (sh.order_id IS NOT NULL) AS has_shipment,
           ROW_NUMBER() OVER (PARTITION BY oi.order_id ORDER BY oi.order_item_id) AS rn,
           COUNT(*)     OVER (PARTITION BY oi.order_id) AS n_lines,
           SUM(oi.gross_amount) OVER (PARTITION BY oi.order_id) AS order_gross
    FROM staging.order_items oi
    JOIN staging.orders o        ON o.order_id = oi.order_id
    LEFT JOIN staging.order_payment op ON op.order_id = oi.order_id
    LEFT JOIN staging.shipping sh      ON sh.order_id = oi.order_id
),
alloc AS (
    SELECT l.*,
           ROUND(COALESCE(order_fee,0) * CASE WHEN order_gross > 0 THEN gross_amount / order_gross
                                              ELSE 1.0 / n_lines END, 2) AS fee_part
    FROM lines l
),
alloc2 AS (
    SELECT a.*, COALESCE(order_fee,0) - SUM(fee_part) OVER (PARTITION BY order_id) AS fee_diff FROM alloc a
)
SELECT
    a.order_item_id, a.order_id,
    to_char(a.order_date,'YYYYMMDD')::int,
    COALESCE(dc.customer_key,-1), COALESCE(dp.product_key,-1), COALESCE(ds.seller_key,-1), COALESCE(dl.location_key,-1),
    a.quantity::int, a.unit_price, a.gross_amount, a.discount_amount, a.net_amount, a.discount_pct,
    CASE WHEN dp.cost_price IS NOT NULL THEN ROUND(dp.cost_price * a.quantity, 2)
         ELSE ROUND(a.unit_price * a.quantity * (SELECT r FROM cost_ratio), 2) END,
    (dp.cost_price IS NULL) OR COALESCE(p.cost_imputed, false),
    a.fee_part + CASE WHEN a.rn = 1 THEN a.fee_diff ELSE 0 END,
    COALESCE(a.fee_imputed,false), a.has_shipment,
    a.shipping_days::int,
    (a.order_status = 'Cancelled'),
    (a.order_status = 'In Transit'),
    (a.order_status NOT IN ('Cancelled','In Transit')),
    (rl.order_item_id IS NOT NULL),
    (a.order_status <> 'Cancelled' AND rl.order_item_id IS NULL),
    COALESCE(rs.returned_amount, 0),
    CASE WHEN rl.order_item_id IS NULL THEN NULL
         WHEN rl.return_date IS NULL OR rl.return_date < a.order_date OR rl.return_date > DATE '2025-12-31' THEN -1
         ELSE to_char(rl.return_date,'YYYYMMDD')::int END,
    rl.return_reason, rl.return_status,
    a.order_status, COALESCE(a.primary_payment_method,'Unknown'), a.channel
FROM alloc2 a
LEFT JOIN dw.dim_customer dc ON dc.customer_id = a.customer_id
LEFT JOIN dw.dim_product  dp ON dp.product_id  = a.product_id
LEFT JOIN staging.products p ON p.product_id   = a.product_id
LEFT JOIN dw.dim_seller   ds ON ds.seller_id   = a.seller_id
LEFT JOIN dw.dim_location dl ON dl.city_id     = a.ship_city_id
LEFT JOIN ret_sum  rs ON rs.order_item_id = a.order_item_id
LEFT JOIN ret_last rl ON rl.order_item_id = a.order_item_id;

COMMIT;
ANALYZE dw.fact_sales;
