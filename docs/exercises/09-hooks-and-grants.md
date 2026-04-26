# Exercise 09: on-run-end hook で grants を自動化する

## シナリオ

MVP では Terraform が `readonly_user` に `marts.*` の SELECT 権限を grant している。これは「Terraform apply 時に存在する table」にしか効かない。`dbt run` で **新しい mart table が増える** と、Terraform を再 apply するまで `readonly_user` は新マートを参照できない（`permission denied for table` エラー）。

実運用では「`dbt run` した瞬間に readonly_user が新マートも見られる」状態にしたい。dbt の **post-hook / on-run-end** フックを使うと、dbt run の最後に「marts schema 内の全 table に SELECT を grant する」 SQL を自動発行できる。

このエクササイズでは hook の 3 種類（`pre-hook` / `post-hook` / `on-run-start` / `on-run-end`）を比較し、grant 自動化を `on-run-end` で実装する。

## 学べること

- `on-run-start` / `on-run-end` / `pre-hook` / `post-hook` の違い
- Jinja で動的に SQL を生成する基本パターン
- `target.schema` / `target.database` の参照
- `GRANT SELECT ON ALL TABLES IN SCHEMA ... TO ...` を発行
- dbt の grants 機能（`+grants:` config、dbt 1.2+）との対比

## 前提

- main HEAD 完了状態
- Exercise 07 / 08 で MVP の dbt 設定を改変済みでも問題なし
- 他 Exercise との依存なし

## 入力データ

不要。既存の `marts.*` を再 build するだけ。

## 課題

> **MVP への影響に注意**: 本演習は `dbt/dbt_project.yml` を直接編集する。MVP の `dbt run` も grant フック実行を伴うようになる（無害だが 1 秒程度遅くなる）。ロールバックは Step 5 を参照。

### Step 1: 現状確認 — 新 mart は readonly_user から見えない

readonly_user で接続して mart の中身を見る:

```bash
docker exec -it local-data-postgres psql -U readonly_user -d analytics
```

```sql
\dt marts.*
SELECT count(*) FROM marts.mart_daily_sales;   -- OK
\q
```

ここで dbt から新マート `marts.mart_test_grant_visibility` を作る（適当な実験用 model を `dbt/models/exercises/09/mart_test_grant_visibility.sql` に作成、内容は `select 1 as id`）。`dbt run --select mart_test_grant_visibility` で table を生成。

readonly_user で:

```sql
SELECT * FROM marts.mart_test_grant_visibility;
-- ERROR: permission denied for table mart_test_grant_visibility
```

これが grant 不足の症状。

### Step 2: `on-run-end` hook を追加

`dbt/dbt_project.yml` に追記:

```yaml
on-run-end:
  - "{{ grant_select_on_marts() }}"
```

そして `dbt/macros/grant_select_on_marts.sql` を作成:

```sql
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

ポイント:

- `target.name` チェック: production 環境で誤って同じ grant が走らないようガード（学習用なので必須ではない）
- `{% do run_query(sql) %}` で SQL を実際に発行
- `{% do log(..., info=true) %}` で dbt run のログに 1 行残す

### Step 3: dbt run 後に grant が走ることを確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select mart_test_grant_visibility
```

出力末尾に:

```
... Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1
... Running 1 on-run-end hook
... 1 of 1 START hook: local_analytics.on-run-end.0 ............... [RUN]
... granted select on marts.* to readonly_user
... 1 of 1 OK   hook: local_analytics.on-run-end.0 ............... [OK in 0.05s]
```

readonly_user で:

```sql
SELECT * FROM marts.mart_test_grant_visibility;
-- 1
```

成功。

### Step 4 (任意): pre-hook / post-hook も試す

`dbt/models/exercises/09/mart_test_grant_visibility.sql` の `config()` に追記:

```sql
{{ config(
    materialized='table',
    schema='marts',
    pre_hook="set local statement_timeout = '30s'",
    post_hook="analyze {{ this }}"
) }}

select 1 as id
```

- `pre_hook`: model build 直前に発行（model 単位）
- `post_hook`: model build 直後に発行（model 単位）
- `on-run-start` / `on-run-end`: 全 model 実行の前後 1 回ずつ（dbt project 全体）

`dbt run --select mart_test_grant_visibility` で `analyze marts.mart_test_grant_visibility` が走ることをログで確認。

### Step 5: ロールバック手順

このエクササイズを撤去するには:

```bash
# 1. dbt_project.yml の on-run-end: ブロックを削除
# 2. dbt/macros/grant_select_on_marts.sql を削除
rm dbt/macros/grant_select_on_marts.sql

# 3. (任意) 実験用 mart を drop
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "DROP TABLE IF EXISTS marts.mart_test_grant_visibility CASCADE;"

# 4. exercises ディレクトリを片付け
rm -rf dbt/models/exercises/09/
```

これで MVP の状態に戻る。

## 完了条件

- [ ] grant 前は readonly_user が新マートを参照できない（`permission denied`）
- [ ] `dbt/dbt_project.yml` に `on-run-end:` フックを追加し、`grant_select_on_marts()` macro を呼ぶ
- [ ] `dbt run` のログに `Running 1 on-run-end hook` と `granted select on marts.*` が出る
- [ ] grant 後は readonly_user が新マートを参照できる
- [ ] (任意) pre/post hook が model 単位で発行される

## ヒント（詰まったら）

- **hook の 4 種類**:
  | 種類 | 単位 | 発行タイミング |
  |---|---|---|
  | `on-run-start` | project 全体 | `dbt run` の開始時 1 回 |
  | `on-run-end` | project 全体 | `dbt run` の終了時 1 回 |
  | `pre-hook` | model | 各 model build 直前 |
  | `post-hook` | model | 各 model build 直後 |

- **`run_query` の戻り値**: `agate.Table` オブジェクト。SELECT 結果を取り出して Jinja loop で使うことも可能（高度）。本 Exercise では戻り値は使わない。

- **dbt 公式の `+grants:` config (dbt 1.2+)**: hook を書かずに済む手段として `models:` config に `+grants: {select: [readonly_user]}` を書く方法もある。本演習では「hook の仕組みを学ぶ」目的で macro 方式を採るが、本番で grants だけ自動化したいなら `+grants:` を使う方がシンプル。
  ```yaml
  models:
    local_analytics:
      marts:
        +materialized: table
        +schema: marts
        +grants:
          select: ['readonly_user']
  ```
  これで dbt が自動で `GRANT SELECT` を発行する（ただし Postgres adapter が `+grants:` を完全サポートしているかは version 依存。dbt-postgres 1.10 はサポート）。

- **`target.name == 'dev'` で囲む理由**: profiles.yml の target 名が `dev` のときだけ grant が走る。本番で target 名 `prod` に切り替えたとき、自動 grant が走らないようにしておくとセキュリティ事故が減る。

- **「on-run-end は失敗しても成功する」**: hook が SQL エラーで落ちても dbt run の exit code は 0 のまま、というのが dbt の挙動だった時期がある。1.6+ では hook 失敗で exit 非 0 になる。CI で grants の漏れを検知したい場合は dbt version を確認。

- **新マートが追加された瞬間に grant したい**: `on-run-end` は run の最後にまとめて 1 回。grant 漏れリスクを減らすため、`post-hook` で「自分自身の table に grant する」方式もある:
  ```sql
  {{ config(post_hook="grant select on {{ this }} to readonly_user") }}
  ```
  ただし これは model 数だけ grant が発行されるので、grant 1 回より遅い場合がある。

## 解答例

詳細は [`solutions/09-hooks-and-grants.solution.md`](solutions/09-hooks-and-grants.solution.md) を参照。
