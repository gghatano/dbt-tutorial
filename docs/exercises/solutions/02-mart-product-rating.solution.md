# Exercise 02 解答例

## Step 1: `dbt/models/exercises/02/int_product_reviews.sql`

```sql
{{ config(materialized='view', schema='intermediate') }}

select
    product_id,
    count(*)                                        as review_count,
    avg(rating::numeric)::numeric(4, 2)             as avg_rating,
    max(posted_date)                                as last_review_date
from {{ ref('stg_reviews') }}
group by product_id
```

**ポイント**:

- `count(*)` はレビュー件数（重複顧客カウント込み、ビジネス的には「投稿回数」）。
- `avg(rating)` をいきなり書くと Postgres は `numeric` を返すが scale が予測しにくい。`numeric(4,2)` に明示キャストして、下流マートで桁ぶれを起こさない。
- `last_review_date` は Exercise 01 の派生列 `posted_date` をそのまま `max()` できる。

## Step 2: `dbt/models/exercises/02/mart_top_rated_products.sql`

```sql
{{ config(materialized='table', schema='marts') }}

with reviews as (
    select * from {{ ref('int_product_reviews') }}
),
products as (
    select * from {{ ref('stg_products') }}
),
sales as (
    select
        product_id,
        total_sales_amount
    from {{ ref('mart_product_sales') }}
)
select
    r.product_id,
    p.product_name,
    p.category,
    r.review_count,
    r.avg_rating,
    r.last_review_date,
    coalesce(s.total_sales_amount, 0)::numeric(18, 2) as total_sales_amount
from reviews r
inner join products p on r.product_id = p.product_id
left  join sales    s on r.product_id = s.product_id
where r.avg_rating   >= 4.0
  and r.review_count >= 10
order by r.avg_rating desc, r.review_count desc
```

**ポイント**:

- 3 つの CTE で source を整理 → メイン SELECT が読みやすい。
- `mart_product_sales` には全 100 商品が必ず出ているとは限らない（注文ゼロの商品は出ない）。`LEFT JOIN + COALESCE` で「売上 0 円」を許容する設計にした。`INNER JOIN` だと売上ゼロの高評価商品（あれば）がランキングから消える。
- `where` は CTE 段階で集計済みの値に対して使うので問題なく動く。`HAVING` の代用としての CTE フィルタは dbt で頻出パターン。

## Step 3: `dbt/models/exercises/02/schema.yml`

```yaml
version: 2

models:
  - name: int_product_reviews
    description: "Per-product review aggregates (count / avg / last date)."
    columns:
      - name: product_id
        description: "Primary key. FK to stg_products.product_id."
        tests:
          - not_null
          - unique
          - relationships:
              arguments:
                to: ref('stg_products')
                field: product_id
      - name: review_count
        tests:
          - not_null
      - name: avg_rating
        tests:
          - not_null
      - name: last_review_date

  - name: mart_top_rated_products
    description: |
      Products with avg_rating >= 4.0 and review_count >= 10, joined with
      mart_product_sales to surface revenue alongside ratings.
    columns:
      - name: product_id
        description: "Primary key."
        tests:
          - not_null
          - unique
      - name: product_name
      - name: category
      - name: review_count
        tests:
          - not_null
      - name: avg_rating
        tests:
          - not_null
      - name: total_sales_amount
        tests:
          - not_null
```

### 任意: custom singular test

`dbt/tests/exercises/assert_avg_rating_in_range.sql`:

```sql
-- avg_rating must stay within [1, 5].
select
    product_id,
    avg_rating
from {{ ref('int_product_reviews') }}
where avg_rating < 1 or avg_rating > 5
```

`dbt/dbt_project.yml` の `test-paths` は `["tests"]` なので、`dbt/tests/` 直下にサブディレクトリを切れば自動的に拾われる（MVP の `assert_*.sql` 群とは混ざらない）。

## Step 4: 実行例

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select int_product_reviews mart_top_rated_products
# 1 of 2 OK created sql view  model intermediate.int_product_reviews ...
# 2 of 2 OK created sql table model marts.mart_top_rated_products .....
# Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2

../.venv/bin/dbt test --profiles-dir . --select int_product_reviews mart_top_rated_products
# Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8
```

`psql` 確認（数値はデータの seed に依存して変動する）:

```sql
analytics=> SELECT product_id, product_name, review_count, avg_rating, total_sales_amount
            FROM marts.mart_top_rated_products
            ORDER BY avg_rating DESC, review_count DESC LIMIT 5;
 product_id |   product_name    | review_count | avg_rating | total_sales_amount
------------+-------------------+--------------+------------+--------------------
         42 | foo_042           |           23 |       4.43 |           845230.00
         ...
```

## 解説まとめ

1. **集計は intermediate に閉じ込める**: 商品単位の `count` / `avg` / `max` は再利用しうるので、`int_product_reviews` という汎用名にして、マート側はフィルタとマスタ JOIN だけに集中させた。
2. **JOIN の方向選択**: `mart_product_sales` は売上が一度も無い商品を持たない。INNER だと「レビュー満点だが注文ゼロ」の商品がドロップする — 学習データではほぼ起きないが、設計判断として `LEFT JOIN + COALESCE(0)` を選ぶのは妥当。
3. **しきい値フィルタの位置**: SQL 標準では集計直後に WHERE は使えないので CTE で集計 → 次の SELECT で WHERE が定石。HAVING でも書けるが、フィルタ条件が複数あるなら CTE の方が読みやすい。
4. **DAG への組み込み**: `mart_top_rated_products` は `mart_product_sales` を ref しているので、dbt は新マートを既存マートの下流として正しく DAG 配置する。`dbt run --select +mart_top_rated_products` で MVP マートまで遡って再構築できる。
