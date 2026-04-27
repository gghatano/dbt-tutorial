# 4-10: int_order_details_100knock を model versions で v1 (税抜) → v2 (税込列追加) に分岐

## シナリオ

業務側から「int_order_details_100knock に税込金額列も追加してほしい、ただし既存 mart は
壊さないでほしい」 と要望が来た。SQL を直接書き換えると下流の mart が新列を期待していない
場合に SELECT が壊れる可能性がある (列数が変わる、既存テストが落ちる、など)。

dbt 1.5+ で導入された **model versions** 機能を使うと、**同じ model 名の v1 と v2 を並走**
させることができる。`schema.yml` に `versions:` ブロックを書き、`int_order_details_100knock_v2.sql`
という命名規約のファイルを別に作る。下流 mart は `{{ ref('int_order_details_100knock', v=1) }}` で
v1 を、`{{ ref('int_order_details_100knock', v=2) }}` で v2 を指定して参照する。
これで「**下流を壊さない schema 進化**」 が実現される。

これは Topic ⑤ の mart contract / Topic ⑩ のリリース管理と直結する **dbt 1.5+ の目玉機能** で、
実務での schema migration の **デファクト** になりつつある。

## 学べること

- `versions:` ブロックを `schema.yml` に書く
- ファイル命名規約 `<model_name>_v<N>.sql` (定義された version は別ファイル)
- `{{ ref('model_name', v=N) }}` で version 指定参照
- **defined_in** で 「v1 はこの SQL ファイル」 を明示する書き方
- manifest 上 `model.<project>.<name>.v1` / `model.<project>.<name>.v2` の 2 ノードに分岐すること
- `dbt ls --select int_order_details_100knock` で v1 / v2 両方が出ること
- 「下流の壊さない schema 進化」 を **DAG で管理する** という設計思想

## 前提

- Topic ② ③ 完了 + Topic ④ 4-1 完了 + 4-9 推奨 (description 完了)
- `int_order_details_100knock` の materialization が view または table (4-8 で ephemeral にしたなら view に戻すこと)
- dbt 1.5 以上 (`dbt --version` で確認)
- `dbt parse` が通る

## 入力データ

不要。学習者が schema.yml に versions ブロックを書き、v2 用 SQL を新規作成。

## 課題

### Step 1: v2 用 SQL ファイルを作成

`dbt/models/100-knock/topic-4/int_order_details_100knock_v2.sql` を新規作成
(ファイル名末尾の `_v2` が version の宣言と紐付く):

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (v1 と同じ grain)。
-- v2 で追加した変更点: 税込金額列 sales_amount_with_tax を追加 (10% 固定)。
-- v1 と並走: 既存 mart は v=1 のまま参照、新規 mart のみ v=2 を参照する想定。
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
    (o.quantity * o.unit_price)::numeric(14, 2)              as sales_amount,
    (o.quantity * o.unit_price * 1.10)::numeric(14, 2)       as sales_amount_with_tax
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

> v1 (= 4-1 で書いた `int_order_details_100knock.sql`) は **そのまま残す**。本問で消したり編集したりしない。

### Step 2: schema.yml に `versions:` ブロックを追加

`dbt/models/100-knock/topic-4/schema.yml` の `int_order_details_100knock` ブロックを
`versions:` 形式に書き換える:

```yaml
version: 2

models:
  - name: int_order_details_100knock
    description: |
      Grain: 1 row = 1 order_id。stg_orders_100knock を主軸に customers / products /
      stores の master 3 本を INNER JOIN し、sales_amount を算出した中間モデル。
      v2 で sales_amount_with_tax 列を追加 (税込金額)。既存 mart は v=1 のまま、
      新規 mart は v=2 を参照する段階移行設計。
    latest_version: 2
    columns:
      - name: order_id
        description: "Primary key (= grain key)。"
        tests:
          - not_null
          - unique
      - name: sales_amount
        description: "売上金額 (税抜, numeric(14,2))。v1/v2 共通。"
        tests:
          - not_null
      - name: sales_amount_with_tax
        description: "売上金額 (税込, numeric(14,2))。v2 で追加。"
        # ※ ここに tests を書くと v1 にも適用されてしまう (v1 にはこの列が無いので失敗)。
        # version 固有 column の test は version ブロック内で書く。
    versions:
      - v: 1
        # v1 は元の int_order_details_100knock.sql ファイルを参照
        # defined_in を省略するとデフォルトで <model_name>_v<N>.sql を期待するため、
        # v1 はファイル名と version のマッピングを明示する必要がある。
        defined_in: int_order_details_100knock
        columns:
          - name: order_id
          - name: order_date
          - name: customer_id
          - name: customer_name
          - name: product_id
          - name: product_name
          - name: category
          - name: store_id
          - name: quantity
          - name: unit_price
          - name: sales_amount
      - v: 2
        # v2 はファイル名 int_order_details_100knock_v2.sql から自動解決される
        columns:
          - name: order_id
          - name: order_date
          - name: customer_id
          - name: customer_name
          - name: product_id
          - name: product_name
          - name: category
          - name: store_id
          - name: quantity
          - name: unit_price
          - name: sales_amount
          - name: sales_amount_with_tax
            tests:
              - not_null
```

### Step 3: dbt parse + ls で v1 / v2 両方が見えることを確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt ls --select int_order_details_100knock --profiles-dir .
```

期待出力 (v1 / v2 の 2 ノード):

```
local_analytics.intermediate.int_order_details_100knock.v1
local_analytics.intermediate.int_order_details_100knock.v2
```

### Step 4: build

```bash
../.venv/bin/dbt build --select int_order_details_100knock --profiles-dir .
```

`PASS=2` (v1 と v2 がそれぞれ build される)。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-4-intermediate/4-10-model-versions.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-4/int_order_details_100knock_v2.sql` が存在する
- [ ] `dbt/models/100-knock/topic-4/schema.yml` に `versions:` ブロックがある
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_order_details_100knock.v1` が登録されている
- [ ] manifest に `model.local_analytics.int_order_details_100knock.v2` が登録されている
- [ ] `dbt ls --select int_order_details_100knock` の出力に v1 / v2 両方が出る
- [ ] `dbt build --select int_order_details_100knock` で v1 / v2 両方が PASS

## ヒント (詰まったら)

- **`defined_in` の書き方**: 通常 dbt は v=N の version SQL を `<model_name>_v<N>.sql` ファイルから自動解決する。本問では v1 が元のファイル名 `int_order_details_100knock.sql` (= `_v1` suffix 無し) のままで残したいので、`defined_in: int_order_details_100knock` を明示する必要がある。v2 は `_v2.sql` 命名なので `defined_in` を書かなくても自動解決される。
- **node 名の形式**: model versions を使うと dbt の unique_id が `model.<project>.<name>.v<N>` になる (末尾に `.v1` / `.v2` が付く)。manifest_node_exists の確認時に注意。
- **下流 mart の参照**: 既存 mart はそのまま `{{ ref('int_order_details_100knock') }}` だが、これは **`latest_version` (= 2) を参照する** ので、本問で latest=2 とすると下流の挙動が変わる可能性あり。本問では下流を触らないが、Topic ⑤ 5-10 で `{{ ref('int_order_details_100knock', v=1) }}` / `v=2` の使い分けを学ぶ。
- **`latest_version` の意味**: `versions:` を書く時、`latest_version: N` で「version 指定なしの ref はどの version を返すか」 を制御。デフォルトは `versions:` の最大値。本問では `latest_version: 2` で「v 指定なし = v2」 を宣言。
- **dbt 1.5 未満だと parse が落ちる**: `dbt --version` で 1.5 以上を確認。本プロジェクトは dbt 1.11 系なので問題なし。
- **物理化先のテーブル名**: v=1 は `intermediate.int_order_details_100knock_v1` という物理名になる (デフォルトで `_v<N>` suffix が付く)。これを避けたければ `defined_in` + `alias` を組み合わせる (本問では物理名は気にせず、論理名だけ揃える方針)。

## 解答例

詳細は [`4-10-model-versions.solution.md`](4-10-model-versions.solution.md) を参照。
