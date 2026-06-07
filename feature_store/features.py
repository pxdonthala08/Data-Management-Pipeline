from datetime import timedelta

from feast import Entity, FeatureView, FileSource, Field, ValueType
from feast.types import Int64, Float32


# ── Entities ─────────────────────────────────────────
user_entity = Entity(
    name="visitorid",
    value_type=ValueType.INT64,
)

item_entity = Entity(
    name="itemid",
    value_type=ValueType.INT64,
)


# ── Data Sources ─────────────────────────────────────
# 🔥 IMPORTANT: use ../ because Feast runs inside feature_store folder
user_features_source = FileSource(
    path="../data/transformed/user_features.parquet",
    timestamp_field="event_timestamp",
)

item_features_source = FileSource(
    path="../data/transformed/item_features.parquet",
    timestamp_field="event_timestamp",
)


# ── Feature Views ────────────────────────────────────
user_features_view = FeatureView(
    name="user_features",
    entities=[user_entity],
    ttl=timedelta(days=30),
    source=user_features_source,
    schema=[
        Field(name="total_events", dtype=Int64),
        Field(name="total_views", dtype=Int64),
        Field(name="total_carts", dtype=Int64),
        Field(name="total_transactions", dtype=Int64),
        Field(name="unique_items_viewed", dtype=Int64),
        Field(name="cart_rate", dtype=Float32),
        Field(name="purchase_rate", dtype=Float32),
        Field(name="session_days", dtype=Int64),
    ],
)

item_features_view = FeatureView(
    name="item_features",
    entities=[item_entity],
    ttl=timedelta(days=30),
    source=item_features_source,
    schema=[
        Field(name="total_views", dtype=Int64),
        Field(name="total_purchases", dtype=Int64),
        Field(name="unique_visitors", dtype=Int64),
        Field(name="cart_conversion", dtype=Float32),
        Field(name="purchase_conversion", dtype=Float32),
    ],
)
