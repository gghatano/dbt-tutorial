# 8-9 解答例

## ゴール再掲

`metric_revenue(model, date_col, amount_col)` macro を 1 つ書き、3 mart (`mart_daily_revenue_100knock` / `mart_customer_revenue_100knock` / `mart_product_revenue_100knock`) から **同じ macro を別 grain で呼ぶ** だけで完成する状態を作る。式変更時に macro 1 行修正で 3 mart 全部が更新されることを目視確認する。

## Step 1: macro `metric_revenue` を作る

`dbt/macros/100-knock/topic-8/metric_revenue.sql` (新規):

```sql
-- 100-knock Topic ⑧ 8-9: KPI 集計式 (revenue) を 1 箇所に閉じ込める汎用 macro。
--
-- 引数:
--   model      - ref で参照する model 名 (例: 'int_order_details_100knock')
--   group_col  - GROUP BY する列 (= mart の grain。例: 'order_date', 'customer_id')
--   amount_col - 集計対象の金額列 (例: 'sales_amount')
--
-- 戻り値: SELECT 全体 (mart 側は {{ metric_revenue(...) }} だけで完結)
--
-- 集計式の変更 (税込・キャンセル除外等) は本 macro 内 1 行を編集するだけで
-- 3 mart 全てに伝播する (= Single Source of Truth for revenue metric)。

{% macro metric_revenue(model, group_col, amount_col) %}
    {{ return(_metric_revenue_sql(model, group_col, amount_col)) }}
{% endmacro %}


{% macro _metric_revenue_sql(model, group_col, amount_col) -%}
select
    {{ group_col }}                              as period,
    sum({{ amount_col }})::numeric(14, 2)        as revenue,
    count(*)                                     as order_count
from {{ ref(model) }}
group by {{ group_col }}
{%- endmacro %}
```

ポイント:

- **2 段構成 (`metric_revenue` / `_metric_revenue_sql`)**: 公開 macro が `return()` で内部 macro の結果を返す。1 段でも書けるが、後で「dispatch 化したい」 (例えば adapter 別最適化) ときに公開 interface が安定するメリットがある (8-7 dispatch との連携)
- **`{{ return(...) }}`**: macro が「SQL 文字列を返す」 ことを明示。call 側で `{{ metric_revenue(...) }}` と書くと、戻り値の SQL がその位置にレンダリングされる
- **`{{ ref(model) }}`**: 引数 `model` (= 文字列) を `ref()` に渡すことで、macro が **特定 table に縛られない** 汎用性を持つ。これが「3 mart で再利用できる」 鍵
- **`numeric(14, 2)` キャスト**: BI で float 表示にぶれないよう精度固定。8-1 の `cast_money` macro があるならそれを呼んでもよい
- **`order_count` も一緒に返す**: 同じ macro で「revenue + 件数」 を出す方が呼び側が薄くなる。粒度別の補助 metric を呼び側で書く設計でも可

## Step 2: 3 mart で macro を呼ぶ

### `dbt/models/100-knock/topic-8/mart_daily_revenue_100knock.sql`

```sql
{{ config(materialized='table', schema='marts') }}

-- 100-knock Topic ⑧ 8-9: metric_revenue macro を呼ぶだけで完結する mart。
-- grain: 1 日 1 行 (period = order_date)
{{ metric_revenue('int_order_details_100knock', 'order_date', 'sales_amount') }}
```

### `dbt/models/100-knock/topic-8/mart_customer_revenue_100knock.sql`

```sql
{{ config(materialized='table', schema='marts') }}

-- grain: 1 顧客 1 行 (period = customer_id)
{{ metric_revenue('int_order_details_100knock', 'customer_id', 'sales_amount') }}
```

### `dbt/models/100-knock/topic-8/mart_product_revenue_100knock.sql`

```sql
{{ config(materialized='table', schema='marts') }}

-- grain: 1 商品 1 行 (period = product_id)
{{ metric_revenue('int_order_details_100knock', 'product_id', 'sales_amount') }}
```

3 mart 全て **2 行で完結** する (config + macro 呼び出し)。集計ロジックは 1 行も書いていない — それが本問の主旨。

### schema.yml (オプション)

`dbt/models/100-knock/topic-8/schema.yml` に 3 mart の test を足しておくと安全:

```yaml
version: 2
models:
  - name: mart_daily_revenue_100knock
    columns:
      - name: period
        tests: [not_null, unique]
      - name: revenue
        tests: [not_null]
  - name: mart_customer_revenue_100knock
    columns:
      - name: period
        tests: [not_null, unique]
  - name: mart_product_revenue_100knock
    columns:
      - name: period
        tests: [not_null, unique]
```

## Step 3: 式変更 → 3 mart 同時更新の確認

「税込にする」 想定で macro 1 行を変更:

```sql
-- 変更前
sum({{ amount_col }})::numeric(14, 2)        as revenue,

-- 変更後
sum({{ amount_col }} * 1.10)::numeric(14, 2) as revenue,
```

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select 100-knock.topic-8 --profiles-dir .
```

3 mart の合計を確認:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT 'daily'    AS mart, sum(revenue)::numeric(20,2) FROM marts.mart_daily_revenue_100knock
UNION ALL
SELECT 'customer' AS mart, sum(revenue)::numeric(20,2) FROM marts.mart_customer_revenue_100knock
UNION ALL
SELECT 'product'  AS mart, sum(revenue)::numeric(20,2) FROM marts.mart_product_revenue_100knock;
SQL
# 全 3 行で sum が等しいはず (同じソースを別 grain で集計しただけなので合計は不変)
# 例:
# daily    | 12345678.90
# customer | 12345678.90
# product  | 12345678.90
```

3 mart 全部の合計が一致 (= 同じソース・同じ式から派生) を観測できれば、macro による集約が動いている証拠。

## Step 4: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-9-metric-revenue-macro.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | metric-revenue-macro-file-exists  | 15/15 |
| OK | macro-uses-return                 | 15/15 |
| OK | three-marts-call-macro            | 25/25 |
| OK | dbt-build-three-marts-success     | 20/20 |
| OK | three-marts-revenue-sums-equal    | 25/25 |
```

## ポイント

- **「KPI 集計式の Single Source of Truth」**: 3 mart で `revenue` の定義が散らばると、誰かが 1 mart だけ修正して **silent な不整合** が生まれる (= ダッシュボード A と B で売上が違う、という現場の典型事故)。macro に集約すれば、定義変更は macro 1 箇所、影響は dbt の lineage で追える
- **`{{ ref(model) }}` の動的参照**: `ref()` は **コンパイル時に静的解析される** ので、引数で渡された string でも dbt は依存を正しく追える。これにより macro 経由でも **`dbt build --select +mart_daily_revenue_100knock`** で `int_order_details_100knock` が正しく上流として認識される
- **mart が「2 行で完結」 する効果**:
  - レビュー: SQL の集計ロジックを読まなくてよい (macro 名で意図が伝わる)
  - 拡張: 同じ macro を呼ぶ第 4 mart を追加するのが簡単 (`mart_store_revenue_100knock` を 2 行で書ける)
  - テスト: macro 単独で `dbt run-operation` テスト可能
- **後の Semantic Layer (dbt 1.6+) との関係**: 本問の macro 集約は「**SQL の片を集約**」だが、Semantic Layer は「**metric 概念そのものを宣言** (`metrics:` YAML)」。Semantic Layer では BI ツールが metric を直接参照でき、SQL 自体が不要になる。本問はそこに至る前段としての「macro 集約パターン」 を体験する位置づけ
- **macro による KPI 集約の限界**: 集約軸 (group by) が完全に同じ式で書けない場合 (例: 商品マートだけ `category` でロールアップしたい) は macro 1 つで全 mart は賄えない。こういう場合は macro を **戦略パターン** で複数用意するか (`metric_revenue_simple` / `metric_revenue_with_category`)、Semantic Layer に移行する
- **`amount_col` を文字列で渡す危うさ**: `{{ amount_col }}` で SQL に直接展開されるので、悪意ある呼び側が `'1; drop table foo;--'` を渡すと SQL injection が可能 (= dbt は安全側で運用される前提)。`adapter.quote(...)` を使うとより安全だが、本問は学習者環境を想定して素朴形

## 実行例 (採点 shell_command 視点)

```bash
$ ls dbt/macros/100-knock/topic-8/metric_revenue.sql
dbt/macros/100-knock/topic-8/metric_revenue.sql

$ grep -cE "macro\\s+metric_revenue\\s*\\(" \
    dbt/macros/100-knock/topic-8/metric_revenue.sql
1

$ grep -cE "\\{\\{\\s*return\\(" \
    dbt/macros/100-knock/topic-8/metric_revenue.sql
1

$ grep -rlE "\\{\\{\\s*metric_revenue\\(" dbt/models/100-knock/topic-8/ | wc -l
3   # 3 mart で呼び出されている

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT
  (SELECT round(sum(revenue),2) FROM marts.mart_daily_revenue_100knock) =
  (SELECT round(sum(revenue),2) FROM marts.mart_customer_revenue_100knock) AND
  (SELECT round(sum(revenue),2) FROM marts.mart_customer_revenue_100knock) =
  (SELECT round(sum(revenue),2) FROM marts.mart_product_revenue_100knock)
SQL
t   # 3 mart の合計が一致 = 同一 macro から派生した証跡
```

## 解説まとめ

- **なぜ KPI 式の集約が「再利用」 の中で重要か**: KPI は「**ビジネス側に対して dbt project が約束する数値定義**」。これが mart ごとに微妙に違うと、dbt project は **複数の真実を同時に主張する** ことになる。再利用 = DRY ではなく、再利用 = **整合性の保証** という側面がここに表れる
- **macro vs CTE の使い分け**: 同じ mart 内で再利用するなら CTE で十分。**複数 mart で再利用** するなら macro。**プロジェクト横断で再利用** するなら package。**マルチプロジェクト** で共有するなら Semantic Layer。再利用の **スコープ** が macro / package / Semantic Layer の選択基準
- **8-1 (`cast_money`) と本問の対比**:
  - `cast_money` = **型変換** の集約 (= 列 1 つに対する変換)
  - `metric_revenue` = **集計** の集約 (= GROUP BY を含む変換)
  - 両者は粒度が違うが「重複した SQL 片を 1 箇所に閉じ込める」 構造は同じ
- **8-7 (dispatch) との合わせ技**: `metric_revenue` を dispatch 化すれば「**adapter ごとに最適化された集計**」 (例えば BigQuery で `APPROX_SUM`) を入れ替えられる。本問では single 実装で十分だが、設計の余白として
- **「macro が肥大化したら」 のサイン**: 引数 4 個以上、内部 if/else 多用、になったら **dispatch / 設計分割** を検討。`metric_revenue` も将来「税抜 vs 税込」「キャンセル含む vs 除外」 のフラグを増やしすぎると破綻する。そうなる前に **semantic layer に移行** が現実解
- **テストの書き方**: 「macro が壊れていない」 を保証する singular test を `tests/100-knock/topic-8/test_metric_revenue_consistency.sql` に書く: 「3 mart の合計が等しい」 を検証。CI で macro 変更が事故ったら即検知できる

## 拡張アイデア

- **`metric_revenue_yoy` (前年比)**: macro を拡張し、`previous_year_revenue` を join する集計を追加。1 macro でより複雑な metric が作れる
- **macro を package 化**: `dbt/macros/100-knock/topic-8/` を別 git repo に切り出し、`packages.yml` で `git: ...` 経由で参照。複数 dbt project で共有
- **Semantic Layer 移行**: `dbt/metrics/revenue.yml` に `metrics:` ブロックで metric を宣言、`mart_*_revenue_*` は不要になる。dbt-cloud 限定機能
- **dispatch 化**: 8-7 と組み合わせ、`postgres__metric_revenue` で Postgres 慣用句、`bigquery__metric_revenue` で BQ 関数を使う 2 実装に分ける
- **macro 単体テスト**: `tests/generic/test_metric_revenue_invariants.sql` を書き、「revenue 合計 = source の sum(amount_col)」 を検証する単体テスト的な singular test
- **「式変更で 3 mart 全部が更新される」 を CI で証跡化**: 現在の `target/manifest.json` から 3 mart 各 node の `compiled_code` を取り出し、共通の式 (`sum({{ amount_col }})`) が **3 model で同じ位置に出現** することを Python で検査
