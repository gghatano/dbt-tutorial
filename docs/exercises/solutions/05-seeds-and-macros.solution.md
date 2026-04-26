# Exercise 05 解答例

## Step 1: `dbt/seeds/exercises/prefectures.csv`

```csv
prefecture,region
北海道,北海道
青森県,東北
岩手県,東北
宮城県,東北
秋田県,東北
山形県,東北
福島県,東北
茨城県,関東
栃木県,関東
群馬県,関東
埼玉県,関東
千葉県,関東
東京都,関東
神奈川県,関東
新潟県,中部
富山県,中部
石川県,中部
福井県,中部
山梨県,中部
長野県,中部
岐阜県,中部
静岡県,中部
愛知県,中部
三重県,関西
滋賀県,関西
京都府,関西
大阪府,関西
兵庫県,関西
奈良県,関西
和歌山県,関西
鳥取県,中国
島根県,中国
岡山県,中国
広島県,中国
山口県,中国
徳島県,四国
香川県,四国
愛媛県,四国
高知県,四国
福岡県,九州
佐賀県,九州
長崎県,九州
熊本県,九州
大分県,九州
宮崎県,九州
鹿児島県,九州
沖縄県,九州
```

47 行。`wc -l` すると 48（ヘッダ込）。

## Step 2: `dbt/seeds/exercises/_seeds.yml`

```yaml
version: 2

seeds:
  - name: prefectures
    description: "47 都道府県 → 地方区分マスタ。"
    config:
      schema: staging
      column_types:
        prefecture: text
        region: text
    columns:
      - name: prefecture
        description: "Primary key. Joinable to stg_stores.prefecture."
        tests:
          - not_null
          - unique
      - name: region
        description: "Geographic region (北海道/東北/関東/中部/関西/中国/四国/九州)."
        tests:
          - not_null
          - accepted_values:
              arguments:
                values:
                  - 北海道
                  - 東北
                  - 関東
                  - 中部
                  - 関西
                  - 中国
                  - 四国
                  - 九州
```

**ポイント**:

- `config.schema: staging` で MVP の `get_custom_schema.sql` を経由し、`staging.prefectures` テーブルになる。
- `column_types` を明示しない場合、dbt-postgres は CSV から型を推定する（短い CSV だと varchar(数字) になりがちで使いにくい）。`text` を明示すると安心。
- `accepted_values` で region 8 種類を lock しているので、CSV にタイポが入ると seed 直後の test で気づける。

## Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt seed --profiles-dir . --select prefectures
# 1 of 1 OK loaded seed file staging.prefectures .... [INSERT 47 in 0.05s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

../.venv/bin/dbt test --profiles-dir . --select prefectures
# Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4   (not_null x2, unique, accepted_values)
```

```sql
analytics=> SELECT region, count(*) FROM staging.prefectures GROUP BY region ORDER BY 1;
 region | count
--------+-------
 中国   |     5
 中部   |     9
 九州   |     8
 北海道 |     1
 関東   |     7
 関西   |     7
 東北   |     6
 四国   |     4
```

合計 47。

## Step 4: `dbt/macros/exercises/cast_jpy.sql`

```jinja
{#-
    Cast an expression to numeric(14, 2) for JPY money values.

    Usage:
        select {{ cast_jpy('unit_price') }} as unit_price from ...
        select {{ cast_jpy('sum(quantity * unit_price)') }} as revenue from ...

    Why a macro?
        - Centralises the (14, 2) precision/scale choice. If we ever need to
          change to numeric(18, 2) for a higher upper bound, only this macro
          changes.
        - Documents intent: ``cast_jpy`` is more explanatory than `::numeric(14,2)`.
-#}
{% macro cast_jpy(column) -%}
    ({{ column }})::numeric(14, 2)
{%- endmacro %}
```

**ポイント**:

- 引数を `({{ column }})` で括っているのは、`sum(...)` のような式を渡しても優先順位が崩れないようにするため。`cast_jpy('a + b')` が `(a + b)::numeric(14,2)` になる。
- `{# ... #}` でドキュメントコメントを残すと `dbt docs generate` で macro ページに表示される。

## Step 5: `dbt/models/exercises/05/mart_regional_sales.sql`

```sql
{{ config(materialized='table', schema='marts') }}

with order_with_region as (
    select
        iod.order_id,
        iod.order_date,
        iod.quantity,
        iod.sales_amount,
        iod.store_id,
        pref.region
    from {{ ref('int_order_details') }} iod
    inner join {{ ref('stg_stores') }}  s    on iod.store_id  = s.store_id
    inner join {{ ref('prefectures') }} pref on s.prefecture  = pref.prefecture
)
select
    region,
    count(*)                                    as order_count,
    count(distinct store_id)                    as store_count,
    sum(quantity)                               as total_quantity,
    {{ cast_jpy('sum(sales_amount)') }}         as total_sales_amount
from order_with_region
group by region
order by total_sales_amount desc
```

**ポイント**:

- `ref('prefectures')` で seed をモデルと同じ書き方で参照できる（source 介在不要）。これが seed の旨味。
- `cast_jpy('sum(sales_amount)')` が `(sum(sales_amount))::numeric(14, 2)` に展開される。`dbt/target/compiled/local_analytics/models/exercises/05/mart_regional_sales.sql` で確認できる。
- INNER JOIN: prefectures に存在しない都道府県名が `stg_stores` に出現しないことを前提。出現したら集計が落ちるので、accepted_values テストでマスタ側を担保している。

## Step 6: 実行

```bash
../.venv/bin/dbt run --profiles-dir . --select mart_regional_sales
# 1 of 1 OK created sql table model marts.mart_regional_sales ... [SELECT in 0.20s]

../.venv/bin/dbt test --profiles-dir . --select mart_regional_sales
# Done. (count depends on schema.yml below)
```

`dbt/models/exercises/05/schema.yml`:

```yaml
version: 2

models:
  - name: mart_regional_sales
    description: "Sales aggregated by geographic region (joins stg_stores.prefecture with the prefectures seed)."
    columns:
      - name: region
        tests:
          - not_null
          - unique
      - name: order_count
        tests:
          - not_null
      - name: total_sales_amount
        tests:
          - not_null
```

```sql
analytics=> SELECT * FROM marts.mart_regional_sales ORDER BY total_sales_amount DESC;
 region | order_count | store_count | total_quantity | total_sales_amount
--------+-------------+-------------+----------------+--------------------
 関東   |        2843 |           5 |          15633 |        87654321.00
 中部   |        1965 |           4 |          10880 |        59876543.00
 ...
```

（数値はダミーデータの seed に依存する。MVP の `stores.csv` は 20 都道府県のうち最初の 20 件をサンプリングしているので、登場する region は 6〜7 種類になる。）

## 解説まとめ

1. **seed = git 管理する小さい CSV**: マスタ・対応表・国コード一覧などは seed が最適。`dbt seed` で簡単に schema にロードでき、`ref()` でモデルから参照できる。
2. **`column_types`**: 推定型ではなく明示型を渡すと運用が安定する。文字列は `text`、数値は `numeric(p, s)` を明示。
3. **macro の使い所**: 1 行の SQL でも、**複数モデルで同じパターンが出る** 場合は macro 化する価値がある。`cast_jpy` は一見薄いラッパだが、「金額は 14,2 で揃える」という命名された意図を持たせると、後で `numeric(18, 2)` に変えたくなった時に 1 箇所で済む。
4. **macro vs source vs seed**: 「型変換ロジック → macro」「外部 CSV のロード → source（COPY経由）or seed（dbt経由）」「小さいマスタ表 → seed」のように責務分離する。今回は対応表が小さく更新頻度も低いので seed が綺麗。
5. **macro 展開の確認**: `dbt run` 後の `target/compiled/.../*.sql` を見るのが学習で一番の理解促進になる。
