# 6-3 解答例

## dbt/models/100-knock/topic-3/stg_orders_100knock.sql (改訂版)

`payment_method` 派生列を末尾に追加:

```sql
{{ config(materialized='view', schema='staging') }}

-- Staging contract for raw_100knock.orders (Topic ③ Q3 + Topic ⑥ Q3 で payment_method 派生列追加).
--
-- 型を staging で確定させる + payment_method を 3 値の enum として確定する。
-- payment_method は CSV に存在しないので order_id を mod 3 で割って決定論的に割り振る:
--   order_id % 3 = 0 → 'card'
--   order_id % 3 = 1 → 'cash'
--   order_id % 3 = 2 → 'qr'
-- enum 値は schema.yml の accepted_values で契約として宣言される。
select
    order_id::bigint                            as order_id,
    order_date::date                            as order_date,
    customer_id::bigint                         as customer_id,
    product_id::bigint                          as product_id,
    store_id::bigint                            as store_id,
    quantity::int                               as quantity,
    unit_price::numeric(10, 2)                  as unit_price,
    case (order_id % 3)
        when 0 then 'card'
        when 1 then 'cash'
        when 2 then 'qr'
    end                                         as payment_method
from {{ source('raw_100knock', 'orders') }}
```

**ポイント**:

- **決定論的派生**: `order_id` を mod 3 で割るので、同じ raw に対して
  必ず同じ `payment_method` を返す。test が flaky にならない。
- **CASE で enum を確定**: 3 値以外は取らない (= NULL も出ない) ので、
  下流の `accepted_values` test が確実に PASS する。
- **`else` 節を書かない**: あえて else を省くと、想定外の `order_id`
  (負数など、本来あり得ない) が来た瞬間に NULL を返す。`not_null` が
  併記されているので NULL が来たら即 FAIL = 異常検知になる。
- **コメントで「enum 値は YAML 側に書く」 と明記**: SQL 側と YAML 側の
  二箇所に enum 値が登場するので、変更時にどちらを直せばいいか迷う。
  本リポジトリでは「**SQL は派生ロジック / YAML は契約**」と役割を
  分けるので、新値追加は両方を必ずペアで直す。

## dbt/models/100-knock/topic-3/schema.yml (該当ブロックに追記)

```yaml
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders。"
    columns:
      # ... 既存列 (order_id / order_date / ...) ...
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null
      - name: payment_method
        description: "支払い方法 (enum: card / cash / qr)。staging で派生 + accepted_values で domain 契約。"
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: ['card', 'cash', 'qr']
                quote: true
```

**ポイント**:

- **`not_null` + `accepted_values` の二段構え**: `accepted_values` は
  「**値があれば** 集合のいずれかであれ」 を検査するので NULL は素通り。
  「NULL も拒否」 を加えるなら `not_null` を併記する。
- **`quote: true`**: 値が文字列なら `true`。`accepted_values: { values: [1, 2, 3] }`
  のような数値列なら `quote: false`。
- **`arguments:` ネスト**: 1.11+ で test の引数渡しを `arguments:` 配下に
  整理した最新構文。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 76 data tests ...

$ ../.venv/bin/dbt run  --profiles-dir . --select stg_orders_100knock
1 of 1 OK created sql view model staging.stg_orders_100knock ... [CREATE VIEW]
Done. PASS=1 ...

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
1 of N PASS not_null_stg_orders_100knock_order_id ...
2 of N PASS unique_stg_orders_100knock_order_id ...
... 
N of M PASS not_null_stg_orders_100knock_payment_method ...
N+1 of M PASS accepted_values_stg_orders_100knock_payment_method__card__cash__qr ...
Done. PASS=N+1 WARN=0 ERROR=0 SKIP=0 TOTAL=N+1
```

## わざと違反値を仕込んで FAIL を体感 (任意 / 学習体験)

`stg_orders_100knock.sql` の CASE 句を一時的に改悪:

```sql
case (order_id % 4)            -- mod 3 → mod 4 に
    when 0 then 'card'
    when 1 then 'cash'
    when 2 then 'qr'
    when 3 then 'paypay'        -- ← 違反値を 25% の行に注入
end                            as payment_method
```

```bash
$ ../.venv/bin/dbt run  --profiles-dir . --select stg_orders_100knock
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... 
N of M FAIL 2500 accepted_values_stg_orders_100knock_payment_method__card__cash__qr [FAIL 2500 in 0.07s]
... 
Failure in test accepted_values_stg_orders_100knock_payment_method__card__cash__qr (models/100-knock/topic-3/schema.yml)
  Got 2500 results, configured to fail if != 0
```

戻す: CASE を元の `(order_id % 3)` に戻して `dbt run` → `dbt test` で全 PASS。

dbt がコンパイルした test SQL を読むと:

```sql
select payment_method as value_field, count(*) as n_records
from "analytics"."staging"."stg_orders_100knock"
where payment_method not in ('card', 'cash', 'qr')
group by payment_method
```

「**集合に含まれない値の出現回数**」 を行ごとに返す = 1 行でも返れば FAIL。

## 解説まとめ

- **`accepted_values` = 列の値域 (domain / enum) 契約**: 「この列は
  取りうる値が有限集合 X」 を YAML 1 行で表現。RDB の `CHECK` 制約や
  enum 型に相当する不変条件を、staging が view でも宣言できる。
- **enum を「コード上に書く」 価値**: 業務に新値 (PayPay) が追加された
  瞬間、test が即落ちる = 「**ダッシュボードに未知カテゴリが出現する
  前に気付ける**」。enum 拡張を **意識的なリリース作業** として扱える。
- **YAML と SQL の二箇所に値が出る**: SQL 側 (`case ... when 0 then 'card' ...`)
  と YAML 側 (`values: ['card', 'cash', 'qr']`) で同じ値が登場する。
  片方を直してもう片方を忘れる事故を防ぐため、本リポジトリは「**SQL は
  派生ロジック / YAML は契約**」 と役割分担を明示する。
- **`not_null` 併記**: `accepted_values` は NULL を素通すので、NULL も
  拒否したい場合は `not_null` を併記する二段構え。本問では CASE に
  `else` 節がないので想定外入力時のみ NULL になる = 異常検知。
- **派生列の決定論性**: `order_id % 3` のような関数的な派生は再現可能で
  test を安定させる。`random()` / `current_timestamp` 系は staging で
  使うと再生成のたびに値が変わって test が運任せになる。
- **採点ロジックの設計**: 本問では「**accepted_values が宣言されていること**」
  と「PASS していること」 を厳密に見る。違反値の混入 / 復帰は **学習体験**
  に振り、採点ノイズにしない。FAIL を採点したい問は 6-2 で別途扱った。
- **`dbt-utils` / `dbt-expectations` の関連 test**: `cardinality_equality`
  (2 列の値集合一致)、`expect_column_values_to_be_in_set` (大規模集合に
  対する versatile な enum チェック) などが応用先。6-8 で `dbt-expectations`
  を入れた後に再訪する話。
- **EC ドメインでの実話**: 決済手段は規制対応 / 顧客行動 / 手数料計算で
  非常に効く分析軸。enum を契約化しておくと、KPI ダッシュボード
  (例: 「QR 決済比率の月次推移」) が enum の整合崩れで突然壊れる事故を
  根元から塞げる。
