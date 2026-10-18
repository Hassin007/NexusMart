"""Shared helpers: loading, parsers, label mapping, reject collection, logging."""
import json
import re
import logging
from datetime import datetime

import numpy as np
import pandas as pd

import rules

log = logging.getLogger("nexus.clean")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ------------------------------------------------------------------ loading
def load_raw(name: str) -> pd.DataFrame:
    """Everything as string, nothing auto-converted. _row = CSV line number."""
    path = rules.RAW_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Raw file missing: {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip().lower() for c in df.columns]
    df.insert(0, "_row", np.arange(2, len(df) + 2))
    return df


def strip_all(df: pd.DataFrame) -> pd.DataFrame:
    """Trim + collapse whitespace; null-like tokens -> '' (still str)."""
    out = df.copy()
    for c in out.columns:
        if c == "_row":
            continue
        s = out[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        out[c] = s.mask(s.str.lower().isin(rules.NULL_TOKENS), "")
    return out


# ------------------------------------------------------------------ parsers
def norm_key(s: pd.Series) -> pd.Series:
    """lower-case, keep only a-z0-9 (used for label mapping and fuzzy keys)."""
    return s.astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)


def parse_date(s: pd.Series) -> pd.Series:
    """Explicit formats only (never let pandas guess).  Slash dates are D/M/Y."""
    x = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=x.index, dtype="datetime64[ns]")
    for rx, fmt in [(r"^\d{4}-\d{1,2}-\d{1,2}$", "%Y-%m-%d"),
                    (r"^\d{1,2}/\d{1,2}/\d{4}$", "%d/%m/%Y"),
                    (r"^[A-Za-z]{3,9} \d{1,2},? \d{4}$", None)]:
        m = x.str.match(rx)
        if not m.any():
            continue
        if fmt:
            out[m] = pd.to_datetime(x[m], format=fmt, errors="coerce")
        else:   # 'Nov 23 2024'
            y = x[m].str.replace(",", "", regex=False)
            y = y.str.replace(r"^([A-Za-z]{3})[A-Za-z]* ", r"\1 ", regex=True)
            out[m] = pd.to_datetime(y, format="%b %d %Y", errors="coerce")
    return out


def parse_money(s: pd.Series) -> pd.Series:
    """'Rs. 2,290' -> 2290.0 ; blanks/garbage -> NaN."""
    x = s.astype(str).str.replace(r"(?i)rs\.?|pkr|,|\s", "", regex=True)
    return pd.to_numeric(x, errors="coerce")


def parse_qty(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.strip().str.lower().replace(rules.WORD_NUMBERS)
    return pd.to_numeric(x, errors="coerce")


def in_window(d: pd.Series) -> pd.Series:
    return d.between(pd.Timestamp(rules.DATE_MIN), pd.Timestamp(rules.DATE_MAX))


def norm_phone(s: pd.Series) -> pd.Series:
    """Any of 0343-4328042 / 03292755530 / +923332812162 / 330 2812162 -> 03XXXXXXXXX."""
    d = s.astype(str).str.replace(r"\D", "", regex=True)
    d = d.str.replace(r"^0092", "92", regex=True)
    last10 = d.where(d.str.len() >= 10, "").str[-10:]
    return ("0" + last10).where(last10 != "", "")


# ------------------------------------------------------------ label mapping
def map_labels(s: pd.Series, mapping: dict, col: str, log_dict: dict,
               default=None, strict: bool = None) -> pd.Series:
    """Map messy labels through `mapping` (alnum-normalised keys).
    Blank stays blank. Unmapped values are logged; if the column is STRICT the
    pipeline stops so a new Hour-6 label can never slip through silently."""
    key = norm_key(s)
    mapped = key.map(mapping)
    blank = s.astype(str).str.strip() == ""
    unmapped = ~blank & mapped.isna()
    if unmapped.any():
        bad = s[unmapped].value_counts().head(20).to_dict()
        log_dict.setdefault("unmapped_labels", {})[col] = bad
        msg = f"{col}: {int(unmapped.sum())} values have NO mapping: {bad}"
        if strict if strict is not None else col in rules.STRICT_COLUMNS:
            raise ValueError("UNMAPPED LABEL (add it to rules.py) -> " + msg)
        log.warning(msg)
    changed = int(((s != mapped) & mapped.notna()).sum())
    log_dict.setdefault("labels_standardised", {})[col] = changed
    return mapped.fillna(default) if default is not None else mapped


# ----------------------------------------------------- reject collection
class Rejects:
    """One place that every cleaner writes unrepairable/removed rows to."""
    COLS = ["source_file", "source_row", "record_key", "reason_code", "reason_detail", "raw_record", "rejected_at"]

    def __init__(self):
        self.parts = []
        self.ts = datetime.now().isoformat(timespec="seconds")

    def add(self, source_file, raw_df, mask, reason_code, reason_detail="", key_col=None):
        sub = raw_df.loc[mask[mask].index]
        if sub.empty:
            return 0
        rec = sub.drop(columns=[c for c in sub.columns if c.startswith("_") and c != "_row"], errors="ignore")
        raw_json = rec.drop(columns=["_row"], errors="ignore").apply(lambda r: json.dumps(r.to_dict(), default=str), axis=1)
        self.parts.append(pd.DataFrame({
            "source_file": source_file,
            "source_row": sub["_row"].values,
            "record_key": sub[key_col].values if key_col else "",
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "raw_record": raw_json.values,
            "rejected_at": self.ts}))
        return len(sub)

    def add_rows(self, source_file, raw_df, rows, reason_code, reason_detail="", key_col=None):
        """Reject by CSV line numbers (use when the working frame's index no longer matches raw)."""
        mask = raw_df["_row"].isin(set(rows))
        return self.add(source_file, raw_df, mask, reason_code, reason_detail, key_col)

    def frame(self):
        return pd.concat(self.parts, ignore_index=True) if self.parts else pd.DataFrame(columns=self.COLS)

    def write(self):
        rules.REJECT_DIR.mkdir(parents=True, exist_ok=True)
        df = self.frame()
        df.to_csv(rules.REJECT_DIR / "rejects.csv", index=False)
        return df


def new_log(name, raw_rows):
    return {"file": name, "raw_rows": int(raw_rows), "rejected": {}, "repairs": {}, "flags": {}}


def assert_identity(lg, clean_rows, merged=0):
    """raw = clean + rejected(+ duplicates) + merged.  The core before/after proof."""
    rej = sum(lg["rejected"].values())
    lg["clean_rows"] = int(clean_rows)
    lg["merged_into_master"] = int(merged)
    ok = lg["raw_rows"] == clean_rows + rej + merged
    lg["identity_ok"] = bool(ok)
    if not ok:
        raise AssertionError(f"{lg['file']}: raw {lg['raw_rows']} != clean {clean_rows} + rejected {rej} + merged {merged}")
    log.info("%-12s raw=%7d clean=%7d rejected=%6d merged=%5d  OK", lg["file"], lg["raw_rows"], clean_rows, rej, merged)
