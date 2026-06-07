import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 🔹 Update if needed
DB_URL = "postgresql://recomart_admin:recomartadmin@recomart-db-instance.cle0w60wm8ki.ap-south-1.rds.amazonaws.com:5432/recomart_db"


# ── USER FEATURES ──────────────────────────────────────
def create_user_features(events):
    logger.info("Creating user features...")

    events["is_view"] = (events["event"] == "view").astype(int)
    events["is_cart"] = (events["event"] == "addtocart").astype(int)
    events["is_transaction"] = (events["event"] == "transaction").astype(int)

    user_features = events.groupby("visitorid").agg(
        total_events=("event", "count"),
        total_views=("is_view", "sum"),
        total_carts=("is_cart", "sum"),
        total_transactions=("is_transaction", "sum"),
        unique_items_viewed=("itemid", "nunique"),
        first_event=("datetime", "min"),
        last_event=("datetime", "max"),
    ).reset_index()

    views_safe = user_features["total_views"].replace(0, 1)
    user_features["cart_rate"] = (user_features["total_carts"] / views_safe).round(4)
    user_features["purchase_rate"] = (user_features["total_transactions"] / views_safe).round(4)

    user_features["session_days"] = (
        (user_features["last_event"] - user_features["first_event"]).dt.days
    ).fillna(0)

    logger.info(f"User features: {user_features.shape}")
    return user_features


# ── ITEM FEATURES ──────────────────────────────────────
def create_item_features(events, item_props):
    logger.info("Creating item features...")

    events["is_view"] = (events["event"] == "view").astype(int)
    events["is_cart"] = (events["event"] == "addtocart").astype(int)
    events["is_transaction"] = (events["event"] == "transaction").astype(int)

    item_features = events.groupby("itemid").agg(
        total_views=("is_view", "sum"),
        total_carts=("is_cart", "sum"),
        total_purchases=("is_transaction", "sum"),
        unique_visitors=("visitorid", "nunique"),
    ).reset_index()

    views_safe = item_features["total_views"].replace(0, 1)
    item_features["cart_conversion"] = (item_features["total_carts"] / views_safe).round(4)
    item_features["purchase_conversion"] = (item_features["total_purchases"] / views_safe).round(4)

    if item_props is not None and len(item_props) > 0:
        item_features = item_features.merge(item_props, on="itemid", how="left")

    logger.info(f"Item features: {item_features.shape}")
    return item_features


# ── USER-ITEM INTERACTIONS ─────────────────────────────
def create_user_item_matrix(events):
    logger.info("Creating user-item interaction matrix...")

    event_weights = {"view": 1, "addtocart": 2, "transaction": 3}
    events["weight"] = events["event"].map(event_weights)

    interactions = (
        events.groupby(["visitorid", "itemid"])["weight"]
        .max()
        .reset_index()
        .rename(columns={"weight": "implicit_rating"})
    )

    logger.info(f"Interaction matrix: {len(interactions):,} rows")
    return interactions


# ── CO-OCCURRENCE ─────────────────────────────────────
def create_cooccurrence_features(events, top_n=50):
    logger.info(f"Creating co-occurrence features (Top {top_n} items)...")

    views = events[events["event"] == "view"][["visitorid", "itemid"]]

    top_items = views["itemid"].value_counts().head(top_n).index
    views = views[views["itemid"].isin(top_items)]

    cooccur = views.merge(views, on="visitorid")
    cooccur = cooccur[cooccur["itemid_x"] < cooccur["itemid_y"]]

    cooccur_counts = (
        cooccur.groupby(["itemid_x", "itemid_y"])
        .size()
        .reset_index(name="co_view_count")
    )

    cooccur_counts.rename(columns={
        "itemid_x": "itemid_a",
        "itemid_y": "itemid_b"
    }, inplace=True)

    logger.info(f"Co-occurrence pairs: {len(cooccur_counts):,}")
    return cooccur_counts


# ── STORE TO DATABASE ─────────────────────────────────
def store_to_warehouse(engine, **dfs):
    for name, df in dfs.items():
        df.to_sql(name, engine, if_exists="replace", index=False)
        logger.info(f"Stored {name}: {len(df):,} rows")


# ── MAIN ──────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # Load prepared data
        events = pd.read_parquet("data/prepared/events_cleaned.parquet")
        item_props = pd.read_parquet("data/prepared/item_features.parquet")

        # Optional safety sampling (can remove if you want full run)
        if len(events) > 200000:
            logger.info("Large dataset, sampling 200k rows for stability.")
            events = events.head(200000)

        # Create features
        user_feats = create_user_features(events)
        item_feats = create_item_features(events, item_props)
        interactions = create_user_item_matrix(events)
        cooccur = create_cooccurrence_features(events)

        # Save locally
        os.makedirs("data/transformed", exist_ok=True)
        user_feats.to_parquet("data/transformed/user_features.parquet", index=False)
        item_feats.to_parquet("data/transformed/item_features.parquet", index=False)
        interactions.to_parquet("data/transformed/interactions.parquet", index=False)
        cooccur.to_parquet("data/transformed/cooccurrence.parquet", index=False)

        # Store in PostgreSQL
        engine = create_engine(DB_URL)
        store_to_warehouse(
            engine,
            user_features=user_feats,
            item_features=item_feats,
            user_item_interactions=interactions,
            item_cooccurrence=cooccur,
        )

        logger.info("All features stored in warehouse")

    except Exception as e:
        logger.error(f"Transformation failed: {e}")
        raise e
