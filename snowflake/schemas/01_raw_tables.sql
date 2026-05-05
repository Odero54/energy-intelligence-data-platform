-- ============================================================
-- 01_raw_tables.sql
-- Raw-layer table definitions.
-- All columns VARCHAR / VARIANT by design — transformations
-- happen in dbt staging models, not here.
-- ============================================================

USE DATABASE ENERGY_INTELLIGENCE;
USE SCHEMA RAW;

-- ─── World Bank: Electricity Access ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS WORLD_BANK_ELECTRICITY_ACCESS (
    country_code        VARCHAR(10),
    country_name        VARCHAR(255),
    indicator_code      VARCHAR(100),
    indicator_name      VARCHAR(500),
    year                VARCHAR(10),
    value               VARCHAR(50),           -- NULL if no data
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── IEA: Renewable Energy Production ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS IEA_RENEWABLE_PRODUCTION (
    country             VARCHAR(255),
    product             VARCHAR(255),          -- Solar, Wind, Hydro, etc.
    flow                VARCHAR(255),          -- Production, Imports, etc.
    year                VARCHAR(10),
    value_gwh           VARCHAR(50),
    unit                VARCHAR(50),
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── Power Plants (Global Power Plant Database) ───────────────────────────────
CREATE TABLE IF NOT EXISTS POWER_PLANTS (
    plant_id            VARCHAR(100),
    country             VARCHAR(100),
    country_long        VARCHAR(255),
    name                VARCHAR(500),
    capacity_mw         VARCHAR(50),
    latitude            VARCHAR(50),
    longitude           VARCHAR(50),
    primary_fuel        VARCHAR(100),
    other_fuel1         VARCHAR(100),
    other_fuel2         VARCHAR(100),
    other_fuel3         VARCHAR(100),
    commissioning_year  VARCHAR(10),
    owner               VARCHAR(500),
    source              VARCHAR(500),
    url                 VARCHAR(1000),
    geolocation_source  VARCHAR(255),
    wepp_id             VARCHAR(100),
    year_of_capacity_data VARCHAR(10),
    generation_gwh_2013 VARCHAR(50),
    generation_gwh_2014 VARCHAR(50),
    generation_gwh_2015 VARCHAR(50),
    generation_gwh_2016 VARCHAR(50),
    generation_gwh_2017 VARCHAR(50),
    generation_gwh_2018 VARCHAR(50),
    generation_gwh_2019 VARCHAR(50),
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── Administrative Boundaries (GeoJSON / Shapefile metadata) ────────────────
CREATE TABLE IF NOT EXISTS ADMIN_BOUNDARIES (
    gid                 VARCHAR(100),
    country_code        VARCHAR(10),
    country_name        VARCHAR(255),
    admin_level         VARCHAR(10),           -- 0=country, 1=state/province, 2=district
    admin_name          VARCHAR(500),
    admin_name_alt      VARCHAR(500),
    area_km2            VARCHAR(50),
    geometry_wkt        TEXT,                  -- WKT polygon
    source_dataset      VARCHAR(255),          -- GADM, OCHA, etc.
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── VIIRS Nighttime Lights (aggregated by admin boundary) ───────────────────
CREATE TABLE IF NOT EXISTS NIGHTLIGHTS (
    admin_gid           VARCHAR(100),
    country_code        VARCHAR(10),
    admin_name          VARCHAR(500),
    admin_level         VARCHAR(10),
    year                VARCHAR(10),
    month               VARCHAR(10),
    mean_radiance       VARCHAR(50),           -- avg nW/cm²/sr
    max_radiance        VARCHAR(50),
    min_radiance        VARCHAR(50),
    sum_radiance        VARCHAR(50),
    pixel_count         VARCHAR(20),
    sensor              VARCHAR(100),          -- VIIRS/NPP, VIIRS/NOAA-20
    product             VARCHAR(100),          -- VNP46A1, VNP46A3, VNP46A4
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── WorldPop: Population Density (aggregated by admin boundary) ──────────────
CREATE TABLE IF NOT EXISTS POPULATION_DENSITY (
    admin_gid           VARCHAR(100),
    country_code        VARCHAR(10),
    admin_name          VARCHAR(500),
    admin_level         VARCHAR(10),
    year                VARCHAR(10),
    total_population    VARCHAR(50),
    area_km2            VARCHAR(50),
    pop_density_km2     VARCHAR(50),
    source_dataset      VARCHAR(255),          -- WorldPop, Meta HRSL
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── Grid Infrastructure ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS GRID_INFRASTRUCTURE (
    feature_id          VARCHAR(100),
    country_code        VARCHAR(10),
    feature_type        VARCHAR(100),          -- transmission_line, substation, distribution_line
    voltage_kv          VARCHAR(50),
    status              VARCHAR(100),          -- operational, under_construction, planned
    source_dataset      VARCHAR(255),          -- gridfinder, ENERGYDATA.INFO, OSM
    geometry_wkt        TEXT,                  -- WKT linestring or point
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file        VARCHAR(500)
);

-- ─── Grid Proximity (computed by processing/geospatial/grid_proximity.py) ─────
CREATE TABLE IF NOT EXISTS GRID_PROXIMITY (
    admin_gid               VARCHAR(100),
    country_code            VARCHAR(10),
    admin_name              VARCHAR(500),
    admin_level             VARCHAR(10),
    dist_to_grid_km         FLOAT,
    grid_proximity_category VARCHAR(50),
    _loaded_at              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ─── Energy Access Score (computed, loaded by processing pipeline) ────────────
CREATE TABLE IF NOT EXISTS ENERGY_ACCESS_SCORE_RAW (
    admin_gid           VARCHAR(100),
    country_code        VARCHAR(10),
    admin_name          VARCHAR(500),
    admin_level         VARCHAR(10),
    score_date          VARCHAR(10),
    electricity_access_pct VARCHAR(50),
    mean_nightlight_radiance VARCHAR(50),
    dist_to_grid_km     VARCHAR(50),
    population          VARCHAR(50),
    pop_density_km2     VARCHAR(50),
    composite_score     VARCHAR(50),
    _loaded_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
