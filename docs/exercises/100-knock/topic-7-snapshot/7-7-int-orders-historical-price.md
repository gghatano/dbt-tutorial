# 7-7: snap を ref した int_orders_with_historical_price_100knock を作る

## シナリオ

7-6 で「ある 1 つの `as_of` 時刻に有効だった行」を取り出す point-in-time クエリ
を書いた。だが現実の用途は **「注文 1 件ごとに、その注文日時点での価格」**
を引き当てることが圧倒的に多い (= 売上を当時価格で再計算する監査クエリ)。

これは `as_of` が「注文ごとに違う」点が point-in-time との違い。SQL では
**range JOIN** で表現する: `int_order_details_100knock.order_date` を
`snap_products_100knock.dbt_valid_from <= order_date < dbt_valid_to` の
範囲で snapshot 側にぶつける。snapshot を `ref()` で取り込むので、
**dbt の DAG に snapshot がノードとして組み込まれる** のがポイント。

## 学べること

- `ref('snap_products_100knock')` で snapshot を **DAG の上流ノード** として参照
- range JOIN (`a.t BETWEEN b.from AND b.to` 系) のテンプレ
- 注文 1 件ごとに違う `as_of` を持つクエリ = bitemporal の典型形
- intermediate 層に「**注文時点の価格列**」を持たせる設計 (= mart は集計するだけ)
- snapshot を model から ref する瞬間に dbt が依存解決する仕組み

## 前提

- 7-1 〜 7-5 完了 (`snapshots.snap_products_100knock` が存在、120 行)
- Topic ④ 4-1 完了 (`int_order_details_100knock` が存在、10,000 行、
  `order_date` / `product_id` / `quantity` / `unit_price` 列を持つ)
- `dbt parse` が通る

## 入力データ

不要。既存の snapshot と intermediate を JOIN するだけ。

## 課題

### Step 1: int_orders_with_historical_price_100knock を新規作成

`dbt/models/100-knock/topic-7/int_orders_with_historical_price_100knock.sql`:

要件:

- `{{ config(materialized='view', schema='intermediate') }}` を明示
- `{{ ref('int_order_details_100knock') }}` を主軸 (orders + master)
- `{{ ref('snap_products_100knock') }}` を range JOIN
  - JOIN 条件: `o.product_id = sp.product_id`
    AND `o.order_date >= sp.dbt_valid_from::date`
    AND `o.order_date <  coalesce(sp.dbt_valid_to::date, date '9999-12-31')`
- 出力列: `order_id`, `order_date`, `product_id`, `quantity`,
  `unit_price` (= 注文時点の snap 側 unit_price), `unit_price_at_order` (alias 推奨),
  `historical_sales_amount` (= `quantity * unit_price`、`numeric(14,2)` cast)
- 冒頭コメントで grain (1 row = 1 order_id) と「`unit_price` は **注文時点の
  snapshot から引いた価格**」 を 2 行で宣言

### Step 2: schema.yml に追記

`dbt/models/100-knock/topic-7/schema.yml` (既存なら追記、無ければ新規):

```yaml
version: 2

models:
  - name: int_orders_with_historical_price_100knock
    description: |
      Grain: 1 row = 1 order_id.
      snap_products_100knock を range JOIN し、注文 1 件ずつに
      「その注文日時点で有効だった unit_price」を引き当てた intermediate。
    columns:
      - name: order_id
        tests: [not_null, unique]
      - name: unit_price
        description: "注文時点で有効だった snap_products の unit_price (numeric)。"
        tests: [not_null]
      - name: historical_sales_amount
        description: "quantity * unit_price (注文時点の価格で再計算)。"
        tests: [not_null]
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select int_orders_with_historical_price_100knock
../.venv/bin/dbt test --profiles-dir . --select int_orders_with_historical_price_100knock
```

### Step 4: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-7-snapshot/7-7-int-orders-historical-price.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-7/int_orders_with_historical_price_100knock.sql` が存在
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_orders_with_historical_price_100knock` が登録
- [ ] manifest 上、上流に `snapshot.local_analytics.snap_products_100knock` を含む
- [ ] DB 上で intermediate.int_orders_with_historical_price_100knock に `unit_price` 列が存在
- [ ] 行数 = 10,000 (= 注文 1 件 1 行、master の漏れなし)

## ヒント (詰まったら)

- **行が 10,000 を超える / 下回る**: range JOIN の不等号が怪しい。
  `>= dbt_valid_from AND < dbt_valid_to` の半開区間 (7-6 と同じ規約) でないと
  境界の瞬間に重複/穴が出る。`coalesce(dbt_valid_to, '9999-12-31')` で
  「現役行 = +∞」を表現する。
- **`unit_price` が NULL**: snapshot 側に「注文日より古い `dbt_valid_from`」の
  行が無いケース (= 注文が snapshot 1 回目より古い場合) で起こる。本演習データ
  では起こらない想定だが、本番運用なら LEFT JOIN + coalesce で staging 側の
  価格にフォールバックする設計もある。
- **manifest の上流に snapshot が出ない**: `ref('snap_products_100knock')` の
  綴り (suffix `_100knock` 忘れなど) を確認。snapshot は dbt 上 `snapshot.<pkg>.<name>`
  として登録され、`ref()` で model と同じインターフェースで引ける。
- **`dbt_valid_from` の型**: snapshot のメタ列は `timestamptz`。`order_date` が
  `date` の場合、`sp.dbt_valid_from::date` のように cast すると比較が素直。
- **MVP の `int_orders_with_historical_price` (Exercise 04 の解答例) と紛らわしい**:
  本問は **`_100knock` suffix 必須**。MVP のものは Exercise 04 用で、本問とは
  独立して並走させる。

## 解答例

詳細は [`7-7-int-orders-historical-price.solution.md`](7-7-int-orders-historical-price.solution.md) を参照。
