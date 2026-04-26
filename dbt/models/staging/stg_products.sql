-- Staging view for products: explicit type casts and snake_case column names.
-- Materialized as a view per dbt_project.yml.
select
    product_id::bigint           as product_id,
    product_name::text           as product_name,
    category::text               as category,
    unit_price::numeric(12, 2)   as unit_price
from {{ source('raw', 'products') }}
