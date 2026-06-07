-- RecoMart Data Warehouse Schema

CREATE TABLE IF NOT EXISTS user_features (
    visitorid BIGINT PRIMARY KEY,
    total_events INT,
    total_views INT,
    total_carts INT,
    total_transactions INT,
    unique_items_viewed INT,
    first_event TIMESTAMP,
    last_event TIMESTAMP,
    cart_rate FLOAT,
    purchase_rate FLOAT,
    session_days INT
);

CREATE TABLE IF NOT EXISTS item_features (
    itemid BIGINT PRIMARY KEY,
    total_views INT,
    total_carts INT,
    total_purchases INT,
    unique_visitors INT,
    cart_conversion FLOAT,
    purchase_conversion FLOAT,
    categoryid VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS user_item_interactions (
    visitorid BIGINT,
    itemid BIGINT,
    implicit_rating INT,
    PRIMARY KEY (visitorid, itemid)
);

CREATE TABLE IF NOT EXISTS item_cooccurrence (
    itemid_a BIGINT,
    itemid_b BIGINT,
    co_view_count INT,
    PRIMARY KEY (itemid_a, itemid_b)
);