"""
warehouse.py - loads cleaned data into PostgreSQL and builds the star schema.

Each function is one pipeline step (they become the Airflow tasks):
    init_schema()        create schemas/tables            (sql/01)
    load_staging()       TRUNCATE + COPY cleaned CSVs     (idempotent)
    build_dimensions()   upsert 5 dimensions              (sql/02)
    build_fact()         rebuild FactSales + RFM segments (sql/03 + sql/05)
    quality_checks()     run sql/04, FAIL on critical     (raises QualityCheckFailed)

Connection settings come from environment variables (never hard-coded):
    PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD   (defaults match docker-compose.yml)

CLI:  python src/warehouse.py all | init | load_staging | dims | fact | quality  [--reset]
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules
from utils import log

SQL_DIR = Path(os.environ.get("NEXUS_SQL_DIR", rules.ROOT / "sql"))

# clean CSV file -> staging table
STAGING_TABLES = ["locations", "sellers", "customers", "customer_id_map", "products", "product_id_map",
                  "orders", "order_items", "payments", "order_payment", "shipping", "returns"]


class QualityCheckFailed(Exception):
    pass


def connect():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"), port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ.get("PGDATABASE", "nexusmart"), user=os.environ.get("PGUSER", "nexus"),
        password=os.environ.get("PGPASSWORD", "nexus_pass"))


def run_sql_file(name, conn=None):
    own = conn is None
    conn = conn or connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute((SQL_DIR / name).read_text())
        log.info("executed %s", name)
    finally:
        if own:
            conn.close()


def init_schema(reset=False):
    conn = connect()
    try:
        if reset:
            with conn, conn.cursor() as cur:
                cur.execute("DROP SCHEMA IF EXISTS dw CASCADE; DROP SCHEMA IF EXISTS staging CASCADE; "
                            "DROP SCHEMA IF EXISTS audit CASCADE;")
            log.warning("schemas dropped (--reset)")
        run_sql_file("01_schema.sql", conn)
    finally:
        conn.close()


def _copy_csv(cur, schema_table, path):
    with open(path, newline="", encoding="utf-8") as fh:
        cols = next(csv.reader(fh))
    with open(path, "r", encoding="utf-8") as fh:
        cur.copy_expert(f"COPY {schema_table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, HEADER true)", fh)
    cur.execute(f"SELECT COUNT(*) FROM {schema_table}")
    return cur.fetchone()[0]


def load_staging():
    """TRUNCATE + COPY in ONE transaction: re-running replaces the data, never appends."""
    counts = {}
    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            for t in STAGING_TABLES:
                path = rules.CLEAN_DIR / f"{t}.csv"
                if not path.exists():
                    raise FileNotFoundError(f"clean file missing: {path} (run clean.py first)")
                cur.execute(f"TRUNCATE staging.{t}")
                counts[t] = _copy_csv(cur, f"staging.{t}", path)
                expected = sum(1 for _ in open(path, encoding="utf-8")) - 1
                # a quoted field may contain a newline; compare against pandas-independent csv count
                with open(path, newline="", encoding="utf-8") as fh:
                    expected = sum(1 for _ in csv.reader(fh)) - 1
                if counts[t] != expected:
                    raise RuntimeError(f"staging.{t}: loaded {counts[t]} rows but file has {expected}")
                log.info("staging.%-16s loaded %8d rows", t, counts[t])
            # audit tables: latest run only
            cur.execute("TRUNCATE audit.rejects")
            rej = rules.REJECT_DIR / "rejects.csv"
            if rej.exists():
                counts["audit.rejects"] = _copy_csv(cur, "audit.rejects", rej)
            cur.execute("TRUNCATE audit.cleaning_summary")
            lg_path = rules.REPORT_DIR / "cleaning_log.json"
            if lg_path.exists():
                lg = json.loads(lg_path.read_text())
                for name in rules.RAW_FILES:
                    x = lg[name]
                    cur.execute(
                        "INSERT INTO audit.cleaning_summary(file_name, raw_rows, clean_rows, rejected_rows, merged_rows,"
                        " identity_ok, repairs, flags) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (name, x["raw_rows"], x["clean_rows"], sum(x["rejected"].values()), x["merged_into_master"],
                         x["identity_ok"], json.dumps(x["repairs"]), json.dumps(x["flags"])))
    finally:
        conn.close()
    return counts


def build_dimensions():
    run_sql_file("02_build_dimensions.sql")


def build_fact():
    run_sql_file("03_build_fact.sql")
    run_sql_file("05_customer_segments.sql")
    run_sql_file("06_headline_metrics.sql")


def quality_checks(raise_on_fail=True):
    conn = connect()
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute((SQL_DIR / "04_quality_checks.sql").read_text())
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                cur.execute("INSERT INTO audit.quality_check_results(check_name, actual, expectation, status, severity)"
                            " VALUES (%s,%s,%s,%s,%s)",
                            (r["check_name"], r["actual"], r["expectation"], r["status"], r["severity"]))
    finally:
        conn.close()
    for r in rows:
        level = log.info if r["status"] == "PASS" else (log.error if r["severity"] == "CRITICAL" else log.warning)
        level("%-6s %-8s %-52s actual=%s  expected %s", r["status"], r["severity"], r["check_name"], r["actual"], r["expectation"])
    failed = [r["check_name"] for r in rows if r["status"] == "FAIL" and r["severity"] == "CRITICAL"]
    if failed and raise_on_fail:
        raise QualityCheckFailed(f"critical quality checks failed: {failed}")
    return rows


def run_all(reset=False):
    init_schema(reset)
    load_staging()
    build_dimensions()
    build_fact()
    return quality_checks()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["all", "init", "load_staging", "dims", "fact", "quality"])
    ap.add_argument("--reset", action="store_true", help="drop and recreate all schemas first")
    a = ap.parse_args()
    {"all": lambda: run_all(a.reset), "init": lambda: init_schema(a.reset), "load_staging": load_staging,
     "dims": build_dimensions, "fact": build_fact, "quality": quality_checks}[a.step]()
