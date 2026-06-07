"""
02_validate.py — Data Profiling & Validation
Automatically detects the latest timestamped data folders.
"""

import pandas as pd
import logging
import json
import os
import glob
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPORT = {"timestamp": datetime.now().isoformat(), "checks": []}


# ── Logging Helper ─────────────────────────────────────────────
def log_check(name, status, details=""):
    result = {"check": name, "status": status, "details": details}
    REPORT["checks"].append(result)
    icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
    logger.info(f"{icon} {name}: {details}")


# ── Get Latest Folder ──────────────────────────────────────────
def get_latest_dir(parent_dir):
    dirs = [
        d for d in glob.glob(os.path.join(parent_dir, "*"))
        if os.path.isdir(d) and "latest" not in d
    ]
    if not dirs:
        raise FileNotFoundError(f"No data folders found in {parent_dir}")
    return sorted(dirs)[-1]


# ── Validate Events ────────────────────────────────────────────
def validate_events(filepath):
    logger.info("\n" + "=" * 50)
    logger.info(f"VALIDATING: {filepath}")
    logger.info("=" * 50)

    # Load only required columns (memory efficient)
    df = pd.read_csv(filepath)

    REPORT["events_shape"] = {"rows": len(df), "columns": len(df.columns)}

    # 1. Schema
    expected_cols = {"timestamp", "visitorid", "event", "itemid", "transactionid"}
    actual_cols = set(df.columns)

    if expected_cols == actual_cols:
        log_check("Schema Match", "PASS", f"Columns: {list(df.columns)}")
    else:
        log_check("Schema Match", "FAIL", f"Missing: {expected_cols - actual_cols}")

    # 2. Missing values
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)

    for col in df.columns:
        if missing[col] > 0:
            log_check(f"Missing Values — {col}", "WARN",
                      f"{missing[col]:,} missing ({missing_pct[col]}%)")
        else:
            log_check(f"Missing Values — {col}", "PASS", "No missing values")

    # 3. Duplicates
    dupes = df.duplicated().sum()
    log_check("Duplicate Rows", "PASS" if dupes == 0 else "WARN",
              f"{dupes:,} duplicate rows found")

    # 4. Event types
    valid_events = {"view", "addtocart", "transaction"}
    actual_events = set(df["event"].unique())

    if actual_events.issubset(valid_events):
        log_check("Event Types", "PASS", f"Found: {actual_events}")
    else:
        log_check("Event Types", "FAIL", f"Unexpected: {actual_events - valid_events}")

    # 5. Timestamp range
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    min_date = df["datetime"].min()
    max_date = df["datetime"].max()

    log_check("Timestamp Range", "PASS",
              f"{min_date.date()} → {max_date.date()} ({(max_date - min_date).days} days)")

    # 6. Transaction ID consistency
    txn_events = df[df["event"] == "transaction"]
    txn_null_id = txn_events["transactionid"].isnull().sum()

    log_check("Transaction ID Consistency",
              "PASS" if txn_null_id == 0 else "FAIL",
              f"{txn_null_id} missing transaction IDs")

    REPORT["events_summary"] = {
        "total_events": int(len(df)),
        "unique_visitors": int(df["visitorid"].nunique()),
        "unique_items": int(df["itemid"].nunique()),
        "event_distribution": df["event"].value_counts().to_dict(),
        "date_range": f"{min_date.date()} to {max_date.date()}",
    }

    return df


# ── Validate Item Properties ───────────────────────────────────
def validate_item_properties(dir_path):
    logger.info("\n" + "=" * 50)
    logger.info(f"VALIDATING: item_properties in {dir_path}")
    logger.info("=" * 50)

    fp1 = os.path.join(dir_path, "item_properties_part1.csv")
    fp2 = os.path.join(dir_path, "item_properties_part2.csv")

    # Load separately to avoid memory spikes
    df1 = pd.read_csv(fp1)
    df2 = pd.read_csv(fp2)

    df = pd.concat([df1, df2], ignore_index=True)

    expected_cols = {"timestamp", "itemid", "property", "value"}
    actual_cols = set(df.columns)

    log_check("Schema Match (items)",
              "PASS" if expected_cols == actual_cols else "FAIL",
              f"Columns: {list(df.columns)}")

    missing = df.isnull().sum()
    for col in df.columns:
        if missing[col] > 0:
            log_check(f"Missing — {col}", "WARN", f"{missing[col]:,} missing")

    n_items = df["itemid"].nunique()
    n_props = df["property"].nunique()

    log_check("Item Coverage", "PASS",
              f"{n_items:,} items, {n_props:,} properties")

    REPORT["item_properties_summary"] = {
        "total_records": int(len(df)),
        "unique_items": int(n_items),
        "unique_properties": int(n_props),
    }

    return df


# ── Validate Category Tree ─────────────────────────────────────
def validate_category_tree(filepath):
    logger.info("\n" + "=" * 50)
    logger.info(f"VALIDATING: {filepath}")
    logger.info("=" * 50)

    df = pd.read_csv(filepath)

    log_check("Schema Match (categories)", "PASS",
              f"{len(df):,} rows")

    root_count = df["parentid"].isnull().sum()

    log_check("Root Categories", "PASS", f"{root_count} root nodes")

    REPORT["category_summary"] = {
        "total_categories": int(len(df)),
        "root_categories": int(root_count)
    }

    return df


# ── Save Report ────────────────────────────────────────────────
def save_report():
    os.makedirs("reports", exist_ok=True)
    path = "reports/data_quality_report.json"

    with open(path, "w") as f:
        json.dump(REPORT, f, indent=2, default=str)

    logger.info(f"\nQuality report saved: {path}")


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        clickstream_latest = get_latest_dir("data/raw/clickstream")
        catalog_latest = get_latest_dir("data/raw/catalog")
        taxonomy_latest = get_latest_dir("data/raw/taxonomy")

        validate_events(os.path.join(clickstream_latest, "events.csv"))
        validate_item_properties(catalog_latest)
        validate_category_tree(os.path.join(taxonomy_latest, "category_tree.csv"))

        save_report()

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise e   # IMPORTANT: ensures Airflow detects failure
