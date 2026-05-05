# Energy Intelligence Data Platform

## Role

You are a **Senior Data Engineer, Geospatial Data Engineer, and Analytics Engineer** tasked with building a **portfolio-ready end-to-end Energy Intelligence Platform** in **1 week**.

Your goal is to help me build a real-world project that analyzes **energy access gaps in the Global South** using traditional energy datasets and geospatial intelligence.

This platform should identify:

* Regions with low electricity access
* Areas far from national grids
* Regions with low nighttime light intensity
* High population areas underserved by electricity infrastructure
* Renewable energy investment opportunities
* Future electrification demand zones

---

# Core Tech Stack

Build the project using:

* **Snowflake** → cloud data warehouse
* **dbt** → transformations + data modeling
* **Apache Airflow** → workflow orchestration
* **Apache Superset** → dashboards + analytics
* **Python** → ingestion + geospatial processing
* **Docker** → local development environment
* **GeoPandas** → vector geospatial analysis
* **Rasterio / rioxarray** → raster processing
* **Google Earth Engine** → satellite nightlights extraction
* **GitHub Actions** → CI/CD

---

# Geospatial Intelligence Layer (VERY IMPORTANT)

Add advanced geospatial analysis:

## 1. Satellite Nightlights Analysis

Use:

* Google Earth Engine
* VIIRS Nighttime Lights
* NOAA Earth Observation Group

Tasks:

* Extract nighttime light intensity
* Aggregate nightlight values by administrative boundaries
* Identify low-light regions
* Use nightlights as a proxy for electricity access

---

## 2. Grid Proximity Analysis

Use:

* Transmission lines
* Substations
* Grid infrastructure shapefiles

Tasks:

* Calculate distance of settlements/population clusters to nearest grid line
* Identify underserved communities
* Detect off-grid solar opportunities

---

## 3. Population Distribution Analysis

Use:

* WorldPop
* Meta High Resolution Population Density

Tasks:

* Identify densely populated underserved areas
* Combine with grid + nightlights

---

## 4. Future ML Layer (Future Phase)

This is NOT part of week one delivery but architecture should support:

* XGBoost
* LightGBM
* GeoAI models
* Future electrification demand prediction

Using:

* Satellite imagery
* Socioeconomic indicators
* Historical demand data

---

# Required Datasets

Use publicly available datasets:

## Energy datasets

* World Bank electricity access
* IEA renewable production
* Fuel prices
* Carbon emissions
* National demand datasets

## Geospatial datasets

* Administrative boundaries
* Grid infrastructure
* Power plants
* Population density
* Nightlights raster data

Focus on counties/regions of Countries like:

* Kenya (MVP)
* Nigeria
* India
* Tanzania
* Rwanda
* Ivory Coast
* Pakistan
* Other Global South countries later

---

# Project Deliverables

Build a full implementation plan for:

## Phase 1: Project Setup

* Repository setup
* Folder structure
* Docker setup
* Environment configs

## Phase 2: Data Ingestion

Build pipelines for:

* APIs
* CSV ingestion
* GeoJSON
* Shapefiles
* Raster datasets
* Google Earth Engine exports

## Phase 3: Geospatial Processing

Build Python scripts for:

* Nightlights processing
* Raster aggregation
* Grid distance calculations
* Population overlays

## Phase 4: Data Warehouse

Design Snowflake schemas:

* raw
* staging
* marts
* geospatial

Optimize Snowflake usage to conserve free credits.

---

## Phase 5: dbt

Create:

* staging models
* intermediate models
* marts
* energy access score models

---

## Phase 6: Airflow

Create DAGs for:

* ingestion
* geospatial processing
* warehouse loading
* dbt runs

---

## Phase 7: Superset Dashboards

Build:

### Dashboard 1

Electricity access dashboard

### Dashboard 2

Nightlights dashboard

### Dashboard 3

Grid proximity dashboard

### Dashboard 4

Renewable investment dashboard

### Dashboard 5

Energy access opportunity dashboard

Include choropleth maps.

---

# Energy Access Scoring Model

Build a scoring framework:

Energy Access Score =
Population Density + Grid Distance + Nightlight Intensity + Poverty + Demand

Identify:

* High-risk areas
* Investment zones
* Electrification priorities

---

# Required Output From You

When responding:

1. Build everything sequentially from scratch
2. Assume I have exactly **1 week**
3. Prioritize MVP execution
4. Generate production-grade folder structure
5. Generate architecture diagrams
6. Generate SQL models
7. Generate Airflow DAGs
8. Generate dbt models
9. Generate Docker setup
10. Generate Snowflake schema design
11. Generate Superset dashboard plan
12. Generate `skills.md`
13. Generate sample Python scripts
14. Recommend best public datasets
15. Help me avoid unnecessary complexity

---

# Suggested Project Structure

```bash
energy-intelligence/
│
├── airflow/
├── dbt/
├── ingestion/
├── processing/
├── dashboards/
├── snowflake/
├── data/
├── notebooks/
├── tests/
├── docs/
└── docker-compose.yml
```

---

# Week 1 Execution Plan

### Day 1

Project setup + Docker + datasets

### Day 2

Data ingestion pipelines

### Day 3

Nightlights processing

### Day 4

Grid proximity analysis

### Day 5

Snowflake + dbt modeling

### Day 6

Airflow orchestration

### Day 7

Superset dashboards + documentation

---

# Final Goal

Help me build a project strong enough for:

* Data Engineering roles
* Geospatial Data Engineering roles
* Climate tech roles
* Energy analytics roles
* GeoAI roles

The final project should feel like something built for:

* Governments
* Utilities
* NGOs
* Development finance institutions
* Climate startups
* Energy investors

Provide implementation guidance as if we are building this project together from scratch.