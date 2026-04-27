# 9-8: `staging/stg_orders_100knock.sql` の 1 列を変更し、`dbt run --select state:modified+` で自分と下流のみ build

## シナリオ

PR レビューで「`stg_orders_100knock` の 1 列を変えただけなのに、CI で全 model 再 build しているせいで遅い」という不満が出た。dbt の `state:modified+` セレクタは **前回 manifest と現在 manifest の差分** から「変更された model + その下流」を自動で算出してくれる仕組み。これを使うと「壊れた箇所だけ最小コストで再 build」が可能になる。

本問では `staging/stg_orders_100knock.sql` に 1 列追加 → 前回 manifest を `prev-manifest/` に保存 → `dbt run --select state:modified+ --state ./prev-manifest/` で差分 build → ログを `state-modified.md` に記録、という手順を踏む。

「変更影響範囲を **manifest 差分から宣言で導出**」する dbt の核心機能。本番 CI では `--defer` と組み合わせて「PR で触った model + 下流 + テスト」だけを最小コストで回す王道パターンになる。

## 学べること

- `dbt run --select state:modified+` の意味 (`state:modified` = 自身、`+` で下流まで)
- `--state <dir>` で **前回 manifest を別 dir に保存**して比較する作法
- 変更検出の粒度 (SQL 文字列比較 + macro 依存 + config 変更)
- CI における「差分 build」の典型パターン
- `state:modified+` で「上流 (`+state:modified`) は含まない」 — 上流が変わっていれば別問

## 前提

- Topic ② 〜 ⑦ + ⑧ + 9-1〜9-7 完了
- `dbt/models/100-knock/topic-3/stg_orders_100knock.sql` が存在
- `stg_orders_100knock` の **下流が 1 つ以上ある** (例: `int_order_details_100knock` や `mart_*_100knock`)
- `dbt parse` が通る
- `git status` がクリーン

## 入力データ

不要。既存 model を使うのみ。

## 課題

### Step 1: 前回 manifest を別 dir に保存 (ベースライン)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .

# 前回 manifest を prev-manifest/ にコピー
mkdir -p prev-manifest
cp target/manifest.json prev-manifest/manifest.json
ls -la prev-manifest/
```

`prev-manifest/manifest.json` が「変更前の DAG スナップショット」になる。

### Step 2: stg_orders_100knock.sql の 1 列を変更

`dbt/models/100-knock/topic-3/stg_orders_100knock.sql` の SELECT 句に新しい列を 1 つ追加:

```sql
-- 例: line_amount を追加 (quantity * unit_price の派生列)
select
    order_id::bigint               as order_id,
    order_date::date               as order_date,
    customer_id::bigint            as customer_id,
    product_id::bigint             as product_id,
    store_id::bigint               as store_id,
    quantity::int                  as quantity,
    unit_price::numeric            as unit_price,
    (quantity * unit_price)::numeric as line_amount   -- ← 追加
from {{ source('raw_100knock', 'orders') }}
```

(line_amount を既に持っている場合は `null::int as new_dummy_col` のような無害な列を追加するだけでも OK)

### Step 3: state:modified+ で差分 run

```bash
# 1. 現在 manifest を再 parse (= 変更後の DAG)
../.venv/bin/dbt parse --profiles-dir .

# 2. state:modified+ で run
../.venv/bin/dbt run \
    --select state:modified+ \
    --state ./prev-manifest/ \
    --profiles-dir . \
    --no-colors 2>&1 | tee /tmp/9-8-state-modified.log
```

ログ末尾に「`stg_orders_100knock`」と **その下流** (例: `int_order_details_100knock`、`mart_customer_sales_100knock` など) の `OK` 行が出るはず。**変更していない他の staging (`stg_customers_100knock` 等) は含まれない**。

### Step 4: state-modified.md に記録

`docs/exercises/100-knock/topic-9-performance/state-modified.md` を新規作成。最低限以下を含める:

- ベースライン manifest の作成手順 (Step 1)
- 変更内容 (どの SQL のどの列を変えたか)
- `dbt run --select state:modified+ --state ./prev-manifest/` の実行コマンドとログ抜粋
- 「**変更した model + 下流のみ build され、他の staging は含まれない**」という観察
- `state:modified+` の `+` の方向についての一文

詳細は解答例を参照。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-9-performance/9-8-state-modified.grading.yaml
```

## 完了条件

- [ ] `prev-manifest/manifest.json` が存在 (Step 1 のスナップショット)
- [ ] `stg_orders_100knock.sql` に変更が入っている (`git diff` で確認)
- [ ] `dbt run --select state:modified+ --state ./prev-manifest/` が成功 (exit 0)
- [ ] `docs/exercises/100-knock/topic-9-performance/state-modified.md` が存在
- [ ] md に `state:modified+` キーワードと変更 model 名 + 下流 model 名 が含まれている

## ヒント (詰まったら)

- **`state:modified+` の `+` の方向**: dbt のセレクタ慣習で `+` は「右側 = 下流」を意味する。`+state:modified` (= 上流) はほぼ使わない (上流は変わっていないので)
- **`--state` の dir**: `manifest.json` が直接置いてある dir を指定する。`./prev-manifest/manifest.json` ではなく `./prev-manifest/` (ディレクトリ指定)
- **何も差分検出されない**: `dbt parse` を変更後にやり忘れている可能性。Step 3 の頭で必ず `dbt parse` を再実行する
- **macro 変更でも検出される**: dbt は **SQL 文字列の hash + 依存 macro の hash** で変更検出する。SQL を変えなくても macro を変えれば下流が `state:modified+` に含まれる
- **`state:modified.body` / `state:modified.configs` などの細分指定**: より細かく「SQL 本体の変更だけ」「config 変更だけ」を検出できる。普段は `state:modified` で十分
- **本番 CI では `--defer` と組み合わせる**: 「PR で触っていない model は **本番 schema を参照**して、touched 部分だけ dev schema で build」 という最強パターン (上級トピック)

## 解答例

詳細は [`9-8-state-modified.solution.md`](9-8-state-modified.solution.md) を参照。
