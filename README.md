# Energy Intelligence Data Platform

[![CI](https://github.com/georgeodero/energy-intelligence-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/georgeodero/energy-intelligence-data-platform/actions/workflows/ci.yml)

An end-to-end data engineering platform that analyses **energy access gaps in the Global South** using satellite imagery, geospatial analysis, and open government datasets.

**MVP countries:** Kenya · Nigeria · India · Tanzania · Rwanda · Ivory Coast · Pakistan

---

## What This Platform Does

- Ingests electricity access statistics from the World Bank SE4ALL API
- Downloads VIIRS nighttime light composites from Google Earth Engine
- Computes each admin-2 region's distance to the nearest transmission line (OSM)
- Overlays WorldPop population density for demand pressure
- Calculates a composite **Energy Access Score (0–100)** per admin region per year
- Surfaces "critical" zones (score ≥ 75) to guide energy investment decisions
- Visualises results in an Apache Superset choropleth dashboard

---

## Architecture

```
External Sources                  Ingestion (Python)           Snowflake
────────────────                  ──────────────────           ──────────────────
World Bank SE4ALL  ─────────────► world_bank/pipeline.py  ──► RAW schema
WRI Power Plants   ─────────────► power_plants/pipeline.py──►
GADM Boundaries    ─────────────► admin_boundaries/        ──►
VIIRS (via GEE)    ─────────────► nightlights/gee_pipeline ──►       │
OSM (Overpass)     ─────────────► grid/pipeline.py         ──►       │
WorldPop           ─────────────► (population_density)     ──►       │
                                                                      │
                   Processing (GeoPandas)                             │
                   ──────────────────────                             │
                   grid_proximity.py  ─────────────────────►RAW.GRID_PROXIMITY
                                                                      │
                                                             dbt (staging → intermediate → marts)
                                                                      │
                             Apache Airflow 2.9                       │
                             (dag_energy_pipeline)──────────────────► │
                                                                      ▼
                                                            MARTS.MART_ENERGY_ACCESS_SUMMARY
                                                            MARTS.MART_COUNTRY_KPI
                                                                      │
                                                            Apache Superset 3.1
                                                            (choropleth + KPI dashboard)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Cloud warehouse | Snowflake |
| Transformations | dbt-snowflake 1.9 |
| Orchestration | Apache Airflow 2.9 (LocalExecutor) |
| Dashboards | Apache Superset 3.1 |
| Geospatial | GeoPandas · Rasterio · Shapely · PyProj |
| Satellite data | Google Earth Engine API (VIIRS Black Marble) |
| Language | Python 3.11 |
| Packaging | uv + pyproject.toml |
| Containers | Docker Compose |
| CI/CD | GitHub Actions |

---

## Energy Access Score

Each admin-2 region receives a composite score (0–100, **higher = more underserved**):

```
Energy Access Score =
    (100 − electricity_access_pct)            × 0.35   [access gap]
  + max(0, 10 − mean_radiance) / 10 × 100    × 0.25   [nightlight darkness]
  + min(pop_density_km2, 100) / 100 × 100     × 0.20   [population demand]
  + min(dist_to_grid_km, 100) / 100 × 100     × 0.20   [grid distance]
```

| Tier | Score | Meaning |
|---|---|---|
| **Critical** | 75–100 | Highest priority for intervention |
| **High** | 50–74 | Significant access gap |
| **Medium** | 25–49 | Partial access |
| **Low** | 0–24 | Near full access |

---

## Snowflake Schema Design

```
ENERGY_INTELLIGENCE (database)
│
├── RAW          — raw source data (all VARCHAR, no transforms)
├── STAGING      — typed dbt views (stg_*)
├── INTERMEDIATE — joined dbt views (int_*)
└── MARTS        — analytics tables (mart_*)
```

## dbt DAG

```
stg_nightlights ─────────────────────────────────┐
stg_population_density ──────────────────────────┤
stg_admin_boundaries ────────────────────────────┴──► int_admin_energy_metrics ──► mart_energy_access_summary
source(raw, grid_proximity) ──────────────────────────────────────────────────────────────┘

stg_electricity_access ──────────────────────────────────────────────────────────────────► mart_country_kpi
stg_power_plants ────────────────────────────────────────────────────────────────────────►
```

---

## Airflow Pipeline

Master DAG (`energy_intelligence_pipeline`, daily 02:00 UTC):

```
┌─ ingest_world_bank ──────────────────────────────────────────────────┐
├─ ingest_power_plants ────────────────────────────────────────────────┤
├─ ingest_admin_boundaries ──────────────────┐                         │
├─ ingest_nightlights ─────────────────────── │ ───────────────────────┼──► dbt_deps ─► dbt_run ─► dbt_test
└─ ingest_grid ──────────────────────────────┤                         │
                                             ▼                         │
                                 compute_grid_proximity                 │
                                             │                         │
                                             ▼                         │
                                 load_grid_proximity ───────────────────┘
```

All Snowflake loads use **MERGE** (upsert) — re-running any task never creates duplicate rows.

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x
- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- A free [Snowflake trial account](https://signup.snowflake.com/)
- A [Google Earth Engine](https://earthengine.google.com/) service account (for nightlights)

### 1. Clone and configure

```bash
git clone https://github.com/georgeodero/energy-intelligence-data-platform.git
cd energy-intelligence-data-platform
cp .env.example .env
```

Edit `.env` with your credentials. Generate the required secret keys:

```bash
make fernet-key      # paste into AIRFLOW_FERNET_KEY
make superset-secret # paste into SUPERSET_SECRET_KEY
```

### 2. Bootstrap Snowflake

```bash
make install
make snowflake-setup
```

### 3. Run ingestion pipelines

```bash
make ingest-world-bank      # World Bank electricity access
make ingest-power-plants    # WRI power plant database
make ingest-boundaries      # GADM admin boundaries
make ingest-nightlights     # VIIRS via Google Earth Engine
make ingest-grid            # OSM transmission lines
make grid-proximity         # compute admin-2 → grid distances
make load-grid-proximity    # load distances to Snowflake
```

### 4. Run dbt models

```bash
make dbt-deps
make dbt-run    # materialises all 9 models
make dbt-test   # runs 45 data quality tests
```

### 5. Start the full stack

```bash
make airflow-build   # build custom Airflow image (first time only)
make up
make airflow-init    # first time only
```

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | `AIRFLOW_ADMIN_USER` / `_PASSWORD` in `.env` |
| Superset | http://localhost:8088 | `SUPERSET_ADMIN_USER` / `_PASSWORD` in `.env` |

### 6. Configure Superset

```bash
uv run python scripts/superset_setup.py
```

Open Superset and build charts. See [dashboards/README.md](dashboards/README.md) for chart-by-chart instructions.

---

## Project Structure

```
energy-intelligence-data-platform/
│
├── .github/workflows/ci.yml         # lint · typecheck · pytest · dbt compile
│
├── airflow/
│   ├── Dockerfile                   # extends apache/airflow with pipeline deps
│   ├── requirements.txt
│   └── dags/
│       ├── dag_energy_pipeline.py   # master orchestration DAG
│       ├── dag_dbt_run.py
│       └── dag_world_bank_ingestion.py
│
├── dbt/
│   ├── models/
│   │   ├── staging/                 # stg_* + _sources.yml + _models.yml
│   │   ├── intermediate/            # int_admin_energy_metrics
│   │   └── marts/                   # mart_energy_access_summary · mart_country_kpi
│   ├── profiles.yml                 # env-var driven Snowflake connection
│   └── packages.yml
│
├── ingestion/
│   ├── _snowflake.py                # upsert_dataframe (MERGE-based, idempotent)
│   ├── world_bank/pipeline.py
│   ├── power_plants/pipeline.py
│   ├── admin_boundaries/pipeline.py
│   ├── nightlights/gee_pipeline.py
│   └── grid/pipeline.py
│
├── processing/
│   ├── geospatial/grid_proximity.py # sjoin_nearest → dist_to_grid_km
│   └── raster/zonal_stats.py
│
├── snowflake/schemas/               # DDL: 00_create_schemas · 01_raw · 02_marts
├── scripts/
│   ├── snowflake_setup.py
│   ├── load_grid_proximity.py
│   └── superset_setup.py           # REST API setup for Superset
│
├── dashboards/README.md            # chart-by-chart Superset setup guide
├── tests/                          # 21 unit tests (no Snowflake required)
├── docker-compose.yml
├── pyproject.toml
└── Makefile
```

---

## Data Sources

| Dataset | Source | Grain | Update freq |
|---|---|---|---|
| Electricity access % | World Bank SE4ALL API | country × year | Annual |
| Power plants | WRI GPPD v1.3 | plant | Periodic |
| Admin boundaries | GADM 4.1 | admin-2 polygon | Periodic |
| Nighttime lights | VIIRS Black Marble via GEE | admin-2 × year | Annual |
| Population density | WorldPop | admin-2 × year | Annual |
| Grid infrastructure | OSM Overpass API | line geometry | Continuous |
| Grid proximity | Computed (GeoPandas) | admin-2 | On demand |

---

## Development

```bash
make help            # list all targets
make lint            # ruff check
make format          # ruff format
make typecheck       # mypy
make test            # pytest (unit, no network required)
make dbt-docs        # serve dbt lineage docs at :8085
```
