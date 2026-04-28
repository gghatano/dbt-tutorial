# 5-2 解答例

## dbt/packages.yml

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.0.0", "<2.0.0"]
```

```bash
$ cd dbt
$ ../.venv/bin/dbt deps --profiles-dir .
04:30:00  Installing dbt-labs/dbt_utils
04:30:01  Installed from version 1.x.x
```

## dbt/models/100-knock/topic-5/mart_monthly_sales_by_category_100knock.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- ============================================================================
-- mart_monthly_sales_by_category_100knock
-- ----------------------------------------------------------------------------
-- grain          : 1 (month, category) combination = 1 row.
--                  primary key is the surrogate hash of (month, category).
-- consumers      : Metabase "Monthly Sales by Category" line chart,
--                  exec dashboard
-- upstream       : int_order_details_100knock
-- ============================================================================

with details as (
    select
        date_trunc('month', order_date)::date as month,
        category,
        order_id,
        quantity,
        sales_amount
    from {{ ref('int_order_details_100knock') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['month', 'category']) }} as monthly_category_id,
    month,
    category,
    count(distinct order_id)             as order_count,
    sum(quantity)                        as total_quantity,
    sum(sales_amount)::numeric(18, 2)    as total_sales_amount
from details
group by month, category
order by month, category
```

**ポイント**:

- **冒頭コメントで複合 grain を宣言**: `1 (month, category) combination = 1 row`
  と書く。grain が単一列ではないことを最初に伝える。
- **`date_trunc('month', order_date)::date as month`**: Postgres の
  `date_trunc('month', ...)` は timestamp を返す。日付軸 BI で扱いやすいよう
  `::date` で揃える。これで `2026-04-01` のような月初日付が並ぶ。
- **`generate_surrogate_key(['month', 'category'])`**: 内部的には
  `md5(coalesce(cast(month as varchar), '_dbt_utils_surrogate_key_null_') || '-' ||
  coalesce(cast(category as varchar), '...'))` のような展開。**md5 ハッシュなので
  衝突は実用上ゼロ**。複合 PK を単一 ID に圧縮するパターン。
- **`count(distinct order_id)`**: `int_order_details` は注文明細単位 (= 1 注文に
  複数行) なので、注文数を数えるには distinct が必要。
- **`order by month, category` を最後に**: table materialization なら
  実テーブルに sort 順は残らないが、`dbt run` の log や `psql \d` で確認する
  ときに見やすい。

## dbt/models/100-knock/topic-5/schema.yml (この問の追記分)

```yaml
version: 2

models:
  # ... (5-1 の mart_top_rated_products_100knock も同居)

  - name: mart_monthly_sales_by_category_100knock
    description: |
      Monthly sales aggregation by product category.
      Grain: 1 (month, category) combination = 1 row.
      Used by Metabase "Monthly Sales by Category" line chart.
    columns:
      - name: monthly_category_id
        description: |
          Surrogate primary key. md5 hash of (month, category) generated
          by dbt_utils.generate_surrogate_key. Unique by grain definition.
        tests:
          - not_null
          - unique
      - name: month
        description: "First day of the month (date), from date_trunc('month', order_date)."
        tests:
          - not_null
      - name: category
        description: "Product category (8 categories from stg_products)."
        tests:
          - not_null
      - name: order_count
        description: "Distinct order_id count for the month/category."
        tests:
          - not_null
      - name: total_quantity
        description: "Sum of quantity for the month/category."
        tests:
          - not_null
      - name: total_sales_amount
        description: "Sum of sales_amount for the month/category, numeric(18,2)."
        tests:
          - not_null
```

**ポイント**:

- **`unique` を `monthly_category_id` に貼る = 複合 grain の宣言検証**:
  `(month, category)` の組合せが mart 内で 2 回出現したらこの test が落ちる。
  GROUP BY が間違っていることを CI が機械的に教えてくれる安全弁。
- **`description` で「Surrogate primary key. md5 hash of (month, category)」**:
  BI 担当が dbt docs を見たとき、なぜ意味のないハッシュ列が PK なのかが分かる。
  「ここは加工せずそのまま使ってね」のサイン。
- **`(month, category)` 自体に dbt_utils の `unique_combination_of_columns` test
  を貼ってもよい**: より直接的に複合 grain を表現できる。本問は最小構成として
  surrogate key + unique で進めるが、dbt-utils を使い慣れたら
  `dbt_utils.unique_combination_of_columns` も選択肢。

## 実行例

```bash
$ ../.venv/bin/dbt deps --profiles-dir .
$ ../.venv/bin/dbt run --profiles-dir . --select mart_monthly_sales_by_category_100knock
04:31:10  1 of 1 OK created sql table model marts.mart_monthly_sales_by_category_100knock [in 0.40s]
04:31:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select mart_monthly_sales_by_category_100knock
04:31:20  PASS not_null_mart_monthly_sales_by_category_100knock_monthly_category_id ...
04:31:20  PASS unique_mart_monthly_sales_by_category_100knock_monthly_category_id   ...
04:31:20  Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8
```

`psql` で確認:

```sql
analytics=> SELECT month, category, total_sales_amount
            FROM marts.mart_monthly_sales_by_category_100knock
            ORDER BY month, category LIMIT 10;
   month    | category    | total_sales_amount
------------+-------------+--------------------
 2026-01-01 | Apparel     |          234560.00
 2026-01-01 | Beauty      |          189230.00
 ...

-- grain 違反チェック (本来は test で済むが手動でも):
analytics=> SELECT month, category, count(*)
            FROM marts.mart_monthly_sales_by_category_100knock
            GROUP BY month, category HAVING count(*) > 1;
 (0 rows)     -- grain 違反 0
```

## 解説まとめ

- **複合 grain の宣言は「PK をどう作るか」とセット**: `(month, category)` で
  unique と書きたいが、SQL の test は単一列を想定するものが多い。サロゲート
  キー化することで「単一列の unique test 1 本」で複合 grain が機械検証できる。
- **`dbt_utils.generate_surrogate_key` の中身は md5 ハッシュ**: 衝突確率は
  事実上ゼロ。引数列を `||` で連結し NULL を sentinel 文字列で埋める。
  順序依存なので `(['month', 'category'])` と `(['category', 'month'])` は
  違う ID になる点に注意。一度決めたら永遠に同じ順序で揃える。
- **mart の grain は BI が GROUP BY する単位**: 「月別売上を見たい」「カテゴリ別
  売上を見たい」「月 × カテゴリで見たい」の 3 つは別 mart に分ける設計が
  自然。BI 側で複雑な GROUP BY を書かせない = mart で完結させる、が分業設計。
- **dbt-utils の意義**: surrogate key 生成、`pivot`、`star`、
  `unique_combination_of_columns` test などの「みんな書きたい SQL」を
  パッケージ化したもの。1 回 deps すれば全 mart で共有できる。
- **サロゲート vs ナチュラル PK**: ナチュラル PK (`(month, category)`) は
  人が読める利点があり、サロゲート PK は外部参照しやすい利点がある。mart で
  外部 (BI / API) に公開する場合はサロゲートを推奨。
