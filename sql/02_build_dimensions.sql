-- =====================================================================
-- 02_build_dimensions.sql - fills the 5 dimensions from staging.
-- Idempotent UPSERTs keyed on the natural key => surrogate keys never change between runs.
-- Overwrite-in-place on conflict = SCD Type 1 (required for dim_customer).
-- =====================================================================

-- ---------------------------------------------------------- DimDate
-- Static public-holiday calendar from the problem statement (the only external data allowed).
TRUNCATE dw.ref_event_calendar;
INSERT INTO dw.ref_event_calendar(event_name, start_date, end_date) VALUES
 ('Ramadan',        '2024-03-11','2024-04-09'), ('Ramadan',        '2025-03-01','2025-03-30'),
 ('Eid-ul-Fitr',    '2024-04-10','2024-04-12'), ('Eid-ul-Fitr',    '2025-03-31','2025-04-02'),
 ('Eid-ul-Adha',    '2024-06-17','2024-06-19'), ('Eid-ul-Adha',    '2025-06-07','2025-06-09'),
 ('Independence Day','2024-08-14','2024-08-14'),('Independence Day','2025-08-14','2025-08-14'),
 ('11.11',          '2024-11-11','2024-11-11'), ('11.11',          '2025-11-11','2025-11-11'),
 ('Black Friday',   '2024-11-29','2024-11-29');

INSERT INTO dw.dim_date (date_key, full_date, day_of_month, day_name, day_of_week, week_of_year, week_start_date,
    month_number, month_name, year_month, quarter, year, is_weekend,
    is_ramadan, is_eid_ul_fitr, is_eid_ul_adha, is_eid, is_independence_day, is_11_11, is_black_friday,
    is_public_holiday, festival_name)
SELECT to_char(d,'YYYYMMDD')::int, d, EXTRACT(day FROM d)::int, trim(to_char(d,'Day')),
       EXTRACT(isodow FROM d)::int, EXTRACT(week FROM d)::int, date_trunc('week', d)::date,
       EXTRACT(month FROM d)::int, trim(to_char(d,'Month')), to_char(d,'YYYY-MM'),
       EXTRACT(quarter FROM d)::int, EXTRACT(year FROM d)::int, EXTRACT(isodow FROM d) IN (6,7),
       ev.ramadan, ev.fitr, ev.adha, (ev.fitr OR ev.adha), ev.indep, ev.e1111, ev.bf,
       (ev.fitr OR ev.adha OR ev.indep),
       CASE WHEN ev.fitr THEN 'Eid-ul-Fitr' WHEN ev.adha THEN 'Eid-ul-Adha' WHEN ev.bf THEN 'Black Friday'
            WHEN ev.e1111 THEN '11.11' WHEN ev.indep THEN 'Independence Day' WHEN ev.ramadan THEN 'Ramadan'
            ELSE 'None' END
FROM generate_series(DATE '2024-01-01', DATE '2025-12-31', INTERVAL '1 day') AS g(d)
CROSS JOIN LATERAL (
    SELECT COALESCE(bool_or(event_name='Ramadan'),false)           AS ramadan,
           COALESCE(bool_or(event_name='Eid-ul-Fitr'),false)       AS fitr,
           COALESCE(bool_or(event_name='Eid-ul-Adha'),false)       AS adha,
           COALESCE(bool_or(event_name='Independence Day'),false)  AS indep,
           COALESCE(bool_or(event_name='11.11'),false)             AS e1111,
           COALESCE(bool_or(event_name='Black Friday'),false)      AS bf
    FROM dw.ref_event_calendar c WHERE g.d BETWEEN c.start_date AND c.end_date) ev
ON CONFLICT (date_key) DO UPDATE SET
    is_ramadan=EXCLUDED.is_ramadan, is_eid_ul_fitr=EXCLUDED.is_eid_ul_fitr, is_eid_ul_adha=EXCLUDED.is_eid_ul_adha,
    is_eid=EXCLUDED.is_eid, is_independence_day=EXCLUDED.is_independence_day, is_11_11=EXCLUDED.is_11_11,
    is_black_friday=EXCLUDED.is_black_friday, is_public_holiday=EXCLUDED.is_public_holiday,
    festival_name=EXCLUDED.festival_name;

INSERT INTO dw.dim_date (date_key, full_date, day_name, month_name, year_month, is_weekend, is_ramadan, is_eid_ul_fitr,
    is_eid_ul_adha, is_eid, is_independence_day, is_11_11, is_black_friday, is_public_holiday, festival_name, is_unknown)
VALUES (-1, DATE '1900-01-01', 'Unknown', 'Unknown', 'Unknown', false,false,false,false,false,false,false,false,false,'Unknown', true)
ON CONFLICT (date_key) DO NOTHING;

-- ---------------------------------------------------------- DimLocation
INSERT INTO dw.dim_location (city_id, city, province, region, latitude, longitude, population_tier)
SELECT city_id, city, province, region, latitude, longitude, population_tier FROM staging.locations
ON CONFLICT (city_id) DO UPDATE SET city=EXCLUDED.city, province=EXCLUDED.province, region=EXCLUDED.region,
    latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, population_tier=EXCLUDED.population_tier, updated_at=now();
INSERT INTO dw.dim_location (location_key, city_id, city, province, region, population_tier, is_unknown)
OVERRIDING SYSTEM VALUE VALUES (-1,'UNKNOWN','Unknown','Unknown','Unknown','Unknown',true) ON CONFLICT (city_id) DO NOTHING;

-- ---------------------------------------------------------- DimSeller (city details denormalised in)
INSERT INTO dw.dim_seller (seller_id, seller_name, join_date, seller_tier, rating, city_id, city, province, region)
SELECT s.seller_id, s.seller_name, s.join_date, s.seller_tier, s.rating, s.city_id,
       COALESCE(l.city,'Unknown'), COALESCE(l.province,'Unknown'), COALESCE(l.region,'Unknown')
FROM staging.sellers s LEFT JOIN staging.locations l ON l.city_id = s.city_id
ON CONFLICT (seller_id) DO UPDATE SET seller_name=EXCLUDED.seller_name, join_date=EXCLUDED.join_date,
    seller_tier=EXCLUDED.seller_tier, rating=EXCLUDED.rating, city_id=EXCLUDED.city_id, city=EXCLUDED.city,
    province=EXCLUDED.province, region=EXCLUDED.region, updated_at=now();
INSERT INTO dw.dim_seller (seller_key, seller_id, seller_name, seller_tier, city_id, city, province, region, is_unknown)
OVERRIDING SYSTEM VALUE VALUES (-1,'UNKNOWN','Unknown','Unknown','UNKNOWN','Unknown','Unknown','Unknown',true)
ON CONFLICT (seller_id) DO NOTHING;

-- ---------------------------------------------------------- DimProduct
INSERT INTO dw.dim_product (product_id, product_name, category, sub_category, brand, list_price, cost_price, weight_kg)
SELECT product_id, product_name, category, sub_category, brand, list_price, cost_price, weight_kg FROM staging.products
ON CONFLICT (product_id) DO UPDATE SET product_name=EXCLUDED.product_name, category=EXCLUDED.category,
    sub_category=EXCLUDED.sub_category, brand=EXCLUDED.brand, list_price=EXCLUDED.list_price,
    cost_price=EXCLUDED.cost_price, weight_kg=EXCLUDED.weight_kg, updated_at=now();
INSERT INTO dw.dim_product (product_key, product_id, product_name, category, sub_category, brand, is_unknown)
OVERRIDING SYSTEM VALUE VALUES (-1,'UNKNOWN','Unknown','Unknown','Unknown','Unknown',true)
ON CONFLICT (product_id) DO NOTHING;

-- ---------------------------------------------------------- DimCustomer (SCD Type 1)
-- Segment / RFM columns are deliberately NOT overwritten here: they are refreshed after the fact load (05).
INSERT INTO dw.dim_customer (customer_id, full_name, email, phone, gender, registration_date, birth_year,
                             city_id, city, province, region, population_tier)
SELECT c.customer_id, c.full_name, c.email, c.phone, c.gender, c.registration_date, c.birth_year::int,
       c.city_id, COALESCE(l.city,'Unknown'), COALESCE(l.province,'Unknown'),
       COALESCE(l.region,'Unknown'), COALESCE(l.population_tier,'Unknown')
FROM staging.customers c LEFT JOIN staging.locations l ON l.city_id = c.city_id
ON CONFLICT (customer_id) DO UPDATE SET full_name=EXCLUDED.full_name, email=EXCLUDED.email, phone=EXCLUDED.phone,
    gender=EXCLUDED.gender, registration_date=EXCLUDED.registration_date, birth_year=EXCLUDED.birth_year,
    city_id=EXCLUDED.city_id, city=EXCLUDED.city, province=EXCLUDED.province, region=EXCLUDED.region,
    population_tier=EXCLUDED.population_tier, updated_at=now();
INSERT INTO dw.dim_customer (customer_key, customer_id, full_name, gender, city_id, city, province, region,
                             population_tier, segment, is_unknown)
OVERRIDING SYSTEM VALUE VALUES (-1,'UNKNOWN','Unknown','Unknown','UNKNOWN','Unknown','Unknown','Unknown','Unknown','Unknown',true)
ON CONFLICT (customer_id) DO NOTHING;
