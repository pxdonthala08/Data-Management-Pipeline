import os
import sys
import json
import shutil
import logging
import requests
from datetime import datetime

# ── Logging Setup ──────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/ingestion_{datetime.now():%Y%m%d_%H%M%S}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
RAW_DATA_DIR = "data/raw"
SOURCE_DIR = "/tmp/retailrocket"
MOCK_API_URL = "http://localhost:5001/api/products"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Helper: Retry Mechanism ────────────────────────────────────
def fetch_with_retry(url, max_retries=3):
    import time

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            logger.info(f"API fetch successful: {url}")
            return response.json()

        except requests.exceptions.RequestException as e:
            wait_time = 2 ** attempt
            logger.warning(
                f"Attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    logger.error(f"All {max_retries} attempts failed for {url}")
    return None


# ── Helper: Update latest symlink ───────────────────────────────
def update_latest_symlink(base_dir, timestamp):
    latest_path = os.path.join(base_dir, "latest")
    target_path = os.path.join(base_dir, timestamp)

    try:
        if os.path.islink(latest_path) or os.path.exists(latest_path):
            os.remove(latest_path)
        os.symlink(timestamp, latest_path)
        logger.info(f"Updated latest → {target_path}")
    except Exception as e:
        logger.warning(f"Could not update latest symlink: {e}")


# ── Source 1: CSV File Ingestion ───────────────────────────────
def ingest_csv_files():
    files_config = {
        "events": {"src": "events.csv", "type": "clickstream"},
        "item_properties_part1": {"src": "item_properties_part1.csv", "type": "catalog"},
        "item_properties_part2": {"src": "item_properties_part2.csv", "type": "catalog"},
        "category_tree": {"src": "category_tree.csv", "type": "taxonomy"},
    }

    for name, config in files_config.items():
        src_path = os.path.join(SOURCE_DIR, config["src"])

        dest_dir = os.path.join(RAW_DATA_DIR, config["type"], TIMESTAMP)
        os.makedirs(dest_dir, exist_ok=True)

        dest_path = os.path.join(dest_dir, config["src"])

        try:
            if not os.path.exists(src_path):
                logger.error(f"Source file not found: {src_path}")
                continue

            shutil.copy2(src_path, dest_path)

            file_size = os.path.getsize(dest_path)

            # Fast row count (safe for large files)
            with open(dest_path, "r") as f:
                row_count = sum(1 for _ in f) - 1

            logger.info(
                f"Ingested {name}: {row_count:,} rows, {file_size/1024/1024:.1f} MB → {dest_path}"
            )

            # Update latest symlink per data type
            update_latest_symlink(
                os.path.join(RAW_DATA_DIR, config["type"]),
                TIMESTAMP
            )

        except Exception as e:
            logger.error(f"Failed to ingest {name}: {e}")


# ── Source 2: REST API Ingestion ───────────────────────────────
def ingest_from_api():
    dest_dir = os.path.join(RAW_DATA_DIR, "api_enrichment", TIMESTAMP)
    os.makedirs(dest_dir, exist_ok=True)

    data = fetch_with_retry(MOCK_API_URL)

    if data:
        dest_path = os.path.join(dest_dir, "product_popularity.json")

        with open(dest_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"✓ Ingested API data: {len(data)} records → {dest_path}")

        update_latest_symlink(
            os.path.join(RAW_DATA_DIR, "api_enrichment"),
            TIMESTAMP
        )
    else:
        logger.warning("API ingestion skipped (service unavailable)")


# ── Upload to S3 ──────────────────────────────────────────────
def upload_to_s3():
    import boto3

    s3 = boto3.client("s3")
    bucket = "recomart-data-lake-001"

    for root, _, files in os.walk(RAW_DATA_DIR):
        for file in files:
            local_path = os.path.join(root, file)

            s3_key = local_path.replace("data/", "")

            try:
                s3.upload_file(local_path, bucket, s3_key)
                logger.info(f"Uploaded to s3://{bucket}/{s3_key}")

            except Exception as e:
                logger.error(f"S3 upload failed for {file}: {e}")


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("RECOMART DATA INGESTION STARTED")
    logger.info("=" * 60)

    ingest_csv_files()
    ingest_from_api()
    upload_to_s3()

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
