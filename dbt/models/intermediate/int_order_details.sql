-- Intermediate model: enriches orders with customer / product / store master data
-- and computes sales_amount = quantity * unit_price.
-- Materialized as a view per dbt_project.yml (intermediate layer).
-- INNER JOIN is appropriate: stg_orders FKs are validated by relationships
-- tests, so any row joining a master is guaranteed to find a match.
select
    o.order_id,
    o.order_date,
    o.customer_id,
    c.customer_name,
    o.product_id,
    p.product_name,
    p.category,
    o.store_id,
    o.quantity,
    o.unit_price,
    (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
from {{ ref('stg_orders') }}    as o
inner join {{ ref('stg_customers') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores') }}    as s on o.store_id    = s.store_id
