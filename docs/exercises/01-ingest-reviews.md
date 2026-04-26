# Exercise 01: 顧客レビューの取り込み

## シナリオ

あなたの会社が運営する EC で、商品レビュー機能をローンチした。日次で `reviews_YYYY-MM-DD.csv` が運用チームから `data/exercises/inbox/` に落ちてくる前提で、新しい raw テーブルとそれを土台にした staging model を作って欲しい。

最初の 1 ファイル（`reviews.csv`、2,000 行）が届いた。これを raw → staging まで運ぶのが今回のゴール。

## 学べること

- raw 層に新しいテーブルを追加する CSV ロードパターン
- `dbt/models/sources.yml` への source 追加
- staging model の書き方（型変換、`comment` の null 許容、派生列 `posted_date`）
- built-in tests: `not_null` / `unique` / `accepted_values` / `relationships`

## 前提

- main HEAD（spec §13 完了状態）— `dbt run` / `dbt test` が緑
- `.venv/` `.env` セットアップ済み
- `raw.customers` (1,000 行) と `raw.products` (100 行) がロード済み

## 入力データ

CSV を生成する:

```bash
.venv/bin/python scripts/exercises/generate_01_reviews.py
# => data/exercises/inbox/reviews.csv (2,000 行 + ヘッダ)
```

スキーマ:

| 列            | 型            | 備考                                       |
|---------------|---------------|--------------------------------------------|
| `review_id`   | bigint        | 1..2000、PK                                |
| `customer_id` | bigint        | 1..1000、`raw.customers` への FK           |
| `product_id`  | bigint        | 1..100、`raw.products` への FK             |
| `rating`      | int           | 1〜5                                       |
| `comment`     | text          | 約 10% は null（コメント無しレビュー）     |
| `posted_at`   | timestamp     | ISO 8601 (`2026-03-03T19:14:58`)           |

サンプル:

```csv
review_id,customer_id,product_id,rating,comment,posted_at
1,479,7,5,バナーインチカレッジオークション...,2025-11-29T06:58:34
2,710,28,3,彼必要ボトル野球風景細かい建築再現する。,2026-03-03T19:14:58
3,612,55,4,,2026-04-10T10:22:11
```

## 課題

### Step 1: CSV を生成して中身確認

```bash
.venv/bin/python scripts/exercises/generate_01_reviews.py
wc -l data/exercises/inbox/reviews.csv  # 2001
head -3 data/exercises/inbox/reviews.csv
```

行数 2001（ヘッダ + 2000）になることを確認。

### Step 2: raw.reviews テーブルを作って CSV をロード

`scripts/load_raw_data.py` の `TABLES` 構成を参考に、新しい簡易ローダーを 1 本書く。

- 接続は `.env` の `DB_HOST/PORT/NAME/USER/PASSWORD`（`dbt_user`）
- `DROP TABLE IF EXISTS raw.reviews CASCADE` → `CREATE TABLE raw.reviews (...)` → `COPY raw.reviews FROM STDIN WITH (FORMAT CSV, HEADER TRUE)`
- 列定義は上のスキーマ表に合わせる（`comment` は NULL 許容）

完了の見え方: `psql` で `SELECT count(*) FROM raw.reviews;` が `2000` を返す。

### Step 3: source として宣言

既存の `dbt/models/sources.yml` には raw の 4 テーブルが宣言されている。**既存ファイルは編集しない方針** なので、新しい source 定義ファイルを `dbt/models/exercises/01/sources.yml` に置く。

最低限以下を含めること:

- `version: 2`
- `sources` 配下に `name: raw_exercise` を追加（既存の `name: raw` と衝突させないため、別名で同じ schema を指す）
- `schema: raw`
- `tables:` に `name: reviews` を 1 件
- 各 column の `tests` （PK の `not_null` / `unique`、FK 列の `not_null`）

### Step 4: staging model `stg_reviews.sql` を書く

`dbt/models/exercises/01/stg_reviews.sql` を作る。

要件:

- 明示的な型キャスト（`review_id::bigint`、`rating::int`、`posted_at::timestamp` など）
- 派生列 `posted_date` を `posted_at::date` で生成（後続マートで日次集計に使えるようにする）
- materialization は `view`（dbt_project.yml の staging デフォルトに従う、または `{{ config(materialized='view', schema='staging') }}` を明示）

### Step 5: schema.yml にテストを書く

`dbt/models/exercises/01/schema.yml` を作る。最低限:

- `review_id`: `not_null`, `unique`
- `customer_id`: `not_null` + `relationships` to `ref('stg_customers')` の `customer_id`
- `product_id`:  `not_null` + `relationships` to `ref('stg_products')` の `product_id`
- `rating`: `not_null` + `accepted_values` (1, 2, 3, 4, 5)
- `posted_at`: `not_null`

### Step 6: 実行して通すこと

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_reviews
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
```

## 完了条件

- [ ] `wc -l data/exercises/inbox/reviews.csv` が `2001`
- [ ] `SELECT count(*) FROM raw.reviews` が `2000`
- [ ] `dbt run --select stg_reviews` が `Done. PASS=1`
- [ ] `dbt test --select stg_reviews` が全て PASS（最低でも 7〜8 件）
- [ ] `staging.stg_reviews` を `psql` で覗くと `posted_date` 列が DATE 型で返る

## ヒント（詰まったら）

- **dbt が新 source を見つけてくれない**: `sources.yml` は `dbt/models/` 配下のどこにあっても OK だが、`name:` がプロジェクト全体でユニークである必要がある。`name: raw` は MVP で使われているので別名（`raw_exercise` など）にする。
- **relationships テストが落ちる**: `to:` には `ref('stg_customers')` のように既存 staging を指すと FK 不整合に強い。`source('raw', 'customers')` を直接参照することもできるが MVP の依存関係グラフを汚すので非推奨。
- **派生列の型**: Postgres は `'2026-03-03T19:14:58'::timestamp` を受け付けるが、CSV 由来の文字列は staging で明示キャストすると下流で安心。
- **`comment` が NULL の行を扱う**: COPY は空フィールドを NULL として読み込んでくれる（`COPY ... WITH (FORMAT CSV, HEADER TRUE)` のデフォルト挙動）。テーブル DDL で `comment` を NULL 許容にしておくこと。

## 解答例

詳細は [`solutions/01-ingest-reviews.solution.md`](solutions/01-ingest-reviews.solution.md) を参照。
