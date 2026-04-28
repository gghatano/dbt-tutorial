# 2-1: `raw` schema を作って 4 テーブルを CSV から COPY 投入する

## シナリオ

Topic ① で生成した 4 つの CSV (`customers` / `products` / `stores` / `orders`) を、
分析 DB の `raw` schema にロードする。これは「**dbt が触れない外部世界 ↔ 分析基盤**」の
**物理境界** を確定する作業で、後で `sources.yml` に書く論理 source の "実体" になる。

ここでは MVP の `scripts/load_raw_data.py` を雛形にして、Topic ② 専用の
`scripts/100-knock/topic-2/load_raw.py` を書き起こす。**MVP のスクリプトはそのまま動かす**
のではなく、入力パスを `data/100-knock/topic-1/` に切り替えた "学習者バージョン" を
自分の手で組むことで、`COPY ... FROM STDIN` の流れと DDL を体に通す。

## 学べること

- `psycopg.connect` + `cursor.copy()` で CSV を高速一括投入する `COPY ... FROM STDIN` パターン
- DDL に **PK / 型** を明示することで、後段の `source` テストが机上の空論にならない土台を作る
- `DROP TABLE IF EXISTS ... CASCADE` → `CREATE TABLE` → `COPY` という **冪等ロード** の 3 段
- 同一トランザクション内で 4 テーブルをまとめて commit して "all-or-nothing" にする意味
- `.env` 経由の DSN 構築 (host/port/db/user/password を環境変数から拾う)

## 前提

- Topic ① 1-1〜1-9 を完了済みで、`data/100-knock/topic-1/` 配下に
  `customers.csv` / `products.csv` / `stores.csv` / `orders.csv` の 4 ファイルが揃っている
- MVP の docker-compose で Postgres が立ち上がっており、`raw` schema が bootstrap 済み
  (`docker compose up -d` + `scripts/ci/bootstrap_schemas.sql` 相当)
- `.env` に `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` が定義済み
- `requirements.txt` から `psycopg[binary]` と `python-dotenv` がインストール済み

## 入力データ

| パス | 行数 | 主キー | 列 |
|---|---|---|---|
| `data/100-knock/topic-1/customers.csv` | 1,000 | `customer_id` | `customer_id, customer_name, email, created_at` |
| `data/100-knock/topic-1/products.csv` | 100 | `product_id` | `product_id, product_name, category, unit_price` |
| `data/100-knock/topic-1/stores.csv` | 20 | `store_id` | `store_id, store_name, prefecture` |
| `data/100-knock/topic-1/orders.csv` | 10,000 | `order_id` | `order_id, order_date, customer_id, product_id, store_id, quantity, unit_price` |

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-2/load_raw.py` を新規作成する。

要件:

- 4 テーブルを `raw.customers` / `raw.products` / `raw.stores` / `raw.orders` として作る
- 各テーブルの DDL を **PK + 型** 付きで宣言 (MVP 版の `TableSpec` 構造を参考にする)
- 入力 CSV パスは `data/100-knock/topic-1/<table>.csv`
- `DROP TABLE IF EXISTS raw.<name> CASCADE` → `CREATE TABLE raw.<name> (...)` → `COPY raw.<name> FROM STDIN WITH (FORMAT CSV, HEADER TRUE)` の 3 段
- 接続情報は `.env` から `python-dotenv` 経由で読む (`DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`)
- 1 つの `psycopg.connect` 内で 4 テーブルをロードし、最後に **1 回だけ commit**
- 標準出力に `Loaded raw.<name>: <n> rows` のような行数サマリを出す

### Step 2: 実行

```bash
set -a; source .env; set +a
python3 scripts/100-knock/topic-2/load_raw.py
```

期待される出力例:

```
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows
```

### Step 3: 件数を psql で確認

```bash
psql "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT count(*) FROM raw.orders;"
# => 10000
```

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-1-raw-load.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-2/load_raw.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `raw.customers` が 1,000 行
- [ ] `raw.products` が 100 行
- [ ] `raw.stores` が 20 行
- [ ] `raw.orders` が 10,000 行
- [ ] 2 回実行しても結果が同じ (`DROP TABLE IF EXISTS CASCADE` で冪等)

## ヒント (詰まったら)

- **DROP CASCADE が怖い**: MVP 設計上、`raw.*` を CASCADE で落とすと依存している view が一緒に消えるが、
  dbt は次回 `dbt run` で再構築するだけなので壊れない (詳細は `docs/decisions/0004-raw-load-strategy.md`)。
- **COPY の速さ**: `INSERT` を 10,000 回打つより `COPY ... FROM STDIN` の方が **桁違いに速い**。
  ローカルでも数秒で終わるはず。
- **バイナリで読む**: `table.csv_path.open("rb")` で開いてバイト列のままパイプに流すと、
  日本語 (店舗名・顧客名) のエンコード往復事故を防げる。
- **トランザクション境界**: `with psycopg.connect(dsn) as conn:` ブロックを抜けるときに
  例外が出ていれば自動 rollback、出ていなければ commit が走る。明示 `conn.commit()` を最後に書いておくと安全。
- **DB_USER の権限**: `dbt_user` で接続するのが推奨 (`raw` schema の owner)。
  `analytics_user` (superuser) でも動くが、最小権限の原則からは外れる。

## 解答例

詳細は [`2-1-raw-load.solution.md`](2-1-raw-load.solution.md) を参照。
