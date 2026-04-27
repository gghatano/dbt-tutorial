# Exercise 04: 価格変動を snapshot で履歴化

## シナリオ

マーチャンダイザが `products` の `unit_price` を時々改定する。改定すると `raw.products` の値が新しい価格に **上書き** されるため、過去の注文に「当時の価格」を紐づける手段が無くなる。

これを救うのが dbt snapshot。`raw.products` を SCD Type-2 として履歴化し、`valid_from` / `valid_to` 列で「いつからいつまで有効だったか」を持つ。

## 学べること

- `dbt snapshot` の基本（`snapshots/*.sql`、`{% snapshot %}` ブロック）
- `check` strategy（特定列の値変化で履歴化）
- `dbt_valid_from` / `dbt_valid_to` / `dbt_scd_id` メタ列
- target_schema の指定（カスタム `generate_schema_name` macro との組み合わせ）

## 前提

- main HEAD 完了状態
- `data/raw/products.csv`（`generate_dummy_data.py` の出力）が手元にある
- Exercise 01〜03 とは独立

## 入力データ

```bash
.venv/bin/python scripts/exercises/generate_04_price_update.py
# => data/exercises/inbox/products_v2.csv
```

`products_v2.csv` は元の `data/raw/products.csv`（100 行）と **20 行だけ unit_price が違う**。残り 80 行は完全に同じ。

## 課題

### Step 0: snapshots schema を用意する

Terraform は raw / staging / intermediate / marts の 4 schema しか作っていない。snapshot を `snapshots` schema に置くために事前に手で作る。

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -c "CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;"
```

本番運用なら Terraform に schema を追加するべきだが、本演習では学習目的で手動作成にとどめる（Terraform 拡張は [Exercise 09](09-hooks-and-grants.md) で扱う運用近接の話題）。

### Step 1: snapshot 定義を書く

`dbt/snapshots/exercises/snap_products.sql` を作る。

要件:

- `{% snapshot snap_products %}` ブロック
- target は `raw.products` を `source('raw', 'products')` で参照
- strategy は `check`、`check_cols=['unit_price']`
- `unique_key='product_id'`
- `target_schema='snapshots'` を明示する（custom macro と整合させる、後述）

ヒント: dbt のドキュメント [Snapshots](https://docs.getdbt.com/docs/build/snapshots) を参考に。

### Step 2: 1 回目の `dbt snapshot`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products
```

完了の見え方:

- `snapshots.snap_products` が作られて `count(*) = 100`
- `dbt_valid_from` は今の timestamp、`dbt_valid_to` は全て NULL（最新行）

### Step 3: raw.products を v2 で更新

`scripts/load_raw_data.py` の products 部分を流用するか、簡単な単発スクリプトを書く:

```python
# 雰囲気
DROP TABLE IF EXISTS raw.products CASCADE;
CREATE TABLE raw.products (...);
COPY raw.products FROM stdin WITH (FORMAT csv, HEADER true);
# ファイルは data/exercises/inbox/products_v2.csv
```

完了の見え方: `SELECT count(*) FROM raw.products;` が 100 のまま、ただし 20 行だけ `unit_price` が変わっている。

### Step 4: 2 回目の `dbt snapshot`

```bash
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products
```

完了の見え方:

- `snapshots.snap_products` が `count(*) = 120`（更新された 20 行 × 2 + 変わらない 80 行 × 1）
- 旧行（v1）: `dbt_valid_to` が今の timestamp で埋まる
- 新行（v2）: `dbt_valid_to` が NULL

### Step 5: 履歴を確認

```sql
SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to
FROM snapshots.snap_products
WHERE product_id IN (
    SELECT product_id
    FROM snapshots.snap_products
    GROUP BY product_id
    HAVING count(*) > 1
)
ORDER BY product_id, dbt_valid_from;
```

20 商品が 2 行ずつ（v1 + v2）出れば成功。

### Step 6 (任意): 当時の価格を引ける view を作る

`dbt/models/exercises/04/int_orders_with_historical_price.sql`:

- `int_order_details` の `order_date` を、`snap_products` の `dbt_valid_from <= order_date < coalesce(dbt_valid_to, '9999-12-31')` 範囲で JOIN
- 「注文時点でのその商品の `unit_price`」を取り出せる

## 完了条件

- [ ] `dbt snapshot --select snap_products`（1 回目）後、`snapshots.snap_products` が 100 行
- [ ] `raw.products` を v2 にロードして 2 回目を実行後、120 行
- [ ] 更新された 20 商品それぞれが履歴 2 行（v1: `dbt_valid_to` あり、v2: `dbt_valid_to` NULL）

## ヒント（詰まったら）

- **snapshot の schema が `<target>_snapshots` に飛ぶ**: 既存 MVP の `dbt/macros/get_custom_schema.sql` が `generate_schema_name` を override して「`custom_schema_name` をそのまま返す」仕様。snapshot の `target_schema='snapshots'` がそのまま `snapshots` schema として作られる（schema 自体は Step 0 で作成済み）。
- **strategy の選択**: `timestamp` strategy は CSV に `updated_at` 列があれば最も効率的だが、今の `raw.products` には無い。`check` strategy なら任意の列の値変化を検知してくれる。
- **`dbt snapshot` を 2 回叩いても何も起きない**: ソース側 (`raw.products`) が変わっていない限り snapshot は no-op（既存行の `dbt_valid_to` も触らない）。Step 3 で v2 を流し込むのを忘れていないか確認。
- **2 回目で全 100 行に新版が出る**: `check_cols=['unit_price']` ではなく `check_cols=['product_id']` のように **常に変わらない列** を指定すると一切履歴化されないし、逆に存在しない列だと dbt が ERROR で落ちる。`unit_price` を指定する。
- **`dbt snapshot` が「snapshot is missing schema_name」エラー**: snapshot ブロック内 `target_schema` を必ず指定する。`dbt_project.yml` の `snapshots:` セクションで一括指定もできる。

## 解答例

詳細は [`solutions/04-snapshot-product-price.solution.md`](solutions/04-snapshot-product-price.solution.md) を参照。
