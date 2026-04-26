# task-003: load_raw_data.py

- Phase: 03
- Status: Done
- Owner: -
- Depends on: phase-02/task-002 (raw schema が必要), phase-03/task-001, phase-03/task-002
- Parallelizable with: -

## 目的
生成CSVを raw schema に冪等にロードする。

## 入力 / 前提
- spec §11.2
- `data/raw/{customers,products,stores,orders}.csv`（`generate_dummy_data.py` で生成、gitignore 済み）
- `.env`（`.env.example` を雛形にコピー、`DB_USER=dbt_user / DB_PASSWORD=dbt_password` に上書き）

## 成果物
- `scripts/load_raw_data.py`
- `docs/decisions/0004-raw-load-strategy.md`（ロード戦略の判断記録）

## 受入条件
- [x] 1回目実行で raw.customers/products/stores/orders が件数通り存在 (1000/100/20/10000)
- [x] 2回目以降の再実行でも件数が変わらない（DROP+CREATE+COPY で idempotent）
- [x] 環境変数（.env）から接続情報を取得（`python-dotenv` で defensive load）

## 実行ログ

### venv セットアップ + ダミーデータ生成

```text
$ uv venv --python 3.12
Using CPython 3.12.12
Creating virtual environment at: .venv

$ uv pip install -r requirements.txt
# (snowplow-tracker 経由を含めて 60+ パッケージを 3.12 環境にインストール)

$ .venv/bin/python scripts/generate_dummy_data.py
Generated dummy data:
  data/raw/customers.csv: 1000 rows
  data/raw/products.csv:  100 rows
  data/raw/stores.csv:     20 rows
  data/raw/orders.csv:  10000 rows

$ wc -l data/raw/*.csv
    1001 data/raw/customers.csv
   10001 data/raw/orders.csv
     101 data/raw/products.csv
      21 data/raw/stores.csv
```

### load_raw_data.py 1回目

```text
$ .venv/bin/python scripts/load_raw_data.py
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows
```

DB側からの確認 (`analytics_user` で `psql`):

```text
     t     | count
-----------+-------
 customers |  1000
 products  |   100
 stores    |    20
 orders    | 10000
```

### load_raw_data.py 2回目（冪等性チェック）

```text
$ .venv/bin/python scripts/load_raw_data.py
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows
```

DB側でも件数不変 (1000/100/20/10000)。二重投入されていないことを確認。

### サンプルデータチェック

```text
$ docker exec local-data-postgres psql -U analytics_user -d analytics \
    -c "SELECT * FROM raw.orders ORDER BY order_id LIMIT 3;"
 order_id | order_date | customer_id | product_id | store_id | quantity | unit_price
----------+------------+-------------+------------+----------+----------+------------
        1 | 2025-10-25 |         384 |         56 |        5 |        4 |    1050.00
        2 | 2025-07-29 |         422 |         73 |        6 |        3 |    8960.00
        3 | 2026-01-27 |          81 |         79 |       13 |       10 |    7240.00

$ ... -c "SELECT count(DISTINCT customer_id) FROM raw.orders;"
 distinct_customers
--------------------
               1000
```

- `order_date` が DATE として格納されていること（`2025-10-25` 形式）を確認。
- 全 1000 顧客が orders に少なくとも1回登場している（FK 整合性は staging テストでさらに検証する想定）。

### DDL 実物 (`\d raw.orders`)

```text
   Column    |     Type      | Nullable
-------------+---------------+----------
 order_id    | bigint        | not null   -- PRIMARY KEY
 order_date  | date          |
 customer_id | bigint        |
 product_id  | bigint        |
 store_id    | bigint        |
 quantity    | integer       |
 unit_price  | numeric(12,2) |
```

## 実装メモ / 判断ログ

### 1. 接続ロールに `dbt_user` を採用（最小権限）
- `.env.example` の既定は `analytics_user`（superuser）だが、`.env` では `dbt_user / dbt_password` に上書き。
- 根拠: Terraform で `raw` schema の owner は `dbt_user` であり、`CREATE` / `ALL` 権限が明示付与されている (`infra/terraform/main.tf` L34-67)。superuser を使う必要が無い。
- dbt 本体も `dbt_user` で接続する想定なので、ロード〜変換が同一ロール所有のままシームレスに進み、所有権由来のトラブルが起きない。

### 2. ロード戦略: DROP+CREATE+COPY（TRUNCATE ではなく）
- spec §11.2 は「truncateまたは再作成」と書いているので、再作成側を選択。
- 採用理由（要約、詳細は `docs/decisions/0004-raw-load-strategy.md`）:
  - CSV 列構造が変わったときも DDL を直せばロードがそのまま通る。
  - 初回実行・別環境構築時にも `IF EXISTS` のおかげで安全。
  - dbt source は実行時に名前解決するので、間で DROP/CREATE が走っても影響なし。
  - 現フェーズでは raw に依存する DB オブジェクト（FK・view）が存在しないため、`CASCADE` しても実害なし。

### 3. raw 層に FK 制約を入れない方針
- spec §4 の役割定義（raw=「CSVをそのまま投入」、staging=「型変換・列名統一・軽微な正規化」）に則る。
- `relationships` テストは spec §8.2 で staging に課されており、整合性検証はそちらで担保する。
- raw に FK を入れると、上流データの不整合をロード段階で弾いてしまい、調査の機会を奪うため。

### 4. psycopg3 `cursor.copy()` API + bytes モード
- `with cur.copy("COPY raw.x FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as cp` で COPY パイプを開き、`Path.open("rb")` から 64KiB チャンクを `cp.write(chunk)` で流す。
- bytes モードを選んだ理由: 顧客名・店舗名・都道府県に日本語が含まれるため、テキストモードでの暗黙の encode/decode を挟まずに、ファイルバイト列をそのまま COPY パイプに渡したい。Postgres 側の `client_encoding=UTF8` と CSV の UTF-8 出力で素直に整合する。

### 5. トランザクションの粒度
- `psycopg.connect(dsn)` を `with` で開き、4 テーブルを順に再作成→COPY したあと最後に `conn.commit()`。途中で失敗した場合は `with` 文の終了時にロールバックされ、raw 層は前回の状態のまま残る（部分的に DROP 済み・COPY 失敗、というハーフロード状態を避ける）。

### 6. 環境変数読み込みの方針
- `python-dotenv` の `load_dotenv(REPO_ROOT/'.env', override=False)` を使用。
- `override=False` により、shell や CI で既に export されている値を上書きしない（コンテナや CI で `.env` 不在でも動かしたいケースに備える）。
- 必須 5 変数 (`DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`) のチェックを `_build_dsn()` 内で実施し、欠けていれば exit 1 する。
