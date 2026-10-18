"""
clean.py - NexusMart cleaning layer.

Every cleaner is a pure function:   clean_x(raw, ...deps, rj) -> (clean_df, [extras], log_dict)
so each one can later become (part of) an Airflow task.

Treatments, in order of preference:
    REPAIR  fix the value from other data, record it in a flag column + log
    FLAG    keep the row, mark the doubtful value
    REJECT  only if neither is possible -> data/rejects/rejects.csv with a reason code
Identity enforced for every file:  raw rows = clean rows + rejected rows + merged duplicates

Run:  python src/clean.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules
from utils import (Rejects, assert_identity, in_window, load_raw, log, map_labels,
                   new_log, norm_key, norm_phone, parse_date, parse_money, parse_qty, strip_all)


def _flag(d, mask, text):
    """Append a text flag to dq_flags for rows in mask."""
    if "dq_flags" not in d:
        d["dq_flags"] = ""
    d.loc[mask, "dq_flags"] = (d.loc[mask, "dq_flags"] + ";" + text).str.strip(";")


def _drop_exact_and_key_dups(name, raw, d, key, rj, lg):
    """Common first step: exact duplicate rows, then conflicting duplicate keys."""
    exact = d.drop(columns="_row").duplicated()
    lg["rejected"]["DUPLICATE_EXACT"] = rj.add(name, raw, exact, "DUPLICATE_EXACT",
                                               "identical row appears more than once", key)
    d = d[~exact]
    dupkey = d[key].duplicated()
    n = rj.add(name, raw, dupkey, "DUPLICATE_KEY_CONFLICT",
               f"same {key} with different values; first occurrence kept", key)
    if n:
        lg["rejected"]["DUPLICATE_KEY_CONFLICT"] = n
    return d[~dupkey].copy()


# ============================================================ LOCATIONS
def clean_locations(raw, rj):
    lg = new_log("locations", len(raw))
    d = _drop_exact_and_key_dups("locations", raw, strip_all(raw), "city_id", rj, lg)

    prov = map_labels(d["province"], rules.PROVINCE_MAP, "locations.province", lg)
    d["province_source"] = np.where(prov.notna(), "raw", "")
    d["province"] = prov
    d["population_tier"] = map_labels(d["population_tier"], rules.POP_TIER_MAP,
                                      "locations.population_tier", lg, default="Unknown")
    d["region"] = d["region"].replace("", "Unknown")

    lat, lon = pd.to_numeric(d["latitude"], errors="coerce"), pd.to_numeric(d["longitude"], errors="coerce")
    swap = (lat > 40) & (lon < 50)                               # lat/long entered the wrong way round
    lat, lon = lat.where(~swap, lon), lon.where(~swap, lat)
    bad = ~lat.between(23, 38) | ~lon.between(60, 78)
    lg["repairs"]["lat_lon_swapped"] = int(swap.sum())
    lg["flags"]["lat_lon_missing_or_out_of_range"] = int((bad & ~swap).sum())
    d["latitude"], d["longitude"] = lat.where(~bad), lon.where(~bad)

    # missing province: known-city fix first, then nearest neighbour with a known province
    fix = norm_key(d["city"]).map(rules.CITY_PROVINCE_FIX)
    m = d["province"].isna() & fix.notna()
    d.loc[m, "province"], d.loc[m, "province_source"] = fix[m], "inferred_city_name"
    known = d[d["province"].notna() & d["latitude"].notna()]
    todo = d[d["province"].isna() & d["latitude"].notna()]
    for i, r in todo.iterrows():
        k = known[known["region"] == r["region"]]
        if k.empty:
            continue
        j = ((k["latitude"] - r["latitude"]) ** 2 + (k["longitude"] - r["longitude"]) ** 2).idxmin()
        d.loc[i, "province"], d.loc[i, "province_source"] = k.loc[j, "province"], "inferred_nearest_city"
    lg["repairs"]["province_inferred"] = int(d["province_source"].str.startswith("inferred").sum())
    still = d["province"].isna()
    lg["flags"]["province_still_unknown"] = int(still.sum())
    d["province"] = d["province"].fillna("Unknown")

    out = d[["city_id", "city", "province", "region", "latitude", "longitude",
             "population_tier", "province_source"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


# ============================================================ SELLERS
def clean_sellers(raw, locs, rj):
    lg = new_log("sellers", len(raw))
    d = _drop_exact_and_key_dups("sellers", raw, strip_all(raw), "seller_id", rj, lg)
    d["seller_tier"] = map_labels(d["seller_tier"], rules.SELLER_TIER_MAP, "sellers.seller_tier", lg,
                                  default="Unknown")
    rating = pd.to_numeric(d["rating"], errors="coerce")
    bad = rating.notna() & ~rating.between(rules.RATING_MIN, rules.RATING_MAX)
    lg["flags"]["rating_out_of_range_set_null"] = int(bad.sum())
    lg["flags"]["rating_missing"] = int(rating.isna().sum())
    d["rating"] = rating.where(~bad)
    jd = parse_date(d["join_date"])
    fut = jd > pd.Timestamp(rules.DATE_MAX)
    lg["flags"]["join_date_missing_or_invalid"] = int((jd.isna() | fut).sum())
    d["join_date"] = jd.where(~fut)
    ok = d["city_id"].isin(set(locs["city_id"]))
    lg["flags"]["city_unknown"] = int((~ok).sum())
    d["city_id"] = d["city_id"].where(ok, rules.UNKNOWN)
    out = d[["seller_id", "seller_name", "join_date", "seller_tier", "city_id", "rating"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


# ============================================================ CUSTOMERS
def clean_customers(raw, locs, rj):
    lg = new_log("customers", len(raw))
    d = _drop_exact_and_key_dups("customers", raw, strip_all(raw), "customer_id", rj, lg)

    d["full_name"] = d["full_name"].str.title()
    d["email"] = d["email"].str.lower().replace("", np.nan)
    d["phone"] = norm_phone(d["phone"]).replace("", np.nan)
    d["gender"] = map_labels(d["gender"], rules.GENDER_MAP, "customers.gender", lg)
    d["registration_date"] = parse_date(d["registration_date"])
    fut = d["registration_date"] > pd.Timestamp(rules.DATE_MAX)
    lg["flags"]["registration_date_missing_or_invalid"] = int((d["registration_date"].isna() | fut).sum())
    d.loc[fut, "registration_date"] = pd.NaT
    by = pd.to_numeric(d["birth_year"], errors="coerce")
    badby = by.notna() & ~by.between(rules.BIRTH_YEAR_MIN, rules.BIRTH_YEAR_MAX)
    lg["flags"]["birth_year_impossible_set_null"] = int(badby.sum())
    d["birth_year"] = by.where(~badby)
    ok_city = d["city_id"].isin(set(locs["city_id"]))
    lg["flags"]["city_blank_or_invalid"] = int((~ok_city).sum())
    d["city_id"] = d["city_id"].where(ok_city, np.nan)

    # ---- deduplication: same person under different IDs (NEVER on name alone) ----
    parent = {c: c for c in d["customer_id"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    info = pd.DataFrame({
        "phone": d["phone"].fillna(""), "birth": d["birth_year"].map(lambda v: "" if pd.isna(v) else str(int(v))),
        "city": d["city_id"].fillna(""), "name": norm_key(d["full_name"])}).set_axis(d["customer_id"])
    info = info.to_dict("index")

    def compare(a, b):
        """(# comparable signals that agree, # that disagree) over phone / birth_year / city."""
        agree = conflict = 0
        for k in ("phone", "birth", "city"):
            x, y = info[a][k], info[b][k]
            if x != "" and y != "":
                agree += x == y
                conflict += x != y
        return agree, conflict

    rule_hits = {"A_email+signals_no_majority_conflict": 0, "B_phone+birth+city+name": 0}

    def union(a, b, rule):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
            rule_hits[rule] += 1

    def pairs(ids):
        return [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]

    skipped = 0
    for _, ids in d[d["email"].notna()].groupby("email")["customer_id"].apply(list).items():
        if len(ids) < 2:
            continue
        if len(ids) > 6:
            skipped += 1
            continue
        for a, b in pairs(ids):
            ag, cf = compare(a, b)
            if ag >= 1 and ag > cf:        # same email, >=1 agreeing signal, more agree than conflict
                union(a, b, "A_email+signals_no_majority_conflict")
    for _, ids in d[d["phone"].notna()].groupby("phone")["customer_id"].apply(list).items():
        if len(ids) < 2:
            continue
        if len(ids) > 6:
            skipped += 1
            continue
        for a, b in pairs(ids):
            ag, cf = compare(a, b)
            if ag >= 3 and info[a]["name"] == info[b]["name"]:   # name only as corroboration
                union(a, b, "B_phone+birth+city+name")

    d["_root"] = d["customer_id"].map(find)
    ordered = d.sort_values(["registration_date", "customer_id"], na_position="last")
    master = ordered.groupby("_root")["customer_id"].first()
    d["customer_id_master"] = d["_root"].map(master)

    cmap = d.loc[:, ["customer_id", "customer_id_master"]].rename(columns={"customer_id": "customer_id_original"})
    rule_of = {}
    cmap["match_rule"] = np.where(cmap["customer_id_original"] != cmap["customer_id_master"], "merged", "master")

    # master record = earliest ID, with blanks filled from the duplicates (first() skips nulls)
    ordered = d.sort_values(["registration_date", "customer_id"], na_position="last")
    out = (ordered.drop(columns=["_root", "customer_id", "_row"])
           .groupby("customer_id_master", sort=False).first().reset_index()
           .rename(columns={"customer_id_master": "customer_id"}))
    out["gender"] = out["gender"].fillna("Unknown")
    out["city_id"] = out["city_id"].fillna(rules.UNKNOWN)
    out = out[["customer_id", "full_name", "email", "phone", "gender", "registration_date",
               "city_id", "birth_year"]].sort_values("customer_id").reset_index(drop=True)
    merged = len(d) - len(out)
    lg["dedup"] = {"rule_hits": rule_hits, "large_groups_skipped": skipped, "customers_merged": int(merged)}
    assert_identity(lg, len(out), merged=merged)
    return out, cmap, lg


# ============================================================ PRODUCTS
def clean_products(raw, sellers, rj):
    lg = new_log("products", len(raw))
    d = _drop_exact_and_key_dups("products", raw, strip_all(raw), "product_id", rj, lg)
    d["category"] = map_labels(d["category"], rules.CATEGORY_MAP, "products.category", lg, default="Unknown")
    d["sub_category"] = d["sub_category"].replace("", "Unknown")
    d["brand"] = d["brand"].replace("", "Unknown")
    d["product_name"] = d["product_name"].str.strip()

    lp, cp = parse_money(d["list_price"]), parse_money(d["cost_price"])
    bad_lp = lp.isna() | (lp <= 0) | (lp >= rules.PRICE_MAX)
    bad_cp = cp.isna() | (cp <= 0) | (cp >= rules.PRICE_MAX)
    lp, cp = lp.where(~bad_lp), cp.where(~bad_cp)
    ratio = (cp / lp).where((cp / lp).between(0.1, 3))
    cat_ratio = ratio.groupby(d["category"]).transform("median").fillna(ratio.median())
    d["flags"] = ""
    fill_cp = cp.isna() & lp.notna()
    fill_lp = lp.isna() & cp.notna()
    d["cost_price"] = cp.where(~fill_cp, (lp * cat_ratio).round(0))
    d["list_price"] = lp.where(~fill_lp, (cp / cat_ratio).round(0))
    lg["repairs"]["cost_price_imputed_from_category_ratio"] = int(fill_cp.sum())
    lg["repairs"]["list_price_imputed_from_cost"] = int(fill_lp.sum())
    lg["flags"]["both_prices_missing"] = int((d["list_price"].isna() & d["cost_price"].isna()).sum())
    d["cost_imputed"], d["list_price_imputed"] = fill_cp, fill_lp
    d["cost_gt_list"] = d["cost_price"] > d["list_price"]
    lg["flags"]["cost_greater_than_list"] = int(d["cost_gt_list"].sum())

    w = pd.to_numeric(d["weight_kg"], errors="coerce")
    badw = w.notna() & ((w <= 0) | (w > rules.WEIGHT_MAX))
    lg["flags"]["weight_impossible_set_null"] = int(badw.sum())
    lg["flags"]["weight_missing"] = int(w.isna().sum())
    d["weight_kg"] = w.where(~badw)

    okseller = d["seller_id"].isin(set(sellers["seller_id"]))
    lg["flags"]["seller_unknown"] = int((~okseller).sum())
    d["seller_id"] = d["seller_id"].where(okseller, rules.UNKNOWN)

    # duplicate products: same normalised name + brand + seller under different IDs
    d["_k"] = norm_key(d["product_name"]) + "|" + norm_key(d["brand"]) + "|" + d["seller_id"]
    d = d.sort_values("product_id")
    d["product_id_master"] = d.groupby("_k")["product_id"].transform("first")
    pmap = d[["product_id", "product_id_master"]].rename(columns={"product_id": "product_id_original"})
    out = d[d["product_id"] == d["product_id_master"]].drop(columns=["_k", "_row", "product_id_master", "flags"])
    out = out[["product_id", "product_name", "category", "sub_category", "brand", "list_price",
               "cost_price", "weight_kg", "seller_id", "cost_imputed", "list_price_imputed",
               "cost_gt_list"]].reset_index(drop=True)
    merged = len(d) - len(out)
    lg["dedup"] = {"products_merged": int(merged)}
    assert_identity(lg, len(out), merged=merged)
    return out, pmap, lg


# ============================================================ SHIPPING
def clean_shipping(raw, raw_order_ids, rj):
    lg = new_log("shipping", len(raw))
    d = _drop_exact_and_key_dups("shipping", raw, strip_all(raw), "order_id", rj, lg)
    orphan = ~d["order_id"].isin(raw_order_ids)
    lg["rejected"]["ORPHAN_FK"] = rj.add("shipping", raw, orphan, "ORPHAN_FK", "order_id not in orders", "shipment_id")
    d = d[~orphan].copy()

    d["courier"] = map_labels(d["courier"], rules.COURIER_MAP, "shipping.courier", lg, default="Unknown")
    d["delivery_status"] = map_labels(d["delivery_status"], rules.DELIVERY_STATUS_MAP,
                                      "shipping.delivery_status", lg, default="Unknown")
    d["dq_flags"] = ""
    s, v = parse_date(d["shipped_date"]), parse_date(d["delivered_date"])
    lo, hi_s, hi_d = pd.Timestamp(rules.DATE_MIN), pd.Timestamp(rules.DATE_MAX) + pd.Timedelta(days=10), \
        pd.Timestamp(rules.DATE_MAX) + pd.Timedelta(days=rules.SHIP_DAYS_MAX)
    bs = s.notna() & ~s.between(lo, hi_s)
    bv = v.notna() & ~v.between(lo, hi_d)
    s, v = s.where(~bs), v.where(~bv)
    days = (v - s).dt.days
    inconsistent = (days < 0) | (days > rules.SHIP_DAYS_MAX)
    lg["flags"]["delivered_before_shipped"] = int((days < 0).sum())
    lg["flags"][f"delivery_over_{rules.SHIP_DAYS_MAX}_days"] = int((days > rules.SHIP_DAYS_MAX).sum())
    _flag(d, inconsistent, "DELIVERY_DATES_INCONSISTENT")
    v, days = v.where(~inconsistent), days.where(~inconsistent)          # nulled, never zero-filled
    miss = d["delivery_status"].eq("Delivered") & v.isna()
    lg["flags"]["delivered_status_but_no_valid_delivery_date"] = int(miss.sum())
    d["shipped_date"], d["delivered_date"], d["shipping_days"] = s, v, days

    fee = parse_money(d["shipping_fee"])
    neg = fee < 0
    fee = fee.where(~neg, fee.abs())
    big = fee >= rules.SHIP_FEE_MAX
    lg["repairs"]["negative_fee_made_positive"] = int(neg.sum())
    lg["flags"]["fee_sentinel_set_null"] = int(big.sum())
    fee = fee.where(~big)
    d["fee_imputed"] = fee.isna()               # estimated later, once cleaned order lines exist
    d["shipping_fee"] = fee
    lg["flags"]["fee_missing_to_be_estimated"] = int(fee.isna().sum())

    out = d[["shipment_id", "order_id", "courier", "shipped_date", "delivered_date", "shipping_fee",
             "delivery_status", "shipping_days", "fee_imputed", "dq_flags"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


def impute_shipping_fees(ship, items, lg):
    """Estimate missing courier fees from order size (courier carries no signal: all medians ~420 PKR).
    Holdout test: error 212 PKR/row with units-median vs 248 with courier-median. Rows stay flagged."""
    units = items.groupby("order_id")["quantity"].sum().clip(upper=8)
    ship = ship.copy()
    b = ship["order_id"].map(units)
    real = ship.loc[~ship["fee_imputed"]]
    med_by_units = real.groupby(b[real.index])["shipping_fee"].median()
    est = b.map(med_by_units).fillna(real["shipping_fee"].median()).round(0)
    ship["shipping_fee"] = ship["shipping_fee"].where(~ship["fee_imputed"], est)
    lg["repairs"]["fee_imputed_by_order_units_median"] = int(ship["fee_imputed"].sum())
    lg["repairs"]["fee_total_real_values"] = float(real["shipping_fee"].sum())
    lg["repairs"]["fee_total_added_by_estimates"] = float(ship.loc[ship["fee_imputed"], "shipping_fee"].sum())
    return ship


# ============================================================ PAYMENTS
def clean_payments(raw, raw_order_ids, rj):
    lg = new_log("payments", len(raw))
    d = _drop_exact_and_key_dups("payments", raw, strip_all(raw), "payment_id", rj, lg)
    orphan = ~d["order_id"].isin(raw_order_ids)
    lg["rejected"]["ORPHAN_FK"] = rj.add("payments", raw, orphan, "ORPHAN_FK", "order_id not in orders", "payment_id")
    d = d[~orphan].copy()
    d["payment_method"] = map_labels(d["payment_method"], rules.PAYMENT_METHOD_MAP, "payments.payment_method",
                                     lg, default="Unknown")
    d["payment_status"] = map_labels(d["payment_status"], rules.PAYMENT_STATUS_MAP, "payments.payment_status",
                                     lg, default="Unknown")
    d["payment_date"] = parse_date(d["payment_date"])
    amt = parse_money(d["amount"])
    neg = amt < 0
    amt = amt.where(~neg, amt.abs())
    big = amt >= rules.SENTINEL_MIN
    lg["repairs"]["negative_amount_made_positive"] = int(neg.sum())
    lg["flags"]["amount_sentinel_set_null"] = int(big.sum())
    d["amount"] = amt.where(~big)

    # one PRIMARY payment per order (largest amount; tie -> lowest payment_id). Payments can be SPLITS.
    ranked = d.sort_values(["order_id", "amount", "payment_id"], ascending=[True, False, True], na_position="last")
    g = ranked.groupby("order_id")
    prim = g.first()[["payment_method", "payment_status"]].rename(
        columns={"payment_method": "primary_payment_method", "payment_status": "primary_payment_status"})
    prim["n_payments"] = g.size()
    prim["payments_total"] = g["amount"].sum(min_count=1)
    prim["first_payment_date"] = g["payment_date"].min()
    prim = prim.reset_index()
    lg["split_payment_orders"] = int((prim["n_payments"] > 1).sum())
    out = d[["payment_id", "order_id", "payment_method", "payment_status", "amount", "payment_date"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, prim, lg


# ============================================================ ORDERS + ORDER ITEMS
def clean_orders(raw, cust_map, locs, ship, prim, rj):
    lg = new_log("orders", len(raw))
    d = _drop_exact_and_key_dups("orders", raw, strip_all(raw), "order_id", rj, lg)

    d["order_status"] = map_labels(d["order_status"], rules.ORDER_STATUS_MAP, "orders.order_status", lg,
                                   default="Unknown")
    d["channel"] = map_labels(d["channel"], rules.CHANNEL_MAP, "orders.channel", lg, default="Unknown")
    d["discount_code"] = d["discount_code"].str.upper()
    d["discount_pct"] = pd.to_numeric(d["discount_code"].str.extract(r"(\d+)")[0], errors="coerce").fillna(0.0)

    # ---- dates: parse -> validate window -> repair from other tables -> else reject ----
    dt = parse_date(d["order_date"])
    ok = dt.notna() & in_window(dt)
    d["order_date_source"] = np.where(ok, "raw", "")
    lg["flags"]["order_date_unparseable"] = int(dt.isna().sum())
    lg["flags"]["order_date_out_of_window"] = int((dt.notna() & ~in_window(dt)).sum())
    sh = ship.set_index("order_id")["shipped_date"]
    pd_ = prim.set_index("order_id")["first_payment_date"]
    from_ship = d["order_id"].map(sh) - pd.Timedelta(days=rules.SHIP_LAG_DAYS)
    from_pay = d["order_id"].map(pd_) - pd.Timedelta(days=rules.PAY_LAG_DAYS)
    use_ship = ~ok & from_ship.notna() & in_window(from_ship)
    use_pay = ~ok & ~use_ship & from_pay.notna() & in_window(from_pay)
    dt = dt.where(ok | ~use_ship, from_ship).where(~use_pay, from_pay)
    d.loc[use_ship, "order_date_source"] = "repaired_from_shipping"
    d.loc[use_pay, "order_date_source"] = "repaired_from_payment"
    lg["repairs"]["order_date_repaired_from_shipping"] = int(use_ship.sum())
    lg["repairs"]["order_date_repaired_from_payment"] = int(use_pay.sum())
    dead = ~(ok | use_ship | use_pay)
    lg["rejected"]["INVALID_DATE"] = rj.add("orders", raw, dead, "INVALID_DATE",
                                            "order_date invalid/out of window and no usable shipping/payment date",
                                            "order_id")
    d["order_date"] = dt
    d = d[~dead].copy()

    # ---- foreign keys ----
    cm = cust_map.set_index("customer_id_original")["customer_id_master"]
    d["customer_id"] = d["customer_id"].map(cm)
    orphan_c = d["customer_id"].isna()
    lg["flags"]["customer_orphan_to_UNKNOWN"] = int(orphan_c.sum())
    d["customer_id"] = d["customer_id"].fillna(rules.UNKNOWN)
    okc = d["ship_city_id"].isin(set(locs["city_id"]))
    lg["flags"]["ship_city_blank_or_invalid_to_UNKNOWN"] = int((~okc).sum())
    d["ship_city_id"] = d["ship_city_id"].where(okc, rules.UNKNOWN)

    tot = parse_money(d["order_total"])
    d["order_total_reported"] = tot.where((tot > 0) & (tot < rules.SENTINEL_MIN))
    lg["flags"]["order_total_invalid_sentinel_or_nonpositive"] = int(d["order_total_reported"].isna().sum())
    out = d[["order_id", "customer_id", "order_date", "order_status", "ship_city_id", "order_total_reported",
             "discount_code", "discount_pct", "channel", "order_date_source"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


def clean_items(raw, raw_order_ids, orders, products, pmap, sellers, rj):
    lg = new_log("order_items", len(raw))
    d = _drop_exact_and_key_dups("order_items", raw, strip_all(raw), "order_item_id", rj, lg)

    orphan = ~d["order_id"].isin(raw_order_ids)
    lg["rejected"]["ORPHAN_FK"] = rj.add("order_items", raw, orphan, "ORPHAN_FK", "order_id not in orders", "order_item_id")
    d = d[~orphan]
    parent_dead = ~d["order_id"].isin(set(orders["order_id"]))
    lg["rejected"]["PARENT_ORDER_REJECTED"] = rj.add("order_items", raw, parent_dead, "PARENT_ORDER_REJECTED",
                                                     "its order was rejected", "order_item_id")
    d = d[~parent_dead].copy()
    d["dq_flags"] = ""
    d["discount_amount_raw"] = parse_money(d["discount_amount"])      # kept for audit only

    # ---- products / sellers ----
    pm = pmap.set_index("product_id_original")["product_id_master"]
    d["product_id"] = d["product_id"].map(pm)
    unk = d["product_id"].isna()
    lg["flags"]["product_orphan_to_UNKNOWN"] = int(unk.sum())
    _flag(d, unk, "UNKNOWN_PRODUCT")
    d["product_id"] = d["product_id"].fillna(rules.UNKNOWN)
    oks = d["seller_id"].isin(set(sellers["seller_id"]))
    lg["flags"]["seller_orphan_to_UNKNOWN"] = int((~oks).sum())
    d["seller_id"] = d["seller_id"].where(oks, rules.UNKNOWN)
    d = d.merge(products[["product_id", "list_price"]], on="product_id", how="left")

    # ---- parse + trivial sign repairs ----
    q, up = parse_qty(d["quantity"]), parse_money(d["unit_price"])
    d["quantity_raw"], d["unit_price_raw"] = q, up
    neg_q = q.notna() & (q < 0) & (q.abs() < rules.QTY_MAX)
    q = q.where(~neg_q, q.abs())
    _flag(d, neg_q, "QTY_SIGN_FIXED")
    lg["repairs"]["negative_quantity_made_positive"] = int(neg_q.sum())
    neg_p = up.notna() & (up < 0)
    up_abs = up.abs()
    lr = rules.PRICE_LIST_RATIO
    sign_ok = neg_p & ((up_abs / d["list_price"]).between(*lr))
    up = up.where(~sign_ok, up_abs)
    _flag(d, sign_ok, "PRICE_SIGN_FIXED")
    lg["repairs"]["negative_price_made_positive"] = int(sign_ok.sum())

    bad_q = q.isna() | (q < 1) | (q >= rules.QTY_MAX)
    ratio = up / d["list_price"]
    bad_p = up.isna() | (up < rules.PRICE_MIN) | (up >= rules.PRICE_MAX) | (ratio.notna() & ~ratio.between(*lr))

    # ---- discount: the order-level code % is the source of truth (reconciles to order_total) ----
    o = orders.set_index("order_id")
    d["discount_pct"] = d["order_id"].map(o["discount_pct"])
    tot = d["order_id"].map(o["order_total_reported"])

    # ---- solve bad lines from order_total when exactly ONE line in the order is bad ----
    d["_good_gross"] = np.where(~bad_q & ~bad_p, q * up, 0.0)
    n_bad = (bad_q | bad_p).groupby(d["order_id"]).transform("sum")
    others = d.groupby("order_id")["_good_gross"].transform("sum")
    resid = tot / (1 - d["discount_pct"] / 100) - others
    can = (n_bad == 1) & tot.notna() & (resid > 0)

    q_new = (resid / up).round()
    ok_q = can & bad_q & ~bad_p & q_new.between(1, rules.QTY_MAX - 1) & \
        ((q_new * up - resid).abs() <= rules.RECON_TOLERANCE * resid)
    p_new = (resid / q).round()
    pr = p_new / d["list_price"]
    ok_p = can & bad_p & ~bad_q & p_new.between(rules.PRICE_MIN, rules.PRICE_MAX) & \
        (pr.isna() | pr.between(*lr)) & ((p_new * q - resid).abs() <= rules.RECON_TOLERANCE * resid)
    q = q.where(~ok_q, q_new)
    up = up.where(~ok_p, p_new)
    _flag(d, ok_q, "QTY_SOLVED_FROM_ORDER_TOTAL")
    _flag(d, ok_p, "PRICE_SOLVED_FROM_ORDER_TOTAL")
    lg["repairs"]["quantity_solved_from_order_total"] = int(ok_q.sum())
    lg["repairs"]["price_solved_from_order_total"] = int(ok_p.sum())
    bad_q, bad_p = bad_q & ~ok_q, bad_p & ~ok_p

    # ---- fallbacks ----
    fb_p = bad_p & d["list_price"].notna()
    up = up.where(~fb_p, (d["list_price"] * rules.FALLBACK_PRICE_FACTOR).round(0))
    _flag(d, fb_p, "PRICE_FROM_LIST_PRICE")
    lg["repairs"]["price_from_list_price_fallback"] = int(fb_p.sum())
    fb_q = bad_q
    q = q.where(~fb_q, 1)
    _flag(d, fb_q, "QTY_IMPUTED_1")
    lg["repairs"]["quantity_imputed_as_1"] = int(fb_q.sum())
    dead = bad_p & ~fb_p
    lg["rejected"]["UNREPAIRABLE_PRICE"] = rj.add_rows(
        "order_items", raw, d.loc[dead, "_row"].values, "UNREPAIRABLE_PRICE",
        "bad price and no list price to fall back on", "order_item_id")
    keep = ~dead

    d["quantity"], d["unit_price"] = q, up
    d["gross_amount"] = (d["quantity"] * d["unit_price"]).round(2)
    d["discount_amount"] = (d["gross_amount"] * d["discount_pct"] / 100).round(2)
    d["net_amount"] = (d["gross_amount"] - d["discount_amount"]).round(2)
    d = d[keep]
    out = d[["order_item_id", "order_id", "product_id", "seller_id", "quantity", "unit_price", "gross_amount",
             "discount_amount", "net_amount", "discount_amount_raw", "dq_flags"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


def finalise_orders(orders, items):
    """Attach calculated totals + reconciliation status (reported order_total vs sum of lines)."""
    calc = items.groupby("order_id")["net_amount"].sum().round(2).rename("order_total_calc")
    o = orders.merge(calc, on="order_id", how="left")
    rep = o["order_total_reported"]
    diff = (o["order_total_calc"] - rep).abs()
    o["recon_status"] = np.select(
        [rep.isna(), diff <= np.maximum(1, 0.01 * o["order_total_calc"])],
        ["REPORTED_TOTAL_INVALID", "MATCH"], default="MISMATCH")
    return o


# ============================================================ RETURNS
def clean_returns(raw, raw_item_ids, items, orders, rj):
    lg = new_log("returns", len(raw))
    d = _drop_exact_and_key_dups("returns", raw, strip_all(raw), "return_id", rj, lg)
    orphan = ~d["order_item_id"].isin(raw_item_ids)
    lg["rejected"]["ORPHAN_FK"] = rj.add("returns", raw, orphan, "ORPHAN_FK", "order_item_id not in order_items", "return_id")
    d = d[~orphan]
    dead = ~d["order_item_id"].isin(set(items["order_item_id"]))
    lg["rejected"]["PARENT_ITEM_REJECTED"] = rj.add("returns", raw, dead, "PARENT_ITEM_REJECTED",
                                                    "its order line was rejected", "return_id")
    d = d[~dead].copy()
    d["dq_flags"] = ""

    key = norm_key(d["return_status"])
    unmapped = key[~key.isin(rules.RETURN_STATUS_MAP)]
    if len(unmapped):
        raise ValueError(f"UNMAPPED return_status (add to rules.py): {d.loc[unmapped.index, 'return_status'].unique()[:10]}")
    d["return_status"] = key.map(lambda k: rules.RETURN_STATUS_MAP[k][0])
    d["is_valid_return"] = key.map(lambda k: rules.RETURN_STATUS_MAP[k][1]).astype(bool)
    lg["flags"]["rejected_status_kept_but_invalid"] = int((~d["is_valid_return"]).sum())
    d["return_reason"] = map_labels(d["return_reason"], rules.RETURN_REASON_MAP, "returns.return_reason", lg,
                                    default="Unknown").fillna("Unknown")
    d.loc[d["return_reason"].eq("Unknown") | d["return_reason"].isna(), "return_reason"] = "Unknown"

    rd = parse_date(d["return_date"])
    lg["flags"]["return_date_unparseable"] = int(rd.isna().sum())
    d["return_date"] = rd
    it = items.set_index("order_item_id")
    od = orders.set_index("order_id")
    d["_oid"] = d["order_item_id"].map(it["order_id"])
    d["_odate"] = d["_oid"].map(od["order_date"])
    d["_ostatus"] = d["_oid"].map(od["order_status"])
    before = d["return_date"] < d["_odate"]
    shifted = d["return_date"] + pd.Timedelta(days=rules.RETURN_DATE_SHIFT_DAYS)
    fixable = before & ((shifted - d["_odate"]).dt.days).between(0, rules.RETURN_GAP_MAX_DAYS)
    d.loc[fixable, "return_date"] = shifted[fixable]
    _flag(d, fixable, "RETURN_DATE_REPAIRED_PLUS_150D")
    lg["repairs"]["return_date_before_order_shifted_plus_150d"] = int(fixable.sum())
    still_bad = before & ~fixable
    _flag(d, still_bad, "RETURN_BEFORE_ORDER")
    lg["flags"]["return_before_order_date_not_repairable"] = int(still_bad.sum())
    cx = d["_ostatus"].isin(["Cancelled", "In Transit"]) & d["is_valid_return"]
    _flag(d, cx, "RETURN_ON_CANCELLED_OR_IN_TRANSIT_ORDER")
    lg["flags"]["valid_return_on_cancelled_or_in_transit_order"] = int(cx.sum())

    ref = parse_money(d["refund_amount"])
    d["refund_amount"] = ref
    net = d["order_item_id"].map(it["net_amount"])
    gross = d["order_item_id"].map(it["gross_amount"])
    # a refund larger than the line's own GROSS value is impossible (raw data has a spike at exactly 1.4x net)
    inflated = d["is_valid_return"] & (ref > gross * 1.0001)
    ref = ref.where(~inflated, net)
    d["refund_amount"] = ref
    _flag(d, inflated, "REFUND_CAPPED_TO_LINE_NET")
    lg["repairs"]["refund_above_gross_capped_to_line_net"] = int(inflated.sum())
    over = d["is_valid_return"] & (ref > net * 1.0001)
    _flag(d, over, "REFUND_GT_LINE_NET")
    lg["flags"]["refund_between_net_and_gross_kept(partial refund on pre-discount price)"] = int(over.sum())
    miss = d["is_valid_return"] & (ref.isna() | (ref <= 0))
    _flag(d, miss, "VALID_RETURN_REFUND_MISSING")
    lg["flags"]["valid_return_with_missing_or_zero_refund"] = int(miss.sum())

    out = d[["return_id", "order_item_id", "return_date", "return_reason", "return_status",
             "is_valid_return", "refund_amount", "dq_flags"]].reset_index(drop=True)
    assert_identity(lg, len(out))
    return out, lg


# ============================================================ ORCHESTRATION
def run_all():
    rules.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    rules.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rj, logs = Rejects(), {}
    raw = {n: load_raw(n) for n in rules.RAW_FILES}
    raw_order_ids = set(strip_all(raw["orders"])["order_id"])
    raw_item_ids = set(strip_all(raw["order_items"])["order_item_id"])

    locs, logs["locations"] = clean_locations(raw["locations"], rj)
    sellers, logs["sellers"] = clean_sellers(raw["sellers"], locs, rj)
    customers, cmap, logs["customers"] = clean_customers(raw["customers"], locs, rj)
    products, pmap, logs["products"] = clean_products(raw["products"], sellers, rj)
    ship, logs["shipping"] = clean_shipping(raw["shipping"], raw_order_ids, rj)
    pay, prim, logs["payments"] = clean_payments(raw["payments"], raw_order_ids, rj)
    orders, logs["orders"] = clean_orders(raw["orders"], cmap, locs, ship, prim, rj)
    items, logs["order_items"] = clean_items(raw["order_items"], raw_order_ids, orders, products, pmap, sellers, rj)
    ship = impute_shipping_fees(ship, items, logs["shipping"])
    orders = finalise_orders(orders, items)
    logs["orders"]["reconciliation"] = orders["recon_status"].value_counts().to_dict()
    returns, logs["returns"] = clean_returns(raw["returns"], raw_item_ids, items, orders, rj)

    outputs = {"locations": locs, "sellers": sellers, "customers": customers, "customer_id_map": cmap,
               "products": products, "product_id_map": pmap, "shipping": ship, "payments": pay,
               "order_payment": prim, "orders": orders, "order_items": items, "returns": returns}
    for name, df in outputs.items():
        df.to_csv(rules.CLEAN_DIR / f"{name}.csv", index=False)
    rejects = rj.write()
    logs["_rejects_by_reason"] = rejects.groupby(["source_file", "reason_code"]).size().rename("rows").reset_index() \
        .to_dict("records")
    (rules.REPORT_DIR / "cleaning_log.json").write_text(json.dumps(logs, indent=2, default=str))
    write_summary(logs)
    return outputs, logs


def write_summary(logs):
    rows = ["| file | raw | clean | rejected | merged | identity |", "|---|--:|--:|--:|--:|:-:|"]
    for n in rules.RAW_FILES:
        lg = logs[n]
        rows.append(f"| {n} | {lg['raw_rows']:,} | {lg['clean_rows']:,} | {sum(lg['rejected'].values()):,} | "
                    f"{lg['merged_into_master']:,} | {'OK' if lg['identity_ok'] else 'FAIL'} |")
    detail = []
    for n in rules.RAW_FILES:
        lg = logs[n]
        detail.append(f"\n### {n}\n- rejected: {lg['rejected']}\n- repairs: {lg['repairs']}\n- flags: {lg['flags']}")
        if "dedup" in lg:
            detail.append(f"- dedup: {lg['dedup']}")
    (rules.REPORT_DIR / "cleaning_summary.md").write_text(
        "# Cleaning summary (before / after)\n\n" + "\n".join(rows) + "\n" + "\n".join(detail))


if __name__ == "__main__":
    run_all()
