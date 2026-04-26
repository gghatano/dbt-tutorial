# task-002: generate_dummy_data.py

- Phase: 03
- Status: Todo
- Owner: -
- Depends on: -（実装はrequirements.txtに依存しない、実行は依存）
- Parallelizable with: phase-03/task-001

## 目的
Faker で再現性ある4種のCSVを生成する。

## 入力 / 前提
- spec §5 / §11.1

## 成果物
- `scripts/generate_dummy_data.py`
- 実行後: `data/raw/customers.csv`(1,000) / `products.csv`(100) / `stores.csv`(20) / `orders.csv`(10,000)

## 受入条件
- 同一seedで2回実行し、CSVの内容が完全一致
- 件数がspec通り
- orders は customers/products/stores の id を参照（外部キー整合）
- products に `category` 列を含む（mart_product_sales で使用）
- orders に `order_date`, `quantity`, `unit_price` を含み、quantity > 0, unit_price > 0
- customers に `customer_name` を含む

## 実装メモ / 判断ログ
- seed: `Faker.seed(42)`, `random.seed(42)`
- order_date: 過去365日間でランダム
- unit_price: products から参照（orders.unit_priceは生成時点のスナップショット）
- ロケールは `ja_JP`（日本語名）デフォルト
