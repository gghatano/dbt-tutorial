# 9-1 解答例

## dbt/models/100-knock/topic-4/int_order_details_100knock.sql (最終 state = table 版)

```sql
{{ config(materialized='table', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (orders を主軸に master 3 本を INNER JOIN)。
-- materialization: table を選択した理由 ↓
--   - 下流 mart (mart_daily_sales_100knock など) が JOIN 済み snapshot を読むだけで済む
--   - 9-1 の比較で view 版だと下流 build 時間が線形に伸びることを確認
--   - ephemeral 版だと下流 SQL に CTE 展開され、複数 mart で重複展開される
--   - 中間層は table が無難 (storage コストは小さく、build 時間は CTAS 1 回で済む)
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
from {{ ref('stg_orders_100knock') }} o
inner join {{ ref('stg_customers_100knock') }} c using (customer_id)
inner join {{ ref('stg_products_100knock') }} p using (product_id)
inner join {{ ref('stg_stores_100knock') }} s using (store_id)
```

**ポイント**:

- **`materialized='table'` (最終)**: 同じ SQL 本体を view / table / ephemeral の 3 通りで
  動かす演習だが、**最終 state は table** で確定させる。これは Topic ⑨ 後半の問題
  (9-2 〜 9-5) でも `int_order_details_100knock` を上流として ref する想定だから。
- **冒頭コメントに選択理由**: 「なぜ table を選んだか」を SQL に書き残すのが実務作法。
  半年後の自分や他のチームメンバーが「これ view でよくない?」と思ったとき、根拠を
  読み戻せる。
- **schema='intermediate' 明示**: `models/100-knock/topic-4/` は dbt_project.yml の
  `intermediate/` パス指定に引っかからないため、明示しないと target schema (public)
  に作られてしまう。

## docs/exercises/100-knock/topic-9-performance/materialization-comparison.md

```markdown
# int_order_details_100knock: view / table / ephemeral 3 通り build 比較

実行日: 2026-04-26
実行者: 学習者
ベース: Topic ④ 4-1 完了 (int_order_details_100knock = 10,000 行)
計測対象: dbt run --select +mart_daily_sales_100knock (intermediate と mart 2 本 build)

## 1. view 版 (デフォルト)

config:
```sql
{{ config(materialized='view', schema='intermediate') }}
```

実行ログ:
```
real    0m4.21s
user    0m1.35s
sys     0m0.28s
```

物理化:
```
nspname=intermediate, relname=int_order_details_100knock, relkind=v
```

`compiled/.../mart_daily_sales_100knock.sql` (抜粋):
```sql
select order_date, count(*) as order_count, ...
from intermediate.int_order_details_100knock
group by order_date
```
→ view を **直接 ref** している。SELECT のたびに view の内側 (4 staging JOIN) が再展開。

## 2. table 版

config:
```sql
{{ config(materialized='table', schema='intermediate') }}
```

実行ログ:
```
real    0m4.78s
user    0m1.42s
sys     0m0.31s
```

物理化:
```
nspname=intermediate, relname=int_order_details_100knock, relkind=r
size=720 KB
```

`compiled/.../mart_daily_sales_100knock.sql`:
view 版と **構造は同じ** (`from intermediate.int_order_details_100knock`)。
ただし下流 SELECT 時には **物質化済み table を読むだけ** で、JOIN は再発しない。

## 3. ephemeral 版

config:
```sql
{{ config(materialized='ephemeral') }}
```

実行ログ:
```
real    0m3.98s
user    0m1.30s
sys     0m0.25s
```

物理化:
```
(pg_class に出てこない — ephemeral は物質化されない)
```

`compiled/.../mart_daily_sales_100knock.sql` (大きく構造変化):
```sql
with __dbt__cte__int_order_details_100knock as (
    select
        o.order_id, o.order_date, o.customer_id, c.customer_name,
        ...
    from staging.stg_orders_100knock o
    inner join staging.stg_customers_100knock c using (customer_id)
    ...
)
select order_date, count(*) as order_count, ...
from __dbt__cte__int_order_details_100knock
group by order_date
```
→ intermediate の SQL が **下流 mart の SQL の冒頭に CTE として展開** されている。
これが ephemeral の挙動。

## 4. 比較表

| 観点                     | view              | table              | ephemeral             |
|--------------------------|-------------------|--------------------|-----------------------|
| `pg_class.relkind`       | `v`               | `r`                | (なし)                |
| storage                  | 0 KB              | 720 KB             | 0 KB                  |
| 自分 build 時間          | 速い (DDL のみ)   | 遅い (CTAS)        | なし (no-op)          |
| 下流 SELECT 速度         | JOIN 再展開       | 直接 read          | CTE 展開→クエリプラン |
| 下流 `compiled/` 構造    | ref そのまま      | ref そのまま       | **CTE 展開**          |
| 下流 N 本での CTE 重複   | 0                 | 0                  | N 回展開される        |
| 鮮度                     | 常に上流最新      | run 時 snapshot    | 常に上流最新          |
| `+mart_daily_sales` 計測 | 4.21 s            | 4.78 s             | 3.98 s                |

## 5. 考察

- **本問では下流が 1 本 (mart_daily_sales_100knock のみ)** なので、ephemeral が
  最速 (中間 table を作らず一発 SELECT)、table が最遅 (CTAS のオーバーヘッド)
- ただし下流 mart が **4〜5 本** に増えると逆転: view / ephemeral は SELECT のたびに
  4 staging JOIN を再実行、table は 1 回書込で N 回読み — table が最速になる
- ephemeral は「**下流が 1 本だけ + storage を 1 byte も使いたくない**」という限定
  シナリオで強い。3 段以上ネストすると下流 SQL が爆発的に長くなり、デバッグ困難
- **結論**: 本プロジェクトのように「intermediate を複数 mart で再利用する」DAG では
  table を選ぶのが堅実。今回 9-2 以降でも下流 mart が増えるので、最終 state は table
```

**ポイント**:

- **3 つすべての `time` 結果**: 数値は学習者環境の実測。本サンプルは Mac M1 + Postgres 16 +
  ローカル接続の参考値
- **`compiled/` SQL の構造変化**: ephemeral だけが下流 SQL を **書き換える** ことが要点
- **比較表 + 考察 1〜2 段落** が grader の最低ライン

## 実行例 (採点視点)

```bash
$ cd dbt && dbt run --select int_order_details_100knock --profiles-dir .
... PASS=1 ...

# manifest 確認
$ python3 -c "
import json
with open('dbt/target/manifest.json') as f: m = json.load(f)
node = m['nodes']['model.local_analytics.int_order_details_100knock']
print('materialized=', node['config']['materialized'])
"
materialized= table

# DB 確認
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c \
  "SELECT relkind FROM pg_class WHERE relname = 'int_order_details_100knock'"
 relkind
---------
 r
```

## 解説まとめ

- **なぜ materialization 選択が重要?**: dbt は SQL を「どう物質化するか」をコード側で
  宣言する。同じ SELECT でも view にすれば storage 0 / 常に最新、table にすれば storage
  消費 / snapshot、ephemeral にすれば物理ゼロで CTE 展開、incremental にすれば差分マージ。
  **同じビジネスロジックを異なる物質化戦略で動かせる** のが dbt の核心的な強み。
- **ephemeral の本質**: 「**物理化を持たず、下流 SQL に CTE で埋め込まれる**」材料化。
  Postgres には「ephemeral」という SQL 概念は無く、dbt が **コード生成で実現する** 抽象。
  だから `pg_class` に何も無く、`compiled/` SQL を読まないと実体が見えない。
- **3 つの選択基準** (実務でよく使う):
  1. **下流 N ≥ 2 で重い JOIN がある** → **table** (1 回書込で N 回読、トータル最速)
  2. **下流 N = 1 + 中継だけしたい + storage 節約** → **ephemeral** (物理化なし)
  3. **下流 N = 1 + 鮮度最優先** → **view** (常に上流最新)
  4. **下流 N ≥ 2 + 鮮度最優先 + storage 余裕あり** → **view** (storage 0 / でも遅い)
- **ephemeral の落とし穴 (なぜ多用しない?)**:
  - 下流 SQL に CTE が **重複展開** される (N 本が ref すると N 回コピペ)
  - 3 段ネストで SQL が膨大に → デバッグ・パフォーマンスチューニング困難
  - エラー時のスタックトレースが「下流 model の SQL の中の CTE のここ」になり追いづらい
  - `dbt docs` の lineage には出るが、DB 上に物質化されないので「データを直接覗く」ができない
  - 結論: ephemeral は **「単 1 下流 + 中継だけしたい」専用**。**初手は table か view から**
- **比較ログを残す習慣**: `materialization-comparison.md` のようなドキュメントを残しておくと、
  半年後に「なぜこの int は table なんだっけ?」と疑問が湧いたとき、根拠を読み戻せる。
  PR レビュー時の説明にもなる。**文書化はキャッシュ**。
- **`time` 計測の注意点**: 1 回目と 2 回目で OS / Postgres のキャッシュが効くので、
  ベンチマーク目的なら **複数回測って分布で見る**。本演習は「桁感を体感する」目的なので
  1 回計測で十分。重要なのは **3 通りの相対比較**。
