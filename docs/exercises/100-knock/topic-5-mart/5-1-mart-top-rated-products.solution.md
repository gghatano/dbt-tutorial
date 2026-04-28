# 5-1 解答例

## dbt/models/100-knock/topic-5/mart_top_rated_products_100knock.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- ============================================================================
-- mart_top_rated_products_100knock
-- ----------------------------------------------------------------------------
-- grain          : 1 product 1 row (product_id is unique).
-- business filter: avg_rating >= 4.0 AND review_count >= 10
--                  (= "高評価かつレビュー件数が信頼に足る商品" の業務定義)
-- consumers      : Metabase "Top Products" dashboard, marketing team weekly review
-- upstream       : int_product_reviews_100knock (集計済みレビュー)
--                  stg_products_100knock         (master data)
--                  mart_product_sales            (MVP 売上 mart, 売上連結)
-- ============================================================================

with reviews as (
    select * from {{ ref('int_product_reviews_100knock') }}
),

products as (
    select
        product_id,
        product_name,
        category
    from {{ ref('stg_products_100knock') }}
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

- **冒頭の grain / filter / consumer 宣言ブロック**: コメントを 9 行使って
  「この mart は何者か」を SQL 自身に書き残す。後から読んだ人 (自分含む) が
  WHERE / GROUP BY を見るより先に意図を掴める。Topic ⑤ 全 mart で同じ
  ヘッダ形式を使う癖をつけるのが本問の狙い。
- **`avg_rating >= 4.0 AND review_count >= 10`**: `4.0` (浮動小数) と `10` の
  しきい値はビジネス側からの要求。これを **mart 内の WHERE で実装** すること
  自体が業務契約。intermediate に書いてしまうと、「レビュー数が少ない商品も
  使いたい別 mart」が後から作れなくなる。
- **LEFT JOIN + COALESCE(0)**: 「売上ゼロだが高評価レビューが付いている商品」
  をランキングから落とさない設計。INNER JOIN にすると売上 mart 由来の欠損が
  即ドロップにつながる。設計判断はコメントに残しておくと議論の起点になる。
- **`mart_product_sales` を ref**: 100-knock 内で完結させたければ
  `int_order_details_100knock` を直接集計してもよいが、本問は grain 宣言が
  主眼なので、依存先は薄くまとめた。

## dbt/models/100-knock/topic-5/schema.yml (この問の最小版)

```yaml
version: 2

models:
  - name: mart_top_rated_products_100knock
    description: |
      Products with avg_rating >= 4.0 AND review_count >= 10.
      Grain: 1 product 1 row. Used by Metabase "Top Products" dashboard.
    columns:
      - name: product_id
        description: "Primary key (FK to stg_products_100knock.product_id)."
        tests:
          - not_null
          - unique
      - name: product_name
        description: "Display name of the product."
      - name: category
        description: "Product category (8 categories)."
        tests:
          - not_null
      - name: review_count
        description: "Number of reviews for this product (>= 10 by business filter)."
        tests:
          - not_null
      - name: avg_rating
        description: "Average rating, numeric(4,2). >= 4.0 by business filter."
        tests:
          - not_null
      - name: last_review_date
        description: "Most recent review date for this product."
      - name: total_sales_amount
        description: "Lifetime sales amount from mart_product_sales (numeric(18,2)). 0 if no sales."
        tests:
          - not_null
```

**ポイント**:

- **`product_id` の `not_null + unique` が grain 宣言の検証**: コメントで
  「1 product 1 row」と書いただけでは保証されない。`unique` test がコードに
  あって初めて、CI が grain 違反を検知できる。
- **description に業務しきい値を書く**: SQL コメントは SQL を読む人向け、
  schema.yml の description は `dbt docs` を見る人 (BI 担当) 向け。同じ宣言を
  二箇所に書くのは冗長に見えるが、読者が違うので両方必要。
- **`accepted_values` for category は省略**: 3-2 / MVP 側 staging で既に
  category の有限集合は test 済みのため、mart 側で重複させない。

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt run --profiles-dir . --select mart_top_rated_products_100knock
04:31:10  1 of 1 START sql table model marts.mart_top_rated_products_100knock ... [RUN]
04:31:10  1 of 1 OK   created sql table model marts.mart_top_rated_products_100knock [in 0.30s]
04:31:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select mart_top_rated_products_100knock
04:31:20  PASS  not_null_mart_top_rated_products_100knock_product_id ...
04:31:20  PASS  unique_mart_top_rated_products_100knock_product_id   ...
04:31:20  Done. PASS=6 WARN=0 ERROR=0 SKIP=0 TOTAL=6
```

`psql` でしきい値が効いていることを確認:

```sql
analytics=> SELECT count(*) FROM marts.mart_top_rated_products_100knock
            WHERE avg_rating < 4.0 OR review_count < 10;
 count
-------
     0     -- 0 行 = しきい値違反なし = WHERE が効いている
```

## 解説まとめ

- **mart の最初の作業はコメントを書くこと**: 「grain は何か」「業務しきい値は
  何か」「誰が消費するか」を SQL 上部に書いてから、初めて WHERE / SELECT を
  書く。順序が逆だと、設計意図が SQL の挙動の中に埋もれる。
- **grain 宣言は `unique` test で機械検証**: コメントは人向けの宣言だが、
  CI は SQL を読まない。`schema.yml` の `unique` test が grain 宣言の機械
  可読版。両方揃って初めて mart の grain が「契約」になる。
- **業務しきい値は mart で実装する理由**: 「平均評価 4 以上」という基準は
  business rule であり、レビュー集計そのもの (intermediate の責務) ではない。
  intermediate には全件を残し、mart で初めて選別する。これにより別 mart
  (例: `mart_low_rated_products`) を後付けできる。
- **MVP との `_100knock` suffix 命名**: dbt は同名 model を許さないので、
  100-knock 演習の mart には全て `_100knock` を付ける。MVP の
  `mart_top_rated_products` (Ex.02 で作られたもの、または将来追加予定) と
  並走可能になる。
- **`manifest_lineage` で何を見るか**: CI は SQL を読まないが
  `target/manifest.json` の `depends_on` は読める。「`int_product_reviews_100knock`
  を ref していること」を grading が確認することで、学習者が `stg_reviews` から
  ショートカットしていないかが分かる (= 設計の階層を守れているかの検証)。
