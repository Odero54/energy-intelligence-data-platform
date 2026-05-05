-- Staging: Grid infrastructure (transmission lines, substations)

with source as (
    select * from {{ source('raw', 'grid_infrastructure') }}
),

renamed as (
    select
        trim(feature_id)                                as feature_id,
        upper(trim(country_code))                       as country_code,
        trim(feature_type)                              as feature_type,
        try_to_double(nullif(trim(voltage_kv), ''))     as voltage_kv,
        lower(trim(status))                             as status,
        trim(source_dataset)                            as source_dataset,
        trim(geometry_wkt)                              as geometry_wkt,
        _loaded_at
    from source
    where trim(feature_id) is not null
)

select * from renamed
