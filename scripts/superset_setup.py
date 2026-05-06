"""Configure Apache Superset for the Energy Intelligence platform.

Run once after `make up` to:
  1. Create the Snowflake database connection in Superset
  2. Register the two mart datasets (energy_access_summary, country_kpi)
  3. Create 5 charts from those datasets
  4. Assemble the charts into a published dashboard

Usage:
    uv run python scripts/superset_setup.py

Environment variables (read from .env):
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE,
    SUPERSET_ADMIN_USER, SUPERSET_ADMIN_PASSWORD
"""

import json
import os
import sys
import time
from urllib.parse import quote_plus

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
# dbt dev target prefixes schema with 'staging_', so marts land in staging_marts.
DATASETS = [
    ("STAGING_MARTS", "MART_ENERGY_ACCESS_SUMMARY", "Energy Access Summary (admin-2 × year)"),
    ("STAGING_MARTS", "MART_COUNTRY_KPI", "Country KPIs (country × year)"),
]

DASHBOARD_TITLE = "Energy Intelligence Overview"


# ── helpers ───────────────────────────────────────────────────────────────────


def _metric(col: str, agg: str = "AVG") -> dict:
    return {
        "aggregate": agg,
        "column": {"column_name": col},
        "expressionType": "SIMPLE",
        "label": f"{agg}({col})",
        "hasCustomLabel": False,
        "optionName": f"metric_{agg.lower()}_{col}",
    }


def _count() -> dict:
    return {
        "expressionType": "SQL",
        "sqlExpression": "COUNT(*)",
        "label": "COUNT(*)",
        "hasCustomLabel": True,
        "optionName": "metric_count",
    }


def _year_filter(year: str = "2023") -> dict:
    return {
        "clause": "WHERE",
        "comparator": year,
        "expressionType": "SIMPLE",
        "filterOptionName": f"filter_year_{year}",
        "operator": "==",
        "subject": "YEAR",
        "isExtra": False,
        "isNew": False,
    }


# ── chart definitions ─────────────────────────────────────────────────────────


def _chart_specs(summary_ds_id: int, kpi_ds_id: int) -> list[dict]:
    """Return chart creation payloads — one per chart.

    Column reference:
      mart_energy_access_summary: admin_gid, country_code, admin_name, year,
        electricity_access_pct, mean_nightlight_radiance, dist_to_grid_km,
        total_population, pop_density_km2, energy_access_score, score_tier,
        nightlight_category, population_category, grid_proximity_category
      mart_country_kpi: country_code, year, electricity_access_pct,
        total_population, pop_without_electricity, mean_nightlight_radiance,
        n_power_plants, installed_capacity_mw, n_critical_zones
    """
    return [
        # 1 ── Bar: Avg Energy Access Score by Country (2023)
        {
            "slice_name": "Avg Energy Access Score by Country (2023)",
            "viz_type": "echarts_bar",
            "datasource_id": summary_ds_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_bar",
                    "x_axis": "COUNTRY_CODE",
                    "metrics": [_metric("ENERGY_ACCESS_SCORE")],
                    "groupby": [],
                    "adhoc_filters": [_year_filter("2023")],
                    "row_limit": 50,
                    "orientation": "vertical",
                    "x_axis_title": "Country",
                    "y_axis_title": "Avg Energy Access Score (0-100)",
                    "color_scheme": "supersetColors",
                    "rich_tooltip": True,
                    "show_legend": False,
                }
            ),
        },
        # 2 ── Bar: Electricity Access % by Country (2023)
        {
            "slice_name": "Electricity Access % by Country (2023)",
            "viz_type": "echarts_bar",
            "datasource_id": kpi_ds_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_bar",
                    "x_axis": "COUNTRY_CODE",
                    "metrics": [_metric("ELECTRICITY_ACCESS_PCT")],
                    "groupby": [],
                    "adhoc_filters": [_year_filter("2023")],
                    "row_limit": 50,
                    "orientation": "vertical",
                    "x_axis_title": "Country",
                    "y_axis_title": "Electricity Access (%)",
                    "color_scheme": "supersetColors",
                    "rich_tooltip": True,
                    "show_legend": False,
                }
            ),
        },
        # 3 ── Pie: Score Tier Distribution (2023)
        {
            "slice_name": "Score Tier Distribution (2023)",
            "viz_type": "pie",
            "datasource_id": summary_ds_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "pie",
                    "groupby": ["SCORE_TIER"],
                    "metric": _count(),
                    "adhoc_filters": [_year_filter("2023")],
                    "row_limit": 10,
                    "donut": True,
                    "show_labels": True,
                    "show_legend": True,
                    "color_scheme": "supersetColors",
                }
            ),
        },
        # 4 ── Bar: Critical Zones by Country (2023)
        {
            "slice_name": "Critical Zones by Country (2023)",
            "viz_type": "echarts_bar",
            "datasource_id": kpi_ds_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_bar",
                    "x_axis": "COUNTRY_CODE",
                    "metrics": [_metric("N_CRITICAL_ZONES", "SUM")],
                    "groupby": [],
                    "adhoc_filters": [_year_filter("2023")],
                    "row_limit": 50,
                    "orientation": "vertical",
                    "x_axis_title": "Country",
                    "y_axis_title": "Critical Zones",
                    "color_scheme": "supersetColors",
                    "rich_tooltip": True,
                    "show_legend": False,
                }
            ),
        },
        # 5 ── Table: 25 Lowest-Scoring Regions (2023)
        {
            "slice_name": "25 Lowest-Scoring Regions (2023)",
            "viz_type": "table",
            "datasource_id": summary_ds_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "table",
                    "all_columns": [
                        "COUNTRY_CODE",
                        "ADMIN_NAME",
                        "ENERGY_ACCESS_SCORE",
                        "SCORE_TIER",
                        "ELECTRICITY_ACCESS_PCT",
                        "TOTAL_POPULATION",
                        "DIST_TO_GRID_KM",
                        "MEAN_NIGHTLIGHT_RADIANCE",
                    ],
                    "adhoc_filters": [_year_filter("2023")],
                    "order_by_cols": ['["ENERGY_ACCESS_SCORE", true]'],
                    "row_limit": 25,
                    "include_search": True,
                    "page_length": 25,
                    "color_pn": True,
                }
            ),
        },
    ]


# ── layout builder ────────────────────────────────────────────────────────────


def _build_layout(chart_ids: list[int], chart_names: dict[int, str]) -> dict:
    """Generate a 2-column grid layout with correct parent chains (required by Superset 3.x)."""
    layout: dict = {
        "ROOT_ID": {
            "children": ["GRID_ID"],
            "id": "ROOT_ID",
            "type": "ROOT",
        },
        "GRID_ID": {
            "children": [],
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "type": "GRID",
        },
    }

    for row_idx, i in enumerate(range(0, len(chart_ids), 2)):
        row_key = f"ROW-{row_idx + 1}"
        layout["GRID_ID"]["children"].append(row_key)
        row_children = []

        for j in range(2):
            if i + j >= len(chart_ids):
                break
            cid = chart_ids[i + j]
            col_key = f"CHART-{cid}"
            row_children.append(col_key)
            layout[col_key] = {
                "children": [],
                "id": col_key,
                "meta": {
                    "chartId": cid,
                    "height": 50,
                    "sliceName": chart_names.get(cid, f"Chart {cid}"),
                    "width": 6,
                },
                "parents": ["ROOT_ID", "GRID_ID", row_key],
                "type": "CHART",
            }

        layout[row_key] = {
            "children": row_children,
            "id": row_key,
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW",
        }

    return layout


# ── API helpers ───────────────────────────────────────────────────────────────


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
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Referer": SUPERSET_URL,
        }
    )
    csrf_resp = session.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    csrf_resp.raise_for_status()
    session.headers.update({"X-CSRFToken": csrf_resp.json()["result"]})
    return token


def _get_or_create_database(session: requests.Session) -> int:
    """Return the Superset database ID, creating it if needed."""
    sqlalchemy_uri = (
        f"snowflake://{quote_plus(SNOWFLAKE_USER)}:{quote_plus(SNOWFLAKE_PASSWORD)}"
        f"@{SNOWFLAKE_ACCOUNT}/{SNOWFLAKE_DATABASE}/STAGING_MARTS"
        f"?warehouse={SNOWFLAKE_WAREHOUSE}&role={SNOWFLAKE_ROLE}"
    )

    existing = session.get(f"{SUPERSET_URL}/api/v1/database/", params={"page_size": 100})
    existing.raise_for_status()
    for db in existing.json().get("result", []):
        if db.get("database_name") == "Energy Intelligence (Snowflake)":
            db_id = db["id"]
            print(f"  Database already registered (id={db_id})")
            return db_id

    payload = {
        "database_name": "Energy Intelligence (Snowflake)",
        "sqlalchemy_uri": sqlalchemy_uri,
        "configuration_method": "sqlalchemy_form",
        "expose_in_sqllab": True,
        "allow_run_async": True,
        "allow_dml": False,
        "extra": '{"engine_params":{"connect_args":{"application":"Apache Superset"}}}',
    }
    resp = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if not resp.ok:
        print(f"  ERROR {resp.status_code}: {resp.text}", file=sys.stderr)
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
    existing = session.get(f"{SUPERSET_URL}/api/v1/dataset/", params={"page_size": 100})
    existing.raise_for_status()
    for ds in existing.json().get("result", []):
        if ds.get("table_name") == table:
            ds_id = ds["id"]
            print(f"  Dataset already registered: {table} (id={ds_id})")
            return ds_id

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/dataset/",
        json={"database": db_id, "schema": schema, "table_name": table},
    )
    if not resp.ok:
        print(f"  ERROR {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    ds_id = resp.json()["id"]
    print(f"  Registered dataset: {table} (id={ds_id})")
    return ds_id


def _get_or_create_chart(session: requests.Session, spec: dict) -> int:
    """Return chart ID, creating it if a chart with that name doesn't exist."""
    existing = session.get(f"{SUPERSET_URL}/api/v1/chart/", params={"page_size": 200})
    existing.raise_for_status()
    for chart in existing.json().get("result", []):
        if chart.get("slice_name") == spec["slice_name"]:
            cid = chart["id"]
            print(f"  Chart already exists: {spec['slice_name']} (id={cid})")
            return cid

    resp = session.post(f"{SUPERSET_URL}/api/v1/chart/", json=spec)
    if not resp.ok:
        print(f"  ERROR creating chart '{spec['slice_name']}': {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    cid = resp.json()["id"]
    print(f"  Created chart: {spec['slice_name']} (id={cid})")
    return cid


def _get_or_create_dashboard(
    session: requests.Session,
    chart_ids: list[int],
    chart_names: dict[int, str],
) -> int:
    """Return dashboard ID, creating/updating it with the given charts."""
    existing = session.get(f"{SUPERSET_URL}/api/v1/dashboard/", params={"page_size": 100})
    existing.raise_for_status()
    for dash in existing.json().get("result", []):
        if dash.get("dashboard_title") == DASHBOARD_TITLE:
            did = dash["id"]
            print(f"  Dashboard already exists: '{DASHBOARD_TITLE}' (id={did}) — updating layout")
            _update_dashboard_layout(session, did, chart_ids, chart_names)
            return did

    # Step 1 — create empty dashboard
    resp = session.post(
        f"{SUPERSET_URL}/api/v1/dashboard/",
        json={"dashboard_title": DASHBOARD_TITLE, "published": True},
    )
    if not resp.ok:
        print(f"  ERROR creating dashboard: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    did = resp.json()["id"]
    print(f"  Created dashboard: '{DASHBOARD_TITLE}' (id={did})")

    # Step 2 — set layout with chart components
    _update_dashboard_layout(session, did, chart_ids, chart_names)
    return did


def _link_slices(session: requests.Session, dashboard_id: int, chart_ids: list[int]) -> None:
    """Link charts to a dashboard via the Chart REST API.

    PUT /api/v1/chart/{id} with {"dashboards": [dashboard_id]} creates the
    chart-dashboard relationship that Superset's frontend uses to resolve chart
    components. position_json alone doesn't reliably trigger the DB sync.
    """
    for cid in chart_ids:
        resp = session.put(
            f"{SUPERSET_URL}/api/v1/chart/{cid}",
            json={"dashboards": [dashboard_id]},
        )
        if not resp.ok:
            print(f"  WARN: could not link chart {cid}: {resp.status_code}", file=sys.stderr)
    print(f"  Linked {len(chart_ids)} charts to dashboard")


def _update_dashboard_layout(
    session: requests.Session,
    dashboard_id: int,
    chart_ids: list[int],
    chart_names: dict[int, str],
) -> None:
    position = _build_layout(chart_ids, chart_names)
    resp = session.put(
        f"{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}",
        json={"position_json": json.dumps(position)},
    )
    if not resp.ok:
        print(f"  ERROR updating dashboard layout: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    _link_slices(session, dashboard_id, chart_ids)
    print(f"  Dashboard layout updated ({len(chart_ids)} charts)")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    _wait_for_superset()

    session = requests.Session()
    _get_token(session)
    print("Logged in to Superset.")

    db_id = _get_or_create_database(session)

    ds_ids: dict[str, int] = {}
    for schema, table, verbose in DATASETS:
        ds_ids[table] = _get_or_create_dataset(session, db_id, schema, table, verbose)

    summary_ds_id = ds_ids["MART_ENERGY_ACCESS_SUMMARY"]
    kpi_ds_id = ds_ids["MART_COUNTRY_KPI"]

    print("\nCreating charts ...")
    chart_ids: list[int] = []
    chart_names: dict[int, str] = {}
    for spec in _chart_specs(summary_ds_id, kpi_ds_id):
        cid = _get_or_create_chart(session, spec)
        chart_ids.append(cid)
        chart_names[cid] = spec["slice_name"]

    print("\nCreating dashboard ...")
    dashboard_id = _get_or_create_dashboard(session, chart_ids, chart_names)

    print("\nSetup complete.")
    print(f"Dashboard → {SUPERSET_URL}/superset/dashboard/{dashboard_id}/")


if __name__ == "__main__":
    main()
