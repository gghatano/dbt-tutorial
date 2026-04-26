# task-002: sources.yml + staging models 4本

- Phase: 04
- Status: Todo
- Owner: -
- Depends on: phase-04/task-001
- Parallelizable with: -

## 目的
raw を source として参照し、stg_* 4本を実装する。

## 入力 / 前提
- spec §8.1 / §8.2

## 成果物
- `dbt/models/sources.yml`
- `dbt/models/staging/stg_customers.sql`
- `dbt/models/staging/stg_products.sql`
- `dbt/models/staging/stg_stores.sql`
- `dbt/models/staging/stg_orders.sql`
- `dbt/models/staging/schema.yml`（テスト定義）

## 受入条件
- `dbt run --select staging --profiles-dir .` が成功
- `dbt test --select staging --profiles-dir .` が成功
- 主キー列に not_null + unique
- orders の customer_id, product_id, store_id に relationships テスト
- 数値列（quantity, unit_price）に not_null
- 日付列（order_date）に not_null
- 列名は snake_case で統一

## 実装メモ / 判断ログ
- staging materialization: view（dbt_project.yml で設定）
- 型変換: `::int`, `::numeric`, `::date` など明示キャスト
- 列名統一: id列は `<entity>_id`（spec暗黙）
