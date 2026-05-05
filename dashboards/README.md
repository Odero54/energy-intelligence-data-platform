# Superset Dashboards

## Setup

Run once after `make up` to register the Snowflake connection and datasets:

```bash
uv run python scripts/superset_setup.py
```

Then open [http://localhost:8088](http://localhost:8088) (admin / see `.env`).

---

## Dashboard 1 — Energy Access Map

**Dataset:** `MARTS.MART_ENERGY_ACCESS_SUMMARY`

### Charts

| Chart | Type | Dimensions | Metric | Filter |
|---|---|---|---|---|
| Energy Access Score map | Deck.gl Polygon | `geometry_wkt` | `AVG(energy_access_score)` | latest year |
| Score tier breakdown | Bar chart | `score_tier` | `COUNT(*)` | — |
| Top 20 critical zones | Table | `admin_name`, `country_code` | `energy_access_score` | `score_tier = critical` |
| Access score by country | Box plot | `country_code` | `energy_access_score` | — |
| Nightlight category split | Pie chart | `nightlight_category` | `COUNT(*)` | — |
| Grid proximity breakdown | Bar chart | `grid_proximity_category` | `COUNT(*)` | — |
| Population without electricity | Big number | — | `SUM(total_population) × (1 - AVG(electricity_access_pct)/100)` | — |

### Choropleth map setup (Deck.gl Polygon)

1. Chart type → **Deck.gl Polygon**
2. Spatial column → `geometry_wkt` (WKT polygon)
3. Metric → `AVG(energy_access_score)`
4. Color scheme → `RdYlGn_r` (red = high score = underserved)
5. Stroke width → 0.5, Opacity → 0.8

---

## Dashboard 2 — Country KPIs

**Dataset:** `MARTS.MART_COUNTRY_KPI`

### Charts

| Chart | Type | Dimensions | Metric |
|---|---|---|---|
| Electricity access trend | Line chart | `year` (x), `country_code` (series) | `electricity_access_pct` |
| Population without electricity | Bar chart | `country_code` | `pop_without_electricity` |
| Installed capacity | Bar chart | `country_code` | `installed_capacity_mw` |
| Critical zones over time | Line chart | `year` (x), `country_code` (series) | `n_critical_zones` |
| Nightlight radiance trend | Line chart | `year` (x), `country_code` (series) | `mean_nightlight_radiance` |

---

## Exporting dashboards

Once charts are built in the UI, export via:

```bash
# From inside the Superset container
docker compose exec superset \
  superset export-dashboards -f /tmp/energy_dashboards.json

# Copy out of container
docker compose cp superset:/tmp/energy_dashboards.json dashboards/
```

Commit `dashboards/energy_dashboards.json` and import on any fresh deployment:

```bash
docker compose exec superset \
  superset import-dashboards -p /app/dashboards/energy_dashboards.json
```
