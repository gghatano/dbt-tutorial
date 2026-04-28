# 4-8 解答例

## dbt/models/100-knock/topic-4/int_order_details_100knock.sql (ephemeral 化後)

```sql
{{ config(materialized='ephemeral') }}

-- Grain: 1 row = 1 order_id (orders を主軸に master 3 本を INNER JOIN で enrich)。
-- materialization: ephemeral に変更 (4-8 演習)。
-- 物理化されず、下流 mart の compiled SQL に CTE として展開される。
-- 注意: ephemeral は test が skip されるため、grain 契約を test で守りたいなら view 推奨。
select
    o.order_id,
    o.order_date,
    o.customer_id,
    c.customer_name,
    o.product_id,
    p.product_name,
    p.category,
    o.store_id,
    o.quantity,
    o.unit_price,
    (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

**ポイント**:

- **`materialized='ephemeral'` のみ**: `schema=` は ephemeral では物理化されないので
  指定しても無視。SQL の見た目をシンプルに保つため省略推奨。
- **冒頭コメントを更新**: 「ephemeral に変更した」「test が skip される」を 1〜2 行で
  メモ。半年後に「なんで ephemeral だっけ?」となった時の救命ロープ。

## (前提) 下流 mart が必要 — 例: dbt/models/100-knock/topic-4/mart_dummy_for_ephemeral.sql

4-5 を未着手なら、ephemeral の効果を見るための最小ダミー mart を作る:

```sql
{{ config(materialized='table', schema='marts') }}

-- 4-8 演習用ダミー: ephemeral の int_order_details_100knock の効果を確認するため、
-- 1 本だけ下流 mart を置いて compiled SQL の CTE 展開を観察する。
select
    count(*)             as n_orders,
    sum(sales_amount)    as total_sales,
    sum(quantity)        as total_quantity
from {{ ref('int_order_details_100knock') }}
```

(4-5 で `mart_daily_sales_100knock` を既に作っていればそちらを下流に使う)

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
$ ../.venv/bin/dbt compile --profiles-dir . --select int_order_details_100knock+
04:31:00  Found 11 models, 5 sources, ...
04:31:01  Concurrency: 4 threads
04:31:01  Done.
```

compile された下流 mart を覗く:

```bash
$ cat target/compiled/local_analytics/models/100-knock/topic-4/mart_dummy_for_ephemeral.sql
with __dbt__cte__int_order_details_100knock as (
    select
        o.order_id,
        o.order_date,
        o.customer_id,
        c.customer_name,
        o.product_id,
        p.product_name,
        p.category,
        o.store_id,
        o.quantity,
        o.unit_price,
        (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
    from "analytics"."staging"."stg_orders_100knock"    as o
    inner join "analytics"."staging"."stg_customers_100knock" as c on o.customer_id = c.customer_id
    inner join "analytics"."staging"."stg_products_100knock"  as p on o.product_id  = p.product_id
    inner join "analytics"."staging"."stg_stores_100knock"    as s on o.store_id    = s.store_id
)
select
    count(*)             as n_orders,
    sum(sales_amount)    as total_sales,
    sum(quantity)        as total_quantity
from __dbt__cte__int_order_details_100knock
```

**重要な観察ポイント**:

1. **`with __dbt__cte__int_order_details_100knock as ( ... )`** という CTE が **下流 SQL の冒頭に自動挿入** されている (CTE 名は dbt が `__dbt__cte__<model_name>` 形式で生成)
2. `from {{ ref('int_order_details_100knock') }}` の参照が **`from __dbt__cte__int_order_details_100knock`** に書き換えられている
3. 元の `int_order_details_100knock.sql` の中身が **行ごと展開** されている (CTE 本体)
4. 物理 view / table の参照は一切無い

DB 上で物理オブジェクトが無いことを確認:

```bash
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c \
  "SELECT relname, relkind FROM pg_class WHERE relname = 'int_order_details_100knock'"
 relname | relkind
---------+---------
(0 rows)
```

`intermediate.int_order_details_100knock` という table も view も存在しない。
にもかかわらず下流 mart は正常に build できる:

```bash
$ ../.venv/bin/dbt build --select int_order_details_100knock+ --profiles-dir .
04:32:00  1 of 1 START sql table model marts.mart_dummy_for_ephemeral [RUN]
04:32:01  1 of 1 OK created sql table model marts.mart_dummy_for_ephemeral [CREATE TABLE (1 rows) in 0.45s]
04:32:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

注: `int_order_details_100knock` 自身は dbt run のログに **出てこない**
(物理化が無いので run 対象外)。これも ephemeral の特徴。

## 解説まとめ

- **なぜ ephemeral?**: 「中間ロジックを SQL レベルで再利用したいが、物理化するほど重要ではない」
  ケースで活躍する。例:
  - 単純な JOIN や cast を 1 model に切り出して可読性を上げたいが、storage を消費したくない
  - 中間結果が下流 1 本でしか使われず、独立 SELECT する用途も無い
  - test を書く必要がない (= 中間状態として保証する不変条件が無い)
- **ephemeral の挙動 (3 点セット)**:
  1. **物理化されない**: `pg_class` に出てこない、storage 0、`SELECT * FROM intermediate.<name>` できない
  2. **下流に CTE として展開**: `__dbt__cte__<name>` という命名規約の CTE が下流 compiled SQL の冒頭に自動挿入される
  3. **DAG 上は依存として認識**: `dbt ls --select int_<name>+` で下流が出てくる、`+model+` で巻き込まれる
- **ephemeral の注意点 (4 つ)**:
  1. **test が skip される**: 物理化されないので `not_null` / `unique` test の SQL を当てられない。dbt は警告を出して skip。grain 契約を test で守りたいなら view 推奨
  2. **下流が無いと意味が無い**: ephemeral 単体を `dbt run --select <name>` しても何も起きない。下流の compile / run で初めて展開される
  3. **デバッグが難しい**: 中間結果を `SELECT *` で確認できない。`dbt show --select <name>` で limit 付き SELECT は可能だが、その都度 CTE を展開して走らせるので遅い
  4. **CTE の最適化に依存**: Postgres / Snowflake などは CTE をインライン化してくれることが多いが、CTE が **最適化バリア** になる DB (古い Postgres など) では table 化した方が速いことも
- **ephemeral と CTE の関係**: 「ephemeral = dbt がコード生成で CTE を自動挿入する仕組み」 と
  覚えればよい。ユーザーが書く SQL に CTE を手動で書くのと、ephemeral model で dbt に CTE を
  自動生成させるのは **生成後 SQL としては等価**。違いは「**CTE をプロジェクト全体で再利用できるか
  (ephemeral) / 単一 model 内に閉じるか (手書き CTE)**」。
- **view / table / ephemeral の使い分け**:
  | 観点                  | view             | table             | ephemeral             |
  |-----------------------|------------------|-------------------|-----------------------|
  | 物理化                | あり (定義のみ)  | あり (データ込)   | なし                  |
  | storage               | 0                | データサイズ      | 0                     |
  | 下流 SELECT 速度      | 都度 JOIN        | 直接 read         | 都度 JOIN (CTE 経由)  |
  | test 可否             | 可               | 可                | **不可** (skip)       |
  | 単独で `SELECT *` 可? | 可               | 可                | 不可                  |
  | 推奨ケース            | staging          | 重い JOIN, 再利用 | 軽い再利用、storage 嫌 |
- **実務での頻度**: ephemeral は使いどころが限られるので、プロジェクト全体で 1〜数本程度が
  典型的。staging は view、intermediate は view か table、mart は table か incremental が
  デファクト。ephemeral は「中間ロジックの抽出」 専用と割り切る。
- **本演習後の状態**: 4-9 / 4-10 でも `int_order_details_100knock` を使うが、ephemeral のままだと
  test が走らない / カタログに出ない / model versions が機能しないなど制約が出るので、
  **本問完了後に view に戻す** ことを solution.md は推奨する。grader は本問終了時点
  (= ephemeral) を見る。
