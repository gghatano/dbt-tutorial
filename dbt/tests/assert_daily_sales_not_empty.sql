-- Singular test: mart_daily_sales must contain at least one row.
-- dbt singular tests fail when rows are returned, so we count rows
-- in a CTE and emit exactly one failure row when the count is zero.
with c as (
    select count(*) as n
    from {{ ref('mart_daily_sales') }}
)
select 'mart_daily_sales is empty' as failure
from c
where n = 0
