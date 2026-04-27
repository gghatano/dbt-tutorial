# 4-3: int_customer_daily_activity_100knock を複合 grain で作る (dbt_utils 導入)

## シナリオ

4-1 で作った `int_order_details_100knock` は **「1 行 = 1 order_id」** という
シンプルな単一列 grain だった。が、分析業務では「顧客 × 日」「店舗 × 月」
など **複合キー grain** の中間集計が頻出する。

今回は同じ staging 4 本を起点に、**「1 顧客 × 1 日 = 1 行」** の int を
作る。同じ raw / staging から **異なる grain の int を 2 本派生できる** のが
intermediate 層の柔軟性。

複合 grain の "1 列化" には `dbt_utils.generate_surrogate_key` を使う。
これにより「複合 PK を `unique` test で守れる」「下流 mart の JOIN キーが
1 列で済む」「将来 grain が変わってもキー名は不変」というメリットが出る。
本問は dbt-utils の **modeling 層初導入** も兼ねる。

## 学べること

- 複合 grain (`customer_id × activity_date`) を持つ intermediate の作り方
- `dbt_utils.generate_surrogate_key(['col1','col2'])` で複合 PK を 1 列の hash に集約
- `dbt deps` で外部パッケージを取り込むワークフロー (`packages.yml` → `dbt_packages/`)
- 複合 grain の unique 担保は singular test (`group by ... having count(*) > 1`) で書く
- 「同じ staging から異なる grain の int を派生できる」の体感

## 前提

- 4-1 完了: `int_order_details_100knock` が動いている
- `dbt/packages.yml` が空 (`packages: []`) または存在しない状態でもよい
  (本問で書き換える)
- ネットワーク接続あり (`dbt deps` が GitHub から dbt-utils を取得する)

## 入力データ

`stg_orders_100knock` (10,000 行) と `stg_customers_100knock` (1,000 行) を使う。
注文がない (顧客 × 日) ペアは出さない方針 (= INNER JOIN ベース)。

## 課題

### Step 1: dbt-utils を導入する

`dbt/packages.yml` に dbt-utils を追加 (既存内容があれば追記):

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.3.0"
```

```bash
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

`dbt_packages/dbt_utils/` が作られたら成功。

### Step 2: intermediate model を作る

`dbt/models/100-knock/topic-4/int_customer_daily_activity_100knock.sql` を新規作成。

要件:

- 冒頭コメントで grain を明示: `-- Grain: 1 row = (customer_id, activity_date)`
  と「注文がない (customer × date) ペアは出さない方針」を 1 行で書く
- `{{ config(materialized='view', schema='intermediate') }}` を明示
- `stg_orders_100knock` を `customer_id`, `order_date` で `group by` (= 注文した
  顧客×日のみ拾う方針)
- 派生列 (この問では "1 日に何件注文したか" / "1 日にいくら使ったか" を集計):
  - `activity_date` (= `order_date`)
  - `customer_id`
  - `daily_order_count` (= `count(*)`)
  - `daily_order_quantity` (= `sum(quantity)`)
  - `daily_sales_amount` (= `sum(quantity * unit_price)::numeric(14,2)`)
  - `customer_daily_key` (= `dbt_utils.generate_surrogate_key(['customer_id', 'activity_date'])`)
- 主軸は `stg_orders_100knock`。`stg_customers_100knock` の JOIN は **任意**
  (顧客名がほしければ INNER JOIN、不要なら省略)。本問では unjoin で OK。

例 (このまま使える):

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = (customer_id, activity_date)。
-- 注文がない (customer × date) ペアは出さない (= 注文した顧客×日のみ。明示で疎な事実テーブル)。
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

### Step 3: schema.yml に追記

4-1 で作った `dbt/models/100-knock/topic-4/schema.yml` の `models:` 配下に追記:

```yaml
  - name: int_customer_daily_activity_100knock
    description: |
      Grain: 1 row = (customer_id, activity_date)。
      stg_orders_100knock を customer × date で集計した「顧客の日次活動」。
      注文がない日は出さない (疎な事実テーブル)。
      customer_daily_key は dbt_utils.generate_surrogate_key で 2 列を hash 化した代理キー。
    columns:
      - name: customer_daily_key
        description: "代理キー (customer_id || '||' || activity_date の MD5)。"
        tests:
          - not_null
          - unique
      - name: customer_id
        tests:
          - not_null
      - name: activity_date
        tests:
          - not_null
```

### Step 4: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select int_customer_daily_activity_100knock
../.venv/bin/dbt test --profiles-dir . --select int_customer_daily_activity_100knock
```

### Step 5: psql で複合 grain が unique であることを確認

```sql
analytics=> SELECT customer_id, activity_date, count(*)
            FROM intermediate.int_customer_daily_activity_100knock
            GROUP BY customer_id, activity_date
            HAVING count(*) > 1;
 customer_id | activity_date | count
-------------+---------------+-------
(0 rows)
```

0 行 = (customer_id × activity_date) が unique = 複合 grain が守られている。

## 完了条件

- [ ] `dbt/packages.yml` に `dbt-labs/dbt_utils` が宣言され、`dbt deps` 済み
- [ ] `dbt/models/100-knock/topic-4/int_customer_daily_activity_100knock.sql` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_customer_daily_activity_100knock` が登録される
- [ ] `dbt run --select int_customer_daily_activity_100knock` が PASS
- [ ] psql で `(customer_id, activity_date)` の重複行が 0 件

## ヒント (詰まったら)

- **`dbt deps` が失敗する**: ネットワーク不通 / プロキシ環境の可能性。
  社内ネットなら `https_proxy` を設定。GitHub の rate limit は通常問題に
  ならないが、`dbt deps --no-anonymous-usage-stats` で軽くなる場合がある。
- **`dbt_utils.generate_surrogate_key` が「macro 未定義」エラー**: `dbt deps`
  を打ち忘れか、`packages.yml` の package 名が typo。`dbt list-packages` 相当
  はないが、`dbt_packages/dbt_utils/macros/sql/generate_surrogate_key.sql` が
  存在するか目視で確認。
- **`unique` test が FAIL**: 同じ (customer_id, activity_date) が複数行 = 集計
  キーの `group by` から漏れがある。`group by customer_id, order_date` を
  忘れていないか SQL 確認。
- **行数が想定外**: `select count(distinct customer_id || '||' || order_date::text)
  from staging.stg_orders_100knock` で「ユニークな (customer × date) ペア数」を
  確認 → int の行数と一致するはず。
- **`dbt_utils` のバージョン**: dbt 1.11 系なら `>=1.3.0` で OK。古い (≤ 1.0)
  だと別 macro 名 (`dbt_utils.surrogate_key`) になっている可能性。

## 解答例

詳細は [`4-3-int-customer-daily.solution.md`](4-3-int-customer-daily.solution.md) を参照。
