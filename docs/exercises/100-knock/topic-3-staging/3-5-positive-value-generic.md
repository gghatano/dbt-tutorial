# 3-5: 自作 generic test `positive_value` を stg_orders に適用

## シナリオ

3-4 までで built-in test (`not_null` / `unique` / `relationships`) を staging 全体に
張り終えた。しかし「`quantity` は正の整数」「`unit_price` は 0 より大きい金額」 のような
**業務的な不変条件** は built-in には無い。MVP の `dbt/tests/` には singular test
(`assert_*.sql`) があるが、同じ「正数チェック」を `quantity` と `unit_price` の 2 列で
書くと SQL ファイルが 2 個になる (DRY 違反)。

dbt の **generic test** (`{% test name(model, column_name) %}` ブロック) を 1 本書けば、
`tests: [positive_value]` と YAML 1 行書くだけで、同じロジックを任意の列に適用できる。
**built-in の `not_null` / `unique` と同じ仕組みを自分で増やす** のが今回のゴール。

## 学べること

- generic test の基本構文 `{% test name(model, column_name) %}`
- 「行が返れば FAIL」 という dbt test の評価ルール
- generic test を `schema.yml` から `tests: [positive_value]` で適用する宣言的な使い方
- なぜ generic test が singular test より良いのか (再利用性 / 自動命名 / マージ可能)
- `{{ model }}` / `{{ column_name }}` の 2 つの自動引数

## 前提

- 3-1〜3-4 完了: `stg_orders_100knock` が物理化され、PK / FK 制約が PASS している状態
- Ex.08 の `dbt/tests/generic/test_positive_value.sql` を **既に書いている** か
  **新規に書いてもよい** (MVP には存在しない)

## 入力データ

`staging.stg_orders_100knock` (10,000 行) — 3-3 で物理化済み。
`quantity` (1..10) / `unit_price` (100〜9990) はどちらも正数のはず。

## 課題

### Step 1: generic test を作る

`dbt/tests/generic/test_positive_value.sql` を新規作成 (Ex.08 解答からコピペ可)。

要件:

- `{% test positive_value(model, column_name) %}` ブロック
- 「`column_name` が NULL または `<= 0` の行を返す」 SELECT
- dbt は「行が 1 件でも返れば test FAIL」のルールに従って評価する

```sql
{% test positive_value(model, column_name) %}

    select *
    from {{ model }}
    where {{ column_name }} is null
       or {{ column_name }} <= 0

{% endtest %}
```

> **MVP への影響**: `dbt/tests/generic/` ディレクトリは MVP には存在しない。
> 新規追加でディレクトリごと生やす。`dbt/tests/` 配下なので dbt が自動で拾う。
> Ex.08 を先にやっていれば、このファイルは既にあるので **新規作成は不要**。

### Step 2: schema.yml に適用

`dbt/models/100-knock/topic-3/schema.yml` の `stg_orders_100knock` ブロックの
`quantity` / `unit_price` に generic test を追加:

```yaml
  - name: stg_orders_100knock
    columns:
      - name: quantity
        tests:
          - not_null
          - positive_value         # ← 追加
      - name: unit_price
        tests:
          - not_null
          - positive_value         # ← 追加
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_orders_100knock
```

`positive_value_stg_orders_100knock_quantity` と
`positive_value_stg_orders_100knock_unit_price` の **2 件が PASS** に増えていれば成功。

### Step 4: わざと FAIL させる

```sql
UPDATE raw.orders SET quantity = -1 WHERE order_id = 1;
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
# => positive_value_stg_orders_100knock_quantity が FAIL (Got 1 result, configured to fail if != 0)
```

戻す:

```sql
UPDATE raw.orders SET quantity = 1 WHERE order_id = 1;
```

## 完了条件

- [ ] `dbt/tests/generic/test_positive_value.sql` が存在する (`{% test positive_value(...) %}` 構文)
- [ ] `schema.yml` で `stg_orders_100knock.quantity` / `unit_price` の両方に
      `positive_value` が適用されている
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select stg_orders_100knock` が PASS で、`positive_value` test が
      2 件以上含まれる

## ヒント (詰まったら)

- **`{% test %}` の必須引数**: `model` と `column_name` は固定で dbt が自動で渡す。
  追加引数 (`threshold` / `where` など) は YAML から `tests: [my_test: {arg1: ...}]` で渡せる。
- **`{{ model }}` の中身**: dbt が「テスト対象 model への relation」 を自動挿入する
  Jinja 変数。`{{ ref('stg_orders_100knock') }}` を書く必要は **ない** (むしろ書くと壊れる)。
- **`positive_value` test 名は自動生成**: dbt は
  `positive_value_stg_orders_100knock_quantity` のように
  `<test_name>_<model_name>_<column_name>` の規則で命名する。`name:` を明示すれば
  上書き可能。
- **NULL の扱い**: 上の素直な実装は `column_name is null or column_name <= 0` で
  NULL も拒否している。NULL を許したいなら `{{ column_name }} <= 0` だけでよい。
- **generic vs singular の使い分け**:
  - 同じロジックを **複数列 / 複数モデル** で使う → generic
  - 1 つのテーブル限定の特殊な不変条件 (例: `UNION ALL` で 3 mart 串刺し集計) → singular
- **Ex.08 で既に作っているなら**: `dbt/tests/generic/test_positive_value.sql` は再利用 OK。
  schema.yml だけ追記する。

## 解答例

詳細は [`3-5-positive-value-generic.solution.md`](3-5-positive-value-generic.solution.md) を参照。
