# 8-9: 自作 macro `metric_revenue(model, date_col, amount_col)` で KPI 集計式を 1 箇所に閉じ込める

## シナリオ

`mart_daily_sales_100knock` / `mart_customer_sales_100knock` / `mart_product_sales_100knock` の 3 mart は、それぞれ「日付」「顧客」「商品」 という違う粒度の集計だが、**「revenue (売上) の出し方」 だけは共通** だったとする。例えば:

```sql
-- 仮の現状: 3 mart で同じ集計式が重複
sum(case when status = 'completed' then sales_amount else 0 end) as revenue
```

これを 3 mart で **べた書き** すると、後から「キャンセル分も含める」「税抜きにする」 のような **revenue 定義の変更** で 3 ファイルを同時編集することになる。漏れれば mart 間で集計値がズレ、BI / レポートに矛盾が出る (= **データ品質事故の典型例**)。

dbt の **macro による式の集約** はこれを根本解決する。`metric_revenue(model, date_col, amount_col)` のような macro を 1 つ書き、3 mart からは `{{ metric_revenue(...) }}` を呼ぶだけにする。式変更は macro 1 箇所、3 mart は次の `dbt build` で自動的に新定義になる。

これは Topic ⑧ の中で最も **「KPI 定義の単一情報源 (Single Source of Truth)」** を体感できる問。後の dbt の **Semantic Layer / MetricFlow** (dbt Cloud 1.6+) はこの考えを「YAML で metric を宣言、SQL は dbt が自動生成」 まで推し進めたものだが、その手前で macro による集約を体験することで、なぜ Semantic Layer が要るのかが腹落ちする。

## 学べること

- 集計式 (KPI 定義) を macro 1 つに閉じ込める依存設計
- `{{ return(...) }}` で macro が「式」を返す書き方
- `{{ ref(model_name) }}` を引数経由で動的参照
- 3 mart から同じ macro を呼び、式変更時に 3 mart 全部が更新される様子の確認
- 後の Semantic Layer の予感

## 前提

- Topic ② 〜 ⑤ + Topic ⑧ 8-1〜8-8 完了
- `dbt/models/100-knock/topic-5/` 配下に `mart_daily_sales_100knock` / `mart_customer_sales_100knock` / `mart_product_sales_100knock` が既に存在 — もし未作成 (5-1 の派生として作る前提) なら本問でまとめて 3 mart を作る
- 学習者の macro は `dbt/macros/100-knock/topic-8/`

## 入力データ

不要。既存 mart 3 本を `metric_revenue` 経由の集計に書き換えるだけ。

## 課題

### Step 1: macro `metric_revenue` を新規作成

`dbt/macros/100-knock/topic-8/metric_revenue.sql` を新規作成する。signature は `metric_revenue(model, date_col, amount_col)`。

中身は **「revenue を計算する SQL 片」 を返す macro**:

- 引数: `model` = ref で参照する model 名 (string), `date_col` = 日付列名 (string), `amount_col` = 金額列名 (string)
- 戻り値: `select date_col as period, sum(amount_col) as revenue from {{ ref(model) }} group by 1` のような SQL 片
- 実装には `{{ return(...) }}` を使う

詳細は解答例参照。

### Step 2: 3 mart で macro を呼ぶ

以下 3 mart のいずれかを `metric_revenue` 経由の実装に書き換える:

- `dbt/models/100-knock/topic-8/mart_daily_revenue_100knock.sql`: `{{ metric_revenue('int_order_details_100knock', 'order_date', 'sales_amount') }}`
- `dbt/models/100-knock/topic-8/mart_customer_revenue_100knock.sql`: `{{ metric_revenue('int_order_details_100knock', 'customer_id', 'sales_amount') }}`
- `dbt/models/100-knock/topic-8/mart_product_revenue_100knock.sql`: `{{ metric_revenue('int_order_details_100knock', 'product_id', 'sales_amount') }}`

3 mart は **同じ macro を別の grain で呼ぶ** だけで完成する。これが「**1 metric → N mart の収束**」 の図。

### Step 3: 式変更で 3 mart 同時更新の確認

macro 内の集計式を変更し、3 mart 全部に伝播することを観察する。例えば:

```sql
-- 変更前
sum({{ amount_col }}) as revenue

-- 変更後 (税込にする想定: 1.10 倍)
sum({{ amount_col }} * 1.10)::numeric(14,2) as revenue
```

```bash
cd dbt
../.venv/bin/dbt build --select 100-knock.topic-8 --profiles-dir .
```

3 mart の `revenue` 列が一斉に 10% 増加していれば、macro 1 箇所 → 3 mart 反映が動いた証跡。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-9-metric-revenue-macro.grading.yaml
```

## 完了条件

- [ ] `dbt/macros/100-knock/topic-8/metric_revenue.sql` が存在し、`metric_revenue(model, date_col, amount_col)` 形式の macro を定義
- [ ] macro 内で `{{ return(...) }}` を使って SQL 片 / クエリ全体を返している
- [ ] `dbt/models/100-knock/topic-8/` 配下の **少なくとも 3 mart** から `{{ metric_revenue(...) }}` を呼び出している
- [ ] `dbt build --select 100-knock.topic-8` が PASS
- [ ] 3 mart の `revenue` 列の合計値が、同じ source から算出した独立 SQL の合計と一致する (= macro による集計が壊れていない)

## ヒント (詰まったら)

- **`{{ return(...) }}` の役割**: macro が「文字列 / SQL 片を返す」 ことを明示。`{% macro foo() %}select 1{% endmacro %}` のような出力埋め込み形式でも動くが、return を使うと「macro の戻り値を変数に代入できる」 「他 macro から呼び出せる」 など合成性が上がる
- **`ref()` を引数経由で**: `{{ ref(model) }}` (= 引数 `model` に渡された string を ref) が core トリック。これで macro は「特定の table 名に縛られない」 汎用 metric になる
- **macro の戻り値が SQL 全体か一部か**: 設計判断。本問は「**SELECT 全体を返す**」 (= macro 1 行で mart が完成) を推奨。あるいは「**SELECT 句の式だけ返す**」 (= mart 側で from / group by を書く、もう少し柔軟) も可。後者は Semantic Layer 的な発想に近い
- **macro 呼び出し時の `{{ ... }}` vs `{% ... %}`**: SQL に展開するなら `{{ ... }}` (式). 制御 (do, set) なら `{% ... %}`
- **macro が長くなったら**: `metric_revenue` 1 つで責務が大きすぎたら `metric_revenue_select(amount_col)` (= SELECT 句だけ) と `metric_aggregation(model, group_col, metric_expr)` (= group by 部分) に分割するのも一手
- **dbt-utils との関係**: `dbt_utils.pivot` `dbt_utils.deduplicate` のような汎用 macro と、本問の `metric_revenue` のような **業務固有 macro** は、置き場所も意図も違う。本問は後者
- **Semantic Layer (dbt 1.6+) との関係**: `metrics:` YAML で metric を宣言 → dbt が必要な SQL を自動生成、というのが Semantic Layer の世界。本問の macro は **その手前で macro レベルで同じことをする** 試み。dbt 1.6+ プロジェクトでは Semantic Layer 移行も視野に入る
- **エラー: macro 戻り値が空**: `{% macro %}` 内で `{{ return(...) }}` を呼んでいないと、macro 呼び出しの結果は空文字。`return(...)` の引数に渡したものが戻る

## 解答例

詳細は [`8-9-metric-revenue-macro.solution.md`](8-9-metric-revenue-macro.solution.md) を参照。
