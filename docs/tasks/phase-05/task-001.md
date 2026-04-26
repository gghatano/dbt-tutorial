# task-001: int_order_details

- Phase: 05
- Status: Done
- Owner: -
- Depends on: phase-04/task-002
- Parallelizable with: -

## 目的
注文 × 顧客 × 商品 × 店舗 を結合し、`sales_amount = quantity * unit_price` を持つ中間モデルを作成する。

## 入力 / 前提
- spec §8.3

## 成果物
- `dbt/models/intermediate/int_order_details.sql`
- `dbt/models/intermediate/schema.yml`

## 受入条件
- `dbt run --select int_order_details --profiles-dir .` が成功
- 列: order_id, order_date, customer_id, customer_name, product_id, product_name, category, store_id, quantity, unit_price, sales_amount
- 行数 = stg_orders 件数
- sales_amount > 0（custom test → phase-06 の singular test に委譲）

## 実装メモ / 判断ログ
- materialization: view（dbt_project.yml で intermediate 配下を view 設定済み）
- 結合は INNER JOIN（stg_orders の FK 列に relationships テストがかかっており、staging で外部キー欠損は弾かれる前提）
- `sales_amount` は `(quantity * unit_price)::numeric(14,2)` に明示キャスト。staging の `unit_price` が `numeric(12,2)` なので scale を統一するため。`14,2` は quantity 上限 10 × unit_price 上限 9,990 に対し十分なヘッドルーム。
- `relationships` は dbt 1.11 の deprecation 回避のため `arguments:` 配下にネスト。
- 詳細は `docs/decisions/0006-marts-modeling.md` を参照。

## 実行ログ

### `dbt run --profiles-dir .` (全モデル)
```
Found 8 models, 57 data tests, 4 sources, 466 macros
1 of 8 OK created sql view model staging.stg_customers ............ [CREATE VIEW in 0.09s]
2 of 8 OK created sql view model staging.stg_orders ............... [CREATE VIEW in 0.09s]
3 of 8 OK created sql view model staging.stg_products ............. [CREATE VIEW in 0.09s]
4 of 8 OK created sql view model staging.stg_stores ............... [CREATE VIEW in 0.09s]
5 of 8 OK created sql view model intermediate.int_order_details ... [CREATE VIEW in 0.01s]
6 of 8 OK created sql table model marts.mart_customer_sales ....... [SELECT 1000 in 0.04s]
7 of 8 OK created sql table model marts.mart_daily_sales .......... [SELECT 365  in 0.04s]
8 of 8 OK created sql table model marts.mart_product_sales ........ [SELECT 100  in 0.04s]

Done. PASS=8 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8
```

### `dbt test --profiles-dir .`
```
Done. PASS=57 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=57
```

### DB 確認
```
\dv intermediate.*
 Schema       | Name              | Type | Owner
 intermediate | int_order_details | view | dbt_user

SELECT count(*) FROM intermediate.int_order_details;  -- 10000
```
