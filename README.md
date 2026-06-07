# RecoMart: End-to-End Data Management & MLOps Pipeline for E-Commerce Recommendation Systems

This repository contains the complete design and implementation of a production-ready, end-to-end data management and machine learning pipeline for **RecoMart**, an e-commerce platform seeking to deliver personalized product recommendations to its users. 

---

## System Architecture & Workflow
The entire architecture is modular, resilient by design, and fully decoupled. It automates the progression from multi-source raw data ingestion to online/offline feature serving and model tracking.

<img width="1850" height="910" alt="image" src="https://github.com/user-attachments/assets/faa4d8f1-21d3-4b0d-8d42-5d1b2a194d88" />


---

## 🛠️ Tech Stack & MLOps Core Components
* **Orchestration:** Apache Airflow (DAG topology with isolated environments).
* **Storage & Data Lake:** AWS S3 (Raw ingestion and DVC cache storage).
* **Data Validation:** Custom automated schema and metric validator.
* **Feature Engineering & Warehousing:** PostgreSQL (AWS RDS) & Pandas/Apache Parquet.
* **Feature Store:** Feast (Online/Offline store synchronization with point-in-time correctness).
* **Data Versioning:** DVC (Data Version Control with S3 remote caching).
* **Core Recommendation Engine:** SciPy (Sparse Latent SVD Matrix Factorization).
* **Experiment Tracking:** MLflow (Hyperparameter logging, performance metrics, and artifact registry).

---

## Repository Directory Structure
To set up this repository locally, organize your source files according to the following production directory layout:


recomart/
├── .dvc/                       # Data Version Control internal configurations
├── airflow/
│   └── dags/
│       └── recomart_pipeline_dag.py  # Apache Airflow DAG defining task execution order
├── feature_store/
│   ├── feature_store.yaml      # Feast provider configuration file
│   └── features.py             # Feast entity definition and Feature View declarations
├── models/
│   └── svd_model.pkl           # Serialized production model artifact (tracked by DVC)
├── reports/
│   ├── plots/                  # Automated EDA visual exports (.png format)
│   ├── data_quality_report.json # Continuous validation report output
│   └── model_metrics.json      # Evaluation breakdown tracking file
├── schema.sql                  # PostgreSQL structural setup for data warehousing
├── dvc.yaml                    # DVC multi-stage pipeline pipeline specification
└── scripts/                    # Decoupled component scripts executed by handlers
    ├── 01_ingest.py            # Multi-source data capture handler
    ├── 02_validate.py          # Schema mapping and criteria testing script
    ├── 03_prepare.py           # Deduplication, filtering, and timestamp compiler
    ├── 04_transform.py        # Behavioral matrices builder and PostgreSQL sync
    ├── 05_feature_store.py     # Feature materialization coordinator
    └── 06_train.py             # Model training matrix mapping & MLflow engine


## Step-by-Step Pipeline Implementation Details

### 1. Data Ingestion (`scripts/01_ingest.py`)
* **Sources:** Simultaneously pulls clickstream data (`events.csv`), product metadata (`item_properties.csv`), category hierarchies (`category_tree.csv`), and micro-service mock REST APIs (capturing popularity and text sentiment).
* **Engineering Resilience:** Built with automated exponential backoff retries (up to 3 attempts: 1s → 2s → 4s) to handle transient network or API failures without stalling.
* **Symlink Management:** Maintains a local `latest` symlink pointing to the freshest timestamped folder, abstracting hardcoded dates away from downstream jobs.
* **Cloud Sync:** Syncs the structured local file path tree straight to the centralized AWS data lake: `s3://recomart-data-lake-001/raw/`.

### 2. Automated Data Validation (`scripts/02_validate.py`)
* **Checks:** Performs automatic runtime evaluation of column schemas, datatypes, exact-row duplicates, null rates, and anomalies like future-dated timestamps.
* **Alert Matrix:** Employs a three-level logging evaluation framework (`✓ PASS`, `⚠ WARN`, `✗ FAIL`). Expected sparse dimensions (like missing transaction values on non-purchase actions) generate `WARN` flags instead of braking tasks.
* **Outputs:** Writes a structured JSON quality audit ledger to `reports/data_quality_report.json` on each execution loop.

### 3. Data Preparation & Exploration (`scripts/03_prepare.py`)
* **Data Sanitation:** Drops duplicate rows and filters out "low-signal" users (users with only a single recorded web interaction) to reduce noise in collaborative filter dimensions.
* **Temporal Transformations:** Deconstructs standard UNIX clickstream logs into structured variables like `date`, `hour`, and `day_of_week`.
* **Output:** Saves highly structured binary files to `data/prepared/events_cleaned.parquet` and automatically exports analytical trend plots.

### 4. Behavioral Feature Transformation (`scripts/04_transform.py`)
* **Aggregation:** Compiles granular user summaries (total interactions, click-to-cart rate, conversion velocity) and maps out individual store item metrics.
* **Implicit Intent Weights:** Transforms implicit actions into structured values to mimic true preferences: `view = 1`, `addtocart = 2`, and `transaction = 3`. The script registers the highest relative weight per distinct user-item pairing.
* **Warehouse Sinking:** Opens database connections to update live analytics records across the relational warehouse schemas: `user_features`, `item_features`, `user_item_interactions`, and `item_cooccurrence`.

### 5. Feast Feature Store Materialization (`scripts/05_feature_store.py`)
* **Consistency:** Eliminates training-serving skew by serving as the unified source of truth for both downstream analytical fitting and production lookups.
* **Point-in-Time Correctness:** Enforces a 30-day strict Time-to-Live (TTL) constraint to prevent feature leakage from historical horizons during retrieval.
* **Stores:** Materializes feature views from Parquet files into a localized runtime engine (`data/online_store.db`) to enable ultra-low latency inference responses.

### 6. Model Training & MLflow Tracking (`scripts/06_train.py`)
* **Algorithm:** Implements a Latent Singular Value Decomposition (SVD) algorithm tailored for sparse matrix systems via `scipy.sparse.linalg`.
* **Sparsity Constraints:** Safely maps and factors massive implicit grids showing a baseline interaction sparsity of **99.995%** (density of **0.0045%** across 2.9B potential intersections).
* **Tracking Server:** Interfaces with MLflow to continuously capture hyperparameter assignments (e.g., `n_factors = 50`), performance metrics, and registers the final pickle binaries (`models/svd_model.pkl`).

### 7. Pipeline Orchestration (Apache Airflow)
* **DAG Blueprint:** Chained linearly with the upstream/downstream `>>` binding operator inside `recomart_pipeline_dag.py` to maintain step dependencies.
* **Error Resilience:** Individual nodes are isolated inside dedicated Python virtual environments (`venv`) and run on independent `@daily` loop routines with single-retry fallbacks. If a late-stage task fails, upstream ingestion and validation data states remain completely intact, saving significant processing time and cost.

---

## Model Performance & Evaluation Metrics

The pipeline evaluates recommendations using rank-aware parameters over a random 80/20 train/test evaluation framework:

| Metric | Pipeline Value | Operational Analysis |
| :--- | :--- | :--- |
| **Precision@10** | `0.0093` | Low baseline precision is typical for e-commerce contexts due to catalog vastness and unrecorded user interests. |
| **Recall@10** | `0.0772` | Demonstrates solid coverage, retrieving a meaningful ratio of total relevant baseline targets. |
| **NDCG@10** | `0.0512` | Confirms reliable sorting quality; the engine positions high-interest matches at premium slots within consumer view panels. |
