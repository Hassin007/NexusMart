"""
rules.py - every threshold, mapping and constant used by the cleaning layer.

Nothing in clean.py hard-codes a label or a number. If the Hour-6 data drop
introduces a new label, you add ONE line here (or the pipeline tells you which
label is unmapped) - you never edit cleaning logic.

Mapping keys are written in "alnum-normalised" form: lower-case, every
character that is not a-z or 0-9 removed.  So "Cash On Delivery", "COD ",
"cod" all hit the key for their own spelling, and "T.C.S" -> "tcs".
"""
import os
from pathlib import Path

# ----------------------------------------------------------------- paths
ROOT = Path(os.environ.get("NEXUS_ROOT", Path(__file__).resolve().parent.parent))
RAW_DIR = Path(os.environ.get("NEXUS_RAW_DIR", ROOT / "data" / "raw"))
CLEAN_DIR = Path(os.environ.get("NEXUS_CLEAN_DIR", ROOT / "data" / "clean"))
REJECT_DIR = Path(os.environ.get("NEXUS_REJECT_DIR", ROOT / "data" / "rejects"))
REPORT_DIR = Path(os.environ.get("NEXUS_REPORT_DIR", ROOT / "reports"))

RAW_FILES = ["customers", "products", "sellers", "locations", "orders",
             "order_items", "payments", "shipping", "returns"]

# ------------------------------------------------------- business windows
DATE_MIN = "2024-01-01"
DATE_MAX = "2025-06-30"

# Order->ship lag in the raw data is 0-2 days (median 1); order->payment 0-11 (median 1).
# Used ONLY to repair an impossible order_date from another table.
SHIP_LAG_DAYS = 1
PAY_LAG_DAYS = 1

UNKNOWN = "UNKNOWN"          # key used for every "Unknown" dimension member

# ------------------------------------------------------------ thresholds
NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na", "-", "--", "?", "nil"}
SENTINEL_MIN = 5_000_000      # 9999999 style placeholder values
PRICE_MIN = 10                # unit prices below this (e.g. 2.43) are broken
PRICE_MAX = 1_000_000
QTY_MAX = 100                 # 500-unit lines are injected errors
TOTAL_MAX = 1_000_000
SHIP_FEE_MAX = 50_000
SHIP_DAYS_MAX = 60            # delivery slower than this = date error, not a slow courier
WEIGHT_MAX = 100
RATING_MIN, RATING_MAX = 1.0, 5.0
BIRTH_YEAR_MIN, BIRTH_YEAR_MAX = 1930, 2010
RECON_TOLERANCE = 0.02        # 2 % tolerance when solving a bad line from order_total
# Returns dated BEFORE their order were all 117-147 days early (a consistent ~5-month shift).
# Adding 150 days puts every one back inside the normal 3-44 day return window.  Approximate repair, always flagged.
RETURN_DATE_SHIFT_DAYS = 150
RETURN_GAP_MAX_DAYS = 60      # a repaired return must land 0-60 days after the order, else it is NOT repaired
FALLBACK_PRICE_FACTOR = 1.02  # unit_price ~ list_price * (1.00 .. 1.04)
PRICE_LIST_RATIO = (0.8, 1.3) # a unit_price outside this band vs list_price is an outlier

# --------------------------------------------------------------- mappings
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

ORDER_STATUS_MAP = {
    "delivered": "Delivered", "deliverd": "Delivered",
    "complete": "Delivered", "completed": "Delivered",
    "cancelled": "Cancelled", "canceled": "Cancelled",
    "returned": "Returned", "return": "Returned",
    "intransit": "In Transit", "shipped": "In Transit",
}
CHANNEL_MAP = {
    "app": "App", "mobileapp": "App",              # ASSUMPTION: 'Mobile App' == App
    "web": "Web", "website": "Web",
    "mobileweb": "Mobile Web", "mweb": "Mobile Web",
}
PAYMENT_METHOD_MAP = {
    "cod": "COD", "cashondelivery": "COD",
    "card": "Card", "creditdebitcard": "Card", "debitcard": "Card", "creditcard": "Card",
    "jazzcash": "JazzCash",
    "easypaisa": "EasyPaisa",
    "banktransfer": "Bank Transfer", "banktrf": "Bank Transfer",
}
PAYMENT_STATUS_MAP = {
    "paid": "Paid", "complete": "Paid", "success": "Paid",
    "cancelled": "Cancelled", "canceled": "Cancelled",
    "refunded": "Refunded", "refund": "Refunded",
    "pending": "Pending",
}
COURIER_MAP = {
    "tcs": "TCS", "tcsexpress": "TCS",
    "leopards": "Leopards", "leopardcourier": "Leopards",
    "mp": "M&P", "mnp": "M&P",
    "trax": "Trax",
    "postex": "PostEx",
    "blueex": "BlueEx",
}
DELIVERY_STATUS_MAP = {
    "delivered": "Delivered", "deliverd": "Delivered",
    "complete": "Delivered", "completed": "Delivered",
    "intransit": "In Transit", "shipped": "In Transit",
    "returnedtoseller": "Returned to Seller", "returntoseller": "Returned to Seller",
    "rto": "Returned to Seller",
}
# value = (canonical label, is_valid_return)
RETURN_STATUS_MAP = {
    "refunded": ("Refunded", True), "refund": ("Refunded", True),
    "approved": ("Approved", True),
    "rejected": ("Rejected", False), "declined": ("Rejected", False),   # 'Declined' is a hidden synonym
}
RETURN_REASON_MAP = {
    "sizefitissue": "Size/Fit Issue", "sizeissue": "Size/Fit Issue", "sizefit": "Size/Fit Issue",
    "doesntfit": "Size/Fit Issue", "wrongsize": "Size/Fit Issue",
    "notasdescribed": "Not as Described", "differentfrompicture": "Not as Described",
    "qualityissue": "Quality Issue", "poorquality": "Quality Issue",
    "badquality": "Quality Issue", "quality": "Quality Issue",
    "damagedproduct": "Damaged Product", "damaged": "Damaged Product", "itemdamaged": "Damaged Product",
    "changedmind": "Changed Mind", "changeofmind": "Changed Mind",
    "changedmymind": "Changed Mind", "nolongerneeded": "Changed Mind",
    "wrongitemdelivered": "Wrong Item Delivered", "wrongitem": "Wrong Item Delivered",
    "receivedwrongproduct": "Wrong Item Delivered",
    "colourmismatch": "Colour Mismatch", "colormismatch": "Colour Mismatch",
    "colourdifferent": "Colour Mismatch", "wrongcolour": "Colour Mismatch",
    "latedelivery": "Late Delivery", "deliveredlate": "Late Delivery",
    "toolate": "Late Delivery", "late": "Late Delivery",
    "missingparts": "Missing Parts", "partsmissing": "Missing Parts",
    "missingpart": "Missing Parts", "incomplete": "Missing Parts",
}
CATEGORY_MAP = {
    "fashion": "Fashion", "fashionapparel": "Fashion", "clothing": "Fashion",
    "footwear": "Footwear", "shoes": "Footwear",
    "electronics": "Electronics", "electronicitems": "Electronics", "elec": "Electronics",
    "mobileaccessories": "Mobile & Accessories", "mobileandaccessories": "Mobile & Accessories",
    "mobileacc": "Mobile & Accessories", "mobiles": "Mobile & Accessories",
    "homekitchen": "Home & Kitchen", "homeandkitchen": "Home & Kitchen",
    "beautypersonalcare": "Beauty & Personal Care", "beautyandpersonalcare": "Beauty & Personal Care",
    "beauty": "Beauty & Personal Care", "personalcare": "Beauty & Personal Care",
    "grocery": "Grocery", "groceries": "Grocery", "foodgrocery": "Grocery",
    "sportsoutdoors": "Sports & Outdoors", "sportsandoutdoors": "Sports & Outdoors", "sports": "Sports & Outdoors",
    "healthwellness": "Health & Wellness", "healthandwellness": "Health & Wellness", "health": "Health & Wellness",
    "toysgames": "Toys & Games", "toysandgames": "Toys & Games", "toys": "Toys & Games",
    "booksstationery": "Books & Stationery", "booksandstationery": "Books & Stationery",
    "books": "Books & Stationery", "stationary": "Books & Stationery",
    "automotive": "Automotive", "auto": "Automotive", "caraccessories": "Automotive",
}
PROVINCE_MAP = {
    "punjab": "Punjab", "panjab": "Punjab",
    "sindh": "Sindh", "sind": "Sindh",
    "khyberpakhtunkhwa": "Khyber Pakhtunkhwa", "kp": "Khyber Pakhtunkhwa", "kpk": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan", "baluchistan": "Balochistan",
    "gilgitbaltistan": "Gilgit-Baltistan", "gb": "Gilgit-Baltistan",
    "azadkashmir": "Azad Kashmir", "azadjammukashmir": "Azad Kashmir", "ajk": "Azad Kashmir",
    "islamabad": "Islamabad",
}
# Known city -> province fixes (used before the nearest-neighbour fallback)
CITY_PROVINCE_FIX = {"rawalpindi": "Punjab", "lahore": "Punjab", "islamabad": "Islamabad"}

POP_TIER_MAP = {"metro": "Metro", "tier1": "Tier-1", "tier2": "Tier-2", "tier3": "Tier-3"}
SELLER_TIER_MAP = {"gold": "Gold", "silver": "Silver", "bronze": "Bronze"}
GENDER_MAP = {"m": "M", "male": "M", "f": "F", "female": "F"}

# Labels that, if unseen in the data, must STOP the pipeline (they change metrics).
STRICT_COLUMNS = {"orders.order_status", "returns.return_status",
                  "payments.payment_method", "products.category"}
