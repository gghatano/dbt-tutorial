-- Daily sales mart: one row per order_date.
-- Materialized as a table (per dbt_project.yml) for cheap downstream reads.
select
    order_date,
    count(*)                          as order_count,
    count(distinct customer_id)       as customer_count,
    sum(quantity)                     as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details') }}
group by order_date
order by order_date
