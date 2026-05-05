-- Mart: Energy Access Summary — one row per admin-2 × year
-- Powers the main Superset choropleth dashboard.
--
-- Energy Access Score (0–100, higher = more underserved):
--   35% access gap       (100 - electricity_access_pct)
--   25% nightlight proxy (darkness index: low radiance = high score)
--   20% population       (demand pressure: higher density = more people affected)
--   20% grid distance    (infrastructure gap: farther = more underserved)

with base as (
    select * from {{ ref('int_admin_energy_metrics') }}
),

admin_bounds as (
    select * from {{ ref('stg_admin_boundaries') }}
    where admin_level = 2
),

scored as (
    select
        b.admin_gid,
        b.country_code,
        a.country_name,
        b.admin_level,
        b.admin_name,
        b.year,

        -- Electricity access
        b.electricity_access_pct,

        -- Nightlights
        b.mean_radiance_annual                                          as mean_nightlight_radiance,
        case
            when b.mean_radiance_annual < 0.5  then 'dark'
            when b.mean_radiance_annual < 5.0  then 'dim'
            when b.mean_radiance_annual < 20.0 then 'lit'
            else 'bright'
        end                                                             as nightlight_category,

        -- Grid proximity
        b.dist_to_grid_km,
        coalesce(b.grid_proximity_category, 'unknown')                  as grid_proximity_category,

        -- Population
        b.total_population,
        b.pop_density_km2,
        case
            when coalesce(b.pop_density_km2, 0) < 50  then 'rural'
            when coalesce(b.pop_density_km2, 0) < 300 then 'peri_urban'
            else 'urban'
        end                                                             as population_category,

        -- ── Composite Energy Access Score ──────────────────────────────────
        round(
            -- 35%: access gap (missing data defaults to 50% gap)
            (coalesce(100 - b.electricity_access_pct, 50) * 0.35)

            -- 25%: nightlight darkness (lower radiance → higher score)
            + (greatest(0, 10 - coalesce(b.mean_radiance_annual, 5)) / 10.0 * 100 * 0.25)

            -- 20%: population demand (capped at 100 ppl/km² for normalisation)
            + (least(coalesce(b.pop_density_km2, 0), 100) / 100.0 * 100 * 0.20)

            -- 20%: grid distance (capped at 100 km for normalisation)
            + (least(coalesce(b.dist_to_grid_km, 50), 100) / 100.0 * 100 * 0.20)
        , 2)                                                            as energy_access_score,

        a.geometry_wkt,
        current_timestamp()                                             as _dbt_updated_at

    from base b
    left join admin_bounds a on b.admin_gid = a.admin_gid
),

with_tier as (
    select
        *,
        case
            when energy_access_score >= 75 then 'critical'
            when energy_access_score >= 50 then 'high'
            when energy_access_score >= 25 then 'medium'
            else 'low'
        end as score_tier
    from scored
)

select * from with_tier
