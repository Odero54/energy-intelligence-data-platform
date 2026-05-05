-- Staging: Global Power Plant Database (WRI)

with source as (
    select * from {{ source('raw', 'power_plants') }}
),

renamed as (
    select
        trim(plant_id)                                      as plant_id,
        upper(trim(country))                                as country_code,
        trim(country_long)                                  as country_name,
        trim(name)                                          as plant_name,
        try_to_double(nullif(trim(capacity_mw),        '')) as capacity_mw,
        try_to_double(nullif(trim(latitude),           '')) as latitude,
        try_to_double(nullif(trim(longitude),          '')) as longitude,
        lower(trim(primary_fuel))                           as primary_fuel,
        try_to_number(nullif(trim(commissioning_year), '')) as commissioning_year,
        trim(owner)                                         as owner,
        _loaded_at
    from source
    where try_to_double(nullif(trim(latitude),  '')) is not null
      and try_to_double(nullif(trim(longitude), '')) is not null
)

select * from renamed
