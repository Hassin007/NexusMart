"""
profile.py - measure the raw data BEFORE touching it (the "before" half of the DQ report).

Run:  python src/profile.py
Output: reports/profile_raw.md  and  reports/profile_raw.json

Per column: blanks, distinct values, top values, value 'shapes' (9=digit, a=letter) that expose
mixed date/money formats, numeric range.  Per file: exact duplicate rows and duplicate keys.
Re-run it on the Hour-6 data drop and diff the two reports.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules
from utils import load_raw, parse_money

KEYS = {"customers": "customer_id", "products": "product_id", "sellers": "seller_id", "locations": "city_id",
        "orders": "order_id", "order_items": "order_item_id", "payments": "payment_id",
        "shipping": "shipment_id", "returns": "return_id"}


def shape(s: pd.Series) -> pd.Series:
    return s.str.replace(r"[A-Za-z]", "a", regex=True).str.replace(r"\d", "9", regex=True)


def profile_file(name):
    df = load_raw(name).drop(columns="_row")
    key = KEYS[name]
    out = {"rows": len(df), "exact_duplicate_rows": int(df.duplicated().sum()),
           "duplicate_key_rows": int(df[key].duplicated().sum()), "columns": {}}
    for c in df.columns:
        s = df[c]
        blank = s.str.strip().eq("") | s.str.strip().str.lower().isin(rules.NULL_TOKENS)
        info = {"blank": int(blank.sum()), "distinct": int(s.nunique()),
                "whitespace_padded": int((s != s.str.strip()).sum()),
                "top_values": s.value_counts().head(8).to_dict()}
        if s.nunique() > 30:
            info["shapes"] = shape(s).value_counts().head(6).to_dict()
        num = parse_money(s)
        if num.notna().mean() > 0.9:
            info["numeric"] = {"min": float(num.min()), "median": float(num.median()),
                               "max": float(num.max()), "negative": int((num < 0).sum()),
                               "zero": int((num == 0).sum()),
                               "unparseable": int((num.isna() & ~blank).sum())}
        out["columns"][c] = info
    return out


def main():
    rules.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    result = {n: profile_file(n) for n in rules.RAW_FILES}
    (rules.REPORT_DIR / "profile_raw.json").write_text(json.dumps(result, indent=2, default=str))
    md = ["# Raw data profile (BEFORE cleaning)\n"]
    for n, p in result.items():
        md.append(f"\n## {n}  ({p['rows']:,} rows | exact duplicate rows: {p['exact_duplicate_rows']:,} | "
                  f"duplicate keys: {p['duplicate_key_rows']:,})\n")
        md.append("| column | blank | distinct | padded | numeric (min / median / max, neg, zero, bad) | formats / top values |")
        md.append("|---|--:|--:|--:|---|---|")
        for c, i in p["columns"].items():
            nm = i.get("numeric")
            nums = f"{nm['min']:,.0f} / {nm['median']:,.0f} / {nm['max']:,.0f}, {nm['negative']}, {nm['zero']}, {nm['unparseable']}" if nm else ""
            fmt = i.get("shapes") or i["top_values"]
            md.append(f"| {c} | {i['blank']:,} | {i['distinct']:,} | {i['whitespace_padded']:,} | {nums} | {str(fmt)[:140]} |")
    (rules.REPORT_DIR / "profile_raw.md").write_text("\n".join(md))
    print(f"profile written to {rules.REPORT_DIR}")


if __name__ == "__main__":
    main()
