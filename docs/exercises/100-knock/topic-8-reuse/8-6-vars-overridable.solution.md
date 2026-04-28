# 8-6 解答例

## ゴール再掲

`dbt_project.yml` に `vars: {min_order_amount: 100}` を宣言し、`int_order_details_100knock.sql` で `where sales_amount >= var('min_order_amount')` を効かせ、`dbt run --vars '{min_order_amount: <別の値>}'` で行数が変わる状態を作る。

## Step 1: 現状確認

フィルタなし状態の行数を控える:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT count(*), min(sales_amount)::int, max(sales_amount)::int
FROM intermediate.int_order_details_100knock;
SQL
# 例: 10000|10|9800
```

`int_order_details_100knock` の現状の行数 (例 10,000)、最小 sales_amount (例 10) を覚えておく。Step 4 で「100 でフィルタすると行が減る」「0 でフィルタすると元に戻る」を比較する基準値になる。

## Step 2: `dbt/dbt_project.yml` を編集

トップレベル (= `models:` と同階層) に `vars:` ブロックを追加:

```yaml
name: 'local_analytics'
version: '1.0.0'
config-version: 2

profile: 'local_analytics'

# ... 中略 (model-paths 等) ...

# 100-knock Topic ⑧ 8-6: ビジネスパラメータをコードから分離。
# 単位は JPY。100 円以下の注文 (= ノベルティ・送料調整等) は下流 mart に流さない方針。
# CI / dev で全件流したい場合は `dbt run --vars '{min_order_amount: 0}'` で上書き。
vars:
  min_order_amount: 100

models:
  local_analytics:
    staging:
      +materialized: view
      +schema: staging
    # ... (既存) ...
```

ポイント:

- **トップレベルに置く**: `vars:` は project 全体スコープ。`models:` の下にネストしないこと。
- **数値リテラル**: `100` (引用符なし)。`'100'` だと文字列になり、SQL に展開時に型不一致を起こす可能性がある。
- **コメントで意図を残す**: 「単位は JPY」「100 にした理由」「上書き方法」を 1 行ずつ。半年後の自分のためのドキュメント。

## Step 3: `int_order_details_100knock.sql` を編集

`dbt/models/100-knock/topic-4/int_order_details_100knock.sql` の最終 SELECT に `where` 句を追加。例えば既存が以下のようになっていたとする:

```sql
{{ config(materialized='view', schema='intermediate') }}

with orders as (
    select * from {{ ref('stg_orders_100knock') }}
),
products as (
    select * from {{ ref('stg_products_100knock') }}
)
select
    o.order_id,
    o.customer_id,
    o.product_id,
    o.quantity,
    p.unit_price,
    o.quantity * p.unit_price as sales_amount,
    o.order_date
from orders o
inner join products p using (product_id)
```

これを以下に書き換える:

```sql
{{ config(materialized='view', schema='intermediate') }}

with orders as (
    select * from {{ ref('stg_orders_100knock') }}
),
products as (
    select * from {{ ref('stg_products_100knock') }}
),
joined as (
    select
        o.order_id,
        o.customer_id,
        o.product_id,
        o.quantity,
        p.unit_price,
        o.quantity * p.unit_price as sales_amount,
        o.order_date
    from orders o
    inner join products p using (product_id)
)
-- 100-knock Topic ⑧ 8-6: 業務閾値を vars に外出し。
-- 既定 100 円。dbt run --vars '{min_order_amount: 0}' で全件流せる。
select *
from joined
where sales_amount >= {{ var('min_order_amount', 0) }}
```

ポイント:

- **CTE で集計 → 最終 SELECT で `where`** の構造にする。CTE 内に `where` を書くと、その後の集計に絞り込みが効くタイミングが変わるので注意。
- **`var('min_order_amount', 0)` の第 2 引数 `0`**: `dbt_project.yml` から `vars:` を削除しても動くようにする防御。`var('min_order_amount')` だけだと未定義時に compile エラーで run が落ちる。
- コメントで「var 化した経緯」「上書き例」を残す。

## Step 4: 3 通りの run で行数比較

```bash
set -a; source .env; set +a
cd dbt

# (a) 既定 = 100
../.venv/bin/dbt run --select int_order_details_100knock --profiles-dir .
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
  -c "select count(*) from intermediate.int_order_details_100knock;"
# 例: 7842

# (b) CLI 上書き = 0 (= 全件)
../.venv/bin/dbt run --select int_order_details_100knock \
  --vars '{min_order_amount: 0}' --profiles-dir .
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
  -c "select count(*) from intermediate.int_order_details_100knock;"
# 例: 10000

# (c) CLI 上書き = 1000 (= 大口注文だけ)
../.venv/bin/dbt run --select int_order_details_100knock \
  --vars '{min_order_amount: 1000}' --profiles-dir .
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
  -c "select count(*) from intermediate.int_order_details_100knock;"
# 例: 1245
```

(a) 7842 < (b) 10000 / (c) 1245 < (a) 7842 が観測できれば var が効いている。

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-6-vars-overridable.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | vars-block-in-project-yml         | 20/20 |
| OK | var-call-in-int-model             | 20/20 |
| OK | dbt-run-default-success           | 15/15 |
| OK | dbt-run-vars-override-zero        | 25/25 |
| OK | filter-applied-when-default       | 20/20 |
```

(`vars-override-zero` は `--vars '{min_order_amount: 0}'` で run した直後の行数が、デフォルト run より厳密に多いことを sql_assert で確認するチェック。)

## ポイント

- **なぜ var 化が「再利用」なのか**: 同じ SQL コードを「閾値 100 (本番)」「閾値 0 (CI 全件テスト)」「閾値 1000 (経営報告)」 と **複数の文脈で再利用** できるから。コードを 3 つ書く代わりに、コード 1 + パラメータ 3。**1 SQL → N 利用シナリオ** の依存設計。
- **dbt の宣言ファースト思想との整合**: model SQL は「ロジックの宣言」、`vars:` は「値の宣言」。両者を分離することで **「ロジックは安定、値は揺らぐ」** という現実の構造を素直に表現できる。
- **`var()` vs `{{ config(...) }}` vs hard-code の使い分け**:
  - **値が変わらない (絶対不変)** → SQL 内 hard-code (例: `1.0` の係数)
  - **値が環境/run で変わる** → `var()` (例: 業務しきい値・税率)
  - **物理化戦略が変わる** → `config(materialized=var('mat', 'view'))` のように両者の組み合わせ
- **CLI `--vars` と `vars:` の優先順位**: CLI > project yml。これにより「project の既定を信じつつ、必要時のみ run で上書き」 ができる。env_var との組み合わせで CI の Secret を流し込むパターンも頻出。
- **マジックナンバーの嗅覚**: SQL に `>= 100`, `<= 30`, `* 0.10` のような数値リテラルを見たら、まず「これは将来変わる値か?」 を自問する。Yes なら var 候補。No なら定数 macro (`{% macro tax_rate() %}0.10{% endmacro %}`) で意味を持たせる手もある。

## 実行例 (採点 shell_command 視点)

```bash
$ grep -E '^vars:' dbt/dbt_project.yml
vars:

$ grep -A3 '^vars:' dbt/dbt_project.yml | grep min_order_amount
  min_order_amount: 100

$ grep -E "var\\(['\"]min_order_amount['\"]" dbt/models/100-knock/topic-4/int_order_details_100knock.sql
where sales_amount >= {{ var('min_order_amount', 0) }}

$ cd dbt && ../.venv/bin/dbt run --select int_order_details_100knock \
    --vars '{min_order_amount: 0}' --profiles-dir . 2>&1 | tail -3
... Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
    -c "select count(*) from intermediate.int_order_details_100knock;"
10000   # = 全件 (var=0 で where が無効化)
```

## 解説まとめ

- **var の本質は「コード/値の分離」**: model SQL = 「どう計算するか」 / `vars:` = 「何の値で計算するか」。両者を 1 ファイルに混ぜると、**値の変更でコードレビューが必要** になり機動力が落ちる。分離すれば「値だけ変えて re-run」 の運用が可能。
- **var は「将来の自分への約束」**: SQL に `>= 100` と書いた時点で「この 100 は将来変わるかも」という暗黙の前提が漏れている。`var('min_order_amount', 100)` と書けば「これはパラメータ、変えていい」 と明示できる。Topic ⑤ の `+grants:` (権限の宣言) と同じ思想 — **暗黙を明示に**。
- **dispatch macro (8-7) との関係**: var は「同じ adapter で値だけ変える」、dispatch は「同じ interface で adapter ごと実装を変える」。両方とも **「1 つのコード、N 通りの動作」** という再利用パターンの 2 種。Topic ⑧ で並べて学ぶ意義は、**柔軟性の軸が複数ある** ことを体感すること。
- **`dbt_project.yml` の `vars:` を消したら**: `var('foo', default)` の default が効くので model run は落ちない。default なしの場合は compile error。**default の有無 = 防御性の宣言** とも言える。チームでルール化するとよい。
- **マイクロ設計判断**: 「var の値を `dbt_project.yml` に書くか / `profiles.yml` に書くか / env_var にするか」 は、その値の性質次第。チーム共通 → `dbt_project.yml`。ユーザ別 → `profiles.yml`。Secret → env_var (`var('min_order_amount', env_var('DBT_MIN_ORDER', '100')|int)`)。

## 拡張アイデア

- **複数 var を組み合わせる**: `min_order_amount` と `max_order_amount` を両方宣言し、`between` で絞る。範囲指定 → A/B test 的な切り出しが可能。
- **`vars:` を package スコープに**: `vars: {local_analytics: {min_order_amount: 100}, dbt_utils: {dispatch_list: ['my_module']}}` のように **package 単位で名前空間を切る** と、外部 package と var 名衝突を防げる。
- **`var()` を `--vars` 経由でテスト**: `dbt test --vars '{min_order_amount: 9999999}'` で「全件落ちる状況をシミュレート」 して test を確認する。CI の retrospective 用。
- **`dbt_project.yml` の `vars:` を `target` で分岐**: `vars:` には target 別分岐は書けないが、profile 単位で project を分けることで実現できる。または `var('min_order_amount', target.name == 'prod' ? 1000 : 0)` のような Jinja 式で分岐 (ただし可読性は落ちる)。
- **8-9 の metric_revenue macro 内で `var()` を呼ぶ**: 集計式の中で「税抜きにする / 税込にする」を `var('include_tax', false)` で切替えると、KPI 定義の柔軟性が上がる (ただし KPI の意味が変わるので慎重に)。
