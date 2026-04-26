# task-001: custom tests

- Phase: 06
- Status: Todo
- Owner: -
- Depends on: phase-05/task-002
- Parallelizable with: phase-06/task-002

## 目的
spec §9.2 の独自テストを実装する。

## 入力 / 前提
- spec §9

## 成果物
- `dbt/tests/assert_positive_sales_amount.sql`（singular: int_order_details の sales_amount >= 0）
- `dbt/tests/assert_positive_quantity.sql`（singular: stg_orders.quantity > 0）
- `dbt/tests/assert_marts_total_sales_non_negative.sql`（singular: 各マートの total_sales_amount >= 0）
- `dbt/tests/assert_daily_sales_not_empty.sql`（singular: mart_daily_sales 件数 > 0）

## 受入条件
- `dbt test --profiles-dir .` が全件成功

## 実装メモ / 判断ログ
- singular tests は「失敗行が返ってきたら失敗」なので、各SQLは `SELECT ... WHERE <違反条件>` の形にする。
