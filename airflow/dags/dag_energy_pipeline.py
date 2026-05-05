"""
DAG: Energy Intelligence — end-to-end pipeline
Schedule: daily 02:00 UTC

Pipeline graph
==============

  ┌─ ingest_world_bank ──────────────────────────────────────────────────┐
  ├─ ingest_power_plants ────────────────────────────────────────────────┤
  ├─ ingest_admin_boundaries ──────────────────┐                         │
  ├─ ingest_nightlights ────────────────────────│────────────────────────┼──► dbt_deps ─► dbt_run ─► dbt_test
  └─ ingest_grid ──────────────────────────────┤                         │
                                               ▼                         │
                                   compute_grid_proximity                 │
                                               │                         │
                                               ▼                         │
                                   load_grid_proximity ───────────────────┘

Notes
-----
- Ingestion tasks run in parallel (no inter-dependency).
- compute_grid_proximity needs admin_boundaries + grid to succeed first.
- dbt tasks wait for all remaining ingestion + load_grid_proximity (trigger_rule=all_done
  so a GEE failure doesn't block the transformation layer).
- dbt deps/run/test are sequential.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from airflow import DAG

# ── Constants ──────────────────────────────────────────────────────────────────
DBT_DIR = "/opt/airflow/dbt"
DBT_CMD = "export PATH=$PATH:/home/airflow/.local/bin && dbt"
DATA_DIR = "/opt/airflow/data"

# ── Default task arguments ─────────────────────────────────────────────────────
default_args = {
    "owner": "energy-intelligence",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}


# ── Callable helpers (imports deferred so DAG parses without heavy libs) ───────


def _ingest_world_bank(**_):
    from ingestion.world_bank.pipeline import run

    run()


def _ingest_power_plants(**_):
    from ingestion.power_plants.pipeline import run

    run()


def _ingest_admin_boundaries(**_):
    from ingestion.admin_boundaries.pipeline import run

    run()


def _ingest_nightlights(**_):
    """GEE-based nightlights ingestion. Requires GEE credentials in environment."""
    from ingestion.nightlights.gee_pipeline import run

    run()


def _ingest_grid(**_):
    from ingestion.grid.pipeline import run

    run()


def _ingest_population(**_):
    """WorldPop 1km raster download + admin-2 zonal aggregation."""
    from ingestion.population.pipeline import run

    run()


def _compute_grid_proximity(**_):
    from processing.geospatial.grid_proximity import run

    run()


def _load_grid_proximity(**_):
    from pathlib import Path

    import pandas as pd

    from ingestion._snowflake import upsert_dataframe

    parquet_path = Path(DATA_DIR) / "processed" / "grid_proximity.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Grid proximity parquet not found at {parquet_path}. "
            "Ensure compute_grid_proximity task completed successfully."
        )
    df = pd.read_parquet(parquet_path)
    n_ins, n_upd = upsert_dataframe(df, "GRID_PROXIMITY", merge_keys=["admin_gid"])
    print(f"Upserted → RAW.GRID_PROXIMITY: {n_ins} inserted, {n_upd} updated")


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="energy_intelligence_pipeline",
    default_args=default_args,
    description="End-to-end pipeline: ingest → process → dbt transform",
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["orchestration", "energy_intelligence"],
) as dag:
    # ── Stage 1: Parallel ingestion ────────────────────────────────────────────
    with TaskGroup(
        "ingestion", tooltip="Raw data ingestion to Snowflake RAW schema"
    ) as ingestion_group:
        ingest_wb = PythonOperator(
            task_id="world_bank",
            python_callable=_ingest_world_bank,
            retries=2,
        )

        ingest_pp = PythonOperator(
            task_id="power_plants",
            python_callable=_ingest_power_plants,
            retries=2,
        )

        ingest_ab = PythonOperator(
            task_id="admin_boundaries",
            python_callable=_ingest_admin_boundaries,
            retries=1,
        )

        ingest_nl = PythonOperator(
            task_id="nightlights",
            python_callable=_ingest_nightlights,
            retries=1,
            # GEE compute can be slow — extend timeout to 2 hours
            execution_timeout=timedelta(hours=2),
        )

        ingest_gi = PythonOperator(
            task_id="grid_infrastructure",
            python_callable=_ingest_grid,
            retries=2,
            # OSM Overpass can be slow on large countries
            execution_timeout=timedelta(hours=1),
        )

        ingest_pop = PythonOperator(
            task_id="population",
            python_callable=_ingest_population,
            retries=1,
            # Large raster downloads (India ~300MB) — allow 3 hours
            execution_timeout=timedelta(hours=3),
        )

    # ── Stage 2: Grid proximity (needs boundaries + grid lines) ───────────────
    compute_gp = PythonOperator(
        task_id="compute_grid_proximity",
        python_callable=_compute_grid_proximity,
        execution_timeout=timedelta(minutes=30),
    )

    load_gp = PythonOperator(
        task_id="load_grid_proximity",
        python_callable=_load_grid_proximity,
    )

    # ── Stage 3: dbt transformation ───────────────────────────────────────────
    with TaskGroup(
        "transformation", tooltip="dbt staging → intermediate → marts"
    ) as transform_group:
        dbt_deps = BashOperator(
            task_id="dbt_deps",
            bash_command=f"{DBT_CMD} deps --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        )

        dbt_run = BashOperator(
            task_id="dbt_run",
            bash_command=f"{DBT_CMD} run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --target prod",
            execution_timeout=timedelta(minutes=30),
        )

        dbt_test = BashOperator(
            task_id="dbt_test",
            bash_command=f"{DBT_CMD} test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --target prod",
            execution_timeout=timedelta(minutes=20),
        )

        dbt_deps >> dbt_run >> dbt_test

    # ── Wire task dependencies ─────────────────────────────────────────────────

    # Grid proximity needs boundaries and grid lines to be loaded first
    [ingest_ab, ingest_gi] >> compute_gp >> load_gp

    # dbt waits for all ingestion tasks + grid proximity load.
    # trigger_rule=all_done means dbt still runs even if nightlights
    # or other optional tasks fail (e.g., GEE not configured).
    [ingest_wb, ingest_pp, ingest_nl, ingest_pop, load_gp] >> dbt_deps
    dbt_deps.trigger_rule = TriggerRule.ALL_DONE
