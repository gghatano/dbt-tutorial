# 3-3 解答例

## dbt/models/100-knock/topic-3/stg_orders_100knock.sql

```sql
{{ config(materialized='view', schema='staging') }}

-- Staging contract for raw_100knock.orders (Topic ③ Q3).
--
-- 型を staging で確定させる:
--   - order_date  : text (CSV 由来)        → date
--   - unit_price  : int  (raw 段階の素朴型) → numeric(10, 2)  [金額は必ず numeric]
--   - その他は raw 型そのまま (bigint / int)
--
-- 下流のマートはこの型を信頼して SUM(unit_price) や
-- WHERE order_date BETWEEN ... を書ける。
select
    order_id::bigint                            as order_id,
    order_date::date                            as order_date,
    customer_id::bigint                         as customer_id,
    product_id::bigint                          as product_id,
    store_id::bigint                            as store_id,
    quantity::int                               as quantity,
    unit_price::numeric(10, 2)                  as unit_price
from {{ source('raw_100knock', 'orders') }}
```

**ポイント**:

- **`order_date::date`**: raw に text として入った `'2025-08-13'` を date 型に持ち上げる。
  これで下流が `WHERE order_date >= '2026-01-01'` を書いたときに **型を意識せず**
  比較できる。text のままだと `'2025-12-31' >= '2026-01-01'` のような文字列辞書順比較が
  発生して事故る (実際にはこの 2 文字列は辞書順でも同じ並びだが、`'2025-9-1' < '2025-12-1'`
  などで破綻する)。
- **`unit_price::numeric(10, 2)`**: int で十分そうに見えるが、将来「割引率を反映した
  単価」「税込み単価」など小数を含む計算が必要になる瞬間が必ず来る。
  staging で先に numeric に持ち上げておくと、その瞬間に SQL を一切変えずに済む。
- **`numeric` であって `float` ではない**: 浮動小数は丸め誤差が出るので会計用途で禁忌。
  Postgres の `numeric` は任意精度なのでこの問題が起きない。
- **配列の順序固定**: `order_id, order_date, customer_id, ...` の順序は raw とも
  揃えてあるが、staging で別の順に並び替えてもよい。重要なのは **「列順を契約として
  宣言する」** こと自体。
- **`view` materialization**: 10,000 行は view でも十分に速い。table にして storage を
  使う必要はない。

## dbt/models/100-knock/topic-3/schema.yml (3-2 までに追記する形)

```yaml
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders. order_date は date, unit_price は numeric(10,2)。"
    columns:
      - name: order_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date 型)。下流の日次集計で BETWEEN しやすい。"
        tests:
          - not_null
      - name: customer_id
        tests:
          - not_null
      - name: product_id
        tests:
          - not_null
      - name: store_id
        tests:
          - not_null
      - name: quantity
        tests:
          - not_null
      - name: unit_price
        description: "単価 (numeric(10,2))。金額は必ず numeric。"
        tests:
          - not_null
```

3-4 で `relationships` テストを本格的に書くので、ここでは FK の `not_null` のみで OK。

## 実行例

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select stg_orders_100knock
1 of 1 OK created sql view model staging.stg_orders_100knock ... [CREATE VIEW in 0.13s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... 全 7 件 PASS ...
Done. PASS=7 WARN=0 ERROR=0 SKIP=0 TOTAL=7
```

物理型を確認:

```sql
analytics=> SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema='staging' AND table_name='stg_orders_100knock'
            ORDER BY ordinal_position;
 column_name |  data_type   | numeric_precision | numeric_scale
-------------+--------------+-------------------+---------------
 order_id    | bigint       |                64 |             0
 order_date  | date         |                   |
 customer_id | bigint       |                64 |             0
 product_id  | bigint       |                64 |             0
 store_id    | bigint       |                64 |             0
 quantity    | integer      |                32 |             0
 unit_price  | numeric      |                10 |             2
```

`order_date = date` / `unit_price = numeric(10, 2)` が確かに staging に物理化されている。

## わざと壊して FAIL を体感する

`order_date` の cast を取って `text` のままにしてみる:

```sql
-- 改悪版 (やってはいけない)
select order_date as order_date, ... from {{ source('raw_100knock', 'orders') }}
```

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select stg_orders_100knock
... PASS ...

$ psql ... -c "SELECT data_type FROM information_schema.columns WHERE table_schema='staging' AND table_name='stg_orders_100knock' AND column_name='order_date'"
 data_type
-----------
 text          -- staging が text を公開してしまった!
```

下流のマートが `WHERE order_date >= '2026-01-01'::date` のように date を期待していると、
ここで型ミスマッチで集計が壊れる。staging contract が崩れた瞬間に下流が落ちる、
という連鎖が起きる。**だからこそ「staging の物理型を採点で検証する」 のは重要**。

## 解説まとめ

- **staging の最重要責務 = 型の境界を確定する**: raw の型は不安定 (CSV 起源 / DDL の
  バージョン違い / 型推論の癖)。staging で `::date` `::numeric` を書き切ると、
  以降は **下流が型を意識しなくてよくなる**。
- **金額は必ず `numeric`**: 浮動小数の丸め誤差を会計に持ち込まない、というデータ基盤の
  鉄則。`numeric(10, 2)` の `(10, 2)` は「全桁数, 小数桁数」で、業務要件 (上限金額) に
  合わせて選ぶ。
- **`information_schema` で staging を検証**: dbt の test は「行レベルの不変条件」を
  見るが、`information_schema.columns` を覗く SQL は「**列の物理型** という structural
  な不変条件」を見る。両方を組み合わせて staging contract を多層で守る。
- **明示 cast の保守的価値**: 「raw が text のまま staging に滑り込む」 という
  サイレントな型崩れを防ぐ。staging で `::date` と書いていれば、raw の text が
  ISO 8601 でなくなった瞬間に dbt run が即 ERROR になる (= 早期検知)。
- **`view` でなぜ速いのか**: Postgres の view は単なる SELECT 文の保存。
  実体化されていないので、参照されるたびに raw に対して SELECT が走る。
  raw が 10,000 行なら view 経由でも一瞬。staging を view にする保守的判断は正しい。
