"""
03_prepare.py — Data Cleaning & Exploratory Data Analysis
Automatically detects the latest timestamped data folders.
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PLOT_DIR = "reports/plots"
os.makedirs(PLOT_DIR, exist_ok=True)


# ── Helper ─────────────────────────────────────────────
def get_latest_dir(parent_dir):
    dirs = [
        d for d in glob.glob(os.path.join(parent_dir, "*"))
        if os.path.isdir(d) and "latest" not in d
    ]
    if not dirs:
        raise FileNotFoundError(f"No data folders found in {parent_dir}")
    return sorted(dirs)[-1]


# ── Events Cleaning ─────────────────────────────────────
def clean_events(filepath):
    logger.info(f"Cleaning events data from: {filepath}")

    df = pd.read_csv(filepath)

    # Remove duplicates
    before = len(df)
    df = df.drop_duplicates()
    logger.info(f"Removed {before - len(df):,} duplicate rows")

    # Timestamp features
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    df["date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.day_name()

    # Fill missing transactionid
    df["transactionid"] = df["transactionid"].fillna(-1).astype(int)

    # Remove low-signal users
    user_counts = df.groupby("visitorid").size()
    active_users = user_counts[user_counts >= 2].index

    before = len(df)
    df = df[df["visitorid"].isin(active_users)]
    logger.info(f"Removed {before - len(df):,} events from single-interaction users")

    return df


# ── Item Properties Cleaning ────────────────────────────
def clean_item_properties(dir_path):
    logger.info(f"Cleaning item properties from: {dir_path}")

    fp1 = os.path.join(dir_path, "item_properties_part1.csv")
    fp2 = os.path.join(dir_path, "item_properties_part2.csv")

    # Load separately to avoid memory spikes
    df1 = pd.read_csv(fp1)
    df2 = pd.read_csv(fp2)

    df = pd.concat([df1, df2], ignore_index=True)

    # Keep latest property per item
    df = df.sort_values("timestamp").drop_duplicates(
        subset=["itemid", "property"], keep="last"
    )

    # Select key properties
    key_props = df[df["property"].isin(["categoryid", "available", "790"])]

    item_features = key_props.pivot_table(
        index="itemid",
        columns="property",
        values="value",
        aggfunc="first"
    ).reset_index()

    logger.info(f"Item features shape: {item_features.shape}")

    return item_features


# ── EDA ────────────────────────────────────────────────
def run_eda(events_df):
    logger.info("Generating EDA plots...")

    # Event Distribution
    plt.figure(figsize=(8, 5))
    events_df["event"].value_counts().plot(kind="bar")
    plt.title("Event Type Distribution")
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/event_distribution.png", dpi=150)
    plt.close()

    # Daily Activity
    plt.figure(figsize=(12, 5))
    events_df.groupby("date").size().plot()
    plt.title("Daily Activity")
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/daily_activity.png", dpi=150)
    plt.close()

    # Hourly Pattern
    plt.figure(figsize=(8, 5))
    events_df.groupby("hour").size().plot(kind="bar")
    plt.title("Hourly Pattern")
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/hourly_pattern.png", dpi=150)
    plt.close()

    # Long Tail
    plt.figure(figsize=(10, 5))
    item_views = events_df[events_df["event"] == "view"]["itemid"].value_counts()
    plt.plot(item_views.values)
    plt.yscale("log")
    plt.title("Long Tail Distribution")
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/long_tail.png", dpi=150)
    plt.close()

    # Funnel
    funnel = events_df["event"].value_counts()
    plt.figure(figsize=(8, 5))
    plt.barh(["Views", "Add to Cart", "Transactions"],
             [funnel.get("view", 0), funnel.get("addtocart", 0), funnel.get("transaction", 0)])
    plt.title("Conversion Funnel")
    plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/conversion_funnel.png", dpi=150)
    plt.close()

    logger.info(f"✓ All plots saved to {PLOT_DIR}/")


# ── Main ───────────────────────────────────────────────
if __name__ == "__main__":
    try:
        clickstream_latest = get_latest_dir("data/raw/clickstream")
        catalog_latest = get_latest_dir("data/raw/catalog")

        events = clean_events(os.path.join(clickstream_latest, "events.csv"))
        items = clean_item_properties(catalog_latest)

        run_eda(events)

        # Save outputs
        os.makedirs("data/prepared", exist_ok=True)

        events.to_parquet("data/prepared/events_cleaned.parquet", index=False)
        items.to_parquet("data/prepared/item_features.parquet", index=False)

        logger.info("✓ Prepared datasets saved")

    except Exception as e:
        logger.error(f"Preparation failed: {e}")
        raise e   # IMPORTANT for Airflow
