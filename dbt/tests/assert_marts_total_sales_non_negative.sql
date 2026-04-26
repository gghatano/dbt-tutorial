-- Singular test: total_sales_amount in every mart must be >= 0.
-- One file with UNION ALL keeps the test name/maintenance cost low
-- while still pinpointing which mart row violated the invariant via
-- the `mart` and `key_value` columns in the failure output.
select
    'mart_daily_sales' as mart,
    order_date::text   as key_value,
    total_sales_amount
from {{ ref('mart_daily_sales') }}
where total_sales_amount < 0

union all

select
    'mart_customer_sales' as mart,
    customer_id::text     as key_value,
    total_sales_amount
from {{ ref('mart_customer_sales') }}
where total_sales_amount < 0

union all

select
    'mart_product_sales' as mart,
    product_id::text     as key_value,
    total_sales_amount
from {{ ref('mart_product_sales') }}
where total_sales_amount < 0
