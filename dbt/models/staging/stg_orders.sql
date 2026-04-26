-- Staging view for orders: explicit type casts and snake_case column names.
-- Materialized as a view per dbt_project.yml.
select
    order_id::bigint             as order_id,
    order_date::date             as order_date,
    customer_id::bigint          as customer_id,
    product_id::bigint           as product_id,
    store_id::bigint             as store_id,
    quantity::int                as quantity,
    unit_price::numeric(12, 2)   as unit_price
from {{ source('raw', 'orders') }}
