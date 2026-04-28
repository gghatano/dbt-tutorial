# 8-1: cast_money macro を桁数引数化、5 model から呼び出す

## シナリオ

Topic ③ で `unit_price::numeric(10, 2)`、Topic ④ の `int_order_details_100knock`
で `(quantity * unit_price)::numeric(14, 2)`、Topic ⑤ で
`sum(sales_amount)::numeric(14, 2)` …のように、**金額系の cast が staging /
intermediate / mart に散在** している。「精度を 12 桁に統一したい」「(税込総額用に)
桁数を 16 に上げたい」 と言われた瞬間に **全 model を grep して書き換える** ことになり、
書き漏れ 1 箇所で SUM 結果が overflow する事故が起きる。

正解は `cast_money(col, precision, scale)` macro に集約。SQL 内では
`{{ cast_money('unit_price', 12, 2) }}` と書くだけで、将来桁数を変えても
**macro 1 ファイルを直すだけ** で全 model に波及する。これが Topic ④ 4-6 の
`calc_tax` 同様、「**派生計算ロジックを 1 箇所に閉じ込める**」 macro 設計の核心。

8-1 では、引数にデフォルト値を持つ汎用 macro `cast_money(col, precision=14, scale=2)`
を書き、5 つの 100-knock model (staging / intermediate / mart) から呼び出して
DRY 化する。

## 学べること

- macro のキーワード引数とデフォルト値 (`precision=14, scale=2`)
- macro 呼び出しを **複数 model にまたがって展開** する作法
- compiled SQL (`target/compiled/.../<model>.sql`) で macro 展開を目視確認
- 「汎用 macro は引数で切り替え可能、デフォルトは安全な値」 設計
- なぜ 4-6 の `calc_tax` よりも引数化の重要性が高いのか (使用箇所が 5 つに増えるため)

## 前提

- Topic ② 〜 ⑦ 完了 (`stg_orders_100knock` / `int_order_details_100knock` /
  `mart_*_100knock` 系が物理化済み)
- Topic ④ 4-6 の `calc_tax` macro パターンは既知
- 学習者の macro は `dbt/macros/100-knock/topic-8/cast_money.sql`

## 入力データ

不要。既存 model 5 本を **書き換える** だけ。新しい model は作らない。

## 課題

### Step 1: macro を作る

`dbt/macros/100-knock/topic-8/cast_money.sql` を新規作成:

```jinja
{% macro cast_money(col, precision=14, scale=2) %}
    {{ col }}::numeric({{ precision }}, {{ scale }})
{% endmacro %}
```

要件:

- 引数 3 つ (`col`, `precision`, `scale`)、`precision` / `scale` にはデフォルト値
- `col` は SQL 列名 / 式 (例: `'unit_price'`, `'sum(sales_amount)'`)
- 出力は `<col>::numeric(<precision>, <scale>)`
- マクロ名 = ファイル名 (`cast_money`) で宣言

### Step 2: 5 model を書き換え

下記 5 model の **金額系 cast を `{{ cast_money(...) }}` 呼び出しに置換** する。
精度・スケールは 4-6 までと同じ (`numeric(10, 2)` / `numeric(14, 2)`) を維持:

| # | model                                               | 書き換え対象列 / 式                          | 引数                          |
|---|-----------------------------------------------------|----------------------------------------------|-------------------------------|
| 1 | `dbt/models/100-knock/topic-3/stg_orders_100knock.sql`           | `unit_price::numeric(10, 2)`                 | `'unit_price', 10, 2`         |
| 2 | `dbt/models/100-knock/topic-3/stg_products_100knock.sql`         | `unit_price::numeric(10, 2)`                 | `'unit_price', 10, 2`         |
| 3 | `dbt/models/100-knock/topic-4/int_order_details_100knock.sql`    | `(quantity * unit_price)::numeric(14, 2)`    | `'quantity * unit_price'` (デフォルト 14, 2) |
| 4 | `dbt/models/100-knock/topic-5/mart_top_rated_products_100knock.sql` | `sum(...)::numeric(14, 2)` 系                | (該当列に `cast_money` を 1 箇所以上適用) |
| 5 | `dbt/models/100-knock/topic-5/mart_monthly_by_category_100knock.sql` | `sum(sales_amount)::numeric(14, 2)`          | (該当列に `cast_money` を 1 箇所以上適用) |

> **方針**: 「金額っぽい列の `::numeric(_, _)` cast は全部 `cast_money` 経由」 にする。
> int 同士の積も結果は数値で扱うので `cast_money` 適用対象。逆に `customer_id::bigint` のような
> ID cast は適用しない (金額ではない)。

### Step 3: parse + run

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run   --profiles-dir . --select stg_orders_100knock stg_products_100knock int_order_details_100knock mart_top_rated_products_100knock mart_monthly_by_category_100knock
```

`PASS=5` になれば成功。

### Step 4: compiled SQL 確認

macro が SQL に展開されているか目視:

```bash
cat target/compiled/local_analytics/models/100-knock/topic-3/stg_orders_100knock.sql | grep numeric
# => unit_price::numeric(10, 2)
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-8-reuse/8-1-cast-money-macro.grading.yaml
```

## 完了条件

- [ ] `dbt/macros/100-knock/topic-8/cast_money.sql` が存在し、`{% macro cast_money(col, precision=14, scale=2) %}` ブロックを含む
- [ ] 5 model の SQL ファイル中で `{{ cast_money(` を 5 回以上呼び出している
  (model 横断 grep で 5 件以上)
- [ ] `dbt parse` が成功
- [ ] `dbt run --select <5 models>` が PASS=5
- [ ] `staging.stg_orders_100knock.unit_price` の物理型が `numeric(10, 2)` を維持
- [ ] `intermediate.int_order_details_100knock.sales_amount` の物理型が `numeric(14, 2)` を維持

## ヒント (詰まったら)

- **macro が見つからない**: dbt は `macro-paths: ["macros"]` を再帰的に走査するので、
  `macros/100-knock/topic-8/` のサブディレクトリでも自動で読み込まれる。
  `dbt parse` 後に `dbt ls --resource-type macro --select cast_money` で確認可能。
- **デフォルト引数の指定法**: `{% macro cast_money(col, precision=14, scale=2) %}` のように
  Python 風に書ける。呼び出し側は `{{ cast_money('unit_price') }}` (デフォルト) でも
  `{{ cast_money('unit_price', 10, 2) }}` (位置引数) でも `{{ cast_money('unit_price', precision=10, scale=2) }}` (キーワード引数) でも OK。
- **第 1 引数を SQL 式にする**: `{{ cast_money('quantity * unit_price') }}` のように
  「文字列として SQL 断片を渡す」 のが macro 流。`'sum(sales_amount)'` のような集約関数式も OK。
- **桁落ち / 浮動小数点誤差**: macro 出力が `numeric` cast を含むので、下流は
  Postgres の数値型ルール通り正確に扱える。`float` ではなく `numeric` が会計の鉄則。
- **MVP との衝突**: MVP の Ex.05 で同様の `cast_jpy` macro があるが、`cast_money` は
  別名なので衝突しない。Ex.05 を完了済みでも本問は独立に動く。

## 解答例

詳細は [`8-1-cast-money-macro.solution.md`](8-1-cast-money-macro.solution.md) を参照。
