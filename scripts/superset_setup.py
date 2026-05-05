"""Configure Apache Superset for the Energy Intelligence platform.

Run once after `make up` to:
  1. Create the Snowflake database connection in Superset
  2. Register the two mart datasets (energy_access_summary, country_kpi)

Usage:
    uv run python scripts/superset_setup.py

Environment variables (read from .env):
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE,
    SUPERSET_ADMIN_USER, SUPERSET_ADMIN_PASSWORD
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

SUPERSET_URL = os.getenv("SUPERSET_URL", "http://localhost:8088")

SNOWFLAKE_ACCOUNT = os.environ["SNOWFLAKE_ACCOUNT"]
SNOWFLAKE_USER = os.environ["SNOWFLAKE_USER"]
SNOWFLAKE_PASSWORD = os.environ["SNOWFLAKE_PASSWORD"]
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "ENERGY_INTELLIGENCE")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "ENERGY_WH")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")

SUPERSET_USER = os.getenv("SUPERSET_ADMIN_USER", "admin")
SUPERSET_PASSWORD = os.getenv("SUPERSET_ADMIN_PASSWORD", "admin")

# Datasets to register (schema, table_name, verbose_name)
DATASETS = [
    ("MARTS", "MART_ENERGY_ACCESS_SUMMARY", "Energy Access Summary (admin-2 × year)"),
    ("MARTS", "MART_COUNTRY_KPI", "Country KPIs (country × year)"),
]


def _wait_for_superset(timeout: int = 120) -> None:
    print(f"Waiting for Superset at {SUPERSET_URL} ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{SUPERSET_URL}/health", timeout=5)
            if r.status_code == 200:
                print("  Superset is up.")
                return
        except requests.ConnectionError:
            pass
        time.sleep(5)
    print("ERROR: Superset did not become ready in time.", file=sys.stderr)
    sys.exit(1)


def _get_token(session: requests.Session) -> str:
    resp = session.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={
            "username": SUPERSET_USER,
            "password": SUPERSET_PASSWORD,
            "provider": "db",
            "refresh": True,
        },
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    # CSRF token required for mutating requests
    csrf_resp = session.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    csrf_resp.raise_for_status()
    session.headers.update({"X-CSRFToken": csrf_resp.json()["result"]})
    return token


def _get_or_create_database(session: requests.Session) -> int:
    """Return the Superset database ID, creating it if needed."""
    sqlalchemy_uri = (
        f"snowflake://{SNOWFLAKE_USER}:{SNOWFLAKE_PASSWORD}"
        f"@{SNOWFLAKE_ACCOUNT}/{SNOWFLAKE_DATABASE}/MARTS"
        f"?warehouse={SNOWFLAKE_WAREHOUSE}&role={SNOWFLAKE_ROLE}"
    )

    # Check if already exists
    existing = session.get(
        f"{SUPERSET_URL}/api/v1/database/",
        params={
            "q": '{"filters":[{"col":"database_name","opr":"eq","value":"Energy Intelligence (Snowflake)"}]}'
        },
    )
    existing.raise_for_status()
    results = existing.json().get("result", [])
    if results:
        db_id = results[0]["id"]
        print(f"  Database already registered (id={db_id})")
        return db_id

    payload = {
        "database_name": "Energy Intelligence (Snowflake)",
        "sqlalchemy_uri": sqlalchemy_uri,
        "expose_in_sqllab": True,
        "allow_run_async": True,
        "allow_dml": False,
        "extra": '{"engine_params":{"connect_args":{"application":"Apache Superset"}}}',
    }
    resp = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    resp.raise_for_status()
    db_id = resp.json()["id"]
    print(f"  Created database connection (id={db_id})")
    return db_id


def _get_or_create_dataset(
    session: requests.Session,
    db_id: int,
    schema: str,
    table: str,
    verbose_name: str,
) -> int:
    """Return the dataset ID, creating it if needed."""
    existing = session.get(
        f"{SUPERSET_URL}/api/v1/dataset/",
        params={"q": f'{{"filters":[{{"col":"table_name","opr":"eq","value":"{table}"}}]}}'},
    )
    existing.raise_for_status()
    results = existing.json().get("result", [])
    if results:
        ds_id = results[0]["id"]
        print(f"  Dataset already registered: {table} (id={ds_id})")
        return ds_id

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/dataset/",
        json={
            "database": db_id,
            "schema": schema,
            "table_name": table,
            "verbose_map": {"__summary__": verbose_name},
        },
    )
    resp.raise_for_status()
    ds_id = resp.json()["id"]
    print(f"  Registered dataset: {table} (id={ds_id})")
    return ds_id


def main() -> None:
    _wait_for_superset()

    session = requests.Session()
    _get_token(session)
    print("Logged in to Superset.")

    db_id = _get_or_create_database(session)

    for schema, table, verbose in DATASETS:
        _get_or_create_dataset(session, db_id, schema, table, verbose)

    print("\nSuperset setup complete.")
    print(f"Open {SUPERSET_URL} and create charts from the registered datasets.")
    print("See dashboards/README.md for recommended chart configurations.")


if __name__ == "__main__":
    main()
