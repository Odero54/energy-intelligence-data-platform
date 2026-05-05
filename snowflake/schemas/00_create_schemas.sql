-- ============================================================
-- 00_create_schemas.sql
-- Run once per environment to bootstrap the Snowflake database.
-- Optimised for free-tier: single XS warehouse, auto-suspend 60s.
-- ============================================================

-- Bootstrap requires account-level privileges
USE ROLE ACCOUNTADMIN;

-- Warehouse (auto-suspend aggressively to conserve credits)
CREATE WAREHOUSE IF NOT EXISTS ENERGY_WH
  WAREHOUSE_SIZE      = 'XSMALL'
  AUTO_SUSPEND        = 60
  AUTO_RESUME         = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT             = 'Energy Intelligence Platform — dev warehouse';

-- Database
CREATE DATABASE IF NOT EXISTS ENERGY_INTELLIGENCE
  COMMENT = 'Energy access gap analysis for the Global South';

USE DATABASE ENERGY_INTELLIGENCE;

-- ─── Schemas ─────────────────────────────────────────────────────────────────

-- Raw: exact copies of source data, never transformed
CREATE SCHEMA IF NOT EXISTS RAW
  COMMENT = 'Source-aligned raw tables loaded by ingestion pipelines';

-- Staging: light cleaning, type casting, column renaming
CREATE SCHEMA IF NOT EXISTS STAGING
  COMMENT = 'Cleaned, typed views over RAW — built by dbt';

-- Intermediate: business-logic joins, not user-facing
CREATE SCHEMA IF NOT EXISTS INTERMEDIATE
  COMMENT = 'Joined and enriched intermediate models — built by dbt';

-- Marts: final analytics tables consumed by Superset
CREATE SCHEMA IF NOT EXISTS MARTS
  COMMENT = 'Wide, query-optimised mart tables — built by dbt';

-- Geospatial: stores WKT/GeoJSON geometry columns
CREATE SCHEMA IF NOT EXISTS GEOSPATIAL
  COMMENT = 'Geometry-enriched tables and spatial aggregations';

-- ─── Role & permissions ───────────────────────────────────────────────────────
CREATE ROLE IF NOT EXISTS ENERGY_ROLE;

GRANT USAGE  ON WAREHOUSE ENERGY_WH               TO ROLE ENERGY_ROLE;
GRANT USAGE  ON DATABASE  ENERGY_INTELLIGENCE      TO ROLE ENERGY_ROLE;
GRANT ALL    ON SCHEMA    ENERGY_INTELLIGENCE.RAW          TO ROLE ENERGY_ROLE;
GRANT ALL    ON SCHEMA    ENERGY_INTELLIGENCE.STAGING       TO ROLE ENERGY_ROLE;
GRANT ALL    ON SCHEMA    ENERGY_INTELLIGENCE.INTERMEDIATE  TO ROLE ENERGY_ROLE;
GRANT ALL    ON SCHEMA    ENERGY_INTELLIGENCE.MARTS         TO ROLE ENERGY_ROLE;
GRANT ALL    ON SCHEMA    ENERGY_INTELLIGENCE.GEOSPATIAL    TO ROLE ENERGY_ROLE;

-- Grant future table privileges so new tables are accessible automatically
GRANT ALL ON FUTURE TABLES IN SCHEMA ENERGY_INTELLIGENCE.RAW          TO ROLE ENERGY_ROLE;
GRANT ALL ON FUTURE TABLES IN SCHEMA ENERGY_INTELLIGENCE.STAGING       TO ROLE ENERGY_ROLE;
GRANT ALL ON FUTURE TABLES IN SCHEMA ENERGY_INTELLIGENCE.INTERMEDIATE  TO ROLE ENERGY_ROLE;
GRANT ALL ON FUTURE TABLES IN SCHEMA ENERGY_INTELLIGENCE.MARTS         TO ROLE ENERGY_ROLE;
GRANT ALL ON FUTURE TABLES IN SCHEMA ENERGY_INTELLIGENCE.GEOSPATIAL    TO ROLE ENERGY_ROLE;