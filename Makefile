.PHONY: help install install-dev up down restart logs ps \
        airflow-build airflow-init airflow-shell \
        dbt-run dbt-test dbt-docs \
        lint format typecheck test \
        snowflake-setup fernet-key \
        ingest-world-bank ingest-power-plants ingest-boundaries ingest-all \
        ingest-nightlights ingest-nightlights-local \
        ingest-grid grid-proximity load-grid-proximity \
        ingest-population streamlit

# ─── Config ───────────────────────────────────────────────────────────────────
PYTHON := python3
UV     := uv
DBT    := uv run dbt

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' | sort

# ─── Python environment ───────────────────────────────────────────────────────
install: ## Install production dependencies with uv
	$(UV) sync

install-dev: ## Install all dependencies (incl. dev extras) with uv
	$(UV) sync --extra dev

# ─── Docker ───────────────────────────────────────────────────────────────────
up: ## Start all services (detached)
	docker compose up -d

down: ## Stop containers (keeps volumes — metadata survives)
	docker compose down

down-clean: ## Stop containers AND delete volumes (wipes Superset/Airflow metadata)
	docker compose down -v

restart: ## Restart all services
	docker compose restart

logs: ## Tail logs for all services
	docker compose logs -f

ps: ## Show running containers
	docker compose ps

# ─── Airflow ──────────────────────────────────────────────────────────────────
airflow-build: ## Build the custom Airflow image (installs pipeline deps)
	docker compose build

airflow-init: ## Initialise Airflow DB and create admin user
	docker compose run --rm airflow-init

airflow-shell: ## Open a shell in the Airflow scheduler container
	docker compose exec airflow-scheduler bash

# ─── dbt ─────────────────────────────────────────────────────────────────────
dbt-run: ## Run all dbt models
	cd dbt && set -a && . ../.env && set +a && $(DBT) run

dbt-test: ## Run dbt tests
	cd dbt && set -a && . ../.env && set +a && $(DBT) test

dbt-docs: ## Generate and serve dbt docs on :8085
	cd dbt && set -a && . ../.env && set +a && $(DBT) docs generate && $(DBT) docs serve --port 8085

dbt-deps: ## Install dbt packages
	cd dbt && $(DBT) deps

# ─── Code quality ─────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	$(UV) run ruff check ingestion processing tests

format: ## Auto-format with ruff
	$(UV) run ruff format ingestion processing tests

typecheck: ## Run mypy type checks
	$(UV) run mypy ingestion processing

test: ## Run pytest with coverage
	$(UV) run pytest

# ─── Ingestion ────────────────────────────────────────────────────────────────
ingest-world-bank: ## Ingest World Bank electricity access data → RAW
	$(UV) run python scripts/run_ingestion.py world-bank

ingest-power-plants: ## Ingest WRI Global Power Plant Database → RAW
	$(UV) run python scripts/run_ingestion.py power-plants

ingest-boundaries: ## Ingest GADM admin boundaries → RAW
	$(UV) run python scripts/run_ingestion.py admin-boundaries

ingest-all: ## Run all ingestion pipelines → RAW
	$(UV) run python scripts/run_ingestion.py all

ingest-nightlights: ## Extract VIIRS nightlights via GEE → RAW (requires GEE auth)
	$(UV) run python -m ingestion.nightlights.gee_pipeline

ingest-nightlights-local: ## Process local VIIRS GeoTIFFs → RAW (fallback)
	$(UV) run python -m processing.raster.nightlights

ingest-population: ## Download WorldPop 1km rasters and aggregate to admin-2 → RAW.POPULATION_DENSITY
	$(UV) run python -m ingestion.population.pipeline

ingest-grid: ## Download OSM transmission lines → RAW.GRID_INFRASTRUCTURE
	$(UV) run python -m ingestion.grid.pipeline

grid-proximity: ## Compute distance from admin centroids to nearest grid line
	$(UV) run python -m processing.geospatial.grid_proximity

load-grid-proximity: ## Load data/processed/grid_proximity.parquet → RAW.GRID_PROXIMITY
	$(UV) run python scripts/load_grid_proximity.py

# ─── Streamlit ───────────────────────────────────────────────────────────────
streamlit: ## Run Streamlit dashboard locally (http://localhost:8501)
	$(UV) run streamlit run dashboards/app.py --server.port 8501

# ─── Snowflake ────────────────────────────────────────────────────────────────
snowflake-setup: ## Run Snowflake schema DDL (requires snowsql or Python connector)
	$(UV) run python scripts/snowflake_setup.py

# ─── Utilities ────────────────────────────────────────────────────────────────
fernet-key: ## Generate an Airflow Fernet key
	$(UV) run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

superset-secret: ## Generate a Superset secret key
	openssl rand -base64 42

env-setup: ## Copy .env.example to .env if .env doesn't exist
	@test -f .env || (cp .env.example .env && echo "Created .env — fill in your credentials")
