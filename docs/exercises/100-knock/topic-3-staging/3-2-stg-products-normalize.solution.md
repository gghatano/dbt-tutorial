# 3-2 解答例

## dbt/models/100-knock/topic-3/stg_products_100knock.sql

```sql
{{ config(materialized='view', schema='staging') }}

-- Staging contract for raw_100knock.products (Topic ③ Q2).
--
-- category 列は raw に表記揺れ ("Electronics" / "electronics " / "  ELECTRONICS")
-- が混入する可能性を見越し、staging で 1 度だけ正規化する:
--   - trim()  : 前後の空白を除去
--   - lower() : 大文字小文字を統一
-- 下流のマート / KPI はこの綺麗な category を信頼して GROUP BY できる。
select
    product_id::bigint                          as product_id,
    product_name::text                          as product_name,
    lower(trim(category))::text                 as category,
    unit_price::numeric(10, 2)                  as unit_price
from {{ source('raw_100knock', 'products') }}
```

**ポイント**:

- **正規化は staging で 1 度だけ**: マート層で `lower(trim(...))` を毎回書くと、
  - (1) 同じロジックが複数モデルに散らばる (DRY 違反)
  - (2) どこかで書き忘れて表記揺れがこっそり残る (サイレントなバグ)
  - (3) `category` で GROUP BY する SQL がインデックス利かない (パフォーマンス劣化)
  という 3 重苦になる。staging で「契約として」正規化する。
- **元の `category` を上書き**: 演習では原本を残さない構成にした。
  もし「raw の表記そのものを監査ログとして見たい」要件があるなら
  `category::text as category_raw, lower(trim(category))::text as category` の 2 列構成にする。
- **`unit_price::numeric(10, 2)`**: int から精度のある型に持ち上げ。
  3-3 で `orders.unit_price` を同じ型に揃える伏線。
- **`view` materialization**: 100 行しかないので table にする旨味もない。staging の
  原則 = view のまま。

## dbt/models/100-knock/topic-3/schema.yml (3-1 に追記する形)

```yaml
version: 2

models:
  - name: stg_customers_100knock
    description: "Type-cast staging view of raw.customers (100-knock topic-3)."
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique

  - name: stg_products_100knock
    description: "Type-cast staging view of raw.products. category は lower(trim(...)) で正規化済み。"
    columns:
      - name: product_id
        description: "Primary key (bigint)."
        tests:
          - not_null
          - unique
      - name: product_name
        description: "商品名。"
      - name: category
        description: "正規化済み (lower + trim) のカテゴリ。下流は表記揺れを気にせず GROUP BY できる。"
        tests:
          - not_null
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null
```

## 実行例

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select stg_products_100knock
1 of 1 OK created sql view model staging.stg_products_100knock ... [CREATE VIEW in 0.07s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
1 of 4 PASS not_null_stg_products_100knock_product_id ... [PASS]
2 of 4 PASS unique_stg_products_100knock_product_id ..... [PASS]
3 of 4 PASS not_null_stg_products_100knock_category ..... [PASS]
4 of 4 PASS not_null_stg_products_100knock_unit_price ... [PASS]
Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

正規化の効きを SQL で確認:

```sql
analytics=> SELECT count(*) FROM staging.stg_products_100knock
            WHERE category != lower(trim(category));
 count
-------
     0     -- 正規化成功 (表記揺れ 0 件)

analytics=> SELECT category, count(*)
            FROM staging.stg_products_100knock
            GROUP BY 1 ORDER BY 1;
  category   | count
-------------+-------
 books       |    21
 clothing    |    19
 electronics |    20
 groceries   |    18
 toys        |    22
```

5 値の enum で揃っているのが目視で確認できる。

## わざと壊して FAIL を体感する

`raw.products` の 1 行に表記揺れを入れて、`sql_assert` 採点が落ちることを確認:

```sql
UPDATE raw.products SET category = '  Electronics  ' WHERE product_id = 1;
```

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select stg_products_100knock
$ psql ... -c "SELECT count(*) FROM staging.stg_products_100knock WHERE category != lower(trim(category));"
 count
-------
     0    -- staging で正規化済みなので 0 のまま!
```

**つまり sql_assert は staging の正規化が効いている限り PASS し続ける**。逆に
正規化を staging から外すと、raw の汚れがそのまま素通しになって sql_assert が FAIL する。
これが「staging contract = データの不変条件をコードで宣言する」 という意味。

## 解説まとめ

- **正規化は staging の責務**: raw は「物理境界 (Topic ②)」、staging は「論理契約」。
  「表記が揺れない」 という不変条件は契約側 = staging が保証する。
- **`lower(trim(...))` イディオム**: 文字列正規化の最頻出パターン。
  staging で 1 度書く / 他の文字列列にも横展開できる。
- **sql_assert で データ側から検証**: schema.yml の `tests:` は「行レベルの宣言」
  だが、`SELECT count(*) WHERE col != lower(trim(col)) = 0` は「**集計レベルの不変条件**」。
  両方を組み合わせて「列の値域 / 不変条件」を多層で守るのが staging contract の運用。
- **distinct カウントを見る習慣**: 正規化後は `SELECT category, count(*) GROUP BY 1` で
  必ず distinct 値の一覧を目視する。5 値想定なのに 7 値出ていれば即「raw の事故」と分かる。
- **下流の安心感**: マート / BI が `WHERE category = 'electronics'` と書けば確実にヒットする。
  これが staging を整える究極の目的 = **下流の認知負荷をゼロにする**。
