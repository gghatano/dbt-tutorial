# 9-10: 大規模 (orders 100,000 行) で `mart_orders_incremental_100knock` (incremental, merge) と `mart_orders_full_100knock` (table, 全件再構築) を 5 回連続 run、所要時間を表で比較

## シナリオ

ここまでで「incremental は差分 merge」「table は全件再構築」と概念は学んだが、**実数値で 「incremental が x 倍速」を出していない**。本問では大規模ダミー (orders 10 万行) を生成し、`incremental` と `table` の 2 本を **5 回連続で run**、各 run の所要時間を表にまとめて「**差分処理の損益分岐点**」を数値で示す。

これは Topic ⑨ の集大成。`materialization='table'` が「**毎回フル再構築**」、`materialization='incremental'` が「**初回フル + 2 回目以降は差分のみ**」 — この差を 100,000 行スケールで体感し、**いつ incremental に切り替えるべきか** を自分の判断軸で語れるようにする。

## 学べること

- `materialized='incremental' vs 'table'` の体感速度差
- `--full-refresh` で incremental を強制フル再構築する方法
- 「初回 build は両者同じ、2 回目以降に incremental が圧勝」というパターン
- 計測スクリプトを書いて「数値で語る」習慣
- ROI (= 何倍速 / 何回回せば元が取れる) の概念

## 前提

- Topic ② 〜 ⑦ + ⑧ + 9-1〜9-9 完了
- 9-2 で `mart_orders_incremental_100knock` (incremental, merge) を実装済み
- `dbt parse` が通る
- ディスク空き 200MB 以上 (10 万行 csv + 物質化テーブル分)

## 入力データ

学習者が Python script で 10 万行の orders CSV を生成し、`raw.orders_100knock` に投入する。

## 課題

### Step 1: 大規模生成スクリプトを書く

`scripts/100-knock/topic-9/generate_large_orders.py` を新規作成。

要件:

- `--rows` 引数 (default 100000) を受け、`data/100-knock/topic-9/large_orders.csv` に書き出す
- 列: `order_id` (1..N PK)、`order_date` (2024-01-01〜2026-04-26 のランダム)、`customer_id` (1..1000)、`product_id` (1..100)、`store_id` (1..20)、`quantity` (1..10)、`unit_price` (100〜9990)、`loaded_at` (各日 23:59:59)
- 同一 `--rows` で何度走らせても同じ結果 (deterministic / 固定シード)

### Step 2: raw.orders_large を投入

CSV 生成 → `raw.orders_large` テーブル DDL (8 列: order_id PK, order_date, customer_id, product_id, store_id, quantity, unit_price, loaded_at) → `\copy` で COPY。`docker exec -i local-data-postgres psql -U dbt_user -d analytics` 経由で実行 (詳細は解答例)。投入後 `select count(*) from raw.orders_large` で 100,000 行を確認。

### Step 3: 2 本の mart モデルを作る

- `dbt/models/100-knock/topic-9/sources.yml` に `raw_100knock_large` source を宣言 (schema: raw, tables: [orders_large])
- `dbt/models/100-knock/topic-9/mart_orders_full_100knock.sql`: `materialized='table'` で `select * from source(...)`
- `dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql`: `materialized='incremental'`, `unique_key='order_id'`, `incremental_strategy='merge'`, `is_incremental()` 分岐で `where loaded_at > (select max(loaded_at) from {{ this }})`

詳細 SQL は解答例参照。9-2 で既に同名 model があるなら本問では別名 (例: `_large_` 付き) にしてもよい — 採点 yaml の対象 model 名は読み替え可能。

### Step 4: 計測スクリプトを書く

`scripts/100-knock/topic-9/measure_incremental_roi.py` を新規作成。

要件:

- 5 回連続で `dbt run --select mart_orders_full_100knock` を回し、各 run の所要時間を計測
- 同じく 5 回連続で `dbt run --select mart_orders_incremental_100knock` を回し計測
  - 1 回目 (= 初回フル) と 2 回目以降 (= 差分 0 行) で挙動が違うことを観察
- 結果を表として stdout 出力 + `docs/exercises/100-knock/topic-9-performance/incremental-roi.md` に書き込み

(簡単版として bash + `time` でも可。Python の `subprocess.run` + `time.perf_counter()` がおすすめ)

### Step 5: 計測実行

```bash
set -a; source .env; set +a
.venv/bin/python scripts/100-knock/topic-9/measure_incremental_roi.py
```

期待出力 (要旨): table は 5 回とも約 2.2s でほぼ一定。incremental は 1 回目だけ ~2.5s (初回フル)、2 回目以降は ~0.18s (差分 0 で no-op)。`高速化倍率 ≒ 12 倍速` を md に記録。

### Step 6: incremental-roi.md に記録

`docs/exercises/100-knock/topic-9-performance/incremental-roi.md` を新規作成。最低限以下を含める:

- 計測環境 (データ行数、DB、日付)
- **5 回 × 2 model の計測表** (秒数の数値が並ぶ markdown 表)
- 高速化倍率 (例: `incremental は table の 12.7 倍速`) — 「**倍速**」キーワード必須
- 損益分岐点の考察 (何回目で incremental の overhead が回収されるか)

詳細は解答例を参照。

### Step 7: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-9-performance/9-10-incremental-roi.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-9/generate_large_orders.py` が存在
- [ ] `data/100-knock/topic-9/large_orders.csv` が 100,000 行 + ヘッダ
- [ ] `raw.orders_large` テーブルに 100,000 行が投入済み
- [ ] `mart_orders_incremental_100knock` (incremental) と `mart_orders_full_100knock` (table) 両方が build 成功
- [ ] `docs/exercises/100-knock/topic-9-performance/incremental-roi.md` に **5 回 × 2 model の計測表** と「**x 倍速**」表現がある

## ヒント (詰まったら)

- **CSV 生成が遅い**: pandas の DataFrame を全件メモリに展開してから `to_csv()` で OK (10 万行程度なら 200MB に収まる)
- **CSV を raw schema に投入**: `\copy` (psql クライアント) または Python `psycopg.copy()`。docker-compose 環境なら `docker exec` 経由で `\copy` が手早い
- **incremental の 2 回目以降が遅い**: `where loaded_at > max(loaded_at)` の `is_incremental()` 分岐が機能していない可能性。`dbt run --select model_name` のログを `--no-colors` で確認し、SQL 末尾に `where` 節があるか確認
- **計測 noise**: 1〜2 回目だけ遅い (DB cache が冷たい) ことがある。3 回目以降の中央値で評価
- **`mart_orders_full_100knock` が `table` で毎回 DROP+CREATE される**: 正しい挙動。これが「全件再構築」のコスト
- **「`x 倍速`」キーワード**: 採点 grep で「`倍速` または `times faster`」を見ているので、md に必ず含めること

## 解答例

詳細は [`9-10-incremental-roi.solution.md`](9-10-incremental-roi.solution.md) を参照。
