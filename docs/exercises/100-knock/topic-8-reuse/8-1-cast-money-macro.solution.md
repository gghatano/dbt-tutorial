# 8-1 解答例

## dbt/macros/100-knock/topic-8/cast_money.sql

```jinja
{#-
    100-knock Topic ⑧ Q1: 金額系列の numeric cast を集約する macro。

    Usage:
        {{ cast_money('unit_price') }}                  -- numeric(14, 2)  デフォルト
        {{ cast_money('unit_price', 10, 2) }}           -- numeric(10, 2)  positional
        {{ cast_money('quantity * unit_price', precision=14, scale=2) }}  -- keyword

    なぜ macro 化するか:
      金額系の cast 桁数を「将来一斉に変えたい」 場面が必ず来る。
      この macro 1 ファイルに集約しておけば、変更コストは O(1)。
      従来は staging / intermediate / mart に O(N) の grep & 修正が必要だった。
-#}
{% macro cast_money(col, precision=14, scale=2) %}
    {{ col }}::numeric({{ precision }}, {{ scale }})
{% endmacro %}
```

**ポイント**:

- **デフォルト値 `precision=14, scale=2`**: 売上金額の典型的な業務上限
  (`99,999,999,999.99` ≒ 1000 億未満) をカバーする保守的な値。staging の
  `unit_price` は `(10, 2)` で十分なので **明示的に小さい値を渡す**。
- **第 1 引数 `col` は SQL 式**: 列名 (`'unit_price'`) でも、計算式
  (`'quantity * unit_price'`)、集約関数 (`'sum(sales_amount)'`) でも OK。
  jinja は `{{ col }}` をそのまま SQL に埋めるので、quote する必要は **ない**。
- **`numeric` であって `float` ではない**: 会計用途の浮動小数禁忌をこの macro
  経由で「無意識に守れる」状態にする。学習者が手書きで `float` と書く誘惑を断つ。
- **macro 名 = ファイル名**: dbt の慣習。`dbt ls --resource-type macro --select cast_money`
  で見つけやすくなる。

## dbt/models/100-knock/topic-3/stg_orders_100knock.sql (書き換え後)

```sql
{{ config(materialized='view', schema='staging') }}

-- Staging contract for raw_100knock.orders (Topic ③ Q3 + Topic ⑧ Q1).
-- 金額系 cast を cast_money macro に集約 (Topic ⑧ で DRY 化)。
select
    order_id::bigint                            as order_id,
    order_date::date                            as order_date,
    customer_id::bigint                         as customer_id,
    product_id::bigint                          as product_id,
    store_id::bigint                            as store_id,
    quantity::int                               as quantity,
    {{ cast_money('unit_price', 10, 2) }}       as unit_price
from {{ source('raw_100knock', 'orders') }}
```

`unit_price::numeric(10, 2)` → `{{ cast_money('unit_price', 10, 2) }}` の置換。

## dbt/models/100-knock/topic-3/stg_products_100knock.sql (書き換え後 抜粋)

```sql
select
    product_id::bigint                          as product_id,
    product_name::text                          as product_name,
    category::text                              as category,
    {{ cast_money('unit_price', 10, 2) }}       as unit_price
from {{ source('raw_100knock', 'products') }}
```

## dbt/models/100-knock/topic-4/int_order_details_100knock.sql (書き換え後)

```sql
{{ config(materialized='view', schema='intermediate') }}

select
    o.order_id,
    o.order_date,
    o.customer_id,
    c.customer_name,
    o.product_id,
    p.product_name,
    p.category,
    o.store_id,
    o.quantity,
    o.unit_price,
    {{ cast_money('o.quantity * o.unit_price') }} as sales_amount
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

`(quantity * unit_price)::numeric(14, 2)` → `{{ cast_money('o.quantity * o.unit_price') }}`
(デフォルト `precision=14, scale=2` を採用)。

## dbt/models/100-knock/topic-5/mart_top_rated_products_100knock.sql (該当部分)

```sql
select
    r.product_id,
    p.product_name,
    p.category,
    r.avg_rating,
    r.review_count,
    {{ cast_money('coalesce(s.total_sales_amount, 0)') }} as total_sales_amount
from reviews r
inner join products p on r.product_id = p.product_id
left  join sales    s on r.product_id = s.product_id
where r.avg_rating >= 4.0 and r.review_count >= 10
order by r.avg_rating desc
```

## dbt/models/100-knock/topic-5/mart_monthly_by_category_100knock.sql (該当部分)

```sql
select
    date_trunc('month', order_date)::date         as order_month,
    category,
    {{ cast_money('sum(sales_amount)') }}         as monthly_sales_amount,
    count(distinct order_id)                      as order_count
from {{ ref('int_order_details_100knock') }}
group by 1, 2
order by 1, 2
```

## 実行例

```text
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 1 macro (cast_money 含む N 個), ...

$ ../.venv/bin/dbt run --profiles-dir . --select \
    stg_orders_100knock stg_products_100knock int_order_details_100knock \
    mart_top_rated_products_100knock mart_monthly_by_category_100knock
... 5 of 5 PASS ...
Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

compiled SQL を確認:

```bash
$ cat target/compiled/local_analytics/models/100-knock/topic-3/stg_orders_100knock.sql | grep numeric
    unit_price::numeric(10, 2)       as unit_price

$ cat target/compiled/local_analytics/models/100-knock/topic-4/int_order_details_100knock.sql | grep numeric
    (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
```

物理型を確認:

```sql
analytics=> SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema='staging' AND table_name='stg_orders_100knock'
              AND column_name='unit_price';
 column_name | data_type | numeric_precision | numeric_scale
-------------+-----------+-------------------+---------------
 unit_price  | numeric   |                10 |             2
```

`unit_price = numeric(10, 2)` が staging に物理化されている (cast_money 経由でも同じ結果)。

## 解説まとめ

- **macro 引数化の真価は「使用箇所が増えた瞬間」に出る**: 4-6 の `calc_tax` は
  使用箇所 1 つだったが、`cast_money` は staging / intermediate / mart に分散して
  5 箇所以上で使う。「将来 precision を 16 桁に上げたい」 と言われた瞬間、macro 1 行
  (`precision=16` をデフォルトに) で済むか、5 model を grep 修正するかの差が発生する。
- **デフォルト引数 = 安全側の選択**: `precision=14, scale=2` をデフォルトにすると、
  「どの桁数にすべきか分からない学習者」 が `cast_money('amount')` と書いた時、
  会計用途として安全な値が選ばれる。staging だけは「raw の精度に合わせる」 ために
  明示的に `(10, 2)` を渡す = **デフォルト値の override は意図を明示している**。
- **「式」 を引数にできる**: `cast_money('quantity * unit_price')` や
  `cast_money('sum(sales_amount)')` のように **任意 SQL 断片を渡せる** のが macro の
  強み。これが `cast_money_unit_price` / `cast_money_total_sales` のような **列専用関数**
  だったら使い回せず DRY が崩れる。
- **compiled SQL を見る癖**: `target/compiled/.../*.sql` を `cat` すると **macro が
  展開された後の SQL** が見える。学習者は「自分が書いた jinja が SQL になる過程」 を
  目視できる。デバッグの定石。
- **MVP との関係**: MVP の Ex.05 で `cast_jpy` macro が定義されているが、`cast_money` は
  「桁数を引数化した汎用版」 として別名で並走する。Ex.05 と並列に存在するので衝突しない。
- **Topic ⑧ 全体の文脈**: 8-1 は **「自前 macro の引数化」**、8-2 / 8-3 は **「外部
  macro (パッケージ) の取り込み」**、8-4 は **「マスタデータの集約」**、8-5 は
  **「Jinja loop による model 横断 DRY」**。集約手段の引き出しを増やしていく流れ。
