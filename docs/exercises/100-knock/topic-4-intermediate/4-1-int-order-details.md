# 4-1: int_order_details_100knock を grain 宣言付きで作る

## シナリオ

Topic ③ で `stg_*_100knock` を 4 本 (`stg_customers_100knock` /
`stg_products_100knock` / `stg_orders_100knock` / `stg_stores_100knock`) 揃えた。
ここから先は **モデリング層 (intermediate / mart)** に入る。intermediate の
最初の役目は「複数 staging を JOIN して、分析対象の "1 行 = 何か" の
**grain (粒度)** をハッキリ宣言する」こと。

今回は MVP の `int_order_details` と同じ集約を 100-knock 名前空間で
**再実装** しつつ、grain が「1 `order_id` = 1 行」であることを **冒頭コメント** と
**`schema.yml` の description**、そして **`unique` / `not_null` テスト** の
3 点セットで宣言する。これが「intermediate を切る = grain を契約する」の
基本形。

## 学べること

- intermediate model の役目 (複数 staging を JOIN し、分析対象の grain を確定)
- **grain (粒度)** をコメント / description / test の 3 点で宣言する作法
- `ref()` で 4 本の staging を依存に取る (DAG が「ハブ 1 点に 4 線が集まる」星形になる)
- `unique` + `not_null` test で grain 契約をデータレベルで担保
- MVP `int_order_details` との衝突回避 (`int_<name>_100knock` 命名)

## 前提

- Topic ③ 3-1〜3-10 完了: 学習者の staging 4 本
  (`stg_customers_100knock` / `stg_products_100knock` / `stg_orders_100knock` /
  `stg_stores_100knock`) が物理化済み
- main HEAD の MVP が動く (`dbt run` / `dbt test` 緑)
- `dbt parse` が通る

## 入力データ

Topic ③ で物理化済みの staging 4 本。

| staging                       | grain                | 行数の目安 |
|-------------------------------|----------------------|------------|
| `stg_customers_100knock`      | 1 customer_id 1 行   | 1,000      |
| `stg_products_100knock`       | 1 product_id 1 行    | 100        |
| `stg_orders_100knock`         | 1 order_id 1 行      | 10,000     |
| `stg_stores_100knock`         | 1 store_id 1 行      | 5          |

## 課題

### Step 1: intermediate model を作る

`dbt/models/100-knock/topic-4/int_order_details_100knock.sql` を新規作成。

要件:

- **冒頭コメント** に grain を 1 行で宣言する。例:
  ```sql
  -- Grain: 1 row = 1 order_id (orders を主軸に master 3 本を INNER JOIN で enrich)。
  ```
- `{{ config(materialized='view', schema='intermediate') }}` を明示
  (`models/100-knock/topic-4/` は `dbt_project.yml` の `intermediate/` パス指定に
  引っかからないため、明示しないと target schema に作られる)
- `{{ ref('stg_orders_100knock') }}` を主軸に、`stg_customers_100knock` /
  `stg_products_100knock` / `stg_stores_100knock` を **INNER JOIN**
  - 理由: Topic ③ 3-4 で FK の `relationships:` test を張ったので、
    全 order に対して master が必ず引ける = INNER JOIN で漏れない
- 出力列: `order_id`, `order_date`, `customer_id`, `customer_name`,
  `product_id`, `product_name`, `category`, `store_id`, `quantity`, `unit_price`,
  `sales_amount` (= `quantity * unit_price`、`numeric(14,2)` cast)
- model ファイル名 = `int_order_details_100knock.sql` (node 名は
  `model.local_analytics.int_order_details_100knock` になる)

### Step 2: schema.yml を作る

`dbt/models/100-knock/topic-4/schema.yml` を新規作成 (4-2 以降の問でも追記していく
共通ファイル):

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
        tests:
          - not_null
      - name: customer_id
        tests:
          - not_null
      - name: product_id
        tests:
          - not_null
      - name: sales_amount
        description: "quantity * unit_price (numeric(14,2))。"
        tests:
          - not_null
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select int_order_details_100knock
../.venv/bin/dbt test --profiles-dir . --select int_order_details_100knock
```

期待出力: `PASS=1` (run) と `PASS=5` (test: order_id × 2 + 3 not_null + sales_amount not_null)。

## 完了条件

- [ ] `dbt/models/100-knock/topic-4/int_order_details_100knock.sql` が存在する
- [ ] 冒頭コメントに grain が 1 行で宣言されている
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_order_details_100knock` が登録される
- [ ] manifest 上、上流に `stg_*_100knock` が 4 本含まれる
- [ ] `dbt test --select int_order_details_100knock` で `unique` (on order_id) が PASS

## ヒント (詰まったら)

- **schema が `intermediate` にならない**: `models/100-knock/topic-4/` は
  `dbt_project.yml` の `intermediate/` パス指定に引っかからない。SQL 冒頭で
  `{{ config(materialized='view', schema='intermediate') }}` を明示する。
- **manifest の上流が 3 本しか出ない**: `ref()` を 4 つ書いたか確認。
  `stg_stores_100knock` を SELECT 列に使っていなくても JOIN しておけば
  manifest は依存と認識する。逆に「使ってないから」と JOIN 自体を消すと
  上流から外れる。
- **`unique` test が FAIL**: orders に複数 master が多重マッチする状況
  (master 側の PK が unique でない、もしくは JOIN 条件のタイポ) が原因。
  `select customer_id, count(*) from staging.stg_customers_100knock group by 1
  having count(*) > 1` で master 側を疑う。
- **MVP の `int_order_details` と紛らわしい**: model 名の suffix `_100knock` を
  忘れると `Found duplicate model` で dbt が落ちる。`dbt ls --select int_*` で
  `int_order_details` (MVP) と `int_order_details_100knock` (本問) が
  両方並ぶのが正しい。

## 解答例

詳細は [`4-1-int-order-details.solution.md`](4-1-int-order-details.solution.md) を参照。
