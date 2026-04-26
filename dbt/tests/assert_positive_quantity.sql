-- Singular test: stg_orders.quantity must be > 0.
-- Returns rows where quantity <= 0 (the violation set), so the
-- test passes only when no such rows exist.
select
    order_id,
    quantity
from {{ ref('stg_orders') }}
where quantity <= 0
