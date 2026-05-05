FROM apache/airflow:2.9.1-python3.11

# Install libspatialindex for geopandas sjoin_nearest (rtree backend)
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Install project pipeline dependencies as airflow user
USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt
