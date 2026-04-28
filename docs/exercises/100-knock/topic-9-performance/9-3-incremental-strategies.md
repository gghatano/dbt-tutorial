# 9-3: incremental の 3 strategy (append / delete+insert / merge) を比較、冪等性を理解

## シナリオ

9-2 で `mart_orders_incremental_100knock` を **`incremental_strategy='merge'`** で実装した。
だが incremental には他にも 2 つの strategy がある:

- **`append`**: 「差分 row を **そのまま INSERT**」。最速、PK 重複チェックなし
- **`delete+insert`**: 「差分のキーを既存から DELETE してから INSERT」。merge と似るが、tmp table 経由で DELETE を発行
- **`merge`**: 9-2 で扱った upsert (Postgres は内部的に delete+insert に展開)

3 つは「**速度・冪等性・ロック範囲**」の三すくみ。本問では **同じ差分データ** (うち
500 行が **既存 PK と重複**) を 3 つの strategy にそれぞれ流して、結果がどう違うかを
比較する。

特に重要なのは **冪等性** (idempotency) — 「同じ入力で何回 run しても同じ結果」。
append は PK 重複でデータが二重化し、冪等性が壊れる。merge / delete+insert は
PK 重複行を更新で吸収するので冪等。

## 学べること

- `incremental_strategy='append'` / `'delete+insert'` / `'merge'` の 3 種類の挙動
- **冪等性** (idempotency) の意味と、不冪等の実害 (重複・集計の二重カウント)
- PK 重複時の三者の振る舞いの違い (新規 row 増 vs 既存 row 上書き)
- どの strategy をいつ選ぶかの判断軸 (速度 vs 整合性 vs ロック範囲)
- **冪等性は dbt model 設計の最重要原則の 1 つ** であることを体感

## 前提

- 9-2 完了 (`mart_orders_incremental_100knock` が存在、merge で 11000 行)
- main HEAD の MVP `dbt run` が緑
- `psql` が `analytics` DB に接続できる

## 入力データ

9-2 の `generate_orders_diff.py` を流用するが、**重複 PK** を含む CSV を生成する
モードを追加する。

## 課題

### Step 1: 3 つの mart を作る (戦略ごとに別 model)

`dbt/models/100-knock/topic-9/` 配下に **3 本** の incremental mart を作る:

- `mart_orders_incremental_append_100knock.sql` (strategy='append')
- `mart_orders_incremental_delete_insert_100knock.sql` (strategy='delete+insert')
- `mart_orders_incremental_merge_100knock.sql` (strategy='merge')

3 本の SQL 本体は **同一**、`config()` の `incremental_strategy` だけ異なる。
コピペで OK。

例 (append 版):

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='append',
    schema='marts'
) }}

select
    order_id, order_date, customer_id, customer_name,
    product_id, product_name, category, store_id,
    quantity, unit_price, sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
-- ↑ わざと max - 500 から SELECT して、前回 run の最後 500 行と
--   今回 run の最初 500 行 (= 重複 PK 500 行) を引き込む
{% endif %}
```

`delete+insert` / `merge` 版も同じ SQL 本体で `incremental_strategy` だけ
変える。

### Step 2: 初回 run (3 本同時)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --select mart_orders_incremental_append_100knock mart_orders_incremental_delete_insert_100knock mart_orders_incremental_merge_100knock --profiles-dir .
```

3 本とも初回は **全件** (11000 行) build される。

### Step 3: 重複 PK 入りの差分を投入 → 2 回目の run

`generate_orders_diff.py` を `--rows 1000` でもう一度実行 (raw.orders が 12000 行に):

```bash
cd ..
.venv/bin/python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000

cd dbt
../.venv/bin/dbt run --select mart_orders_incremental_append_100knock mart_orders_incremental_delete_insert_100knock mart_orders_incremental_merge_100knock --profiles-dir .
```

各 mart の where 句 `order_id > max - 500` により、前回最終 500 行と今回 500 行が
重複 PK として流れ込む。

### Step 4: 行数を比較

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT 'append' AS strategy, count(*) FROM marts.mart_orders_incremental_append_100knock
UNION ALL
SELECT 'delete+insert', count(*) FROM marts.mart_orders_incremental_delete_insert_100knock
UNION ALL
SELECT 'merge', count(*) FROM marts.mart_orders_incremental_merge_100knock;
"
```

期待される結果:

| strategy        | count                   | 備考                                |
|-----------------|-------------------------|-------------------------------------|
| `append`        | **12500** (重複あり)    | PK 重複 500 行が **二重に積まれた** |
| `delete+insert` | 12000 (重複なし)        | 既存 500 を DELETE → 新 500 INSERT |
| `merge`         | 12000 (重複なし)        | UPDATE で重複 PK が上書きされた     |

### Step 5: strategy-comparison.md に記録

`docs/exercises/100-knock/topic-9-performance/strategy-comparison.md` を新規作成:

- 3 strategy の挙動を表で比較 (上記の append/delete+insert/merge 行数)
- **「冪等」キーワードを必ず使う** (どれが冪等かを 1 段落で解説)
- 速度 / ロック範囲 / 重複検知 の 3 軸トレードオフ
- 「自分のチームの mart にどれを選ぶか」の判断基準 (1〜2 段落)

形式は自由。50〜100 行を目安。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-9-performance/9-3-incremental-strategies.grading.yaml
```

## 完了条件

- [ ] 3 本の mart SQL ファイルが存在 (`_append_` / `_delete_insert_` / `_merge_`)
- [ ] 3 本とも `dbt parse` 成功
- [ ] 3 本とも 2 回 dbt run 成功
- [ ] `strategy-comparison.md` に「冪等」キーワード + 3 strategy 表が含まれる

## ヒント (詰まったら)

- **append で重複が出ない**: `where` 句が高水位線厳密 (`order_id > max(order_id)`) に
  なっていないか? `max - 500` で意図的に過去を含めるのが本問の趣旨。
- **delete+insert と merge で結果が同じ?**: Postgres adapter では本質的に **同じ実装**
  (delete + insert)。違うのは **DELETE の発行方式**:
  - `delete+insert`: tmp table 経由で `WHERE order_id IN (SELECT order_id FROM tmp)`
  - `merge`: 上記とほぼ同じだが、dbt-postgres の merge マクロは追加で
    「`when matched then update`」を意識した tmp 中継を組む
  - 他 adapter (Snowflake / BigQuery) では merge はネイティブ MERGE 文に変換され、
    delete+insert と挙動が大きく異なる。**adapter 依存性に注意**。
- **append が高速な理由**: 「重複チェックなし」だから。`unique_key` を見るが、
  `append` strategy はこれを **insert 時の検証に使わない** (`merge` は upsert 判定に使う)。
- **冪等性が壊れたら何が困る?**: 「同じバッチを 2 回流したら売上が 2 倍になる」
  =BI ダッシュボードが嘘をつく。リトライ運用ができなくなる (= 失敗時にロールバック
  →再実行が安全にできない)。冪等性は分散システム / バッチ運用の基本要件。
- **どの strategy をいつ?**:
  - **append**: ログ追記系 (event log, audit trail)。冪等性が要らない。最速
  - **merge**: master データ系 (customer, product, order)。冪等性必須
  - **delete+insert**: 大量更新系 (日次集計の上書き)。merge より一括 DELETE で速いことがある

## 解答例

詳細は [`9-3-incremental-strategies.solution.md`](9-3-incremental-strategies.solution.md) を参照。
