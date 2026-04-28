# 4-6: int_order_with_tax_100knock を作り、税計算 macro `calc_tax(amount, rate)` を呼ぶ

## シナリオ

4-1 で作った `int_order_details_100knock` には「税抜」の `sales_amount` しか無い。
業務部門から「税込金額も欲しい、税率は当面 10% だが将来変わる」 と要望が来た時、
**税率を SQL の中にハードコードすると後で税率変更時に「全 mart を grep して書き換える」 羽目になる**。

dbt の正解は **macro に集約** すること。`calc_tax(amount, rate)` という jinja macro を
`dbt/macros/100-knock/topic-4/calc_tax.sql` に 1 つ書き、`int_order_with_tax_100knock` から
1 箇所だけ呼ぶ。将来税率が変わる、もしくは「商品カテゴリ別に税率を変える (軽減税率)」 となっても
**macro 1 ファイルを直すだけ** で全 int / mart に波及する。これが
「**開発の依存** (= 同じ計算ロジックを使う複数 model 群を、1 つの macro に閉じ込める)」
の核心。

## 学べること

- `{% macro %}` の最小形 (引数 2 つ、1 式の return 相当)
- `dbt/macros/100-knock/topic-4/` のディレクトリ命名と自動読み込み
- macro を SQL 内で `{{ calc_tax(amount, rate) }}` と展開する作法
- 「計算ロジックを 1 箇所に閉じ込める」設計が将来の変更コストをどう減らすか
- compiled SQL (`target/compiled/.../int_order_with_tax_100knock.sql`) で
  macro が SQL に展開されている様子を目で見る

## 前提

- Topic ② ③ 完了 + Topic ④ 4-1 完了 (`int_order_details_100knock` が存在)
- `dbt parse` が通る
- 学習者の int model は `dbt/models/100-knock/topic-4/` 配下

## 入力データ

不要。学習者が macro 1 本 + model 1 本を新規作成するだけ。

## 課題

### Step 1: macro を作る

`dbt/macros/100-knock/topic-4/calc_tax.sql` を新規作成:

```jinja
{% macro calc_tax(amount, rate) %}
    ({{ amount }} * (1 + {{ rate }}))::numeric(14, 2)
{% endmacro %}
```

要件:

- 引数は `amount` (列名 or 式) と `rate` (税率の小数。例 `0.10`)
- 出力は「税込金額」 = `amount * (1 + rate)`
- 桁落ちを防ぐため `numeric(14, 2)` cast を含める
- macro はファイル名と同じ名前 (`calc_tax`) で宣言。dbt が `macros/` 配下を再帰的に走査するので、`100-knock/topic-4/` のサブディレクトリでも自動で読み込まれる

### Step 2: model を作る

`dbt/models/100-knock/topic-4/int_order_with_tax_100knock.sql` を新規作成:

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (int_order_details_100knock を継承)。
-- 税込金額 sales_amount_with_tax を calc_tax macro 経由で算出。
-- 税率は 10% を前提 (将来軽減税率対応するなら macro 側 + var を拡張)。
select
    order_id,
    order_date,
    customer_id,
    product_id,
    quantity,
    unit_price,
    sales_amount,
    {{ calc_tax('sales_amount', 0.10) }} as sales_amount_with_tax
from {{ ref('int_order_details_100knock') }}
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select int_order_with_tax_100knock
```

`PASS=1` (run) になれば成功。compiled SQL を見て macro が展開されていることを確認:

```bash
cat target/compiled/local_analytics/models/100-knock/topic-4/int_order_with_tax_100knock.sql
```

`{{ calc_tax(...) }}` の箇所が `(sales_amount * (1 + 0.10))::numeric(14, 2)` に展開されていれば OK。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-4-intermediate/4-6-int-order-with-tax-macro.grading.yaml
```

## 完了条件

- [ ] `dbt/macros/100-knock/topic-4/calc_tax.sql` が存在する
- [ ] `dbt/models/100-knock/topic-4/int_order_with_tax_100knock.sql` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.int_order_with_tax_100knock` が登録される
- [ ] `dbt run --select int_order_with_tax_100knock` が PASS
- [ ] DB 上で `sales_amount_with_tax = round(sales_amount * 1.10, 2)` が全行で成立する

## ヒント (詰まったら)

- **macro が見つからない**: dbt は `macro-paths: ["macros"]` を再帰的に走査するので、`macros/100-knock/topic-4/` のサブディレクトリでも自動で読み込まれる。`dbt parse` 後に `dbt ls --resource-type macro --select calc_tax` で確認可能。
- **macro 内で引数を quote しすぎる**: `'{{ amount }}' * ...` のようにシングルクォートで括ると **文字列リテラル** として SQL に出てしまい型エラー。引数は jinja の `{{ }}` 展開だけで十分。
- **桁落ち / 浮動小数点誤差**: `1.10` は jinja 上では float。SQL に展開された後の演算は Postgres の数値型ルールに従うが、最終結果を `numeric(14, 2)` cast しておけば下流 mart は安心して GROUP BY SUM できる。
- **税率を変えたくなったら**: 本問では `0.10` をハードコードしているが、実務では `dbt_project.yml` の `vars: tax_rate: 0.10` を `var('tax_rate')` で読む形が一般的 (Topic ⑧ で再登場)。

## 解答例

詳細は [`4-6-int-order-with-tax-macro.solution.md`](4-6-int-order-with-tax-macro.solution.md) を参照。
