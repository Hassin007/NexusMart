# Cleaning summary (before / after)

| file | raw | clean | rejected | merged | identity |
|---|--:|--:|--:|--:|:-:|
| customers | 45,000 | 42,674 | 0 | 2,326 | OK |
| products | 3,200 | 3,198 | 0 | 2 | OK |
| sellers | 420 | 420 | 0 | 0 | OK |
| locations | 650 | 650 | 0 | 0 | OK |
| orders | 163,200 | 159,988 | 3,212 | 0 | OK |
| order_items | 315,143 | 315,113 | 30 | 0 | OK |
| payments | 168,111 | 164,815 | 3,296 | 0 | OK |
| shipping | 151,228 | 151,228 | 0 | 0 | OK |
| returns | 16,048 | 15,908 | 140 | 0 | OK |

### customers
- rejected: {'DUPLICATE_EXACT': 0}
- repairs: {}
- flags: {'registration_date_missing_or_invalid': 497, 'birth_year_impossible_set_null': 142, 'city_blank_or_invalid': 2233}
- dedup: {'rule_hits': {'A_email+signals_no_majority_conflict': 1907, 'B_phone+birth+city+name': 419}, 'large_groups_skipped': 0, 'customers_merged': 2326}

### products
- rejected: {'DUPLICATE_EXACT': 0}
- repairs: {'cost_price_imputed_from_category_ratio': 170, 'list_price_imputed_from_cost': 13}
- flags: {'both_prices_missing': 0, 'cost_greater_than_list': 67, 'weight_impossible_set_null': 17, 'weight_missing': 296, 'seller_unknown': 0}
- dedup: {'products_merged': 2}

### sellers
- rejected: {'DUPLICATE_EXACT': 0}
- repairs: {}
- flags: {'rating_out_of_range_set_null': 22, 'rating_missing': 33, 'join_date_missing_or_invalid': 38, 'city_unknown': 0}

### locations
- rejected: {'DUPLICATE_EXACT': 0}
- repairs: {'lat_lon_swapped': 6, 'province_inferred': 25}
- flags: {'lat_lon_missing_or_out_of_range': 62, 'province_still_unknown': 0}

### orders
- rejected: {'DUPLICATE_EXACT': 3200, 'INVALID_DATE': 12}
- repairs: {'order_date_repaired_from_shipping': 1457, 'order_date_repaired_from_payment': 136}
- flags: {'order_date_unparseable': 1124, 'order_date_out_of_window': 481, 'customer_orphan_to_UNKNOWN': 321, 'ship_city_blank_or_invalid_to_UNKNOWN': 6388, 'order_total_invalid_sentinel_or_nonpositive': 488}

### order_items
- rejected: {'DUPLICATE_EXACT': 0, 'ORPHAN_FK': 0, 'PARENT_ORDER_REJECTED': 30, 'UNREPAIRABLE_PRICE': 0}
- repairs: {'negative_quantity_made_positive': 307, 'negative_price_made_positive': 312, 'quantity_solved_from_order_total': 624, 'price_solved_from_order_total': 1220, 'price_from_list_price_fallback': 26, 'quantity_imputed_as_1': 17}
- flags: {'product_orphan_to_UNKNOWN': 932, 'seller_orphan_to_UNKNOWN': 0}

### payments
- rejected: {'DUPLICATE_EXACT': 3296, 'ORPHAN_FK': 0}
- repairs: {'negative_amount_made_positive': 663}
- flags: {'amount_sentinel_set_null': 162}

### shipping
- rejected: {'DUPLICATE_EXACT': 0, 'ORPHAN_FK': 0}
- repairs: {'negative_fee_made_positive': 159, 'fee_imputed_by_order_units_median': 9311, 'fee_total_real_values': 77212972.0, 'fee_total_added_by_estimates': 4305192.0}
- flags: {'delivered_before_shipped': 1269, 'delivery_over_60_days': 249, 'delivered_status_but_no_valid_delivery_date': 14057, 'fee_sentinel_set_null': 166, 'fee_missing_to_be_estimated': 9311}

### returns
- rejected: {'DUPLICATE_EXACT': 0, 'ORPHAN_FK': 139, 'PARENT_ITEM_REJECTED': 1}
- repairs: {'return_date_before_order_shifted_plus_150d': 121, 'refund_above_gross_capped_to_line_net': 203}
- flags: {'rejected_status_kept_but_invalid': 1311, 'return_date_unparseable': 135, 'return_before_order_date_not_repairable': 0, 'valid_return_on_cancelled_or_in_transit_order': 0, 'refund_between_net_and_gross_kept(partial refund on pre-discount price)': 921, 'valid_return_with_missing_or_zero_refund': 0}