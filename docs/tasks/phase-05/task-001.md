# task-001: int_order_details

- Phase: 05
- Status: Todo
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
- sales_amount > 0（custom test）

## 実装メモ / 判断ログ
- materialization: view
- 結合は INNER JOIN（外部キー欠損は staging で弾かれている前提）
