# 6-3: payment_method に accepted_values を宣言、'paypay' を混ぜて FAIL

## シナリオ

注文には支払い方法 (`payment_method`) があり、業務上は **`'card'` / `'cash'` / `'qr'`
の 3 値しか取らない** はず。これは **「列の値域 (domain / enum) を
契約として宣言する」** 典型例で、dbt の `accepted_values` test 1 行で表現できる。

ただし Topic ① の生成スクリプトには `payment_method` 列を作っていない。
本問では、まず **`stg_orders_100knock` に決定論的な派生列として
`payment_method` を追加** (Topic ③ の SQL を 1 行追記) し、その上で
`accepted_values: ['card','cash','qr']` を宣言する。最後に CSV に `'paypay'`
を 1 行混ぜて FAIL を体感する。

## 学べること

- `accepted_values` test の YAML 構文 (`arguments: { values: [...] }`)
- 「決定論的派生列」 の作り方 (`order_id % 3` で 3 値を割り振る)
- 列の **値域 (enum / domain) 制約** を契約として書く意味
- CSV → raw → staging への **値域違反** が伝播する経路の理解
- accepted_values の **宣言だけ採点** + 違反 / 復帰は学習体験、というパターン

## 前提

- Topic ② ③ ④ ⑤ 完了
- `dbt/models/100-knock/topic-3/stg_orders_100knock.sql` を 1 行追記して
  `payment_method` 派生列を作る (本問の Step 1)

## 入力データ

`raw.orders` 10,000 行。`order_id` (1..10000) を mod 3 で割って:

- `order_id % 3 = 0` → `'card'`
- `order_id % 3 = 1` → `'cash'`
- `order_id % 3 = 2` → `'qr'`

の 3 値をランダムに割り振る (CSV に列が無い前提なので、staging で派生)。

## 課題

### Step 1: stg_orders_100knock に payment_method 派生列を追加

`dbt/models/100-knock/topic-3/stg_orders_100knock.sql` の SELECT 句末尾に
1 行追加:

```sql
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
    end                                         as payment_method   -- ← 追加
from {{ source('raw_100knock', 'orders') }}
```

> **設計判断**: payment_method を CSV に持たず staging の派生列で作る
> のは、Topic ① を遡及的に直したくないため。本来は raw 投入時から
> 持つべき列だが、本問では「**staging で domain を確定する**」 という
> もう一つの staging contract の役割を体感する場とする。

### Step 2: schema.yml に accepted_values を宣言

`dbt/models/100-knock/topic-3/schema.yml` の `stg_orders_100knock` ブロックに
`payment_method` 列を追記:

```yaml
      - name: payment_method
        description: "支払い方法 (enum: card / cash / qr)。"
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: ['card', 'cash', 'qr']
                quote: true
```

`arguments:` ネスト形式が dbt 1.11+ の推奨。`quote: true` は
「`values:` リストの各要素を SQL 上で文字列として quote する」 指示。

### Step 3: 実行 (PASS することを確認)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select stg_orders_100knock
../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
```

`accepted_values_stg_orders_100knock_payment_method__card__cash__qr` が
PASS で出れば成功。

### Step 4: わざと違反値を仕込む (任意 / 学習体験)

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
-- payment_method を CASE で生成しているので、order_id を弄ると派生値も変わる。
-- ここでは「accepted_values の SQL を直接走らせて、違反値を入れたら何が出るか」
-- を簡単な手元実験で見る:
SELECT 'paypay' AS payment_method
WHERE NOT 'paypay' IN ('card', 'cash', 'qr');
-- 1 行返る = もし staging に 'paypay' が混ざっていたら test FAIL する
SQL
```

本格的に FAIL を見たい場合は staging 側で `case ... else 'paypay' end`
のような改悪をして再 run → test。学習体験のための寄り道で、採点には影響しない。

戻す: 上記 `case` 句を元の 3 値に戻して `dbt run --select stg_orders_100knock`。

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/stg_orders_100knock.sql` に
      `payment_method` 派生列が追加されている
- [ ] `dbt/models/100-knock/topic-3/schema.yml` に
      `accepted_values: { values: ['card', 'cash', 'qr'] }` 宣言がある
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select stg_orders_100knock` で
      `accepted_values_stg_orders_100knock_payment_method__card__cash__qr` が PASS
- [ ] manifest に
      `test.local_analytics.accepted_values_stg_orders_100knock_payment_method__card__cash__qr`
      が登録されている

## ヒント (詰まったら)

- **`accepted_values` の test 名規則**: `accepted_values_<model>_<col>__<v1>__<v2>__<v3>`
  のように **値の連結** が test 名に入る。値が多いと長くなる。
- **`quote: true` の意味**: `values:` の要素を SQL 上で `'card'` のように
  クォートする。文字列列なら `true`、数値列 (例: `rating` の 1〜5) なら `false`。
- **enum を YAML に書く意味**: 業務的に「取りうる値が有限集合」 を **コード上で
  宣言** することで、新しい値が増えた瞬間 (例: PayPay 導入) に test が落ちて
  「下流ダッシュボードに新カテゴリが現れる前に気付ける」。値域変更を
  **意図的な作業** として扱える。
- **派生列の決定論性**: `order_id % 3` のような決定論的な式は、再生成しても
  同じ結果を返す = test の flaky を起こさない。`random()` を使うと毎回
  値域が変動して test が運任せになるので NG。
- **CSV に 'paypay' を混ぜる別解**: `data/100-knock/topic-1/orders.csv` を
  直接編集して 1 行に `payment_method='paypay'` を入れる、という方法もあるが、
  Topic ① の生成スクリプトを再走させた瞬間に消える。本問では「staging で
  enum を確定する」 体験を優先し、CSV 改変は採点対象から外している。
- **採点ロジック**: 本問は「**accepted_values が宣言されていること**」 を
  厳密に見る。違反 / 復帰は学習体験 (= 自由) で、採点しない。FAIL を採点
  したい問は 6-2 で扱った。
- **dbt-utils の関連 test**: `dbt_utils.cardinality_equality` で「2 列の
  ユニーク値集合が一致すること」 を検査できる。enum と enum の対応関係を
  カチッと縛るユースケース。

## 解答例

詳細は [`6-3-accepted-values.solution.md`](6-3-accepted-values.solution.md) を参照。
