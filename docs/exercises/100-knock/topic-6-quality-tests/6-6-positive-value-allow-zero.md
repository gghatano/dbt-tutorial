# 6-6: positive_value を引数付き (allow_zero) に拡張、mart に allow_zero=true で適用

## シナリオ

6-5 で書いた `positive_value` generic test は「`column_name` が NULL または `<= 0` の
行を返す」 という固定ロジックだった。`stg_orders_100knock.quantity` のような
**「絶対に 1 以上」** の列にはちょうどよいが、`mart_daily_sales_100knock.total_sales_amount`
のように **「日次集計なので 0 円の日があってもおかしくない」** 列に貼ると、
売上ゼロの祝日 1 日があるだけで test FAIL してしまう。

dbt の generic test は **デフォルト引数付き Python 関数のように書ける**:
`{% test positive_value(model, column_name, allow_zero=False) %}` と宣言しておけば、
`schema.yml` で `tests: [positive_value]` と書けば従来通り厳しく `> 0`、
`tests: [positive_value: {allow_zero: true}]` と書けば緩く `>= 0` を許容できる。
**1 つの test macro が「対象に応じて挙動を切り替えられる」** ようになり、
staging の厳しさと mart の緩さを **同じ宣言** で表現できる。

## 学べること

- generic test に **デフォルト引数** を持たせる構文 (`allow_zero=False`)
- `schema.yml` から **辞書形式** で test に引数を渡す書き方
- なぜ厳しさを 2 段階用意するのか (= staging と mart の不変条件は別物)
- 引数付き test の **manifest 上での記録** (`test_metadata.kwargs`)
- 後方互換性の維持: 引数を省略すると **デフォルト値** で旧挙動

## 前提

- Topic ② ③ ④ ⑤ 完了 — `stg_orders_100knock` / `mart_daily_sales_100knock` が物理化済み
- Topic ⑥ 6-1〜6-5 完了 — `dbt/tests/generic/test_positive_value.sql` が
  `(model, column_name)` 2 引数版で動いている
- 5-3 完了 — `mart_daily_sales_100knock.total_sales_amount` が contract 付きで物理化済み

## 入力データ

`marts.mart_daily_sales_100knock` (約 90 行 / 日付分)。
`total_sales_amount` は `numeric(18,2)`、通常 100,000 円〜数百万円。
売上ゼロの日が 1 日あっても **「事業として正常」** と扱う。

## 課題

### Step 1: generic test を引数付きに拡張

`dbt/tests/generic/test_positive_value.sql` を編集 (6-5 で書いたファイルを上書き):

```sql
{% test positive_value(model, column_name, allow_zero=False) %}

    select *
    from {{ model }}
    where {{ column_name }} is null
       {% if allow_zero %}
       or {{ column_name }} < 0
       {% else %}
       or {{ column_name }} <= 0
       {% endif %}

{% endtest %}
```

要件:

- `allow_zero` を **デフォルト False** で受け取る
- `allow_zero=True` のときは `< 0` だけを違反扱い (0 は OK)
- `allow_zero=False` のときは従来通り `<= 0` を違反扱い (6-5 と同じ挙動)
- どちらの分岐でも NULL は違反扱い (NULL を許したいなら `not_null` 不要設計が別途必要)

### Step 2: schema.yml で mart に allow_zero=true で適用

`dbt/models/100-knock/topic-5/schema.yml` の `mart_daily_sales_100knock` ブロックの
`total_sales_amount` 列に追加:

```yaml
  - name: mart_daily_sales_100knock
    columns:
      # ... (5-3 までの記述はそのまま) ...
      - name: total_sales_amount
        data_type: numeric(18,2)
        tests:
          - not_null
          - positive_value:
              arguments:
                allow_zero: true   # ← 0 円の日も許容
```

> **YAML 構文の注意**: dbt 1.8+ では `arguments:` ブロック配下に引数を書く
> 推奨構文。旧構文 (`positive_value: {allow_zero: true}`) も動くが、新規は
> `arguments:` で書く。

`stg_orders_100knock.quantity` / `unit_price` 側の宣言は **触らない** (6-5 のまま、
`allow_zero` を省略するとデフォルト False で `<= 0` を弾く厳しい挙動が保たれる)。

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_orders_100knock mart_daily_sales_100knock
```

期待:

- `positive_value_stg_orders_100knock_quantity` が PASS (allow_zero 省略 → 厳しい)
- `positive_value_stg_orders_100knock_unit_price` が PASS (同上)
- `positive_value_mart_daily_sales_100knock_total_sales_amount` が PASS (allow_zero=true)

### Step 4: 引数の効き目を確認 (任意)

mart 側に売上ゼロの日を仮に作って、`allow_zero: true` を外すと FAIL することを確認:

```sql
-- 一時的に schema.yml で allow_zero を外して dbt test → FAIL することを観察 → 戻す
```

## 完了条件

- [ ] `dbt/tests/generic/test_positive_value.sql` に `allow_zero=False` 引数定義がある
- [ ] schema.yml で `mart_daily_sales_100knock.total_sales_amount` に
      `positive_value` + `arguments: {allow_zero: true}` が宣言されている
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select mart_daily_sales_100knock` で `positive_value` が PASS
- [ ] manifest 上で test の `test_metadata.kwargs.allow_zero` が `true` になっている

## ヒント (詰まったら)

- **デフォルト引数の Python 風記法**: `{% test name(model, column_name, arg=default) %}`
  と書ける。Jinja は Python の関数定義をかなり真似ている。
- **Jinja の `{% if %}` 分岐**: コンパイル時に評価されて 1 つの SQL に展開される。
  `allow_zero=true` のときと `false` のときで、生成 SQL が違う形になる。
  `target/compiled/local_analytics/.../positive_value_*.sql` を覗くと確認できる。
- **manifest での kwargs 記録**: `target/manifest.json` の test node の
  `test_metadata.kwargs` に渡した引数が記録される。grader はここを見て
  「学習者が allow_zero を渡したか」を判定する。
- **`arguments:` vs 旧構文**: dbt 1.8 で test の引数は `arguments:` ブロックに
  入れる構文が推奨化された (旧 `kwargs` フラット記法も後方互換で動く)。本問は
  新構文で書く。
- **stg と mart で厳しさを変える設計判断**: staging は raw 由来の生データなので
  「不正値があれば即気付きたい」 → 厳しい契約。mart は集計後の値なので
  「業務として 0 が正常な瞬間」 がある → 緩い契約。test の厳しさは
  **データ層ごとに使い分ける** のが dbt 流。

## 解答例

詳細は [`6-6-positive-value-allow-zero.solution.md`](6-6-positive-value-allow-zero.solution.md) を参照。
