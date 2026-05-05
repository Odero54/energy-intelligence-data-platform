-- Mart: Country-level KPIs — one row per country × year

with access as (
    select
        country_code,
        year,
        electricity_access_pct
    from {{ ref('stg_electricity_access') }}
),

pop as (
    select
        country_code,
        year,
        sum(total_population) as total_population
    from {{ ref('stg_population_density') }}
    where admin_level = 1
    group by 1, 2
),

plants as (
    select
        country_code,
        count(*)              as n_power_plants,
        sum(capacity_mw)      as installed_capacity_mw
    from {{ ref('stg_power_plants') }}
    group by 1
),

nightlights_country as (
    select
        country_code,
        year,
        avg(mean_radiance) as mean_nightlight_radiance
    from {{ ref('stg_nightlights') }}
    where admin_level = 1
    group by 1, 2
),

critical_zones as (
    select
        country_code,
        year,
        count(*) as n_critical_zones
    from {{ ref('mart_energy_access_summary') }}
    where score_tier = 'critical'
    group by 1, 2
)

select
    a.country_code,
    a.year,
    a.electricity_access_pct,
    p.total_population,
    round(p.total_population * (1 - coalesce(a.electricity_access_pct, 0) / 100))
                                                    as pop_without_electricity,
    nl.mean_nightlight_radiance,
    pl.n_power_plants,
    pl.installed_capacity_mw,
    cz.n_critical_zones,
    current_timestamp()                             as _dbt_updated_at
from access a
left join pop             p  on a.country_code = p.country_code  and a.year = p.year
left join plants          pl on a.country_code = pl.country_code
left join nightlights_country nl on a.country_code = nl.country_code and a.year = nl.year
left join critical_zones  cz on a.country_code = cz.country_code and a.year = cz.year
