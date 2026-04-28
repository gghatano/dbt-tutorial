# 8-7: dispatch macro `safe_divide(num, den)` を default + postgres 別実装で書く (多態の宣言)

## シナリオ

8-1 で書いた `cast_money` macro は **「全 adapter で同じ SQL」** が出ればよい単純な macro だった。しかし現実の dbt プロジェクトでは「Postgres と Snowflake で NULL 処理関数の名前が違う」「BigQuery では `SAFE_DIVIDE` という組込関数があるが Postgres にはない」 のような **adapter 別の SQL 方言差** に遭遇する。

素朴に書くと:

```sql
{% macro safe_divide(num, den) %}
  {% if target.type == 'postgres' %}
    case when {{ den }} = 0 then null else {{ num }}::numeric / {{ den }} end
  {% elif target.type == 'snowflake' %}
    div0null({{ num }}, {{ den }})
  {% elif target.type == 'bigquery' %}
    safe_divide({{ num }}, {{ den }})
  {% endif %}
{% endmacro %}
```

これでも動くが、**1 macro 内に if/elif が並ぶと拡張で破綻** する。新しい adapter (Redshift, DuckDB) が増えるたびに分岐を足すことになり、PR は同じファイルで衝突する。

dbt の **`adapter.dispatch(...)` 機構** はこれを **Strategy パターン** で解決する。1 つの「公開インタフェース macro」を書き、その中で `adapter.dispatch('safe_divide', 'local_analytics')()` を呼ぶ。実装は `default__safe_divide` (= 既定実装) と `postgres__safe_divide` (= Postgres 専用上書き) のように **prefix 規約で別 macro として書く**。dbt は実行時の `target.type` から正しい実装を **自動選択** する。

このエクササイズでは Postgres 上で動作する `safe_divide(num, den)` を dispatch macro として書き、`mart_*_100knock` の集計式 (例えば `total_revenue / order_count` のような割算) で **0 除算ガード** が効くことを確認する。本リポジトリは Postgres 専用なので深入りはしないが、「**1 interface → adapter 別 N 実装**」という多態の宣言を 1 度書いておくと、Snowflake / BigQuery 移行時に macro 1 つを加えるだけで済む構造が手に入る。

## 学べること

- `adapter.dispatch('macro_name', 'package_name')` の書き方
- `default__macro_name` / `postgres__macro_name` の prefix 規約
- 「公開インタフェース macro」と「adapter 別実装」を別ファイルで管理する流儀
- multi-adapter 対応の依存設計 (1 → N の多態)
- `target.type` で分岐する素朴解との比較

## 前提

- Topic ② 〜 ⑦ + Topic ⑧ 8-1〜8-5 完了
- Postgres 環境で動作 (= `target.type == 'postgres'`)
- 学習者の macro は `dbt/macros/100-knock/topic-8/` 配下に置く

## 入力データ

不要。既存の `int_order_details_100knock` を割り算する集計を `mart_*_100knock` 1 本に追加するだけ。

## 課題

### Step 1: dispatch macro 公開インタフェース

`dbt/macros/100-knock/topic-8/safe_divide.sql` を新規作成。**公開 macro** `safe_divide(num, den)` を書く。中身は `adapter.dispatch('safe_divide', 'local_analytics')(num, den)` の 1 行 (パッケージ名は `dbt_project.yml` の `name` = `local_analytics`)。

### Step 2: default 実装

同じファイル内に `default__safe_divide(num, den)` を書く。中身は `case when {{ den }} = 0 then null else {{ num }}::numeric / {{ den }} end`。これが「Postgres 以外の adapter で fallback として使われる」 既定実装。

### Step 3: postgres 専用実装

同じファイル内に `postgres__safe_divide(num, den)` を書く。Postgres は `nullif()` を使えばより簡潔に書ける:

```sql
{% macro postgres__safe_divide(num, den) %}
    {{ num }}::numeric / nullif({{ den }}, 0)
{% endmacro %}
```

`nullif(x, 0)` は「x が 0 なら NULL」 を返すので、その後の割算は **NULL 伝播 → 結果 NULL** になる。`case when` を書かずに済むので Postgres らしい慣用句。

### Step 4: mart で呼ぶ

任意の `mart_*_100knock` 1 本 (例: `mart_customer_sales_100knock` を新規 or 既存に追記) で `safe_divide` を使った列を 1 つ足す。例えば:

```sql
{{ config(materialized='table', schema='marts') }}
select
    customer_id,
    sum(sales_amount) as total_revenue,
    count(*) as order_count,
    {{ safe_divide('sum(sales_amount)', 'count(*)') }} as avg_order_value
from {{ ref('int_order_details_100knock') }}
group by customer_id
```

`order_count = 0` の顧客は理論上 group by 後には出てこないが、テストの観点で「もし den が 0 でも落ちない」 ことが宣言できているのが価値。

### Step 5: 動作確認 + 採点

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --select mart_customer_sales_100knock --profiles-dir .

# 0 除算が起きないことを sql_assert 視点で確認
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT count(*) FROM marts.mart_customer_sales_100knock
WHERE avg_order_value IS NULL OR avg_order_value > 0;
SQL
# = 全行 (NULL or 正の値、エラーで落ちない)

cd ..
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-7-dispatch-macro.grading.yaml
```

## 完了条件

- [ ] `dbt/macros/100-knock/topic-8/safe_divide.sql` が存在する
- [ ] ファイル内に `safe_divide` (公開) / `default__safe_divide` / `postgres__safe_divide` の 3 macro が定義されている
- [ ] `safe_divide` 内で `adapter.dispatch('safe_divide', 'local_analytics')` を呼んでいる
- [ ] 任意の `mart_*_100knock` で `{{ safe_divide(...) }}` を呼び出し、`dbt run` が PASS
- [ ] 出力 mart の割算列で 0 除算による DB エラーが起きない (NULL 返却)

## ヒント (詰まったら)

- **公開 macro の名前 == dispatch する macro 名**: 公開 `safe_divide` の中で `adapter.dispatch('safe_divide', ...)` を呼ぶ。名前を一致させないと dispatch が探せない。
- **第 2 引数 (`'local_analytics'`)**: dbt project 名 (= `dbt_project.yml` の `name:`)。これにより「自プロジェクト内の `<adapter>__<macro_name>` を探せ」と指示する。外部 package (例: `dbt_utils`) の dispatch macro を上書きしたい場合はここに package 名を書く。
- **prefix 規約**: `default__` / `postgres__` / `snowflake__` / `bigquery__` / `redshift__` / `duckdb__` などが標準。`target.type` の文字列がそのまま使われる。
- **default 実装は何のためにあるか**: dbt が実行時に「`<adapter>__safe_divide`」が見つからないとき、`default__safe_divide` を fallback として使う。新 adapter 追加時の安全網。
- **adapter 別 macro が見つからないとき**: dbt のエラーメッセージに「dispatched macro not found」 が出る。`default__` を書いていれば回避できる。
- **`dispatch_packages` 設定**: `dbt_project.yml` で `dispatch:` を書くと、外部 package の dispatch macro を **自前で override** できる。本問では使わないが、覚えておくと dbt-utils カスタマイズ時に効く。
- **テストでの確認**: `dbt run-operation safe_divide --args '{num: "10", den: "0"}'` のような run-operation コマンドで macro を単独実行できる。debug 時に便利。
- **Postgres の `/` は型で挙動が変わる**: `1/2` (integer 同士) は `0` を返す。`1::numeric / 2` で `0.5`。本問の `default__` は `::numeric` キャストを入れているので integer 系でも安全。
- **複数 macro を 1 ファイルに書く是非**: dbt 公式の流儀では「1 macro = 1 ファイル」推奨だが、dispatch の場合は 3 macro が密結合するので 1 ファイルにまとめてよい (むしろ推奨)。

## 解答例

詳細は [`8-7-dispatch-macro.solution.md`](8-7-dispatch-macro.solution.md) を参照。
