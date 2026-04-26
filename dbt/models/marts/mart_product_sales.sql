-- Product-level sales mart: one row per product.
-- Materialized as a table per dbt_project.yml.
select
    product_id,
    product_name,
    category,
    count(*)                          as order_count,
    sum(quantity)                     as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details') }}
group by product_id, product_name, category
