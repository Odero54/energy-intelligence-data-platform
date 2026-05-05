"""
DAG: dbt full run (standalone)
Schedule: daily 03:00 UTC — runs after all ingestion DAGs.

For the end-to-end orchestrated run use dag_energy_pipeline instead.
This DAG exists for manual dbt refreshes and isolated testing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator

from airflow import DAG

default_args = {
    "owner": "energy-intelligence",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

DBT_DIR = "/opt/airflow/dbt"
# dbt binary installed by pip --user lands in ~/.local/bin
DBT_CMD = "export PATH=$PATH:/home/airflow/.local/bin && dbt"

with DAG(
    dag_id="dbt_full_run",
    default_args=default_args,
    description="Run all dbt models (staging → intermediate → marts) then test",
    schedule_interval="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "transformation"],
) as dag:
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_CMD} deps --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{DBT_CMD} run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --target prod",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT_CMD} test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --target prod",
    )

    dbt_deps >> dbt_run >> dbt_test
