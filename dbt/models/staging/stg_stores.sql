-- Staging view for stores: explicit type casts and snake_case column names.
-- Materialized as a view per dbt_project.yml.
select
    store_id::bigint     as store_id,
    store_name::text     as store_name,
    prefecture::text     as prefecture
from {{ source('raw', 'stores') }}
