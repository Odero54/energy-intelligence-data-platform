"""
DAG: World Bank electricity access ingestion
Schedule: weekly (Sunday 01:00 UTC)

Standalone DAG for on-demand or scheduled refreshes of the World Bank
SE4ALL electricity access dataset independent of the full pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.operators.python import PythonOperator

from airflow import DAG

default_args = {
    "owner": "energy-intelligence",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _run(**_context):
    from ingestion.world_bank.pipeline import run

    run()


with DAG(
    dag_id="world_bank_electricity_access_ingestion",
    default_args=default_args,
    description="Fetch World Bank SE4ALL electricity access data → RAW.WORLD_BANK_ELECTRICITY_ACCESS",
    schedule_interval="0 1 * * 0",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "world_bank", "electricity_access"],
) as dag:
    PythonOperator(
        task_id="fetch_world_bank_electricity_access",
        python_callable=_run,
    )
