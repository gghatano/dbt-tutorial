# 8-5: Jinja `{% for %}` loop で 4 staging に last_updated_at 列を一括追加 (pre_hook 経由)

## シナリオ

「全 staging テーブルに **`last_updated_at`** 列を持たせて、最終 build 時刻を
記録したい」 という運用要望がある (障害調査で「いつ build された staging か」
を知る必要が出る場面)。素直にやると、4 つの staging model 全部に
`current_timestamp as last_updated_at` を追加する SQL 改修が発生する。

これを **macro + Jinja `{% for %}` loop** で「全 staging に共通の audit 列を
ALTER TABLE で 1 度に追加する」 と書き換えれば、staging 側の SQL を 1 行も触らず、
**`pre_hook` から macro を呼ぶだけ** で同じ効果が出る。`for` loop で対象テーブル
list を 1 箇所にまとめておけば、staging が増えた時も list に 1 行足すだけ。

8-5 では、Jinja `{% for %}` loop で 4 staging テーブルに対して **`ALTER TABLE
... ADD COLUMN IF NOT EXISTS last_updated_at`** + 値更新を実行する macro
`add_audit_columns()` を書き、対象 staging に `pre_hook` 経由で適用する。

## 学べること

- Jinja `{% for %}` ループの基本構文
- `dbt run` 実行時に走る hook (`pre_hook` / `post_hook` / `on-run-start` / `on-run-end`) の使い分け
- macro を `pre_hook` 経由で呼ぶ作法
- `ALTER TABLE ADD COLUMN IF NOT EXISTS` で冪等性を確保する書き方
- model SQL を 1 行も触らずに「列を一括追加」 する DRY 設計
- `{% if execute %}` で parse 時の安全策 (jinja の評価ガード)

## 前提

- Topic ② 〜 ⑦ 完了 (staging が 4 本 = `stg_orders_100knock` / `stg_customers_100knock` /
  `stg_products_100knock` / `stg_stores_100knock` 物理化済み)
- 学習者の macro は `dbt/macros/100-knock/topic-8/add_audit_columns.sql`
- 4 staging はいずれも `materialized='view'` ではなく **`table` で物理化** している前提
  (view では ALTER TABLE が効かないため)。`view` のままなら、本問の `pre_hook` 適用前に
  `materialized='table'` に切り替える Step が必要

> **注**: 100-knock の 3 系は staging を view で書く設計だが、本問だけは「audit 列を
> 永続化したい」 という業務要件のため table 化する。Topic ⑨ パフォーマンスで
> view vs table の切り分けを再学習する伏線。

## 入力データ

不要。staging 側の SQL も触らない。macro 1 本 + 4 staging の `pre_hook` config 追加だけ。

## 課題

### Step 1: macro を作る

`dbt/macros/100-knock/topic-8/add_audit_columns.sql` を新規作成:

```jinja
{#-
    Topic ⑧ 8-5: 対象 staging テーブルに last_updated_at 列を冪等に追加する。

    使い方 (model 側 config):
        {{ config(
            pre_hook=["{{ add_audit_columns() }}"]
        ) }}

    挙動:
      - {% for tbl in [...] %} で 4 staging を回す
      - 各テーブルに ALTER TABLE ... ADD COLUMN IF NOT EXISTS last_updated_at timestamptz
      - 値は current_timestamp で UPDATE
-#}
{% macro add_audit_columns() %}
    {%- set tables = [
        ('staging', 'stg_orders_100knock'),
        ('staging', 'stg_customers_100knock'),
        ('staging', 'stg_products_100knock'),
        ('staging', 'stg_stores_100knock'),
    ] -%}
    {%- for schema, tbl in tables %}
        ALTER TABLE {{ schema }}.{{ tbl }}
            ADD COLUMN IF NOT EXISTS last_updated_at timestamptz DEFAULT current_timestamp;
        UPDATE {{ schema }}.{{ tbl }} SET last_updated_at = current_timestamp;
    {%- endfor %}
{% endmacro %}
```

要件:

- `tables` list に 4 つの (schema, table) ペアを宣言
- `{% for %}` で 4 回 SQL を生成
- `IF NOT EXISTS` で 2 回目以降の `dbt run` でも冪等
- 値は `current_timestamp` で毎回更新

### Step 2: 4 staging を table 化 + pre_hook 設定

各 staging model 先頭の `config()` を:

```sql
{{ config(
    materialized='table',
    schema='staging',
    pre_hook=["{{ add_audit_columns() }}"]
) }}
```

> **重要**: `pre_hook` は **list of string** で渡す。文字列は jinja `{{ ... }}` を
> 含めると dbt が「runtime に展開」 してくれる。
>
> **冪等性のための工夫**: 4 staging 全部に同じ `pre_hook` を書くと **1 回の dbt run
> につき 4 回 macro が走る** (各 staging build 直前に 1 回ずつ)。冪等なので結果は
> 同じだが、無駄。実務では `on-run-start` (run 全体で 1 回) に切り替える設計もある
> (Step 3 拡張)。本演習は「pre_hook 経由」 を体験する目的で 4 つ全てに付ける。

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run   --profiles-dir . --select stg_orders_100knock stg_customers_100knock stg_products_100knock stg_stores_100knock
```

期待:

- 4 staging が `table` として物理化
- `staging.stg_*_100knock.last_updated_at` 列が追加される (timestamptz)

### Step 4: 物理確認

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='staging'
  AND column_name='last_updated_at'
ORDER BY table_name;
```

期待: 4 行 (各 staging に `last_updated_at` 列あり)。

```sql
SELECT max(last_updated_at) FROM staging.stg_orders_100knock;
-- 直近の dbt run の時刻
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-8-reuse/8-5-jinja-loop-audit-cols.grading.yaml
```

## 完了条件

- [ ] `dbt/macros/100-knock/topic-8/add_audit_columns.sql` が存在し、`{% for %}` loop を含む
- [ ] 4 staging model の `config()` に `pre_hook=["{{ add_audit_columns() }}"]` が設定されている
- [ ] 4 staging が `materialized='table'` になっている (view ではない)
- [ ] `dbt run` が PASS=4 で完了
- [ ] DB 上で 4 staging 全てに `last_updated_at` 列 (timestamptz) が存在

## ヒント (詰まったら)

- **`{% for %}` の構文**: `{% for var in list %}{% endfor %}` の Python 風。`var` を
  tuple unpacking する場合は `{% for schema, tbl in tables %}` のように書ける。
- **`pre_hook` vs `on-run-start` の違い**:
  - **`pre_hook`**: model 1 つ 1 つの直前に走る (4 staging に書けば 4 回)
  - **`on-run-start`**: `dbt_project.yml` に書いて、`dbt run` 全体の最初に 1 回だけ走る
  - 本問は **学習目的で `pre_hook`** を選択。実務では「全 staging が完了してから 1 回」
    の方が効率的なら `on-run-end` 案も検討。
- **`pre_hook` の配列構文**: `pre_hook=["{{ add_audit_columns() }}"]` のように
  list で渡す。`pre_hook="{{ add_audit_columns() }}"` (文字列単独) でも動くが、
  list 形式が将来 hook を増やしやすい。
- **`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`**: PostgreSQL 9.6+ でサポート。
  `IF NOT EXISTS` を付けないと 2 回目で「already exists」 エラー → 冪等性破綻。
- **`view` を `table` にする副作用**: storage を消費する。Topic ⑨ で再考する論点。
  本問は「`pre_hook` で ALTER TABLE する」 ために必要。
- **`{% if execute %}` で parse 時に SQL を出力しない**: parse 時に macro が
  展開されると意図せず `dbt parse` が失敗することがある。`{% if execute %}` で
  「runtime のみ実行」 を保証する書き方もある (本問は不要だが発展課題)。
- **MVP との関係**: MVP の `dbt/models/staging/` 系は触らない。100-knock の staging
  にだけ `last_updated_at` を付ける。MVP staging に付けたいなら、本 macro の
  `tables` list に MVP table 名を追加する (発展)。

## 解答例

詳細は [`8-5-jinja-loop-audit-cols.solution.md`](8-5-jinja-loop-audit-cols.solution.md) を参照。
