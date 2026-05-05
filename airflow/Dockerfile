FROM apache/airflow:2.9.1-python3.11

# Install libspatialindex for geopandas sjoin_nearest (rtree backend)
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Step 1 — pipeline data deps
COPY requirements-pipeline.txt /tmp/requirements-pipeline.txt
RUN pip install --no-cache-dir -r /tmp/requirements-pipeline.txt

# Step 2 — dbt-snowflake installed separately so its click/sqlalchemy pins
# don't interfere with the pipeline deps resolver.
RUN pip install --no-cache-dir "dbt-snowflake>=1.9"
