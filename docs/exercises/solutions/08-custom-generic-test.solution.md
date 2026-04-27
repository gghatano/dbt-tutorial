# Exercise 08 解答例

## Step 1: `dbt/tests/generic/test_positive_value.sql`

```sql
{#-
    Generic test: column value must be > 0 (and not NULL).

    Usage in schema.yml:
        columns:
          - name: quantity
            tests:
              - positive_value

    Returns rows where the value violates the rule. dbt fails the test
    if any row is returned.
-#}
{% test positive_value(model, column_name) %}

    select *
    from {{ model }}
    where {{ column_name }} is null
       or {{ column_name }} <= 0

{% endtest %}
```

**ポイント**:

- `{% test name(model, column_name) %}` の `name` 部分が `tests: [positive_value]` で参照される識別子になる。
- `{{ model }}` は dbt が自動で適切な relation（テスト対象 model の `ref()` 解決済みオブジェクト）を埋めてくれる。
- `{{ column_name }}` も dbt が自動。`schema.yml` で `- name: quantity` と書いたから `column_name = "quantity"` が来る。
- ファイル名は **test 名と一致させなくてもよい**（dbt は `{% test %}` ブロックの宣言名で識別する）。慣例として揃えるとコードジャンプしやすい。

## Step 2: `dbt/models/exercises/08/schema.yml`

```yaml
version: 2

models:
  - name: stg_orders
    columns:
      - name: quantity
        tests:
          - positive_value
      - name: unit_price
        tests:
          - positive_value

  - name: stg_products
    columns:
      - name: unit_price
        tests:
          - positive_value
```

**ポイント**:

- 同じ model 名 (`stg_orders`) が `dbt/models/staging/schema.yml`（MVP）にも存在するが、dbt 1.6+ は **column-level metadata をマージ** する。MVP 側で `quantity` に `not_null` だけが付いていれば、ここで `positive_value` を追加する形になる。
- もし MVP 側で `quantity` に何かしらの test が付いており重複が懸念される場合は、別 model 名（例: `stg_orders_with_extra_tests`）として `models/exercises/08/` に新規 model を作って test を付ける、という方法もとれる。本演習では MVP に重複がない前提で進める。

## Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_orders stg_products
# 04:51:01  Running with dbt=1.11.8
# 04:51:01  Concurrency: 1 threads (target='dev')
# 04:51:02  Found 8 models, 4 sources, ... 64 data tests
# 04:51:03  1 of 64 START test not_null_stg_orders_order_id .................. [RUN]
# ...
# 04:51:05  62 of 64 START test positive_value_stg_orders_quantity ........... [RUN]
# 04:51:05  62 of 64 PASS positive_value_stg_orders_quantity ................. [PASS in 0.05s]
# 04:51:05  63 of 64 START test positive_value_stg_orders_unit_price ......... [RUN]
# 04:51:05  63 of 64 PASS positive_value_stg_orders_unit_price ............... [PASS in 0.04s]
# 04:51:05  64 of 64 START test positive_value_stg_products_unit_price ....... [RUN]
# 04:51:05  64 of 64 PASS positive_value_stg_products_unit_price ............. [PASS in 0.04s]
# Done. PASS=64 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=64
```

MVP 61 件 → 64 件に増えた。

## Step 4: わざと FAIL させる

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET quantity = -1 WHERE order_id = 1;
SQL

../.venv/bin/dbt test --profiles-dir . --select stg_orders
# ...
# 7 of 8 FAIL 1 positive_value_stg_orders_quantity ................. [FAIL 1 in 0.06s]
# Done. PASS=7 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8
# Failure in test positive_value_stg_orders_quantity (models/exercises/08/schema.yml)
#   Got 1 result, configured to fail if != 0
```

元に戻す:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -c \
    "UPDATE raw.orders SET quantity = 1 WHERE order_id = 1;"
../.venv/bin/dbt test --profiles-dir . --select stg_orders   # 全 PASS に戻る
```

## Step 5: 引数付き generic test

`dbt/tests/generic/test_in_range.sql`:

```sql
{#-
    Generic test: column value must be in [min_value, max_value] inclusive.

    Usage:
        columns:
          - name: rating
            tests:
              - in_range:
                  min_value: 1
                  max_value: 5
-#}
{% test in_range(model, column_name, min_value, max_value) %}

    select *
    from {{ model }}
    where {{ column_name }} is null
       or {{ column_name }} < {{ min_value }}
       or {{ column_name }} > {{ max_value }}

{% endtest %}
```

**Exercise 01 完了済みなら適用例**:

`dbt/models/exercises/08/schema.yml` に追記:

```yaml
  - name: stg_reviews   # Exercise 01 で作っている前提
    columns:
      - name: rating
        tests:
          - in_range:
              min_value: 1
              max_value: 5
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# ... in_range_stg_reviews_rating_1_5 ... PASS
```

test 名は dbt が引数値を含めて自動生成する（`in_range_stg_reviews_rating_1_5`）。

## 解説まとめ

- **generic test = テスト macro**。`dbt/tests/generic/*.sql` または `dbt/macros/*.sql`（後方互換）に置けば、dbt が自動で拾う。
- **built-in との関係**: `not_null` / `unique` / `relationships` / `accepted_values` も同じ `{% test %}` ブロック実装。`dbt_packages/dbt-core/include/global_project/tests/generic/builtin.sql` に元実装がある。覗いてみると勉強になる。
- **dbt-utils も generic test を提供**: `dbt_utils.expression_is_true` / `dbt_utils.recency` / `dbt_utils.cardinality_equality` など。Exercise 07 でパッケージを入れたなら、自作する前にまず探す価値あり。
- **dbt-expectations はさらに豊富**: Great Expectations 風の test を 50+ 提供（`expect_column_values_to_be_between` 等）。Exercise 10 で扱う。

## 拡張アイデア

- generic test を `severity: warn` に設定し、FAIL させずに警告だけ出す（CI で「FAIL は止める、WARN は通す」運用）。`schema.yml` 側に `tests: [positive_value: {config: {severity: warn}}]` で指定。
- `where` 引数を取って「特定行のみ検査」に絞れるよう拡張（`{% test positive_value(model, column_name, where=None) %}`）。
- 自作 generic test を packages 化して別リポジトリで再利用 → `dbt-tutorial-utils` のようなパッケージを切り出す。
