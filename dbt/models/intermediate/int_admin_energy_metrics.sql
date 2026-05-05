-- Intermediate: joins electricity access + nightlights + population + grid proximity
-- per admin-2 region × year

with electricity as (
    select
        country_code,
        year,
        electricity_access_pct
    from {{ ref('stg_electricity_access') }}
),

nightlights_annual as (
    -- Annual composites have month IS NULL (stored as 'annual' in RAW)
    select
        admin_gid,
        country_code,
        admin_name,
        admin_level,
        year,
        avg(mean_radiance) as mean_radiance_annual,
        max(max_radiance)  as max_radiance_annual
    from {{ ref('stg_nightlights') }}
    where admin_level = 2
      and month is null
    group by 1, 2, 3, 4, 5
),

population as (
    select
        admin_gid,
        country_code,
        admin_name,
        admin_level,
        year,
        total_population,
        area_km2,
        pop_density_km2
    from {{ ref('stg_population_density') }}
    where admin_level = 2
),

grid as (
    select
        admin_gid,
        dist_to_grid_km,
        grid_proximity_category
    from {{ source('raw', 'grid_proximity') }}
),

joined as (
    select
        coalesce(n.admin_gid, p.admin_gid)          as admin_gid,
        coalesce(n.country_code, p.country_code)    as country_code,
        coalesce(n.admin_name, p.admin_name)        as admin_name,
        coalesce(n.admin_level, p.admin_level)      as admin_level,
        coalesce(n.year, p.year)                    as year,
        e.electricity_access_pct,
        n.mean_radiance_annual,
        n.max_radiance_annual,
        p.total_population,
        p.area_km2,
        p.pop_density_km2,
        g.dist_to_grid_km,
        g.grid_proximity_category
    from nightlights_annual n
    full outer join population p
        on  n.admin_gid    = p.admin_gid
        and n.year         = p.year
    left join electricity e
        on  coalesce(n.country_code, p.country_code) = e.country_code
        and coalesce(n.year, p.year)                 = e.year
    left join grid g
        on  coalesce(n.admin_gid, p.admin_gid) = g.admin_gid
)

select * from joined
