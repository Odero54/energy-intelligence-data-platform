-- Staging: GADM administrative boundaries

with source as (
    select * from {{ source('raw', 'admin_boundaries') }}
),

renamed as (
    select
        trim(gid)                                       as admin_gid,
        upper(trim(country_code))                       as country_code,
        trim(country_name)                              as country_name,
        try_to_number(trim(admin_level))                as admin_level,
        trim(admin_name)                                as admin_name,
        trim(admin_name_alt)                            as admin_name_alt,
        try_to_double(nullif(trim(area_km2), ''))       as area_km2,
        trim(geometry_wkt)                              as geometry_wkt,
        trim(source_dataset)                            as source_dataset,
        _loaded_at
    from source
    where trim(gid) is not null
      and trim(gid) != ''
)

select * from renamed
