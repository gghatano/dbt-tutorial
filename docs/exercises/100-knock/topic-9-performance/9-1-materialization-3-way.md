# 9-1: int_order_details_100knock を view → table → ephemeral の 3 通りで build、build 時間と物質化を比較

## シナリオ

Topic ④ で作った intermediate `int_order_details_100knock` は **デフォルトで view**
として宣言されている。しかし、下流に `mart_daily_sales_100knock` のような **重い
集計 mart** がぶら下がると、view のままだと「mart の SELECT 中で view を再展開する」
ため、JOIN コストが下流ごとに毎回発生する。

dbt の materialization は **同じ SQL を異なる「物理化戦略」で実行する** 仕組みで、
本問では `int_order_details_100knock` を:

- **view** (DDL のみ、storage 0、毎 SELECT で JOIN 再展開)
- **table** (CTAS で物質化、storage 消費、下流 SELECT は table を読むだけ)
- **ephemeral** (物理化なし、下流 model の SQL に CTE として展開)

の 3 通りで build し、`mart_daily_sales_100knock` の `compiled/` SQL がどう変わるか、
build 時間がどう変わるかを比較表にまとめる。

これが「**materialization 選択は宣言で決まる SQL の物質化戦略**」 の本質。
ephemeral は特に重要で、「下流 SQL に **構造変化** が起きる」唯一の戦略。

## 学べること

- `{{ config(materialized='view'/'table'/'ephemeral') }}` の 3 種類の挙動
- ephemeral は **物理化されない** = `pg_class` に出てこない、下流 SQL の CTE になる
- `target/compiled/` の SQL を読んで「下流が依存をどう解決しているか」を確認する習慣
- view / table / ephemeral の build 時間 / storage / 鮮度 / 下流影響の 4 軸トレードオフ
- materialization 選択をログに残す習慣 (PR レビュー時に説明できる)

## 前提

- Topic ② ③ ④ 完了 (`int_order_details_100knock` が存在、view で物質化されている)
- Topic ⑤ 5-3 完了 (`mart_daily_sales_100knock` が存在、table で物質化されている)
  - もし未完了なら、`mart_daily_sales_100knock` は MVP の `mart_daily_sales` を
    模した簡単な集計 mart で代用可 (本問の主役は intermediate の物質化方式)
- `dbt parse` が通る
- `psql` が `analytics` DB に接続できる

## 入力データ

不要。学習者は既存 `int_order_details_100knock` の config を 3 通り切り替えて
build し直す。

## 課題

### Step 1: view 版で build (ベースライン)

`dbt/models/100-knock/topic-4/int_order_details_100knock.sql` の冒頭 config が
view のままであることを確認:

```sql
{{ config(materialized='view', schema='intermediate') }}
```

build と物理化確認:

```bash
set -a; source .env; set +a
cd dbt
time ../.venv/bin/dbt run --select +mart_daily_sales_100knock --profiles-dir .
```

`real` の値 (3〜8 秒程度) をメモ。さらに DB 上の物理形態を確認:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT n.nspname, c.relname, c.relkind FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE c.relname = 'int_order_details_100knock';
"
# nspname=intermediate, relkind='v' (view)
```

`target/compiled/local_analytics/models/100-knock/topic-5/mart_daily_sales_100knock.sql`
を開き、**`from intermediate.int_order_details_100knock`** のような形で view を直接
ref している (CTE 展開ではない) ことを確認する。

### Step 2: table 版に切り替えて build

`int_order_details_100knock.sql` の config を `table` に変更:

```sql
{{ config(materialized='table', schema='intermediate') }}
```

再 build:

```bash
time ../.venv/bin/dbt run --select +mart_daily_sales_100knock --profiles-dir .
```

物理化確認: `relkind='r'` (ordinary table) になっていること。
`compiled/` SQL は **view 版と同じ構造** (table を `from` で読む) になる。

### Step 3: ephemeral 版に切り替えて build

```sql
{{ config(materialized='ephemeral') }}
```

(ephemeral は schema 不要 — 物理化されないため)

```bash
time ../.venv/bin/dbt run --select +mart_daily_sales_100knock --profiles-dir .
```

物理化確認: `pg_class` に **何も無い** (ephemeral なので物質化されない)。
`compiled/` SQL を再度開くと、`mart_daily_sales_100knock` の SQL の冒頭に
**`with __dbt__cte__int_order_details_100knock as (...)`** という CTE が
**展開されている** ことを確認する。これが ephemeral の核心。

### Step 4: 最終 state を table に戻す

採点は **table 版が最終 state** であることを前提とする (sql_assert で確認)。

```sql
{{ config(materialized='table', schema='intermediate') }}
```

```bash
../.venv/bin/dbt run --select int_order_details_100knock --profiles-dir .
```

### Step 5: materialization-comparison.md に記録

`docs/exercises/100-knock/topic-9-performance/materialization-comparison.md` を新規作成:

- 3 通りの `time` 計測結果 (real / user / sys)
- 3 通りの `relkind` (`v` / `r` / 物質化なし)
- `compiled/` SQL の構造変化 (table/view = ref のまま、ephemeral = CTE 展開)
- 「下流が複数 mart になったとき、どの materialization が有利か」の考察 (1〜2 段落)

形式は自由。50〜100 行を目安。比較表を 1 つ含めること。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-9-performance/9-1-materialization-3-way.grading.yaml
```

## 完了条件

- [ ] `int_order_details_100knock.sql` の **最終 config が `materialized='table'`**
- [ ] `dbt parse` が成功する
- [ ] manifest 上 `materialized = table`
- [ ] `dbt run --select int_order_details_100knock` が成功する
- [ ] DB 上で `pg_class.relkind = 'r'` (table)
- [ ] `materialization-comparison.md` に view / table / ephemeral 3 つすべての言及あり

## ヒント (詰まったら)

- **ephemeral で `dbt run --select int_order_details_100knock` を直接走らせると何も起きない**:
  ephemeral は単独で物質化されないので、`dbt run --select <ephemeral_model>` は
  no-op に近い (依存解析だけして終わる)。ephemeral を確認したいときは **下流の
  ある model を build** して `compiled/` SQL を読む。
- **`compiled/` ディレクトリの場所**: `dbt/target/compiled/<project_name>/models/...`。
  ここには **マクロ展開後の純粋 SQL** が入っている。`run/` の方は `CREATE TABLE AS` などの
  DDL も含む。比較目的なら `compiled/` の方が読みやすい。
- **ephemeral の落とし穴 (なぜ多用しない?)**: ephemeral は下流 SQL に CTE 展開されるため、
  下流 N 本が ref すると **同じ CTE が N 回コピペ** される (warehouse がクエリプラン段階で
  共通部分を最適化してくれることもあるが、保証はない)。3 段以上ネストすると
  下流 SQL が爆発的に長くなりデバッグ困難に。**「単 1 下流 + 物理化したくない中継」専用**。
- **`time` の正しい使い方**: `dbt run --select +mart_daily_sales_100knock` のように、
  ピリオド始まりの `+` で「自分とすべての上流」を build。intermediate を 1 本 view → table に
  切り替えた効果を mart の build 時間で測れる。1 回目はキャッシュが冷えて遅いので、
  各 materialization で 2 回ずつ計測し平均を取るとなお良い。
- **採点時に table である必要**: 9-2 〜 9-5 でも `int_order_details_100knock` を ref する
  下流が出てくる前提なので、最終 state は table にしておく。

## 解答例

詳細は [`9-1-materialization-3-way.solution.md`](9-1-materialization-3-way.solution.md) を参照。
