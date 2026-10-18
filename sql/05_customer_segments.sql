-- =====================================================================
-- 05_customer_segments.sql - RFM segmentation, written back into dim_customer (SCD Type 1 overwrite).
-- Runs AFTER the fact load because it needs sales history.
--   Recency   = days from the customer's last NON-CANCELLED order to (last order date in data + 1)
--   Frequency = number of distinct non-cancelled orders
--   Monetary  = NMV (sum of net_amount on non-cancelled lines)
--   R and M scored 1-5 with NTILE (5 = best). F uses fixed bins because most customers have 1-3 orders
--   and NTILE would split ties arbitrarily:  1 order=1, 2=2, 3-4=3, 5-7=4, 8+=5.
--   Segment rules (first match wins):
--     Champions R>=4 & F>=4 | Loyal R>=3 & F>=3 | At Risk R<=2 & F>=3
--     New Customers F=1 & R>=4 | Potential Loyalists R>=3 & F<=2 | Hibernating (everything else)
-- =====================================================================
UPDATE dw.dim_customer
SET segment='No Purchase', rfm_recency_days=NULL, rfm_frequency=NULL, rfm_monetary=NULL,
    rfm_r=NULL, rfm_f=NULL, rfm_m=NULL
WHERE customer_key <> -1;

WITH ref AS (
    SELECT MAX(d.full_date) + 1 AS ref_date
    FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key
),
cust AS (
    SELECT f.customer_key, MAX(d.full_date) AS last_order, COUNT(DISTINCT f.order_id) AS freq, SUM(f.net_amount) AS monetary
    FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key
    WHERE NOT f.is_cancelled AND f.customer_key <> -1
    GROUP BY f.customer_key
),
scored AS (
    SELECT c.*, (SELECT ref_date FROM ref) - c.last_order AS recency_days,
           NTILE(5) OVER (ORDER BY ((SELECT ref_date FROM ref) - c.last_order) DESC, c.customer_key) AS r,
           CASE WHEN freq = 1 THEN 1 WHEN freq = 2 THEN 2 WHEN freq <= 4 THEN 3 WHEN freq <= 7 THEN 4 ELSE 5 END AS f,
           NTILE(5) OVER (ORDER BY c.monetary, c.customer_key) AS m
    FROM cust c
)
UPDATE dw.dim_customer dc
SET rfm_recency_days = s.recency_days, rfm_frequency = s.freq, rfm_monetary = s.monetary,
    rfm_r = s.r, rfm_f = s.f, rfm_m = s.m,
    segment = CASE WHEN s.r >= 4 AND s.f >= 4 THEN 'Champions'
                   WHEN s.r >= 3 AND s.f >= 3 THEN 'Loyal'
                   WHEN s.r <= 2 AND s.f >= 3 THEN 'At Risk'
                   WHEN s.f = 1 AND s.r >= 4 THEN 'New Customers'
                   WHEN s.r >= 3 AND s.f <= 2 THEN 'Potential Loyalists'
                   ELSE 'Hibernating' END,
    updated_at = now()
FROM scored s WHERE s.customer_key = dc.customer_key;
