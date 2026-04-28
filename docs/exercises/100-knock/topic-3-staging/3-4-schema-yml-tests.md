# 3-4: schema.yml に not_null / unique / relationships を書き切る

## シナリオ

3-1〜3-3 で staging model 3 本 (`stg_customers_100knock` / `stg_products_100knock` /
`stg_orders_100knock`) を物理化した。SQL 側で型と命名を整えただけでは、実データの不変条件
(「PK は重複しない」「FK は親テーブルに存在する」) は保証されていない。
今回は **`schema.yml` を仕上げて、staging 全体に `not_null` / `unique` / `relationships` を
張り、`dbt test` でデータ契約を行レベルで検証する** のがゴール。

これが「staging contract = データ契約」の宣言面の集大成になる。

## 学べること

- `schema.yml` の column-level test の書き方 (`tests:` 配下に `not_null` / `unique`)
- `relationships:` テストで FK 整合性を **dbt の DAG として** 担保する
- `arguments: { to: ref(...), field: ... }` の最新 dbt 1.11 構文
- なぜ generic test が singular test より良いのか (再利用性 / 自動命名)
- 1 つの `schema.yml` で staging 全 model のテスト宣言をどう束ねるか

## 前提

- 3-1, 3-2, 3-3 完了: `stg_customers_100knock` / `stg_products_100knock` /
  `stg_orders_100knock` の 3 model が物理化済み
- 学習者は `dbt/models/100-knock/topic-3/schema.yml` を **既に作っている**
  (3-1 で骨格、3-2 / 3-3 で追記してきたもの)。今回はそれを「完成形」に仕上げる

## 入力データ

`staging.stg_customers_100knock` (1,000 行) / `staging.stg_products_100knock` (100 行) /
`staging.stg_orders_100knock` (10,000 行) — 3-1〜3-3 で物理化済み。

## 課題

### Step 1: schema.yml を仕上げる

`dbt/models/100-knock/topic-3/schema.yml` を以下の要件を満たすように書き直す:

- `version: 2` 始まり
- `models:` 配下に 3 model (`stg_customers_100knock` / `stg_products_100knock` /
  `stg_orders_100knock`) を全部列挙
- 各 model の **PK 列** に `not_null` + `unique`
- `stg_orders_100knock` の **FK 列 3 本** (`customer_id` / `product_id` / `store_id`) に:
  - `not_null`
  - `relationships:` で対応する staging を参照
    - `customer_id` → `ref('stg_customers_100knock')` の `customer_id`
    - `product_id`  → `ref('stg_products_100knock')`  の `product_id`
    - `store_id`    → `ref('stg_stores_100knock')`    の `store_id` (← 3-6 で 3-stores 担当の sibling 問題を作る予定。**この問では `store_id` の relationships は省略 OK**、または存在しない参照を残しても relationships test は SKIP される)
- その他の `not_null` 制約 (e.g. `order_date` / `quantity` / `unit_price`) も付ける

### relationships テストの構文 (dbt 1.11+)

```yaml
- name: customer_id
  tests:
    - not_null
    - relationships:
        arguments:
          to: ref('stg_customers_100knock')
          field: customer_id
```

`arguments:` ネスト形式が dbt 1.11 から推奨。古い `to:` / `field:` をトップレベルに
書く形式は warn が出る可能性がある。

### Step 2: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_customers_100knock stg_products_100knock stg_orders_100knock
```

期待出力: `PASS=10` 程度 (PK の not_null+unique 6 件 + orders の FK 関連数件 + その他)。

### Step 3: わざと壊して FAIL を体感する

```sql
-- FK を破壊
UPDATE raw.orders SET customer_id = 99999 WHERE order_id = 1;
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
# => relationships_stg_orders_100knock_... が FAIL
```

戻す:

```sql
UPDATE raw.orders SET customer_id = 1 WHERE order_id = 1;
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/schema.yml` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest 上の test 数が 8 件以上 (PK 系 6 + relationships 2 以上)
- [ ] `dbt test --select stg_orders_100knock` が PASS (FK 違反 0 行)
- [ ] `relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_` のような
      テストが manifest に登録される

## ヒント (詰まったら)

- **`relationships` test が SKIP される**: `to: ref('stg_xxx_100knock')` で参照先が
  manifest に存在しない (タイポなど) と dbt は test 自体を生成しない。
  `dbt ls --select stg_customers_100knock` で参照先 model の存在を確認。
- **`tests:` vs `data_tests:`**: dbt 1.8+ で `data_tests:` が推奨だが、本リポジトリの
  dbt-core 1.11 では `tests:` も後方互換で動く。どちらでも採点は通る。
- **`relationships` の意味**: 「子テーブルの FK 列の値が、親テーブルの PK 列に **必ず存在する**」
  という不変条件を SQL に展開して検査する。実装は `LEFT JOIN ... WHERE parent.pk IS NULL` 相当。
- **複数の test を 1 列に書く**: `tests: [not_null, unique]` のように YAML リストで
  並べるだけ。順序は問わない。
- **MVP の `dbt/models/staging/schema.yml` を真似する**: 同じパターンで FK
  relationships を 3 本書いている。コピペベースで OK。

## 解答例

詳細は [`3-4-schema-yml-tests.solution.md`](3-4-schema-yml-tests.solution.md) を参照。
