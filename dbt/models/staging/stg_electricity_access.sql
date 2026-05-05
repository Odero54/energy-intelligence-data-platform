-- Staging: World Bank electricity access
-- Casts raw strings to typed columns and filters to target countries.

with source as (
    select * from {{ source('raw', 'world_bank_electricity_access') }}
),

renamed as (
    select
        upper(trim(country_code))                       as country_code,
        trim(country_name)                              as country_name,
        trim(indicator_code)                            as indicator_code,
        try_to_number(trim(year))                       as year,
        try_to_double(nullif(trim(value), ''))          as electricity_access_pct,
        _loaded_at
    from source
    where indicator_code = 'EG.ELC.ACCS.ZS'   -- SE4ALL: access to electricity (% of population)
      and try_to_number(trim(year)) is not null
),

filtered as (
    select *
    from renamed
    where country_code in ({{ "'" ~ var('target_countries') | join("','") ~ "'" }})
)

select * from filtered
