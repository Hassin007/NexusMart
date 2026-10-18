-- =====================================================================
-- 01_schema.sql  -  NexusMart warehouse: schemas, staging tables, star schema
-- Idempotent: safe to run many times (CREATE ... IF NOT EXISTS).
--   staging.*  : 1:1 copy of the cleaned CSVs (truncated + reloaded every run)
--   dw.*       : the star schema  (1 fact table + 5 dimensions, no dimension->dimension links)
--   audit.*    : rejected rows, before/after counts, quality-check results
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS audit;

-- ------------------------------------------------------------ STAGING
CREATE TABLE IF NOT EXISTS staging.locations (
    city_id TEXT, city TEXT, province TEXT, region TEXT,
    latitude NUMERIC, longitude NUMERIC, population_tier TEXT, province_source TEXT);

CREATE TABLE IF NOT EXISTS staging.sellers (
    seller_id TEXT, seller_name TEXT, join_date DATE, seller_tier TEXT, city_id TEXT, rating NUMERIC);

CREATE TABLE IF NOT EXISTS staging.customers (
    customer_id TEXT, full_name TEXT, email TEXT, phone TEXT, gender TEXT,
    registration_date DATE, city_id TEXT, birth_year NUMERIC);

CREATE TABLE IF NOT EXISTS staging.customer_id_map (
    customer_id_original TEXT, customer_id_master TEXT, match_rule TEXT);

CREATE TABLE IF NOT EXISTS staging.products (
    product_id TEXT, product_name TEXT, category TEXT, sub_category TEXT, brand TEXT,
    list_price NUMERIC, cost_price NUMERIC, weight_kg NUMERIC, seller_id TEXT,
    cost_imputed BOOLEAN, list_price_imputed BOOLEAN, cost_gt_list BOOLEAN);

CREATE TABLE IF NOT EXISTS staging.product_id_map (
    product_id_original TEXT, product_id_master TEXT);

CREATE TABLE IF NOT EXISTS staging.orders (
    order_id TEXT, customer_id TEXT, order_date DATE, order_status TEXT, ship_city_id TEXT,
    order_total_reported NUMERIC, discount_code TEXT, discount_pct NUMERIC, channel TEXT,
    order_date_source TEXT, order_total_calc NUMERIC, recon_status TEXT);

CREATE TABLE IF NOT EXISTS staging.order_items (
    order_item_id TEXT, order_id TEXT, product_id TEXT, seller_id TEXT, quantity NUMERIC,
    unit_price NUMERIC, gross_amount NUMERIC, discount_amount NUMERIC, net_amount NUMERIC,
    discount_amount_raw NUMERIC, dq_flags TEXT);

CREATE TABLE IF NOT EXISTS staging.payments (
    payment_id TEXT, order_id TEXT, payment_method TEXT, payment_status TEXT,
    amount NUMERIC, payment_date DATE);

CREATE TABLE IF NOT EXISTS staging.order_payment (
    order_id TEXT, primary_payment_method TEXT, primary_payment_status TEXT,
    n_payments INT, payments_total NUMERIC, first_payment_date DATE);

CREATE TABLE IF NOT EXISTS staging.shipping (
    shipment_id TEXT, order_id TEXT, courier TEXT, shipped_date DATE, delivered_date DATE,
    shipping_fee NUMERIC, delivery_status TEXT, shipping_days NUMERIC,
    fee_imputed BOOLEAN, dq_flags TEXT);

CREATE TABLE IF NOT EXISTS staging.returns (
    return_id TEXT, order_item_id TEXT, return_date DATE, return_reason TEXT, return_status TEXT,
    is_valid_return BOOLEAN, refund_amount NUMERIC, dq_flags TEXT);

-- ------------------------------------------------------------ AUDIT
CREATE TABLE IF NOT EXISTS audit.rejects (
    source_file TEXT, source_row INT, record_key TEXT, reason_code TEXT,
    reason_detail TEXT, raw_record TEXT, rejected_at TIMESTAMP);

CREATE TABLE IF NOT EXISTS audit.cleaning_summary (
    file_name TEXT PRIMARY KEY, raw_rows INT, clean_rows INT, rejected_rows INT,
    merged_rows INT, identity_ok BOOLEAN, repairs JSONB, flags JSONB, loaded_at TIMESTAMP DEFAULT now());

CREATE TABLE IF NOT EXISTS audit.quality_check_results (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY, run_at TIMESTAMP DEFAULT now(),
    check_name TEXT, actual NUMERIC, expectation TEXT, status TEXT, severity TEXT);

-- ------------------------------------------------------------ REFERENCE: event calendar
-- The one external dataset the brief allows: the static public-holiday calendar from the brief.
CREATE TABLE IF NOT EXISTS dw.ref_event_calendar (
    event_name TEXT, start_date DATE, end_date DATE, PRIMARY KEY (event_name, start_date));

-- ------------------------------------------------------------ DIMENSIONS
-- Surrogate key -1 is the "Unknown" member in every dimension (natural key 'UNKNOWN').
CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INT PRIMARY KEY,                -- yyyymmdd ; -1 = Unknown
    full_date DATE NOT NULL UNIQUE,          -- Unknown member uses 1900-01-01
    day_of_month INT, day_name TEXT, day_of_week INT, week_of_year INT, week_start_date DATE,
    month_number INT, month_name TEXT, year_month TEXT, quarter INT, year INT,
    is_weekend BOOLEAN, is_ramadan BOOLEAN, is_eid_ul_fitr BOOLEAN, is_eid_ul_adha BOOLEAN,
    is_eid BOOLEAN, is_independence_day BOOLEAN, is_11_11 BOOLEAN, is_black_friday BOOLEAN,
    is_public_holiday BOOLEAN, festival_name TEXT, is_unknown BOOLEAN DEFAULT FALSE);

CREATE TABLE IF NOT EXISTS dw.dim_customer (
    customer_key INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,        -- master ID after de-duplication
    full_name TEXT, email TEXT, phone TEXT, gender TEXT, registration_date DATE, birth_year INT,
    city_id TEXT, city TEXT, province TEXT, region TEXT, population_tier TEXT,   -- denormalised (no link to dim_location)
    segment TEXT DEFAULT 'No Purchase',      -- RFM segment (refreshed after the fact load)
    rfm_recency_days INT, rfm_frequency INT, rfm_monetary NUMERIC,
    rfm_r INT, rfm_f INT, rfm_m INT,
    is_unknown BOOLEAN DEFAULT FALSE, updated_at TIMESTAMP DEFAULT now());     -- SCD Type 1: overwrite in place

CREATE TABLE IF NOT EXISTS dw.dim_product (
    product_key INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id TEXT NOT NULL UNIQUE,
    product_name TEXT, category TEXT, sub_category TEXT, brand TEXT,
    list_price NUMERIC, cost_price NUMERIC, weight_kg NUMERIC,
    is_unknown BOOLEAN DEFAULT FALSE, updated_at TIMESTAMP DEFAULT now());

CREATE TABLE IF NOT EXISTS dw.dim_seller (
    seller_key INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    seller_id TEXT NOT NULL UNIQUE,
    seller_name TEXT, join_date DATE, seller_tier TEXT, rating NUMERIC,
    city_id TEXT, city TEXT, province TEXT, region TEXT,
    is_unknown BOOLEAN DEFAULT FALSE, updated_at TIMESTAMP DEFAULT now());

CREATE TABLE IF NOT EXISTS dw.dim_location (
    location_key INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    city_id TEXT NOT NULL UNIQUE,
    city TEXT, province TEXT, region TEXT, latitude NUMERIC, longitude NUMERIC, population_tier TEXT,
    is_unknown BOOLEAN DEFAULT FALSE, updated_at TIMESTAMP DEFAULT now());

-- ------------------------------------------------------------ FACT  (grain: one row per order line item)
CREATE TABLE IF NOT EXISTS dw.fact_sales (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    date_key INT NOT NULL REFERENCES dw.dim_date(date_key),               -- order date
    customer_key INT NOT NULL REFERENCES dw.dim_customer(customer_key),
    product_key INT NOT NULL REFERENCES dw.dim_product(product_key),
    seller_key INT NOT NULL REFERENCES dw.dim_seller(seller_key),
    location_key INT NOT NULL REFERENCES dw.dim_location(location_key),   -- city the order was SHIPPED TO
    quantity INT NOT NULL, unit_price NUMERIC(14,2) NOT NULL,
    gross_amount NUMERIC(14,2) NOT NULL, discount_amount NUMERIC(14,2) NOT NULL, net_amount NUMERIC(14,2) NOT NULL,
    discount_pct NUMERIC(5,2),
    cost_amount NUMERIC(14,2), cost_estimated BOOLEAN,
    shipping_fee NUMERIC(14,2) NOT NULL DEFAULT 0,      -- order fee allocated to lines; lines sum to the order fee exactly
    shipping_fee_estimated BOOLEAN, has_shipment BOOLEAN,
    shipping_days INT,
    is_cancelled BOOLEAN NOT NULL, is_in_transit BOOLEAN NOT NULL,
    is_delivered BOOLEAN NOT NULL,                      -- non-cancelled and not In Transit
    is_returned BOOLEAN NOT NULL,                       -- has a VALID (non-Rejected) return
    is_kept BOOLEAN NOT NULL,                           -- non-cancelled and no valid return
    returned_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    return_date_key INT REFERENCES dw.dim_date(date_key),   -- 2nd role of dim_date (NULL = no return)
    return_reason TEXT, return_status TEXT,
    order_status TEXT, payment_method TEXT, channel TEXT);

CREATE INDEX IF NOT EXISTS ix_fact_date     ON dw.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_customer ON dw.fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS ix_fact_product  ON dw.fact_sales(product_key);
CREATE INDEX IF NOT EXISTS ix_fact_seller   ON dw.fact_sales(seller_key);
CREATE INDEX IF NOT EXISTS ix_fact_location ON dw.fact_sales(location_key);
CREATE INDEX IF NOT EXISTS ix_fact_order    ON dw.fact_sales(order_id);
