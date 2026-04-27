# Exercise 08: 自作 generic test を作る

## シナリオ

MVP の `dbt/tests/` にある singular test 4 本（`assert_*.sql`）は便利だが、再利用が効かない。「`quantity` が正数」「`unit_price` が正数」「`avg_rating` が正数」のような **同じ条件を別の列で何度も検査したい** ケースで、毎回 `WHERE col < 0` の SQL を別ファイルにコピペするのは DRY 違反。

dbt の **generic test**（`dbt/tests/generic/` 配下に置く `{% test %}` ブロック）を使うと、`tests: [positive_value]` と YAML 1 行書くだけで、同じ判定ロジックを任意の列に適用できる。built-in の `not_null` / `unique` と同じ仕組みを自分で増やす。

## 学べること

- generic test と singular test の違い
- `{% test name(model, column_name) %}` ブロックの書き方
- generic test を `schema.yml` から `tests: [positive_value]` で適用
- 引数付き generic test (`{% test ... (model, column_name, threshold=0) %}`)
- `{{ ref(...) }}` ではなく `{{ model }}` / `{{ column_name }}` を使う

## 前提

- main HEAD 完了状態
- 他 Exercise との依存なし

## 入力データ

不要。既存の `staging.stg_orders` / `staging.stg_products` 等を使う。

## 課題

### Step 1: generic test ファイル

`dbt/tests/generic/test_positive_value.sql` を新規作成。

要件:

- `{% test positive_value(model, column_name) %}` ブロック
- 「`column_name` が NULL でなく、かつ `column_name <= 0` の行を返す」 SELECT を書く
- dbt は「行が 1 件でも返れば test FAIL」のルールに従って評価する

> **MVP への影響**: `dbt/tests/generic/` ディレクトリは MVP には存在しない。新規追加でディレクトリごと生やす形になる。`dbt/tests/` 配下なので dbt は自動で拾う。MVP 既存の singular test 4 本には影響しない。

### Step 2: 既存モデルに適用 (新 schema.yml)

MVP の `dbt/models/staging/schema.yml` は触らず、`dbt/models/exercises/08/schema.yml` を新規作成。`source` ではなく **既存 model に対する追加メタデータ** として書く:

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

> **注**: dbt は `models:` セクションで同じ model 名が複数の schema.yml に書かれた場合、両方をマージする (1.6+)。同じ test が重複定義されるとエラーになるので、MVP の `staging/schema.yml` で `quantity` / `unit_price` に既に test が付いていないか確認する（MVP では `not_null` のみ。`positive_value` は重複しない想定）。

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_orders stg_products
```

3 つの `positive_value` test が PASS で増えていれば成功。

### Step 4: わざと壊して FAIL させる

`raw.orders` の 1 行を負数にして、test が FAIL することを確認:

```sql
UPDATE raw.orders SET quantity = -1 WHERE order_id = 1;
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_orders
```

`positive_value` test が FAIL し、`Failure in test positive_value_stg_orders_quantity` のように出る。元に戻す:

```sql
UPDATE raw.orders SET quantity = 1 WHERE order_id = 1;
```

### Step 5 (任意): 引数付き generic test

`dbt/tests/generic/test_in_range.sql`:

```sql
{% test in_range(model, column_name, min_value, max_value) %}
    select *
    from {{ model }}
    where {{ column_name }} < {{ min_value }}
       or {{ column_name }} > {{ max_value }}
{% endtest %}
```

`schema.yml` で:

```yaml
- name: rating_avg_test_target
  columns:
    - name: avg_rating
      tests:
        - in_range:
            min_value: 1
            max_value: 5
```

引数 `min_value` / `max_value` を YAML から渡す。

## 完了条件

- [ ] `dbt/tests/generic/test_positive_value.sql` が存在し、`{% test positive_value(...) %}` 構文
- [ ] `dbt test --select stg_orders stg_products` が成功し、`positive_value` test が 3 件以上含まれる
- [ ] わざと負数を入れた状態で `dbt test` を回すと FAIL する
- [ ] (任意) 引数付き generic test も同じ要領で動く

## ヒント（詰まったら）

- **`{% test %}` の引数の必須項目**: `model` と `column_name` は固定（dbt がメタとして渡す）。それ以降の引数は YAML から `tests: [my_test: {arg1: ..., arg2: ...}]` で渡せる。
- **`{{ model }}` の中身**: dbt が「テスト対象テーブルへの relation」を自動で挿入する Jinja 変数。`{{ ref('stg_orders') }}` を書く必要はない（むしろ書くと壊れる）。
- **generic test と singular test の使い分け**:
  - 同じロジックを **複数列 / 複数モデル** で使う → generic
  - 1 つのテーブル限定の特殊な不変条件（`UNION ALL` で 3 mart 串刺し集計など）→ singular
- **デフォルト引数**: `{% test positive_value(model, column_name, allow_zero=False) %}` のように Python 風デフォルト引数も書ける。`schema.yml` で省略すると `False` が使われる。
- **`tests:` キーが deprecated** (dbt 1.8+): 新しい構文は `data_tests:`。本リポジトリの dbt-core 1.11 では `tests:` も `data_tests:` も両方動くが、新規プロジェクトでは `data_tests:` 推奨。
- **`positive_value_stg_orders_quantity` のような長い test 名**: dbt が自動生成する。`name:` で `tests:` 内に明示すれば任意名にできる:
  ```yaml
  - positive_value:
      name: stg_orders_quantity_must_be_positive
  ```
- **NULL の扱い**: 上記の素直な実装は `column_name <= 0` だけ見ているので NULL は検知しない。NULL も拒否したい場合は `not_null` を別途追加するか、`coalesce(col, -1) <= 0` のような工夫を入れる。

## 解答例

詳細は [`solutions/08-custom-generic-test.solution.md`](solutions/08-custom-generic-test.solution.md) を参照。
