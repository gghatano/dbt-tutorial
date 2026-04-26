# task-002: marts 3本（daily / customer / product）

- Phase: 05
- Status: Todo
- Owner: -
- Depends on: phase-05/task-001
- Parallelizable with: -

## 目的
分析・BI向けの3つのマートを作成する。

## 入力 / 前提
- spec §8.4

## 成果物
- `dbt/models/marts/mart_daily_sales.sql`
- `dbt/models/marts/mart_customer_sales.sql`
- `dbt/models/marts/mart_product_sales.sql`
- `dbt/models/marts/schema.yml`

## 受入条件
- `dbt run --select marts --profiles-dir .` が成功
- 各列が spec §8.4 通り
- 全マートで not_null / unique（PK列）テストが通る
- `total_sales_amount >= 0` テストが通る
- mart_daily_sales が1件以上存在

## 実装メモ / 判断ログ
- materialization: table
- mart_daily_sales: PKは order_date
- mart_customer_sales: PKは customer_id
- mart_product_sales: PKは product_id
- customer_count: COUNT(DISTINCT customer_id)
