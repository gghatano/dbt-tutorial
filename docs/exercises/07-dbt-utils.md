# Exercise 07: dbt-utils を導入してマートを DRY にする

## シナリオ

`mart_daily_sales` には注文があった日しか行が存在しない。営業日カレンダー上「売上 0 円の日」は欠落している。BI 側で時系列グラフを描くと、欠損日が「点が無い」状態でプロットされ、ぱっと見で「データロストか？」と疑われる。

これを直すには「全営業日 × 売上」の左外結合マートが欲しい。日次カレンダーを SQL で書くのは地味に面倒（再帰 CTE / `generate_series` / window 関数の組み合わせ）。dbt の準公式パッケージ **`dbt-utils`** に `date_spine` macro があり、1 行で日次カレンダーが生成できる。

このエクササイズで packages の入れ方と `dbt-utils` の主要 macro 3 つ（`date_spine` / `surrogate_key` / `pivot`）を体験する。

## 学べること

- `packages.yml` の宣言と `dbt deps` の実行
- `dbt-utils.date_spine` で日次カレンダーを生成
- `dbt-utils.generate_surrogate_key` で複合キーから surrogate key を作る
- `dbt-utils.pivot` で行を列に展開する
- `dbt_packages/` ディレクトリは `.gitignore` 済み

## 前提

- main HEAD 完了状態
- 他 Exercise との依存なし
- インターネット接続（`dbt deps` で hub.getdbt.com から取得）

## 入力データ

不要。既存の `mart_daily_sales` / `mart_product_sales` を使う。

## 課題

### Step 1: `packages.yml` に dbt-utils を追加

`dbt/packages.yml` に追記:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
```

> **注意**: 本リポジトリの `dbt/packages.yml` は MVP 共通設定。学習者は **このファイルを直接書き換えるとほかの Exercise に影響する** ので、自分用ブランチを切るか、`dbt/packages.exercise07.yml` のような別ファイルを作って `dbt deps --packages-yaml-file` で読み込むなどの工夫をする。本演習では「自分用環境で `dbt/packages.yml` を直接編集する」前提で進める。

### Step 2: パッケージのインストール

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

`dbt_packages/dbt_utils/` ができることを確認。

### Step 3: 日次カレンダー intermediate

`dbt/models/exercises/07/int_calendar.sql`:

```sql
{{ config(materialized='view', schema='intermediate') }}

with bounds as (
    select
        (select min(order_date) from {{ ref('mart_daily_sales') }})       as start_date,
        (select max(order_date) + interval '1 day' from {{ ref('mart_daily_sales') }}) as end_date
),
spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="(select start_date from bounds)",
        end_date="(select end_date from bounds)"
    ) }}
)

select date_day::date as calendar_date
from spine
```

注意: `date_spine` の `start_date` / `end_date` は **生 SQL 式** を文字列で渡す。リテラルの `'2026-01-01'` 形式でも、サブクエリ形式でも、両方使える。

### Step 4: マート `mart_calendar_sales`

`dbt/models/exercises/07/mart_calendar_sales.sql`:

```sql
{{ config(materialized='table', schema='marts') }}

select
    cal.calendar_date,
    coalesce(sales.total_sales_amount, 0)::numeric(14, 2) as total_sales_amount,
    coalesce(sales.order_count, 0)                        as order_count,
    coalesce(sales.customer_count, 0)                     as customer_count
from {{ ref('int_calendar') }} cal
left join {{ ref('mart_daily_sales') }} sales
    on sales.order_date = cal.calendar_date
order by cal.calendar_date
```

### Step 5: テスト

`dbt/models/exercises/07/schema.yml`:

```yaml
version: 2
models:
  - name: int_calendar
    columns:
      - name: calendar_date
        tests: [not_null, unique]
  - name: mart_calendar_sales
    columns:
      - name: calendar_date
        tests: [not_null, unique]
      - name: total_sales_amount
        tests: [not_null]
```

### Step 6: 実行

```bash
../.venv/bin/dbt run --profiles-dir . --select int_calendar mart_calendar_sales
../.venv/bin/dbt test --profiles-dir . --select int_calendar mart_calendar_sales
```

### Step 7: 欠損日が 0 で埋まっていることを確認

```sql
SELECT calendar_date, total_sales_amount
FROM marts.mart_calendar_sales
WHERE total_sales_amount = 0
ORDER BY calendar_date
LIMIT 10;
```

`mart_daily_sales` には無かった日（あれば）が 0 として現れる。完全網羅日付なので `count(*)` は連続日数と一致する。

## 完了条件

- [ ] `dbt deps` 後、`dbt/dbt_packages/dbt_utils/` が存在する
- [ ] `dbt run --select int_calendar mart_calendar_sales` が成功
- [ ] `dbt test --select int_calendar mart_calendar_sales` が成功
- [ ] `marts.mart_calendar_sales` の行数 = `(max - min) date diff + 1`（欠損日があれば、行数が `mart_daily_sales` より多くなる）

## ヒント（詰まったら）

- **`dbt_utils.date_spine` の引数**: `datepart` は `day` / `week` / `month` / `year` など。`start_date` / `end_date` は **SQL 式の文字列**。`"'2026-01-01'"`（クオート二重）か、サブクエリで動的取得。
- **end_date は inclusive ではない**: `date_spine` は `[start_date, end_date)` の半開区間。`end_date = max + 1 day` として渡すと max 日まで含まれる。
- **`generate_surrogate_key` の使い所**: 複合キー（`order_date` + `customer_id` のような）を 1 列のハッシュにまとめたい時。本 Exercise では使わないが、`mart_top_rated_products` のような複合 PK を持つマートで便利。
- **`dbt_utils.pivot` の使い所**: 行→列展開。「カテゴリ別売上を 1 行ずつではなく、`food` / `electronics` / `clothing` 列で並べたい」場合など。本 Exercise では使わないが、Step 8（任意）として `mart_product_sales` を category で pivot してみると面白い。
- **ローカルで `dbt_packages/` がコミット対象になる**: `.gitignore` 済み（`dbt/dbt_packages/`）。学習者の手元には残るが、リポジトリには上がらない。
- **packages.yml を MVP 環境に書き戻したい**: 本演習は学習目的で `dbt/packages.yml` を直接編集する前提だが、もし他 Exercise（特に Exercise 10）にも影響を与えたい場合は、そのまま残しておけばよい。

## 解答例

詳細は [`solutions/07-dbt-utils.solution.md`](solutions/07-dbt-utils.solution.md) を参照。
