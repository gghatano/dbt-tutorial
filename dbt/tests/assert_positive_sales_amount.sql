-- Singular test: int_order_details.sales_amount must be >= 0.
-- dbt singular tests fail when any row is returned, so we SELECT
-- the violating rows (sales_amount < 0).
select
    order_id,
    sales_amount
from {{ ref('int_order_details') }}
where sales_amount < 0
