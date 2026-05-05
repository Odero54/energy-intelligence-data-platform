-- ============================================================
-- 02_marts_tables.sql
-- Final analytics tables — populated by dbt, read by Superset.
-- Defined here for reference — dbt manages the actual DDL via
-- `materialized = 'table'` config.
-- ============================================================

USE DATABASE ENERGY_INTELLIGENCE;
USE SCHEMA MARTS;

-- ─── Energy Access Summary ────────────────────────────────────────────────────
-- One row per admin_level-2 region × year
CREATE TABLE IF NOT EXISTS ENERGY_ACCESS_SUMMARY (
    admin_gid               VARCHAR(100)  NOT NULL,
    country_code            VARCHAR(10)   NOT NULL,
    country_name            VARCHAR(255),
    admin_level             NUMBER(2),
    admin_name              VARCHAR(500),
    year                    NUMBER(4)     NOT NULL,

    -- Electricity access
    electricity_access_pct  FLOAT,

    -- Nightlights proxy
    mean_nightlight_radiance FLOAT,
    nightlight_category      VARCHAR(50),  -- dark / dim / lit / bright

    -- Grid proximity
    dist_to_grid_km          FLOAT,
    grid_proximity_category  VARCHAR(50),  -- off_grid / near_grid / on_grid

    -- Population
    total_population         BIGINT,
    pop_density_km2          FLOAT,
    population_category      VARCHAR(50),  -- rural / peri-urban / urban

    -- Composite score (0–100, higher = more underserved)
    energy_access_score      FLOAT,
    score_tier               VARCHAR(50),  -- critical / high / medium / low

    -- Geometry (WKT for Superset choropleth)
    geometry_wkt             TEXT,

    _dbt_updated_at          TIMESTAMP_NTZ
);

-- ─── Renewable Investment Opportunities ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS RENEWABLE_INVESTMENT_ZONES (
    admin_gid               VARCHAR(100)  NOT NULL,
    country_code            VARCHAR(10)   NOT NULL,
    admin_name              VARCHAR(500),
    year                    NUMBER(4),

    -- Investment signals
    energy_access_score      FLOAT,
    population               BIGINT,
    pop_density_km2          FLOAT,
    dist_to_grid_km          FLOAT,
    mean_nightlight_radiance FLOAT,
    renewable_production_gwh FLOAT,

    -- Opportunity tier
    investment_priority      VARCHAR(50),  -- high / medium / low
    recommended_technology   VARCHAR(255), -- solar_mini_grid, standalone_solar, etc.

    geometry_wkt             TEXT,
    _dbt_updated_at          TIMESTAMP_NTZ
);

-- ─── Country-Level KPIs ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS COUNTRY_ENERGY_KPI (
    country_code            VARCHAR(10)   NOT NULL,
    country_name            VARCHAR(255),
    year                    NUMBER(4)     NOT NULL,

    electricity_access_pct  FLOAT,
    population              BIGINT,
    pop_without_electricity BIGINT,
    renewable_share_pct     FLOAT,
    total_renewable_gwh     FLOAT,
    installed_capacity_mw   FLOAT,
    mean_nightlight_radiance FLOAT,
    n_power_plants          INTEGER,
    n_admin2_regions        INTEGER,
    n_critical_zones        INTEGER,       -- score_tier = 'critical'

    _dbt_updated_at          TIMESTAMP_NTZ
);