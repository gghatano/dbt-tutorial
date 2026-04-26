-- Customer-level sales mart: one row per customer.
-- Materialized as a table per dbt_project.yml.
select
    customer_id,
    customer_name,
    count(*)                          as order_count,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount,
    min(order_date)                   as first_order_date,
    max(order_date)                   as last_order_date
from {{ ref('int_order_details') }}
group by customer_id, customer_name
