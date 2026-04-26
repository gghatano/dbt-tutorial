-- Staging view for customers: explicit type casts and snake_case column names.
-- Materialized as a view per dbt_project.yml.
select
    customer_id::bigint   as customer_id,
    customer_name::text   as customer_name,
    email::text           as email,
    created_at::date      as created_at
from {{ source('raw', 'customers') }}
