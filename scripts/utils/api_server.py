"""Mock REST API serving product popularity scores."""

from flask import Flask, jsonify
import pandas as pd
import numpy as np
import os
import glob

app = Flask(__name__)


# ── Helper: Get Latest Events File ─────────────────────────────
def get_latest_events_path():
    base_path = "data/raw/clickstream"

    dirs = [
        d for d in glob.glob(os.path.join(base_path, "*"))
        if os.path.isdir(d) and "latest" not in d
    ]

    if not dirs:
        return None

    latest_dir = sorted(dirs)[-1]
    return os.path.join(latest_dir, "events.csv")


# ── Health Check Endpoint ─────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ── Main API Endpoint ─────────────────────────────────────────
@app.route("/api/products", methods=["GET"])
def get_products():
    print("📡 API called: /api/products")

    events_path = get_latest_events_path()

    if not events_path or not os.path.exists(events_path):
        return jsonify({"error": "No events data found. Run ingestion first."}), 404

    try:
        # Load only required columns (memory optimized)
        events = pd.read_csv(events_path, usecols=["itemid", "event"])

        # Use only meaningful interaction (views)
        events = events[events["event"] == "view"]

        # Compute popularity
        popularity = (
            events.groupby("itemid")
            .size()
            .reset_index(name="view_count")
        )

        # Normalize score
        popularity["popularity_score"] = (
            popularity["view_count"] / popularity["view_count"].max()
        ).round(4)

        # Simulate sentiment
        np.random.seed(42)
        popularity["avg_sentiment"] = np.random.uniform(
            0.3, 0.95, len(popularity)
        ).round(3)

        # Limit response size
        response = popularity.head(5000).to_dict(orient="records")

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Run Server ────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Starting Mock API Server on port 5001...")
    app.run(host="0.0.0.0", port=5001)
