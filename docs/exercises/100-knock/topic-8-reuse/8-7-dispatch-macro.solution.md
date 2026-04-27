# 8-7 解答例

## ゴール再掲

`dbt/macros/100-knock/topic-8/safe_divide.sql` に `safe_divide(num, den)` を **dispatch macro** として書き、`default__safe_divide` (汎用) と `postgres__safe_divide` (Postgres 専用) の 2 実装を持たせる。任意の `mart_*_100knock` 1 本で `{{ safe_divide(...) }}` を呼んで 0 除算ガードが効く状態を作る。

## Step 1〜3: macro ファイルを作る

`dbt/macros/100-knock/topic-8/safe_divide.sql` (新規):

```sql
-- 100-knock Topic ⑧ 8-7: dispatch macro で adapter 別実装を分離する範例。
-- 公開インタフェース: safe_divide(num, den)
-- 既定実装 (default__): どの adapter でも動く CASE WHEN 形式
-- Postgres 実装 (postgres__): nullif() を使った Postgres 慣用句
--
-- 呼び出し側は target.type を意識しない。dbt が自動 dispatch する。

{% macro safe_divide(num, den) %}
    {{ return(adapter.dispatch('safe_divide', 'local_analytics')(num, den)) }}
{% endmacro %}


{% macro default__safe_divide(num, den) %}
    case
        when ({{ den }}) = 0 then null
        else ({{ num }})::numeric / ({{ den }})
    end
{% endmacro %}


{% macro postgres__safe_divide(num, den) %}
    ({{ num }})::numeric / nullif(({{ den }}), 0)
{% endmacro %}
```

ポイント:

- **`{{ return(...) }}` を使う**: dispatch の結果を返すには `return()` でラップする。直接 `{{ adapter.dispatch(...)(...) }}` でもレンダリングはされるが、return の方が「macro 呼び出しの戻り値」 という意図が明確。
- **prefix 規約 (`default__` / `postgres__`)**: dbt はこの prefix から実装を探す。target.type の文字列 (`postgres`) と一致しないと dispatch が `default__` に fall back する。
- **`'local_analytics'` 引数**: 自プロジェクトの macro を探させる指示。外部 package の dispatch macro (例: `dbt_utils.safe_cast`) を上書きしたい場合はここを `'dbt_utils'` にする。

## Step 4: mart で呼ぶ

`dbt/models/100-knock/topic-8/mart_customer_avg_order_100knock.sql` (新規) — 既存 mart に追記でも OK:

```sql
{{ config(
    materialized='table',
    schema='marts'
) }}

-- 100-knock Topic ⑧ 8-7: safe_divide dispatch macro を呼ぶ。
-- 顧客ごとの平均注文金額を 0 除算ガード付きで算出。
-- adapter が postgres なら nullif、それ以外なら CASE WHEN にディスパッチ。
select
    customer_id,
    sum(sales_amount) as total_revenue,
    count(*) as order_count,
    {{ safe_divide('sum(sales_amount)', 'count(*)') }} as avg_order_value
from {{ ref('int_order_details_100knock') }}
group by customer_id
```

`dbt/models/100-knock/topic-8/schema.yml` (新規 or 既存に追記):

```yaml
version: 2
models:
  - name: mart_customer_avg_order_100knock
    description: "Topic ⑧ 8-7: dispatch macro safe_divide を使った顧客別平均注文金額。avg_order_value は 0 除算で NULL を返す。"
    columns:
      - name: customer_id
        tests: [not_null, unique]
      - name: avg_order_value
        description: "safe_divide(sum(sales_amount), count(*)) の結果。0 除算時 NULL"
```

## Step 5: 動作確認 + 採点

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --select mart_customer_avg_order_100knock --profiles-dir .
```

ログに `apply grants` 等は出ないが、`OK created sql table model marts.mart_customer_avg_order_100knock` が出れば成功。

dispatch が効いているかを compile 結果で確認:

```bash
../.venv/bin/dbt compile --select mart_customer_avg_order_100knock --profiles-dir .
cat target/compiled/local_analytics/models/100-knock/topic-8/mart_customer_avg_order_100knock.sql
```

期待される compile 結果 (= postgres 実装が選ばれている):

```sql
select
    customer_id,
    sum(sales_amount) as total_revenue,
    count(*) as order_count,
    (sum(sales_amount))::numeric / nullif((count(*)), 0) as avg_order_value
from intermediate.int_order_details_100knock
group by customer_id
```

`nullif` が出ていれば `postgres__` が dispatch されている (= `default__` の `case when` が出ていれば dispatch されていない)。

run-operation で macro 単独実行 (debug):

```bash
../.venv/bin/dbt run-operation safe_divide --args '{num: "10", den: "0"}' --profiles-dir .
# Compiled SQL: (10)::numeric / nullif((0), 0)
```

採点:

```bash
cd ..
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-7-dispatch-macro.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | safe-divide-macro-file-exists       | 15/15 |
| OK | dispatch-structure-grep             | 25/25 |
| OK | three-macro-defs-grep               | 20/20 |
| OK | mart-uses-safe-divide               | 15/15 |
| OK | safe-divide-no-zero-div-error       | 25/25 |
```

## ポイント

- **dispatch の本質は「依存性の逆転」**: 呼び出し側 (`mart_*`) は「Postgres を使っている」 ことを知らずに済む。`safe_divide` という **interface** にだけ依存する。実装は dbt が target から自動選択。**間接層を 1 枚挟むことで、上流変更 (adapter 変更) が下流 (mart) に波及しない** 古典的な依存制御パターン。
- **`default__` の責務**: 「最低限どの adapter でも動く実装」 を書く。Postgres / Snowflake で specifc 最適化が要らない場面では `default__` 1 つでも済む。`postgres__` を書く意義は「Postgres らしい慣用句が短く書ける / 性能が良い」 ときに限定。
- **8-1 の `cast_money` との対比**: `cast_money` は dispatch を使わない素朴な macro。adapter 差を意識しない用途では dispatch オーバーヘッドが不要。**dispatch を入れるべきタイミング = adapter 差が明確に存在する関数だけ**。何でも dispatch にすると逆に読めなくなる。
- **Postgres `nullif()` の優雅さ**: `nullif(x, 0)` は「x が 0 と等しいなら NULL」 を返す。これと `/` の NULL 伝播 (NULL / 任意 = NULL) を組み合わせると 1 行で 0 除算ガードできる。Snowflake は `div0null()` という専用関数を持つ。adapter 別の慣用句を尊重するのが dispatch の価値。
- **テスト容易性**: `dbt run-operation` で macro を単独テストできる。`dispatched macro not found` エラーは大抵 (a) prefix の typo (`postgress__` 等) (b) `'local_analytics'` 引数の typo、で起きる。
- **多態性が dbt にとって重要な理由**: dbt は **複数 adapter (= warehouse 種別)** を 1 つの DSL で扱うことを目指している。SQL 方言差を `adapter.dispatch` で隠蔽することで、ユーザの SQL は warehouse 中立になる。これが「**dbt project は (理想的には) DB を移行しても再利用できる**」 という公約の技術基盤。

## 実行例 (採点 shell_command 視点)

```bash
$ ls dbt/macros/100-knock/topic-8/safe_divide.sql
dbt/macros/100-knock/topic-8/safe_divide.sql

$ grep -cE "adapter\\.dispatch\\(\\s*['\"]safe_divide['\"]" \
    dbt/macros/100-knock/topic-8/safe_divide.sql
1

$ grep -cE "macro\\s+(default__|postgres__)?safe_divide" \
    dbt/macros/100-knock/topic-8/safe_divide.sql
3   # 公開 + default + postgres

$ grep -rE "safe_divide" dbt/models/100-knock/ | wc -l
1   # 少なくとも 1 mart で呼ばれている

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
    -c "SELECT count(*) FROM marts.mart_customer_avg_order_100knock
        WHERE order_count > 0 AND avg_order_value IS NULL;"
0    # order_count > 0 で avg が NULL になる行はない (= 0 除算ガードが破綻していない)
```

## 解説まとめ

- **「1 interface, N 実装」 という宣言**: macro 名 `safe_divide` を「契約」 として宣言し、その実装を adapter 軸で複数並べる。これが dispatch の本質。Topic ⑤ の `contract: enforced` (列の型契約) と同じ思想 — **約束だけ宣言して、実装は別場所で定義**。
- **8-9 (metric_revenue) との関係**: 8-9 は **「業務ロジックの再利用」** (KPI 式集約) で、本問は **「実装ロジックの再利用」** (adapter 差吸収)。再利用には少なくとも 2 軸あり、それぞれに macro が応答できる。Topic ⑧ で両方を体験する意義は、「macro = 単なる関数」 ではなく **「依存設計の道具」** だと体感すること。
- **Postgres 専用に深入りしない理由**: 本リポジトリは Postgres でのみ動作する。dispatch を書く価値は将来 Snowflake / BigQuery 移行が現実的になった時に効いてくる。**現状コストはほぼゼロ、将来オプション価値は大** という比率なので「とりあえず dispatch 化しておく」 が学習文脈では妥当。
- **dbt-utils との関係**: `dbt_utils.safe_cast` 等は内部で adapter.dispatch を多用している。本問で書いた `safe_divide` も「ミニ dbt-utils」 と思えばよい。チームで共通利用する macro は **package 化** (= リポジトリ分離 + `packages.yml` 経由で配布) するのが次のステップ。
- **`{% if target.type == 'postgres' %}` で書いた素朴解との比較**: 動くが、(a) macro が肥大化 (b) adapter 追加で同ファイルが PR 衝突 (c) test 困難。dispatch にすると (a) 1 ファイル 3 macro で見通し良 (b) 新 adapter は別 macro 追加だけ (c) `run-operation` で個別 test 可能。

## 拡張アイデア

- **`safe_subtract` / `safe_log` も dispatch 化**: `safe_log` は (Postgres) `log(nullif(x, 0))`、(Snowflake) `ln(x)` のように差が出る。dispatch 一族として並べると「数学関数の adapter 差ライブラリ」 が育つ。
- **`dispatch:` 設定で外部 package を override**: `dbt_project.yml` の `dispatch:` で `[{macro_namespace: 'dbt_utils', search_order: ['local_analytics', 'dbt_utils']}]` と書くと、`dbt_utils.safe_cast` を呼んでも自プロジェクトの実装が優先される。
- **`safe_divide(num, den, default_value=0)` と引数追加**: 「0 除算時に NULL ではなく 0 を返したい」 ユースケース対応。ただし adapter 別実装の両方を更新する必要が出るので、interface 設計が固まってから入れる。
- **`tests/generic/` で safe_divide の test**: `dbt test` で「`avg_order_value` が NULL ではない (= safe_divide が壊れていない) 行数が、0 除算リスクのない行数と一致する」 を検証する singular test を書く。
- **postgres__ の `nullif` を `decimal_safe_divide`*** に名前変更し、interface を kept**: 「Postgres は `decimal` 型で精度を保ちたい」 のような要件が出たとき、interface (`safe_divide`) を変えずに実装だけ進化させられる。これが dispatch の中長期メリット。
