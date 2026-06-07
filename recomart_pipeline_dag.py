from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/home/ubuntu/recomart"
VENV_PATH = f"{PROJECT_DIR}/venv/bin/activate"

BASH_PREFIX = f"cd {PROJECT_DIR} && source {VENV_PATH} && export PYTHONPATH=$PYTHONPATH:. && "

default_args = {
    "owner": "recomart-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="recomart_recommendation_pipeline",
    default_args=default_args,
    description="RecoMart Pipeline",
    schedule="@daily",
    start_date=datetime(2026, 4, 1),
    catchup=False,
) as dag:

    ingest = BashOperator(
        task_id="data_ingestion",
        bash_command=f"{BASH_PREFIX} python scripts/01_ingest.py",
    )

    validate = BashOperator(
        task_id="data_validation",
        bash_command=f"{BASH_PREFIX} python scripts/02_validate.py",
    )

    prepare = BashOperator(
        task_id="data_preparation",
        bash_command=f"{BASH_PREFIX} python scripts/03_prepare.py",
    )

    transform = BashOperator(
        task_id="feature_engineering",
        bash_command=f"{BASH_PREFIX} python scripts/04_transform.py",
    )

    feature_store = BashOperator(
        task_id="feature_store_update",
        bash_command=f"{BASH_PREFIX} python scripts/05_feature_store.py",
    )

    train = BashOperator(
        task_id="model_training",
        bash_command=f"{BASH_PREFIX} python scripts/06_train.py",
    )


    ingest >> validate >> prepare >> transform >> feature_store >> train
