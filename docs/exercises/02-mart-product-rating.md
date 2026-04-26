# Exercise 02: 商品評価マートの作成

## シナリオ

マーケ部門から「平均評価が高くてレビュー数も多い商品ランキングが欲しい。既存の売上マート（`mart_product_sales`）と並べて見たい」と依頼が来た。Exercise 01 で作った `stg_reviews` を土台に、intermediate と marts を組み立てる。

## 学べること

- intermediate model のスコープ（複数 staging を集計に絞り込む）
- 集計（`count(*)` / `avg(rating)` / `max(posted_date)`）
- 既存 mart との JOIN（`ref('mart_product_sales')`）
- `WHERE` ではなく `HAVING` 相当のしきい値フィルタ（CTE 後段で扱う方法）

## 前提

- Exercise 01 完了（`staging.stg_reviews` がある）
- main HEAD 完了状態（`marts.mart_product_sales` が存在する）

## 入力データ

新たな CSV は不要。Exercise 01 の `stg_reviews` と既存の `stg_products` / `mart_product_sales` を使う。

## 課題

### Step 1: intermediate `int_product_reviews.sql`

`dbt/models/exercises/02/int_product_reviews.sql` を作る。

要件:

- 商品ID 単位に集計する
- 列: `product_id`, `review_count`, `avg_rating` (numeric(4,2)), `last_review_date`
- materialization は view（intermediate のデフォルトに揃える、または `{{ config(materialized='view', schema='intermediate') }}`）

### Step 2: marts `mart_top_rated_products.sql`

`dbt/models/exercises/02/mart_top_rated_products.sql` を作る。

要件:

- `int_product_reviews` を起点に
- `stg_products` と JOIN して `product_name` / `category` を付与
- 既存 `mart_product_sales` と JOIN して `total_sales_amount` を付与（売上 0 の商品は出ない LEFT JOIN でも INNER JOIN でも可、決めて理由を書く）
- フィルタ: `avg_rating >= 4.0` AND `review_count >= 10`
- ソート: `avg_rating` 降順、`review_count` 降順
- materialization は table（marts のデフォルト、または明示で `{{ config(materialized='table', schema='marts') }}`）

### Step 3: テスト

`dbt/models/exercises/02/schema.yml` を作る。

- `int_product_reviews.product_id`: `not_null` / `unique`
- `int_product_reviews.review_count`: `not_null`
- `int_product_reviews.avg_rating`: `not_null`
- `mart_top_rated_products.product_id`: `not_null` / `unique`
- `mart_top_rated_products.avg_rating`: `not_null`

custom singular test を 1 本書くと尚可:

- `dbt/tests/exercises/assert_avg_rating_in_range.sql`（`dbt/tests/` は MVP のものに混ぜず、サブディレクトリで分離）。`avg_rating < 1 OR avg_rating > 5` を返す行を SELECT する。

### Step 4: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select int_product_reviews mart_top_rated_products
../.venv/bin/dbt test --profiles-dir . --select int_product_reviews mart_top_rated_products
```

## 完了条件

- [ ] `dbt run --select int_product_reviews mart_top_rated_products` が成功
- [ ] `dbt test --select int_product_reviews mart_top_rated_products` が成功
- [ ] `marts.mart_top_rated_products` が `1 行以上` 存在する（avg_rating >= 4.0 と review_count >= 10 を両方満たす商品）
- [ ] `SELECT * FROM marts.mart_top_rated_products ORDER BY avg_rating DESC LIMIT 5;` で TOP 5 が見える

## ヒント（詰まったら）

- **`avg(rating)` の型**: `avg(rating::numeric)` でキャストすると 4 桁スケールの decimal が返る。`numeric(4,2)` に明示キャストしておくと下流で扱いやすい（マートは `numeric(4,2)` 推奨）。
- **しきい値フィルタの場所**: 集計直後の WHERE は集計前に評価されるので使えない。CTE で集計を済ませてから次の SELECT で WHERE をかけるか、`HAVING` を使う。今回は CTE 方式が読みやすい。
- **JOIN 方式**: `mart_product_sales` は全商品 100 件を網羅している（売上 0 の商品も `mart_product_sales` には出ない可能性）。INNER で繋ぐとレビューはあるが売上 0 の商品が落ちる。学習者の好みで INNER / LEFT を選び、解答例の方針と比較すると面白い。
- **ref の依存追跡**: `mart_top_rated_products.sql` から `{{ ref('mart_product_sales') }}` を呼ぶと、dbt はこの新マートを `mart_product_sales` の下流として DAG に組み込む。`dbt run --select +mart_top_rated_products` で MVP 側のマートまで一緒に作り直せるか確認すると面白い。

## 解答例

詳細は [`solutions/02-mart-product-rating.solution.md`](solutions/02-mart-product-rating.solution.md) を参照。
