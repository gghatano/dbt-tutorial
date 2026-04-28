# 4-7: int_orders_enriched_100knock を view → table に切り替え、build 時間を比較

## シナリオ

intermediate model のデフォルトは view (storage 0、常に最新)。だが下流 mart が
複数同じ intermediate を `ref()` するようになると、**毎回 mart の SELECT が view を再展開**
することになり、view の中の JOIN を mart の数だけ実行する羽目になる。
intermediate を **table 化** して結果を物質化すれば、下流 mart は table を読むだけで済むため
全体 build 時間が短縮される。

トレードオフは「**鮮度** (view = 常に最新 / table = run した瞬間の snapshot)」 と
「**storage** (view = 0 / table = データサイズ分)」。本問では同じ model
`int_orders_enriched_100knock` を view と table の 2 通りで build し、`time` コマンドで
build 時間を計測、結果を `materialization-comparison.md` に書き残す。

これが「**materialization 選択は宣言で決まる SQL の物質化戦略**」 の本質。

## 学べること

- `{{ config(materialized='view') }}` と `{{ config(materialized='table') }}` の切り替え
- `pg_class.relkind` (`v` = view, `r` = table) で物理化形態を確認する方法
- view と table の build 時間 / storage / 鮮度のトレードオフ
- materialization 選択をログに残す習慣 (= 後で振り返れる、PR レビュー時に説明できる)
- `dbt build --select <model>` で個別 model の build 時間を計測

## 前提

- Topic ② ③ 完了 + Topic ④ 4-1 完了 (`int_order_details_100knock` が存在)
- `dbt parse` が通る
- `psql` が `analytics` DB に接続できる (`DBT_HOST` / `DBT_USER` 環境変数が設定済み)

## 入力データ

不要。学習者が model 1 本を書き、config を 2 通り切り替える。

## 課題

### Step 1: int_orders_enriched_100knock を作る

`dbt/models/100-knock/topic-4/int_orders_enriched_100knock.sql` を新規作成:

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id。int_order_details_100knock に「年月」「曜日」など
-- 派生列を追加した enriched 中継。下流 mart はここから集計を組む想定。
select
    order_id,
    order_date,
    extract(year from order_date)::int   as order_year,
    extract(month from order_date)::int  as order_month,
    extract(dow from order_date)::int    as order_dow,
    customer_id,
    customer_name,
    product_id,
    product_name,
    category,
    store_id,
    quantity,
    unit_price,
    sales_amount
from {{ ref('int_order_details_100knock') }}
```

### Step 2: view 版で build (1 回目)

```bash
set -a; source .env; set +a
cd dbt
time ../.venv/bin/dbt build --select int_orders_enriched_100knock --profiles-dir .
```

`real` の値 (1〜5 秒程度) をメモする。

物理化を確認:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT relname, relkind FROM pg_class
WHERE relname = 'int_orders_enriched_100knock';
"
# relkind = 'v' (view)
```

### Step 3: table 版に切り替えて build (2 回目)

`dbt/models/100-knock/topic-4/int_orders_enriched_100knock.sql` の冒頭 config を
`materialized='table'` に変更:

```sql
{{ config(materialized='table', schema='intermediate') }}
```

再 build:

```bash
time ../.venv/bin/dbt build --select int_orders_enriched_100knock --profiles-dir .
```

物理化を再確認:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT relname, relkind FROM pg_class
WHERE relname = 'int_orders_enriched_100knock';
"
# relkind = 'r' (table)
```

### Step 4: materialization-comparison.md に記録

`docs/exercises/100-knock/topic-4-intermediate/materialization-comparison.md` を新規作成:

- view 版と table 版の `time` 計測結果 (real / user / sys 各値)
- `relkind` の違い (`v` vs `r`)
- 「下流が複数 mart になったとき、どちらが有利か」の考察 (1〜2 段落)
- 鮮度 (上流 staging が更新された瞬間の挙動) の違い

形式は自由。30〜80 行を目安。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-4-intermediate/4-7-materialization-table-vs-view.grading.yaml
```

> **採点時の最終 state**: 採点は **table 版が最新** であることを前提とする (sql_assert で `relkind = 'r'` を確認)。Step 3 の状態でコミット / push する。

## 完了条件

- [ ] `dbt/models/100-knock/topic-4/int_orders_enriched_100knock.sql` が存在する
- [ ] **最終的に** `materialized='table'` で宣言されている
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_orders_enriched_100knock` が登録され、`materialized = table`
- [ ] `dbt build --select int_orders_enriched_100knock` が成功する
- [ ] DB 上で `pg_class.relkind = 'r'` (table)
- [ ] `materialization-comparison.md` に view / table 両方の build 時間が記録されている

## ヒント (詰まったら)

- **`time` コマンドの読み方**: `real` は実時間 (秒)、`user` は CPU 時間。dbt の build 時間は I/O 待ちが多いので `real` で比較する。1 回目と 2 回目で OS のキャッシュが効くので、可能なら 2 回ずつ計測して平均を取る。
- **table 化の落とし穴**: `materialized='table'` にすると `dbt run` 時に `CREATE TABLE AS SELECT` が走り、storage を消費する。intermediate を全部 table にすると DB 容量が膨れる。**「下流が 2 本以上 ref する intermediate だけ table 化」が現実的な指針**。
- **view → table 切替時のロック**: Postgres では `CREATE OR REPLACE VIEW` が高速だが、view → table 切替時は **`DROP VIEW` + `CREATE TABLE`** になる (dbt が自動で判定)。下流 mart が view を ref している瞬間に切り替えると、瞬間的に依存が壊れる可能性あり (本演習では下流が無いので問題なし)。
- **`pg_class.relkind` の値**: `r` = ordinary table, `v` = view, `m` = materialized view (Postgres の materialized view であって dbt の materialization とは別物), `i` = index。dbt の `materialized='table'` は Postgres の `relkind='r'` に対応。
- **採点が view 版を要求しているように見える**: 採点は **最終 state が table 版** であることだけを見る。view 版は途中の比較目的で動かすだけ。Step 4 でログを残し、Step 3 の table 状態で commit する。

## 解答例

詳細は [`4-7-materialization-table-vs-view.solution.md`](4-7-materialization-table-vs-view.solution.md) を参照。
