# 4-3 解答例

## dbt/packages.yml

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.3.0"
```

```bash
$ cd dbt
$ ../.venv/bin/dbt deps --profiles-dir .
06:21:00  Running with dbt=1.11.x
06:21:01  Updating lock file in file path: ./package-lock.yml
06:21:02  Installing dbt-labs/dbt_utils
06:21:03    Installed from version 1.3.0
```

`dbt/dbt_packages/dbt_utils/` ができれば成功。`package-lock.yml` も自動生成される。

**ポイント**:

- **`>=1.3.0` の意図**: `generate_surrogate_key` macro はかなり前から
  ある (1.0+) が、1.3 以降の挙動が dbt 1.11 と整合性が取れている。
  上限を切らないことで、後で minor up に追従しやすくする。
- **lock ファイルを commit するか**: `package-lock.yml` を commit すると
  「環境ごとに同じバージョン」が保証される。本リポでは現状 lock を commit
  していないので、本問でも commit しない方針 (CI で `dbt deps` を毎回打つ)。

## dbt/models/100-knock/topic-4/int_customer_daily_activity_100knock.sql

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = (customer_id, activity_date)。
-- 注文がない (customer × date) ペアは出さない (= 注文した顧客×日のみ。明示で疎な事実テーブル)。
-- 設計判断:
--   - 注文ゼロ日も埋めたいなら customers × date_spine の cross join → LEFT JOIN orders にするが、
--     dim_dates が無い MVP では本問のスコープ外。「疎」のまま運用する。
--   - customer_daily_key は MD5 hash の代理キー。下流 mart の JOIN キーが 1 列で済む。
select
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'order_date']) }} as customer_daily_key,
    customer_id,
    order_date as activity_date,
    count(*)                                    as daily_order_count,
    sum(quantity)                               as daily_order_quantity,
    sum(quantity * unit_price)::numeric(14, 2)  as daily_sales_amount
from {{ ref('stg_orders_100knock') }}
group by customer_id, order_date
```

**ポイント**:

- **`generate_surrogate_key` の中身**: `md5(coalesce(cast(customer_id as text), '_dbt_utils_surrogate_key_null_') || '-' || coalesce(cast(order_date as text), '_dbt_utils_surrogate_key_null_'))`
  に展開される (1.3+ の実装)。NULL を文字列リテラルに置き換えてから連結 →
  hash する仕組みなので、「片方 NULL のときも別キーになる」のを保証してくれる。
- **代理キーが嬉しい場面**:
  1. **複合 PK の `unique` test を 1 列で書ける** (generic test の `unique` は単一列のみ)
  2. **下流 mart で JOIN キーが 1 列に減る** (`on a.customer_daily_key = b.customer_daily_key`)
  3. **将来 grain が変わっても、キー名 (`customer_daily_key`) が不変**。
     例: 「customer × date × store」grain に拡張しても、代理キーは
     `generate_surrogate_key([..., ..., 'store_id'])` に列を増やすだけで、下流の
     JOIN は壊れない (中身の hash が変わるだけ)
- **疎 vs 密の判断**: 「注文ゼロ日も 0 行で埋めたいか?」は分析要件次第。
  本問は「注文した日のみ拾う = 疎」を選択し、コメントで明示。後から
  「注文ゼロ日も欲しい」と言われたら、`stg_customers_100knock × dim_dates`
  の `cross join` → `LEFT JOIN orders` に拡張する (Topic ⑦ の `dim_dates` 導入後)。
- **`{{ ref('stg_customers_100knock') }}` を JOIN しない理由**: 本問の目的は
  「集計 + 代理キー化」なので、顧客名は不要。下流 mart で必要になったら
  そこで `ref('stg_customers_100knock')` を JOIN すればいい。intermediate に
  「使うかも」で列を足すと、grain が膨らんで責務が曖昧になる。

## dbt/models/100-knock/topic-4/schema.yml (4-1 のものに追記)

```yaml
  - name: int_customer_daily_activity_100knock
    description: |
      Grain: 1 row = (customer_id, activity_date)。
      stg_orders_100knock を customer × date で集計した「顧客の日次活動」。
      注文がない日は出さない (疎な事実テーブル)。
      customer_daily_key は dbt_utils.generate_surrogate_key で 2 列を hash 化した代理キー。
    columns:
      - name: customer_daily_key
        description: "代理キー (md5(customer_id || activity_date))。複合 grain を 1 列で表現。"
        tests:
          - not_null
          - unique
      - name: customer_id
        description: "FK → stg_customers_100knock.customer_id。"
        tests:
          - not_null
      - name: activity_date
        description: "活動日 (= order_date)。"
        tests:
          - not_null
      - name: daily_sales_amount
        description: "1 顧客の 1 日の売上合計 (numeric(14,2))。"
        tests:
          - not_null
```

**ポイント**:

- **`customer_daily_key` に `unique` を張れるのが代理キーの核心メリット**:
  もし代理キーを作らなければ、`(customer_id, activity_date)` の複合 unique は
  generic test では書けず、4-2 のような singular test を毎回書くことになる。
  代理キー化により generic test の世界に持ち込める = `schema.yml` 1 行で
  済む。

## 動作確認

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select int_customer_daily_activity_100knock
06:22:00  1 of 1 START sql view model intermediate.int_customer_daily_activity_100knock ... [RUN]
06:22:00  1 of 1 OK   created sql view model intermediate.int_customer_daily_activity_100knock [CREATE VIEW in 0.10s]
06:22:00  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select int_customer_daily_activity_100knock
06:22:10  1 of 4 START test not_null_int_customer_daily_activity_100knock_customer_daily_key [RUN]
06:22:10  1 of 4 PASS  not_null_int_customer_daily_activity_100knock_customer_daily_key [PASS]
06:22:10  2 of 4 START test unique_int_customer_daily_activity_100knock_customer_daily_key . [RUN]
06:22:10  2 of 4 PASS  unique_int_customer_daily_activity_100knock_customer_daily_key ..... [PASS]
06:22:10  3 of 4 START test not_null_int_customer_daily_activity_100knock_customer_id ........ [RUN]
06:22:10  3 of 4 PASS  not_null_int_customer_daily_activity_100knock_customer_id ............ [PASS]
06:22:10  4 of 4 START test not_null_int_customer_daily_activity_100knock_activity_date ...... [RUN]
06:22:10  4 of 4 PASS  not_null_int_customer_daily_activity_100knock_activity_date .......... [PASS]
06:22:10  Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

```sql
analytics=> SELECT count(*) FROM intermediate.int_customer_daily_activity_100knock;
 count
-------
  XXXX

analytics=> SELECT customer_id, activity_date, count(*)
            FROM intermediate.int_customer_daily_activity_100knock
            GROUP BY customer_id, activity_date HAVING count(*) > 1;
 customer_id | activity_date | count
-------------+---------------+-------
(0 rows)
```

行数 (XXXX) はダミーデータ次第だが、(customer × date) ペア数と一致するのが
正しい。重複 0 件 = 複合 grain が守られている。

## 解説まとめ

- **複合 grain の表現には代理キーが定石**: 単一列 grain なら column そのもの
  に `unique` を張れるが、複合 grain は generic `unique` で書けない。
  `generate_surrogate_key` で 1 列にまとめる → `unique` 1 行で守れる、が
  dbt-utils 流の作法。
- **同じ staging から異なる grain の int を派生する**: 4-1 の int (1 order_id
  = 1 行) と 4-3 の int (1 customer×date = 1 行) は **同じ `stg_orders_100knock`
  から派生**。intermediate 層は「分析グレイン別の中継 hub」を用意する場所
  であり、staging 1 本につき int 1 本という対応ではない。
- **疎 vs 密の意思決定をコメントで残す**: 「注文がない日は出さない方針」
  は分析の意思決定。コメントしないと、半年後に「なぜ X 日が抜けてる?」と
  なったとき意図が辿れない。**意思決定 = ファイル先頭コメント** を癖に。
- **dbt-utils を modeling 層で使う**: dbt-utils は SQL を書く生産性を
  上げるための標準ツールキット。`generate_surrogate_key` のほか、
  `pivot`, `unpivot`, `safe_divide`, `star`, `union_relations` など多数。
  modeling 層に入ったら自然と恩恵を受ける。
- **packages.yml の運用**: `dbt deps` は CI でも毎回打つ前提。lock を
  commit するかは方針次第 (本リポは未 commit)。lock を commit しない場合は
  `version:` の指定で「許容バージョン範囲」を絞り、サイレントな breaking
  change を防ぐ。
- **次の問 (4-4)**: 「intermediate を切るか切らないか」の核心問題。同じ集計を
  「int を切らずに mart 1 本」「int を挟んだ版」で並走させて、lineage の
  違いを目で見比べる。
