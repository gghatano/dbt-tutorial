# Exercise 09 解答例

## Step 1: 現状確認

```bash
# 実験用 model
mkdir -p dbt/models/exercises/09
cat <<'SQL' > dbt/models/exercises/09/mart_test_grant_visibility.sql
{{ config(materialized='table', schema='marts') }}

select 1 as id, 'hello' as label
SQL
```

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select mart_test_grant_visibility
# 1 of 1 OK created sql table model marts.mart_test_grant_visibility ...
```

readonly_user で:

```bash
docker exec -it local-data-postgres psql -U readonly_user -d analytics
```

```sql
analytics=> SELECT * FROM marts.mart_test_grant_visibility;
ERROR:  permission denied for table mart_test_grant_visibility
analytics=> \q
```

期待どおり grant 不足の症状を再現。

## Step 2: hook 追加

### `dbt/dbt_project.yml`

```yaml
name: 'local_analytics'
version: '1.0.0'
config-version: 2

profile: 'local_analytics'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

# Auto-grant marts read access to readonly_user after every dbt run.
# Picks up newly-created mart tables that Terraform's static grants miss.
on-run-end:
  - "{{ grant_select_on_marts() }}"

models:
  local_analytics:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts
```

### `dbt/macros/grant_select_on_marts.sql`

```sql
{#-
    on-run-end hook helper.
    Grants SELECT on every table in the marts schema to readonly_user.

    Why a macro instead of inline SQL in dbt_project.yml:
    - Easier to extend (add other schemas, log output, target gating)
    - Keeps dbt_project.yml readable
-#}
{% macro grant_select_on_marts() %}
    {% if target.name == 'dev' %}
        {%- set sql -%}
            grant usage on schema marts to readonly_user;
            grant select on all tables in schema marts to readonly_user;
        {%- endset -%}
        {% do run_query(sql) %}
        {% do log("granted select on marts.* to readonly_user", info=true) %}
    {% endif %}
{% endmacro %}
```

**ポイント**:

- `grant usage on schema marts` も毎回必要（Terraform で既に付与済みなら no-op）。新 schema を追加したケースで漏れがないように。
- `grant select on all tables` は **その時点で存在する table** に効く。新しく増えた mart にも反映されるので、毎 run で再発行する設計で問題なし。
- 本番環境向けに「特定 schema 一覧をループで回す」拡張例:
  ```sql
  {% for schema in ['marts', 'staging'] %}
      grant usage on schema {{ schema }} to readonly_user;
      grant select on all tables in schema {{ schema }} to readonly_user;
  {% endfor %}
  ```

## Step 3: dbt run で grant が走るのを確認

```bash
../.venv/bin/dbt run --profiles-dir . --select mart_test_grant_visibility
# 04:55:01  Running with dbt=1.11.8
# 04:55:02  Found 9 models, ...
# 04:55:03  1 of 1 START sql table model marts.mart_test_grant_visibility ... [RUN]
# 04:55:04  1 of 1 OK created sql table model marts.mart_test_grant_visibility .. [SELECT 1 in 0.20s]
# 04:55:04
# 04:55:04  Running 1 on-run-end hook
# 04:55:04  1 of 1 START hook: local_analytics.on-run-end.0 ........... [RUN]
# 04:55:04  granted select on marts.* to readonly_user
# 04:55:04  1 of 1 OK   hook: local_analytics.on-run-end.0 ........... [OK in 0.04s]
# 04:55:04
# 04:55:04  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1
```

readonly_user で再確認:

```sql
analytics=> SELECT * FROM marts.mart_test_grant_visibility;
 id | label
----+-------
  1 | hello
(1 row)
```

成功。

## Step 4 (任意): pre/post hook

`dbt/models/exercises/09/mart_test_grant_visibility.sql` を以下に置き換え:

```sql
{{ config(
    materialized='table',
    schema='marts',
    pre_hook="set local statement_timeout = '30s'",
    post_hook="analyze {{ this }}"
) }}

select 1 as id, 'hello' as label
```

```bash
../.venv/bin/dbt run --profiles-dir . --select mart_test_grant_visibility
# 04:56:01  1 of 1 START sql table model marts.mart_test_grant_visibility ... [RUN]
# 04:56:01  + Executing pre_hook: set local statement_timeout = '30s'
# 04:56:01  + Executing post_hook: analyze marts.mart_test_grant_visibility
# 04:56:01  1 of 1 OK created sql table model marts.mart_test_grant_visibility ..
# 04:56:01  Running 1 on-run-end hook
# 04:56:01  granted select on marts.* to readonly_user
```

3 つの hook (pre / post / on-run-end) が順に走る。

## Step 5: ロールバック

```bash
# dbt_project.yml の on-run-end: ブロックと、grant_select_on_marts macro を消す
# (Edit でやってもよい)
git diff dbt/dbt_project.yml dbt/macros/   # 確認
git checkout dbt/dbt_project.yml            # 元に戻す
rm dbt/macros/grant_select_on_marts.sql

# 実験 mart を drop
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "DROP TABLE IF EXISTS marts.mart_test_grant_visibility CASCADE;"

# exercises 09 ディレクトリ片付け
rm -rf dbt/models/exercises/09/
```

`dbt run` がまた MVP デフォルト挙動（hook なし）に戻ったことを確認:

```bash
../.venv/bin/dbt run --profiles-dir .
# Done. PASS=8 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8
# (hook ログが出ない)
```

## 解説まとめ

- **hook の 4 種類** は単位（model / project）と発行タイミング（before / after）の組み合わせ。grant のような「全 mart 共通の後処理」は `on-run-end`。「テーブル個別の最適化」は `post-hook`。
- **macro に切り出す価値**: hook 本体に SQL を直書きするより、macro 化したほうが再利用と読みやすさが上がる。`target.name` チェックなど環境別ロジックも macro 内に閉じ込められる。
- **`+grants:` config の方がシンプル**: dbt 1.2+ では `models:` config に `+grants:` を書けば hook を書かずに済む。アダプタ依存だが、dbt-postgres 1.10 はサポート。学習として hook を一度書いてから `+grants:` に乗り換えるのが理想ルート。
- **本番運用での注意**: `on-run-end` の SQL が失敗すると dbt 1.6+ では exit code が非 0 になる。CI で「grant 漏れを警告」したい場合に有用。

## 拡張アイデア

- `+grants:` config に書き換えて hook を消す → 同じ効果がより少ないコードで実現できることを確認
- production 用の target を `profiles.yml` に追加し、`if target.name == 'prod'` で別ユーザに grant する分岐を試す
- `on-run-start` で `\timing on` 相当の Postgres 設定を入れて、build 時間を計測
