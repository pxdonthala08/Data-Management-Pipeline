"""
06_train.py — Recommendation Model Training & Evaluation
Memory-Optimized SVD for Sparse Retailrocket Data
"""

import pandas as pd
import numpy as np
import pickle
import os
import json
import mlflow
import mlflow.sklearn
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.model_selection import train_test_split
import logging

# ── Logging Setup ──────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── MLflow Setup ──────────────────────────────────────────────
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("recomart-recommendations")


# ── TRAIN MODEL ────────────────────────────────────────────────
def train_svd_model(interactions, n_factors=50):
    logger.info("Training SVD model (Sparse Mode)...")

    user_ids = interactions["visitorid"].unique()
    item_ids = interactions["itemid"].unique()

    user_map = {uid: idx for idx, uid in enumerate(user_ids)}
    item_map = {iid: idx for idx, iid in enumerate(item_ids)}

    interactions["user_idx"] = interactions["visitorid"].map(user_map)
    interactions["item_idx"] = interactions["itemid"].map(item_map)

    matrix = csr_matrix(
        (interactions["implicit_rating"].astype(float),
         (interactions["user_idx"], interactions["item_idx"])),
        shape=(len(user_ids), len(item_ids)),
    )

    k_value = min(n_factors, min(matrix.shape) - 1)

    U, sigma, Vt = svds(matrix, k=k_value)

    model_artifact = {
        "U": U,
        "sigma_diag": np.diag(sigma),
        "Vt": Vt,
        "user_map": user_map,
        "item_map": item_map,
    }

    logger.info(f"SVD model trained: {matrix.shape[0]} users × {matrix.shape[1]} items")
    return model_artifact


# ── EVALUATE MODEL ─────────────────────────────────────────────
def evaluate_model(model, interactions, k=10):
    logger.info(f"Evaluating model (K={k})...")

    U = model["U"]
    sigma_diag = model["sigma_diag"]
    Vt = model["Vt"]
    user_map = model["user_map"]
    item_map = model["item_map"]
    item_map_inv = {v: k for k, v in item_map.items()}

    train_df, test_df = train_test_split(interactions, test_size=0.2, random_state=42)

    precisions, recalls, ndcgs = [], [], []

    test_users = test_df["visitorid"].unique()

    # 🔥 Reduce memory + improve speed
    sample_users = np.random.choice(
        test_users,
        size=min(300, len(test_users)),  # reduced from 500 → more stable
        replace=False
    )

    for user in sample_users:
        if user not in user_map:
            continue

        uidx = user_map[user]

        true_items = set(test_df[test_df["visitorid"] == user]["itemid"])
        train_items = set(train_df[train_df["visitorid"] == user]["itemid"])

        if len(true_items) == 0:
            continue

        # Score computation
        user_vector = U[uidx, :].reshape(1, -1)
        scores = np.dot(np.dot(user_vector, sigma_diag), Vt).flatten()

        ranked_indices = np.argsort(scores)[::-1]

        recs = []
        for idx in ranked_indices:
            item_id = item_map_inv[idx]
            if item_id not in train_items:
                recs.append(item_id)
            if len(recs) >= k:
                break

        rec_set = set(recs)
        hits = len(rec_set & true_items)

        precisions.append(hits / k)
        recalls.append(hits / len(true_items))

        # NDCG
        dcg = sum(
            1.0 / np.log2(i + 2)
            for i, item in enumerate(recs)
            if item in true_items
        )
        idcg = sum(
            1.0 / np.log2(i + 2)
            for i in range(min(len(true_items), k))
        )
        ndcgs.append(dcg / idcg if idcg > 0 else 0)

    metrics = {
        f"precision_at_{k}": round(np.mean(precisions), 4),
        f"recall_at_{k}": round(np.mean(recalls), 4),
        f"ndcg_at_{k}": round(np.mean(ndcgs), 4),
    }

    for name, value in metrics.items():
        logger.info(f"  {name}: {value}")

    return metrics


# ── MAIN ─────────────────────────────────────────────
if __name__ == "__main__":

    interactions_path = "data/transformed/interactions.parquet"

    if not os.path.exists(interactions_path):
        logger.error("Interactions file not found! Run transform step first.")
        exit(1)

    interactions = pd.read_parquet(interactions_path)

    with mlflow.start_run(run_name="svd_sparse_optimized"):

        N_FACTORS = 50
        K = 10

        mlflow.log_params({
            "model_type": "SVD_Sparse",
            "n_factors": N_FACTORS,
            "k": K
        })

        model = train_svd_model(interactions, n_factors=N_FACTORS)
        metrics = evaluate_model(model, interactions, k=K)

        # Log metrics
        for name, value in metrics.items():
            mlflow.log_metric(name, value)

        # Save model
        os.makedirs("models", exist_ok=True)
        with open("models/svd_model.pkl", "wb") as f:
            pickle.dump(model, f)

        # Save metrics JSON (IMPORTANT for DVC)
        os.makedirs("reports", exist_ok=True)
        with open("reports/model_metrics.json", "w") as f:
            json.dump(metrics, f, indent=4)

        mlflow.log_artifact("models/svd_model.pkl")

        logger.info("✓ Model trained and evaluation logged to MLflow.")
