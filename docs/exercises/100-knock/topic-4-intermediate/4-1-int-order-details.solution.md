# 4-1 解答例

## dbt/models/100-knock/topic-4/int_order_details_100knock.sql

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (orders を主軸に master 3 本を INNER JOIN で enrich)。
-- INNER JOIN の根拠: Topic ③ 3-4 で stg_orders_100knock の FK 3 列に
-- relationships test を張ったので、全 order に対して master 行が必ず存在する。
-- materialization は view: storage 不要 / 常に最新。下流 mart 側で table 化する。
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
    (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

**ポイント**:

- **冒頭コメントが grain 宣言の一次情報**: SQL を開いた人が真っ先に読むのが
  ファイル先頭。「この model は 1 行 = 何か」を 1 行で書ける = 設計が
  整理できている、という自己診断にもなる。逆に「1 行 = 〜と〜の組み合わせか
  もしれないけど詳しくは…」と書きたくなったら、その intermediate は
  grain が定まっておらず、まだ作るべきタイミングではない可能性が高い。
- **INNER JOIN を選ぶ判断**: 3-4 で `relationships:` test を張った FK は
  「master に必ず存在する」ことが test で保証されている。LEFT JOIN にすると
  「親が消えたとき NULL で埋まる」が成立してしまい、grain が崩れる
  (1 order_id が NULL master 込みで複数行になる懸念は無いが、`customer_name`
  が NULL の行が生まれて下流が困る)。INNER JOIN + relationships test の
  組み合わせが定石。
- **`sales_amount` を intermediate で確定**: `quantity * unit_price` を
  ここで `numeric(14,2)` cast まで済ませる。下流 mart 側で毎回掛け算する
  のは DRY 違反。「派生列 = 1 箇所で計算、複数箇所で参照」が intermediate の
  存在意義のひとつ。
- **`{{ config(materialized='view', ...) }}` の理由**: intermediate は
  staging と同じく薄い変換層。物理化しても storage の元が取れない (mart の
  table 化のほうが ROI が高い)。view にしておけば staging が更新された
  瞬間に最新化される。

## dbt/models/100-knock/topic-4/schema.yml

```yaml
version: 2

models:
  - name: int_order_details_100knock
    description: |
      Grain: 1 row = 1 order_id.
      stg_orders_100knock を主軸に customers / products / stores の master 3 本を
      INNER JOIN し、sales_amount = quantity * unit_price を算出した
      "分析対象の最小単位" の intermediate。下流 mart はここから集計する。
    columns:
      - name: order_id
        description: "Primary key (= grain key)。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date)。"
        tests:
          - not_null
      - name: customer_id
        description: "FK → stg_customers_100knock.customer_id。"
        tests:
          - not_null
      - name: product_id
        description: "FK → stg_products_100knock.product_id。"
        tests:
          - not_null
      - name: sales_amount
        description: "quantity * unit_price (numeric(14,2))。"
        tests:
          - not_null
```

**ポイント**:

- **description が "grain 宣言" の二次情報**: 冒頭コメントは SQL を開いた人
  しか読まないが、`schema.yml` の description は `dbt docs generate` で
  catalog ページに載る = アナリストが UI から見られる。同じ内容を 2 箇所に
  書く冗長さはあるが、媒体が違うので両方残す。
- **`unique` test が grain 契約の要**: 「1 行 = 1 order_id」を宣言しただけ
  では裏切られる可能性がある (master 側の PK 重複、JOIN タイポなど)。
  `unique` test がデータレベルで grain を担保する。これが 4-2 の前哨戦。
- **FK の `relationships:` は不要**: int は既に staging を `ref()` した
  下流。FK の整合性は staging 側 (3-4) で保証済み。intermediate でもう一度
  relationships を貼るのは過剰。

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
06:01:00  Found 13 models, 5 sources, 70 data tests, ...

$ ../.venv/bin/dbt run --profiles-dir . --select int_order_details_100knock
06:01:10  1 of 1 START sql view model intermediate.int_order_details_100knock ... [RUN]
06:01:10  1 of 1 OK   created sql view model intermediate.int_order_details_100knock [CREATE VIEW in 0.12s]
06:01:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select int_order_details_100knock
06:01:20  1 of 5 START test not_null_int_order_details_100knock_order_id ............ [RUN]
06:01:20  1 of 5 PASS  not_null_int_order_details_100knock_order_id ................ [PASS in 0.05s]
06:01:20  2 of 5 START test unique_int_order_details_100knock_order_id .............. [RUN]
06:01:20  2 of 5 PASS  unique_int_order_details_100knock_order_id .................. [PASS in 0.06s]
06:01:20  3 of 5 START test not_null_int_order_details_100knock_order_date .......... [RUN]
06:01:20  3 of 5 PASS  not_null_int_order_details_100knock_order_date .............. [PASS in 0.04s]
06:01:20  ... (略)
06:01:20  Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

`psql` で物理化 / 行数確認:

```sql
analytics=> SELECT count(*) FROM intermediate.int_order_details_100knock;
 count
-------
 10000

analytics=> SELECT order_id, count(*) FROM intermediate.int_order_details_100knock
            GROUP BY order_id HAVING count(*) > 1;
 order_id | count
----------+-------
(0 rows)
```

10,000 行 (= stg_orders_100knock の行数) で、grain 違反 0 件。期待通り。

## 解説まとめ

- **intermediate を切るのは grain を確定したいから**: staging は raw を
  「列名と型だけ整える」層なので、grain は raw の grain そのまま (= テーブル
  ごとに別)。intermediate で初めて「分析対象の 1 行 = 何か」を JOIN によって
  決める。これが intermediate の最大の存在意義。
- **grain 宣言は 3 点セット**: ① 冒頭コメント (SQL を開いた人向け)、
  ② schema.yml の description (docs catalog)、③ unique test (データ担保)。
  3 つが揃って初めて「下流がこの grain を信じて `ref()` できる」状態になる。
- **INNER JOIN + relationships test の対称性**: staging で relationships を
  保証しているからこそ INNER JOIN が安全に使える。relationships test を
  サボった staging を INNER JOIN すると、データの欠損で行が暗黙に落ちる
  バグが生まれる。
- **MVP との衝突回避 (`_100knock` suffix)**: 同じ node 名は dbt が
  `Found duplicate model` で落とす。100-knock 演習であることを示す suffix で
  名前空間を切り、MVP の int_order_details と並走させる。`dbt ls --select int_*`
  で 2 ノード並んで見える状態が正しい。
- **派生列を intermediate で計算する DRY**: `sales_amount = quantity * unit_price`
  を mart 側で毎回計算すると、税の計算式が変わったとき複数箇所修正に
  なる。intermediate で 1 箇所に集約 = 4-5 で見る fan-out 構図でも修正コストが
  抑えられる。
- **次の問 (4-2)**: 「`unique` test が PASS する = grain が守られている」を
  わざと壊す singular test を書いて、test がきちんと FAIL を捕まえることを
  確認する。
