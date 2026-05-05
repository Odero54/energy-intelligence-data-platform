-- Staging: WorldPop population density

with source as (
    select * from {{ source('raw', 'population_density') }}
),

renamed as (
    select
        trim(admin_gid)                                     as admin_gid,
        upper(trim(country_code))                           as country_code,
        trim(admin_name)                                    as admin_name,
        try_to_number(trim(admin_level))                    as admin_level,
        try_to_number(trim(year))                           as year,
        try_to_number(nullif(trim(total_population), ''))   as total_population,
        try_to_double(nullif(trim(area_km2),         ''))   as area_km2,
        try_to_double(nullif(trim(pop_density_km2),  ''))   as pop_density_km2,
        trim(source_dataset)                                as source_dataset,
        _loaded_at
    from source
)

select * from renamed
