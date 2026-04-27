# Exercise 03: 新規注文を incremental に取り込む

## シナリオ

営業日終わりに、その日新規発生した注文 CSV が `data/exercises/inbox/orders_YYYY-MM-DD.csv` 形式で積まれていく運用が始まった。

毎回フル refresh していると 10 万行 / 100 万行と増えた時に辛くなるので、`incremental` materialization で「**前回 build 以降の差分だけ追加する**」モデル `stg_orders_inc` を実装する。

ここでは MVP の `stg_orders`（10,000 行）はそのまま残しつつ、**別系統** で「日次差分テーブル → incremental 統合 view」のパイプを 1 本作る。

## 学べること

- `materialized='incremental'` の挙動
- `is_incremental()` jinja 関数で初回 vs 差分実行を分岐する
- `unique_key` と `incremental_strategy='merge'` / `'append'` / `'delete+insert'`
- `--full-refresh` で全件作り直し
- `on_schema_change` パラメタの基本

## 前提

- main HEAD 完了状態
- `.venv/` `.env` セットアップ済み
- Exercise 01 / 02 とは独立。Exercise 01 は完了していなくてもよい

## 入力データ

専用の generate スクリプト:

```bash
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-27 --rows 500
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-28 --rows 500
```

出力: `data/exercises/inbox/orders_2026-04-27.csv` / `orders_2026-04-28.csv`、各 500 行 + ヘッダ。

スキーマ（既存 `raw.orders` + `loaded_at` を 1 列追加）:

| 列            | 型         | 備考                                           |
|---------------|------------|------------------------------------------------|
| `order_id`    | bigint     | `100001 + offset(date) * 10000` 起点で連番、PK  |
| `order_date`  | date       | 引数の `--date` と一致                          |
| `customer_id` | bigint     | 1..1000                                       |
| `product_id`  | bigint     | 1..100                                        |
| `store_id`    | bigint     | 1..20                                         |
| `quantity`    | int        | 1..10                                         |
| `unit_price`  | numeric    | 商品ID ベースで安定                            |
| `loaded_at`   | timestamp  | 当日 23:59:59、incremental の高水位線として使う |

`order_id` は MVP の `raw.orders`（1..10000）と衝突しない範囲（>= 100001）を確保する。

## 課題

### Step 1: 受信トレイ的な raw テーブルを作る

`raw.orders_increment` を作成し、CSV を `COPY` で突っ込む簡易スクリプトを書く。

要件:

- テーブル定義は CSV と同じ列構成
- 1 回目（`--date 2026-04-27`）は `DROP + CREATE + COPY`
- 2 回目以降（`--date 2026-04-28` ...）は **TRUNCATE せずに APPEND**（差分検証のため、複数日分が `raw.orders_increment` に積み上がる前提）

簡略化のため、追加 CSV を 1 つずつ `COPY` で append する script でよい。

### Step 2: source を宣言

`dbt/models/exercises/03/sources.yml` に `raw_exercise_03` などの論理名で `raw.orders_increment` を宣言する。

### Step 3: `stg_orders_inc.sql` を incremental で実装

`dbt/models/exercises/03/stg_orders_inc.sql` を作る。

要件:

- `config(...)` で `materialized='incremental'` / `unique_key='order_id'`
- `incremental_strategy='merge'` / `on_schema_change='fail'` / `schema='staging'`
- 本体 SQL は `select ... from {{ source('raw_exercise_03', 'orders_increment') }}`
- 2 回目以降のみ差分に絞る:
  ```jinja
  {% if is_incremental() %}
  where loaded_at > (select coalesce(max(loaded_at), '1970-01-01'::timestamp) from {{ this }})
  {% endif %}
  ```
- 初回 / `--full-refresh` 時は `is_incremental()` が False になり、上記 where 節が消えて全件 SELECT になることを確認

詰まったら下のヒント、それでも分からなければ解答例。

### Step 4: 1 日目を投入 → 初回 dbt run

```bash
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-27 --rows 500
.venv/bin/python scripts/exercises/load_orders_increment.py --csv data/exercises/inbox/orders_2026-04-27.csv --mode replace

set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc
```

完了の見え方:

- `staging.stg_orders_inc` が作られて `count(*) = 500`

### Step 5: 2 日目を append → 差分 dbt run

```bash
cd ..
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-28 --rows 500
.venv/bin/python scripts/exercises/load_orders_increment.py --csv data/exercises/inbox/orders_2026-04-28.csv --mode append

cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc
```

完了の見え方:

- `staging.stg_orders_inc` が `count(*) = 1000`
- ログに `incremental` で `1 of 1 OK created` が出る（フル recreate ではないこと）

### Step 6: full refresh を試す

```bash
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc --full-refresh
```

`is_incremental()` が False に評価され、`where` 節がスキップされて全件再作成される。`count(*) = 1000` のまま（`raw.orders_increment` に 1000 行積まれているので結果は同じ）。

ログ上は table が DROP + CREATE で再作成される（`OK created sql incremental model ...` ではなく、target 上 `model.sql` が full-rebuild モードになる）。

## 完了条件

- [ ] 2 つの CSV (`orders_2026-04-27.csv`, `orders_2026-04-28.csv`) が生成される
- [ ] `raw.orders_increment` が 1000 行
- [ ] 1 回目の `dbt run --select stg_orders_inc` 後、`staging.stg_orders_inc` の件数が 500
- [ ] 2 回目の `dbt run --select stg_orders_inc` 後、件数が 1000
- [ ] `dbt run --select stg_orders_inc --full-refresh` でも件数 1000 のまま、ログ上 full rebuild になる

## ヒント（詰まったら）

- **`is_incremental()` が初回で True を返してしまう**: dbt 1.x では「テーブルが存在し、`--full-refresh` でない時」に True になる。初回は table が無いので False が返る、これが期待挙動。`--full-refresh` を付けると tablle DROP → False に戻る。
- **`unique_key` 無しだと merge できない**: `incremental_strategy='merge'` には `unique_key` が必須。指定しないと dbt が ERROR で落ちる。
- **2 日目の差分が 0 行**: `where loaded_at > max(loaded_at)` の `max` が 1 日目の `2026-04-27 23:59:59` を返すので、2 日目の `2026-04-28 23:59:59` のみが通る。当日 CSV に同 `loaded_at` が並んでいる場合は `>=` ではなく `>` で OK。
- **postgres adapter での merge**: dbt-postgres は merge を内部で `delete + insert` に展開する。`unique_key='order_id'` の重複チェックはここで効く。`append` strategy にすると重複が発生しうるので注意。
- **`load_orders_increment.py` を書くのが面倒**: `psql` コマンドでも代用できる:
  ```bash
  docker exec -i local-data-postgres psql -U dbt_user -d analytics -c \
      "\\copy raw.orders_increment FROM 'data/exercises/inbox/orders_2026-04-27.csv' WITH (FORMAT csv, HEADER true)"
  ```
  ※ コンテナ側のパス解決に注意。コンテナ内に持ち込んでから `\copy` する方が確実。

## 解答例

詳細は [`solutions/03-incremental-orders.solution.md`](solutions/03-incremental-orders.solution.md) を参照。
