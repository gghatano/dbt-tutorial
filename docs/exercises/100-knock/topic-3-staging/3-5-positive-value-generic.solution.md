# 3-5 解答例

## dbt/tests/generic/test_positive_value.sql

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

- **`{% test name(model, column_name) %}`**: `name` 部分が `tests: [positive_value]`
  で参照される識別子。ファイル名と test 名は **揃えなくてもよい** が、
  慣例として `test_<name>.sql` にしておくとコードジャンプが効く。
- **`{{ model }}` は relation オブジェクト**: dbt が「テスト対象 model への参照」を
  自動で埋める。`{{ ref('stg_orders_100knock') }}` を書く必要はない (むしろ書くと壊れる)。
- **`{{ column_name }}` は文字列**: schema.yml で `- name: quantity` と書いた値が
  そのまま入る。
- **NULL も拒否する設計**: `is null or <= 0` の両条件。「NULL を許したい」場合は
  `{{ column_name }} <= 0` だけにすればよい。デフォルト引数で切り替えるなら
  `{% test positive_value(model, column_name, allow_null=False) %}` の形になる。
- **`select *` の理由**: dbt は「返ってきた行数」だけ見て成否判定する。中身は
  ログにダンプされて学習者が「どの行が違反したか」を読める。

## dbt/models/100-knock/topic-3/schema.yml (3-4 完成形に追記)

`stg_orders_100knock` ブロックの該当列に `- positive_value` を追記:

```yaml
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders。order_date は date, unit_price は numeric(10,2)。"
    columns:
      # ... (3-4 までの記述はそのまま) ...
      - name: quantity
        description: "数量 (int, must be > 0)。"
        tests:
          - not_null
          - positive_value         # ← 追加
      - name: unit_price
        description: "単価 (numeric(10,2), must be > 0)。"
        tests:
          - not_null
          - positive_value         # ← 追加
```

**ポイント**:

- **同じ列に複数 test**: YAML リストで `[not_null, positive_value]` のように
  並べるだけ。順序は問わない。
- **`positive_value` は built-in と同じ作法**: `not_null` と完全に同じ宣言の
  仕方で書ける。これが generic test の威力 = **学習者が新しい構文を覚えなくていい**。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 75 data tests ...

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... 既存 tests PASS ...
N of M PASS positive_value_stg_orders_100knock_quantity ........... [PASS in 0.05s]
N of M PASS positive_value_stg_orders_100knock_unit_price ......... [PASS in 0.05s]
Done. PASS=20 WARN=0 ERROR=0 SKIP=0 TOTAL=20
```

## わざと FAIL させて挙動を確認

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET quantity = -1 WHERE order_id = 1;
SQL
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... 
N of M FAIL 1 positive_value_stg_orders_100knock_quantity ........... [FAIL 1 in 0.06s]
... 
Failure in test positive_value_stg_orders_100knock_quantity (models/100-knock/topic-3/schema.yml)
  Got 1 result, configured to fail if != 0
  See test failures: SELECT * FROM staging.dbt_test__audit.positive_value_stg_orders_100knock_quantity
```

戻す:

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -c \
    "UPDATE raw.orders SET quantity = 1 WHERE order_id = 1;"
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock   # 全 PASS に戻る
```

## 解説まとめ

- **generic test = テスト macro**: `dbt/tests/generic/*.sql` または
  `dbt/macros/*.sql` (後方互換) に置けば、dbt が自動で拾って `tests:` から呼べる。
- **built-in との関係**: `not_null` / `unique` / `relationships` / `accepted_values` も
  実は同じ `{% test %}` ブロック実装。`dbt_packages/.../include/global_project/tests/generic/`
  に元実装がある。覗いてみると勉強になる。
- **generic > singular な理由 (3 つ)**:
  1. **再利用性**: 1 ファイル書けば任意の `(model, column)` ペアに `tests:` 1 行で適用できる
  2. **自動命名**: `positive_value_stg_orders_100knock_quantity` のように、どの test が
     落ちたか即わかる名前を dbt が生成
  3. **マージ可能**: 複数 schema.yml に同じ model 名で書けばマージされる (dbt 1.6+) ので、
     MVP の `dbt/models/staging/schema.yml` に手を入れずに 100-knock 側で test を増やせる
- **「行が返れば FAIL」 という評価ルール**: SQL を「**違反行を返すクエリ**」 として書くのが
  dbt 流。test = SELECT が 0 行なら PASS、1 行以上なら FAIL。`assert *` 系の言語と
  違って **データ駆動** で考える。
- **拡張アイデア**: 引数付き generic test (`{% test in_range(model, column_name, min, max) %}`) を
  作って `rating` (1〜5 など) に適用すると、Topic ⑥ 後半で学ぶ「不変条件のパラメータ化」
  に繋がる。Ex.08 Step 5 を参照。
- **MVP との並走**: MVP の `dbt/tests/` には singular test (`assert_*.sql`) しかない。
  generic test は **完全に追加だけ** で MVP には影響しない。学習者が安全に
  「dbt の test 機構を増築する」感覚を体得できる練習になっている。
