# Raw data profile (BEFORE cleaning)


## customers  (45,000 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| customer_id | 0 | 45,000 | 0 |  | {'a999999': 45000} |
| full_name | 0 | 3,463 | 2,275 |  | {'aaaaaa aaaaa': 4990, 'aaaaa aaaaa': 4492, 'aaaaaa aaaaaa': 3676, 'aaaa aaaaa': 3553, 'aaaaa aaaaaa': 3077, 'aaaaaa aaaa': 2825} |
| email | 1,698 | 42,752 | 0 |  | {'aaaaaa.aaaaa9999@aaaaa.aaa': 3690, 'aaaaa.aaaaa9999@aaaaa.aaa': 3353, 'aaaaaa.aaaaaa9999@aaaaa.aaa': 2729, 'aaaa.aaaaa9999@aaaaa.aaa': 262 |
| phone | 3,599 | 40,860 | 0 |  | {'99999999999': 14530, '9999-9999999': 12289, '+999999999999': 6176, '999 9999999': 4248, '9999 9999999': 4158, '': 3599} |
| gender | 2,199 | 9 | 0 |  | {'M': 16672, 'F': 13344, 'male': 2382, 'Male': 2328, 'm': 2327, '': 2199, 'f': 1949, 'Female': 1909} |
| registration_date | 0 | 2,501 | 0 |  | {'9999-99-99': 38087, '99/99/9999': 3760, 'aaa 99 9999': 2235, 'aaa 9 9999': 918} |
| city_id | 2,233 | 651 | 0 | 1 / 450 / 650, 0, 0, 0 | {'999': 39101, '99': 3567, '': 2233, '9': 99} |
| birth_year | 4,600 | 51 | 0 |  | {'9999': 40400, '': 4600} |

## products  (3,200 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| product_id | 0 | 3,200 | 0 |  | {'a99999': 3200} |
| product_name | 0 | 3,176 | 123 |  | {'aaaaaaa aaaaaa aaaaa a999': 88, 'aaaaaaa aaaaa aaaaa a999': 68, 'aaaaaaa aaaa aaaaa a999': 65, 'aaaaaaa aaaaaaaa aaaa a999': 58, 'aaaaaaa  |
| category | 0 | 74 | 641 |  | {'aaaaaaa': 503, 'aaaa & aaaaaaa': 223, 'aaaaaa & aaaaaaaaaaa': 222, 'aaaaaa & aaaaaaaa': 218, 'aaaaaaaaaaa': 204, 'aaaaaaaa': 188} |
| sub_category | 485 | 37 | 0 |  | {'': 485, 'aaaaaa aaaaaaaaaa': 327, 'aaaaaa aaaaaa': 309, 'aaaaaa aaaaaaa': 291, 'aaaaaaa aaaaaa': 228, 'aaaaaaa aaaaaaa': 207} |
| brand | 392 | 17 | 0 |  | {'NexusChoice': 582, 'Generic': 570, 'Zeta': 549, 'Orion': 542, '': 392, 'FashPro': 88, 'HomePro': 70, 'ElecPro': 66} |
| list_price | 0 | 970 | 0 | -3,810 / 1,660 / 9,999,999, 4, 4, 0 | {'9999': 2085, '999': 842, '99999': 155, 'aa. 9,999': 65, 'aa. 999': 35, '9999999': 5} |
| cost_price | 170 | 1,878 | 0 | 82 / 1,010 / 83,205, 0, 0, 0 | {'999': 1497, '9999': 1411, '': 170, '99999': 118, '99': 4} |
| weight_kg | 296 | 473 | 0 | -1 / 1 / 629, 10, 0, 0 | {'9.99': 2583, '9.9': 298, '': 296, '-9.9': 10, '999.9': 7, '99.9': 5} |
| seller_id | 0 | 407 | 0 |  | {'a9999': 3200} |

## sellers  (420 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| seller_id | 0 | 420 | 0 |  | {'a9999': 420} |
| seller_name | 0 | 415 | 15 |  | {'aaaaa aaaaaaa 99': 31, 'aaaaa aaaaaa 99': 22, 'aaaaa aaa 99': 20, 'aaaaa aaaaaaaaa 99': 18, 'aaaaa aaaaaaaa 99': 17, 'aaaaa aaaa 99': 17} |
| join_date | 34 | 358 | 0 |  | {'9999-99-99': 327, '99/99/9999': 36, '': 34, 'aaa 99 9999': 17, 'aaa 9 9999': 6} |
| seller_tier | 22 | 11 | 5 |  | {'Bronze': 215, 'Silver': 79, 'Gold': 35, 'BRONZE': 25, '': 22, 'bronze': 19, 'SILVER': 12, 'silver': 5} |
| city_id | 0 | 106 | 0 | 23 / 450 / 643, 0, 0, 0 | {'999': 390, '99': 30} |
| rating | 33 | 26 | 0 | 0 / 4 / 11, 0, 11, 0 | {'4.1': 38, '': 33, '4.3': 30, '4.0': 28, '3.9': 24, '4.7': 24, '4.2': 23, '4.4': 22} |

## locations  (650 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| city_id | 0 | 650 | 0 | 1 / 326 / 650, 0, 0, 0 | {'999': 551, '99': 90, '9': 9} |
| city | 0 | 650 | 12 |  | {'aaaaaaaa': 111, 'aaaaaaaaaaaa': 104, 'aaaaaaa': 93, 'aaaaaaaaaaa': 91, 'aaaaaaaaa': 69, 'aaaaaaaaaaaaa': 56} |
| province | 25 | 22 | 3 |  | {'Punjab': 250, 'Sindh': 125, 'Khyber Pakhtunkhwa': 82, 'Balochistan': 46, '': 25, 'Panjab': 17, 'Gilgit-Baltistan': 13, 'Azad Kashmir': 13} |
| region | 0 | 3 | 0 |  | {'Central': 300, 'South': 212, 'North': 138} |
| latitude | 33 | 616 | 0 | 23 / 31 / 73, 0, 0, 0 | {'99.9999': 528, '99.999': 42, '99.99': 42, '': 33, '99.9': 5} |
| longitude | 31 | 616 | 0 | 28 / 72 / 79, 0, 0, 0 | {'99.9999': 508, '99.999': 57, '99.99': 49, '': 31, '99.9': 5} |
| population_tier | 0 | 3 | 0 |  | {'Tier-3': 634, 'Tier-2': 10, 'Metro': 6} |

## orders  (163,200 rows | exact duplicate rows: 3,200 | duplicate keys: 3,200)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| order_id | 0 | 160,000 | 0 |  | {'a9999999': 163200} |
| customer_id | 0 | 33,756 | 0 |  | {'a999999': 162870, 'a99999': 330} |
| order_date | 0 | 2,008 | 0 |  | {'9999-99-99': 138516, '99/99/9999': 13583, 'aaa 99 9999': 7742, 'aaa 9 9999': 3359} |
| order_status | 0 | 20 | 924 |  | {'Delivered': 108289, 'Cancelled': 11222, 'Complete': 7292, 'DELIVERD': 7175, 'Completed': 7153, 'DELIVERED': 7118, 'delivered': 6911, 'Retu |
| ship_city_id | 6,516 | 651 | 0 | 1 / 450 / 650, 0, 0, 0 | {'999': 143584, '99': 12776, '': 6516, '9': 324} |
| order_total | 0 | 32,728 | 0 | -78,112 / 4,838 / 9,999,999, 169, 177, 0 | {'9999': 106187, '99999': 38270, '999': 13922, 'aa. 9,999': 2649, 'aa. 99,999': 1004, 'aa. 999': 371} |
| discount_code | 112,059 | 33 | 2,099 |  | {'': 112059, 'aaaa99': 43510, 'aaaa9': 5532, ' aaaa99': 1841, ' aaaa9': 258} |
| channel | 0 | 12 | 0 |  | {'App': 69259, 'Web': 41646, 'Mobile Web': 27941, 'Mobile App': 4069, 'app': 4036, 'APP': 4029, 'WEB': 2482, 'Website': 2463} |

## order_items  (315,143 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| order_item_id | 0 | 315,143 | 0 |  | {'aa99999999': 315143} |
| order_id | 0 | 160,000 | 0 |  | {'a9999999': 315143} |
| product_id | 0 | 4,086 | 0 |  | {'a99999': 315143} |
| seller_id | 0 | 407 | 0 |  | {'a9999': 315143} |
| quantity | 0 | 24 | 0 | -6 / 1 / 500, 307, 0, 965 | {'1': 186706, '2': 71061, '3': 31529, '4': 12740, '5': 6230, '1.0': 2866, '2.0': 1151, '500': 641} |
| unit_price | 0 | 21,868 | 0 | -41,270 / 1,619 / 9,999,999, 316, 331, 0 | {'9999': 204202, '999': 88887, '99999': 12578, 'aa. 9,999': 5463, 'aa. 999': 2238, '9': 331} |
| discount_amount | 31,567 | 7,557 | 0 |  | {'9': 191056, '999': 56898, '': 31567, '9999': 24673, '99': 9770, '99999': 1176} |

## payments  (168,111 rows | exact duplicate rows: 3,296 | duplicate keys: 3,296)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| payment_id | 0 | 164,815 | 0 |  | {'aaa99999999': 168111} |
| order_id | 0 | 160,000 | 0 |  | {'a9999999': 168111} |
| payment_method | 0 | 22 | 5,355 |  | {'COD': 64761, 'Card': 21802, 'JazzCash': 16008, 'EasyPaisa': 14972, 'Bank Transfer': 8475, 'Cash on Delivery': 5460, 'Cash On Delivery': 53 |
| payment_status | 0 | 17 | 757 |  | {'Paid': 113729, 'PAID': 9644, 'paid': 9632, 'Complete': 9509, 'Success': 9472, 'Cancelled': 9153, 'Refunded': 2370, 'cancelled': 814} |
| amount | 0 | 33,179 | 0 | -143,168 / 4,622 / 9,999,999, 671, 165, 0 | {'9999': 109023, '99999': 37844, '999': 15729, 'aa. 9,999': 2819, 'aa. 99,999': 971, '-9999': 477} |
| payment_date | 5,017 | 1,687 | 0 |  | {'9999-99-99': 138906, '99/99/9999': 13503, 'aaa 99 9999': 7382, '': 5017, 'aaa 9 9999': 3303} |

## shipping  (151,228 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| shipment_id | 0 | 151,228 | 0 |  | {'aa99999999': 151228} |
| order_id | 0 | 151,228 | 0 |  | {'a9999999': 151228} |
| courier | 0 | 22 | 0 |  | {'TCS': 36319, 'Leopards': 26570, 'M&P': 18256, 'Trax': 15652, 'PostEx': 14401, 'BlueEx': 9662, 'tcs': 3090, 'TCS Express': 3001} |
| shipped_date | 5,943 | 1,658 | 0 |  | {'9999-99-99': 123431, '99/99/9999': 12118, 'aaa 99 9999': 6807, '': 5943, 'aaa 9 9999': 2929} |
| delivered_date | 18,841 | 1,689 | 0 |  | {'9999-99-99': 112611, '': 18841, '99/99/9999': 10875, 'aaa 99 9999': 6326, 'aaa 9 9999': 2575} |
| shipping_fee | 9,145 | 2,964 | 0 | -2,577 / 421 / 9,999,999, 159, 129, 0 | {'999': 127171, '9999': 14458, '': 9145, '9999999': 166, '-999': 140, '9': 129} |
| delivery_status | 0 | 15 | 0 |  | {'Delivered': 108093, 'DELIVERD': 7334, 'Completed': 7218, 'Complete': 7192, 'DELIVERED': 7092, 'delivered': 7056, 'Returned to Seller': 441 |

## returns  (16,048 rows | exact duplicate rows: 0 | duplicate keys: 0)

| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |
|---|--:|--:|--:|---|---|
| return_id | 0 | 16,048 | 0 |  | {'a999999': 16048} |
| order_item_id | 0 | 16,048 | 0 |  | {'aa99999999': 15909, 'aa99999': 139} |
| return_date | 0 | 1,510 | 0 |  | {'9999-99-99': 13732, '99/99/9999': 1264, 'aaa 99 9999': 774, 'aaa 9 9999': 278} |
| return_reason | 2,390 | 38 | 0 |  | {'': 2390, 'aaa aa aaaaaaaaa': 2046, 'aaaaaaa aaaaa': 1706, 'aaaa/aaa aaaaa': 1680, 'aaaaaaa aaaaaaa': 1650, 'aaaaaaa aaaa': 1180} |
| return_status | 0 | 10 | 0 |  | {'Refunded': 8673, 'Approved': 2403, 'Refund': 997, 'Rejected': 979, 'REFUNDED': 976, 'refunded': 903, 'APPROVED': 407, 'approved': 367} |
| refund_amount | 0 | 6,958 | 0 | 0 / 2,022 / 250,592, 0, 1297, 0 | {'9999': 10408, '999': 2873, '9': 1261, '99999': 1070, 'aa. 9,999': 280, 'aa. 999': 84} |