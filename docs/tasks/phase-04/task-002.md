# task-002: sources.yml + staging models 4本

- Phase: 04
- Status: Done
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
- **dbt_utils を採用しない**: spec §14 と task-001 の判断ログに従って最小構成。`unit_price >= 0` `quantity > 0` のような数値非負制約は phase-06 の singular test (`tests/assert_*.sql`) で扱うため、本タスクでは built-in test (not_null/unique/relationships) のみ使用。
- **`relationships` テストの引数は新形式 (`arguments:`)** で記述。dbt 1.11 で deprecation (`MissingArgumentsPropertyInGenericTestDeprecation`) が出るため。

## 実行ログ

### `dbt run --select staging --profiles-dir .`

```
1 of 4 OK created sql view model staging.stg_customers ......... [CREATE VIEW in 0.05s]
2 of 4 OK created sql view model staging.stg_orders ............ [CREATE VIEW in 0.05s]
3 of 4 OK created sql view model staging.stg_products .......... [CREATE VIEW in 0.05s]
4 of 4 OK created sql view model staging.stg_stores ............ [CREATE VIEW in 0.05s]

Done. PASS=4 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=4
```

### `dbt test --select staging --profiles-dir .`

```
Done. PASS=18 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=18
```

内訳：
- not_null: 11 件 (customer_id / order_id, customer_id, product_id, store_id, order_date, quantity, unit_price / product_id, unit_price / store_id)
- unique: 4 件 (customer_id, product_id, store_id, order_id)
- relationships: 3 件 (orders.customer_id → stg_customers, orders.product_id → stg_products, orders.store_id → stg_stores)

`dbt test --profiles-dir .` (sources も含む全テスト) では PASS=26 (上記 18 + sources の not_null/unique × 4 entity = 8)。

### staging schema 確認 (`\dn`)

```
     Name     |       Owner       
--------------+-------------------
 intermediate | dbt_user
 marts        | dbt_user
 public       | pg_database_owner
 raw          | dbt_user
 staging      | dbt_user
```

`generate_schema_name` override が効いて `<target>_staging` ではなく `staging` schema へ正しく出力されている。

### staging.stg_* row counts

| view | rows |
|---|---:|
| staging.stg_customers | 1,000 |
| staging.stg_products | 100 |
| staging.stg_stores | 20 |
| staging.stg_orders | 10,000 |

raw 層 (1,000 / 100 / 20 / 10,000) と完全一致。型変換のみで filter していないことを確認。

### `\dv staging.*`

```
 staging | stg_customers | view | dbt_user
 staging | stg_orders    | view | dbt_user
 staging | stg_products  | view | dbt_user
 staging | stg_stores    | view | dbt_user
```

すべて view として materialize されている (dbt_project.yml の `+materialized: view` 通り)。
