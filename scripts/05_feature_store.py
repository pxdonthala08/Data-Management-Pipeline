from feast import FeatureStore
import pandas as pd
from datetime import datetime, timedelta
import os
import logging

# 🔥 IMPORTANT: import your feature definitions
from feature_store.features import (
    user_features_view,
    item_features_view,
    user_entity,
    item_entity,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ── CONFIG ────────────────────────────────────────────
REPO_PATH = "feature_store"
USER_PATH = "data/transformed/user_features.parquet"
ITEM_PATH = "data/transformed/item_features.parquet"


# ── STEP 1: PREPARE DATA ──────────────────────────────
def prepare_data_for_feast():
    """
    Add required 'event_timestamp' column for Feast.
    """
    logger.info("Preparing data for Feast...")

    for path in [USER_PATH, ITEM_PATH]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} not found")

        df = pd.read_parquet(path)

        # Add timestamp if missing
        if "event_timestamp" not in df.columns:
            df["event_timestamp"] = datetime.now()

        df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])

        df.to_parquet(path, index=False)

    logger.info("✓ Parquet files updated with Feast timestamps")


# ── STEP 2: SETUP FEATURE STORE ────────────────────────
def setup_feature_store():
    logger.info("Setting up Feature Store...")

    store = FeatureStore(repo_path=REPO_PATH)

    # ✅ Explicit registration (FIXED)
    store.apply([
        user_entity,
        item_entity,
        user_features_view,
        item_features_view,
    ])

    logger.info("✓ Feature views registered")

    # Materialize to online store
    store.materialize_incremental(
        end_date=datetime.now() + timedelta(days=1)
    )

    logger.info("✓ Features materialized to online store")


# ── STEP 3: DEMO RETRIEVAL ────────────────────────────
def demo_feature_retrieval():
    logger.info("Fetching online features...")

    store = FeatureStore(repo_path=REPO_PATH)

    user_df = pd.read_parquet(USER_PATH)

    # Pick a real user
    sample_id = int(user_df["visitorid"].iloc[0])

    features = store.get_online_features(
        features=[
            "user_features:total_views",
            "user_features:cart_rate",
        ],
        entity_rows=[{"visitorid": sample_id}],
    ).to_dict()

    print(f"\n✓ Online features for user {sample_id}:")
    print(features)


# ── MAIN ──────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # ⚠️ Clean old registry (VERY IMPORTANT)
        if os.path.exists("data/registry.db"):
            os.remove("data/registry.db")
        if os.path.exists("data/online_store.db"):
            os.remove("data/online_store.db")

        prepare_data_for_feast()
        setup_feature_store()
        demo_feature_retrieval()

    except Exception as e:
        logger.error(f"Feature store failed: {e}")
        raise e
