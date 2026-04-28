# 9-5 解答例

## dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql (最終 state)

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    merge_exclude_columns=['updated_at'],
    on_schema_change='fail',
    schema='marts',
    post_hook=[
        "create index if not exists ix_orders_order_date on {{ this }} (order_date)"
    ]
) }}

-- Grain: 1 row = 1 order_id (incremental + merge mart)。
-- post_hook で order_date に index を貼り、BI の日付範囲フィルタを高速化。
--   IF NOT EXISTS により毎 run 冪等 (2 回目以降は no-op)。
--   {{ this }} は dbt のマクロで、現在の model の物理参照 ("marts"."mart_..._100knock") に展開される。
select
    order_id,
    order_date,
    customer_id,
    customer_name,
    product_id,
    product_name,
    category,
    store_id,
    quantity,
    unit_price,
    sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
{% endif %}
```

**ポイント**:

- **`post_hook=[...]` (list 形式)**: 1 個でも list で書く習慣を付ける (将来 ANALYZE
  などの追加 SQL が増えるとき自然に拡張できる)
- **`{{ this }}`**: 「自分自身の物理参照」を返すマクロ。`"marts"."mart_orders_incremental_100knock"`
  に展開される
- **`if not exists`**: 冪等性のための必須キーワード。post_hook は毎 run 発火するので
  これがないと 2 回目で `ERROR: relation already exists` で落ちる

## 実行例

```bash
# Step 2: 既存 index を削除して、index 無しの cost を測る
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "DROP INDEX IF EXISTS marts.ix_orders_order_date"
DROP INDEX

$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    EXPLAIN ANALYZE SELECT count(*) FROM marts.mart_orders_incremental_100knock
    WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30'"
                              QUERY PLAN
-----------------------------------------------------------------------
 Aggregate  (cost=345.12..345.13 rows=1 width=8) (actual time=2.345..2.346 rows=1 loops=1)
   ->  Seq Scan on mart_orders_incremental_100knock  (cost=0.00..345.00 rows=10000 ...)
         Filter: ((order_date >= '2026-04-01'::date) AND (order_date <= '2026-04-30'::date))
         Rows Removed by Filter: 8500
 Planning Time: 0.123 ms
 Execution Time: 2.456 ms

# Step 3: post_hook を含む dbt run を実行 → index が自動作成
$ cd dbt && dbt run --select mart_orders_incremental_100knock --profiles-dir .
04:50:11  1 of 1 START sql incremental model marts.mart_orders_incremental_100knock [RUN]
04:50:11  1 of 1 OK created sql incremental model marts.mart_orders_incremental_100knock [SQL OK in 0.34s]
04:50:11  1 of 1 START hook: local_analytics.on-run-... [RUN]
04:50:11  1 of 1 OK hook:  local_analytics.on-run-... [CREATE INDEX in 0.04s]
04:50:11  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

# Step 4: index 確認
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT schemaname, tablename, indexname FROM pg_indexes
    WHERE indexname = 'ix_orders_order_date'"
 schemaname |          tablename               |     indexname
------------+----------------------------------+----------------------
 marts      | mart_orders_incremental_100knock | ix_orders_order_date

# Step 5: index 有りの cost
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    EXPLAIN ANALYZE SELECT count(*) FROM marts.mart_orders_incremental_100knock
    WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30'"
                              QUERY PLAN
-----------------------------------------------------------------------
 Aggregate  (cost=12.45..12.46 rows=1 width=8) (actual time=0.234..0.235 rows=1 loops=1)
   ->  Bitmap Heap Scan on mart_orders_incremental_100knock  (cost=4.60..12.20 ...)
         Recheck Cond: ((order_date >= '2026-04-01'::date) AND (order_date <= '2026-04-30'::date))
         Heap Blocks: exact=42
         ->  Bitmap Index Scan on ix_orders_order_date  (cost=0.00..4.60 ...)
               Index Cond: ((order_date >= '...') AND (order_date <= '...'))
 Planning Time: 0.156 ms
 Execution Time: 0.345 ms
```

→ `Seq Scan` が `Bitmap Index Scan` に変わり、cost は **27 倍**、Execution Time は **7 倍** 速く。

## docs/exercises/100-knock/topic-9-performance/index-comparison.md

```markdown
# mart_orders_incremental_100knock: index 有無で EXPLAIN ANALYZE 比較

実行日: 2026-04-26
クエリ: `SELECT count(*) WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30'`
table 行数: 12500

## 1. index 無し (Seq Scan)

```
Aggregate  (cost=345.12..345.13)
  ->  Seq Scan on mart_orders_incremental_100knock  (cost=0.00..345.00 rows=10000)
        Filter: order_date BETWEEN '2026-04-01' AND '2026-04-30'
        Rows Removed by Filter: 8500
Planning Time: 0.123 ms
Execution Time: 2.456 ms
```

→ 全 12500 行を読み、Filter で 8500 行を捨てている。`Seq Scan`。

## 2. index 有り (Bitmap Index Scan)

post_hook で `create index if not exists ix_orders_order_date on marts.mart_orders_incremental_100knock (order_date)` を発行。

```
Aggregate  (cost=12.45..12.46)
  ->  Bitmap Heap Scan on mart_orders_incremental_100knock  (cost=4.60..12.20)
        ->  Bitmap Index Scan on ix_orders_order_date  (cost=0.00..4.60)
              Index Cond: order_date BETWEEN '2026-04-01' AND '2026-04-30'
Planning Time: 0.156 ms
Execution Time: 0.345 ms
```

→ index で「該当 row のみ」を効率的に拾い、Heap で確定。

## 3. 比較表

| 観点         | index 無し       | index 有り             |
|--------------|------------------|------------------------|
| Plan         | Seq Scan         | Bitmap Index Scan      |
| Total cost   | 345.13           | 12.46 (27 分の 1)      |
| Execution    | 2.456 ms         | 0.345 ms (7 倍速)      |
| Rows scanned | 12500 (全件)     | 該当行のみ             |

## 4. いつ index を貼るべきか

- **WHERE 句で頻繁に使う列**: 本問の `order_date` は BI で必ず日付範囲フィルタが
  かかる、典型的な index 候補
- **JOIN キー**: dbt 上は `unique_key` で PK index は自動だが、外部 FK 結合する mart
  では FK 列にも index を貼る
- **大きすぎる table のみ対象**: 1000 行以下は Seq Scan のほうが速いことが多い、
  index は overhead
- **書込頻度が高すぎる場合は再考**: index は INSERT / UPDATE 時に再構築される、
  hot 系 incremental には post_hook で慎重に
```

## 解説まとめ

- **post_hook の本質**: dbt は「データ変換 + DDL 周辺操作」を **コードで一元管理**
  する設計思想。index / ANALYZE / GRANT / REINDEX などの「DDL 周辺操作」も
  model に紐付けて宣言できる。これにより:
  - **DBA / SRE と分業しなくても model 単独で完結**
  - **環境差が消える** (dev / staging / prod で同じ index)
  - **PR レビューで index 設計を議論できる**
  - **dbt docs に index も載る** (`compiled/` で hook 内容が見える)
- **`{{ this }}` の意味**: `ref()` は他 model の参照だが、`this` は **自分自身の参照**。
  `post_hook` / `pre_hook` 内で「今 build した table」を指すのに必須。
  Postgres では `"<database>"."<schema>"."<name>"` 形式に展開される。
- **冪等性 = `IF NOT EXISTS` 必須**: post_hook は **毎 run 発火** するので、何度
  実行しても安全な DDL を書く必要がある:
  - `CREATE INDEX IF NOT EXISTS`: ある: スキップ、無い: 作る
  - `DROP TABLE IF EXISTS`: 同様
  - `GRANT SELECT ... TO ...`: 既存 GRANT は重複しても OK (Postgres)
  - **危険例**: `CREATE INDEX ix_foo ON {{ this }} (col)` → 2 回目で ERROR
- **`pre_hook` との使い分け**:
  - `pre_hook`: **build 前** (table が無い / 古い状態で発火)。`DROP INDEX`, `LOCK TABLE`,
    `SET SESSION ...` など
  - `post_hook`: **build 後** (新 table が出来た状態で発火)。`CREATE INDEX`, `ANALYZE`,
    `GRANT`, `REINDEX` など
- **EXPLAIN ANALYZE の読み方** (重要):
  - `cost=A..B`: A は最初の row を返すまでの推定 cost、B は全 row を返すまでの cost
    (相対的な指標、単位なし)
  - `actual time=A..B`: 実時間 (ms)、A は最初の row、B は最後の row
  - `rows=N`: 推定 row 数 (`rows actual=M` が実 row 数)
  - `Seq Scan` / `Index Scan` / `Bitmap Heap Scan`: scan の種類
  - `Filter` / `Index Cond`: フィルタが「scan 後に適用」(Filter) or 「scan 中に適用」(Index Cond)
  - **「Filter Removed by N」が大きい = scan 後に大量に捨てている = index で減らせる**
- **index 選定の落とし穴**:
  - **書込が重すぎる table に大量 index を貼ると INSERT/UPDATE が遅くなる**
    (incremental の頻度が高いと逆効果)
  - **selectivity が低い列 (boolean とか) に btree index を貼っても効かない**
    (Bitmap で集約されるが Seq Scan と大差ない)。partial index `WHERE active = true`
    などで工夫
  - **index を貼った後は ANALYZE で統計を更新** しないと planner が古い統計で判断する
    ので post_hook に `analyze {{ this }}` も追加すると堅実
- **本番運用のヒント**: post_hook で index を作る運用は **dev / staging / prod すべてで
  同じ index** を保証する。これは大きな価値 — 「dev で速かったクエリが prod で遅い」
  問題の半分はここで解決する。

## 解説まとめ (補足: hook の書ける場所)

dbt の hook は 3 箇所で定義できる:

1. **model 内 `config(post_hook=[...])`** : 本問の方法。model に紐付く
2. **`dbt_project.yml`** の `models:` 階層: 「全 mart に GRANT を発行」など全体規約
3. **`on-run-start` / `on-run-end`** (project 全体): セッション開始 / 終了 hook

本問のように「特定 model に紐付く index」は 1 が正解。「全 mart にロール GRANT」
なら 2 が正解。役割で選び分ける。
