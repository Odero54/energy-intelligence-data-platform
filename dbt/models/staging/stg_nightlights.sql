-- Staging: VIIRS nighttime lights
-- month is NULL for annual composites (stored as 'annual' string in RAW)

with source as (
    select * from {{ source('raw', 'nightlights') }}
),

renamed as (
    select
        trim(admin_gid)                                 as admin_gid,
        upper(trim(country_code))                       as country_code,
        trim(admin_name)                                as admin_name,
        try_to_number(trim(admin_level))                as admin_level,
        try_to_number(trim(year))                       as year,
        try_to_number(nullif(trim(month), 'annual'))    as month,
        try_to_double(nullif(trim(mean_radiance), ''))  as mean_radiance,
        try_to_double(nullif(trim(max_radiance),  ''))  as max_radiance,
        try_to_double(nullif(trim(sum_radiance),  ''))  as sum_radiance,
        try_to_number(nullif(trim(pixel_count),   ''))  as pixel_count,
        trim(sensor)                                    as sensor,
        trim(product)                                   as product,
        _loaded_at
    from source
    where trim(admin_gid) is not null
)

select * from renamed
