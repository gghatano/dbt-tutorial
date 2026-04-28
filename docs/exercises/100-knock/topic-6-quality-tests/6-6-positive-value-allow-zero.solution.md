# 6-6 解答例

## dbt/tests/generic/test_positive_value.sql

```sql
{#-
    Generic test: column value must be > 0 (or >= 0 if allow_zero=True), and not NULL.

    Args:
      model        : auto-injected by dbt (relation to the model under test)
      column_name  : auto-injected by dbt (string of the column name)
      allow_zero   : default False. When True, treat 0 as a valid value
                     (i.e. only `< 0` is a violation).

    Usage in schema.yml:
        # Strict (legacy / default): treat <= 0 as violation
        - name: quantity
          tests:
            - positive_value

        # Relaxed: treat only < 0 as violation (0 is OK)
        - name: total_sales_amount
          tests:
            - positive_value:
                arguments:
                  allow_zero: true
-#}
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

**ポイント**:

- **デフォルト引数 `allow_zero=False`**: schema.yml で `arguments:` を省略すると
  False が入り、6-5 と完全に同じ挙動 (`<= 0` を弾く) になる。後方互換性が
  保たれているので、6-5 で書いた `quantity` / `unit_price` への適用は **触らずに済む**。
- **Jinja `{% if %} ... {% else %}` 分岐**: コンパイル時にどちらか一方の SQL
  だけが残る。`allow_zero=true` のときは `or column < 0`、false のときは
  `or column <= 0` が出力される。`target/compiled/.../positive_value_mart_daily_sales_100knock_total_sales_amount.sql`
  を `cat` すると、実際に展開された SQL が読める (デバッグの基本動作)。
- **NULL は常に違反扱い**: `is null` 分岐は `allow_zero` に関係なく残す。
  「NULL を許したい」場合は呼び出し側で `not_null` を貼らない設計にすればよく、
  test 側で NULL ハンドリングを器用にやるべきではない (関心の分離)。
- **docstring (`{#- ... -#}`)**: dbt は `tests/generic/*.sql` の冒頭コメントを
  特に拾わないが、人間が読むためには重要。「いつ allow_zero=true を使うか」
  「いつデフォルトで OK か」の指針を書く。

## dbt/models/100-knock/topic-5/schema.yml (mart_daily_sales_100knock 部分)

```yaml
version: 2

models:
  # ... (5-1 / 5-2 の mart 定義はそのまま)

  - name: mart_daily_sales_100knock
    config:
      contract:
        enforced: true
    description: |
      Daily sales mart with enforced column contract.
      total_sales_amount allows zero (a holiday with 0 sales is a valid business state).
    columns:
      - name: order_date
        data_type: date
        tests:
          - not_null
          - unique
      - name: order_count
        data_type: bigint
        tests:
          - not_null
      - name: customer_count
        data_type: bigint
        tests:
          - not_null
      - name: total_quantity
        data_type: bigint
        tests:
          - not_null
      - name: total_sales_amount
        data_type: numeric(18,2)
        description: |
          Sum of sales_amount on this date.
          allow_zero=true: 売上ゼロの祝日もある前提なので 0 は契約違反としない。
        tests:
          - not_null
          - positive_value:
              arguments:
                allow_zero: true
```

**ポイント**:

- **`arguments:` ブロック**: dbt 1.8+ の推奨構文。`positive_value:` の下に
  `arguments:` を入れて、その下に key-value を並べる。旧 flat 記法
  (`positive_value: {allow_zero: true}`) も動くが、新規プロジェクトでは
  `arguments:` 統一が推奨。
- **stg 側は宣言を変えない**: 6-5 で書いた `stg_orders_100knock.quantity` / `unit_price` の
  `tests: [positive_value]` は **そのまま動く** (デフォルト False が効く)。
  「mart だけ緩める」 が schema.yml 1 ヶ所の差分で済むのが、引数付き generic test の威力。
- **description で `allow_zero` の理由を残す**: 6 ヶ月後に「なんで mart だけ
  ゆるい?」と聞かれないように、業務的根拠を YAML 上に書いておく。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 80 data tests ...

$ ../.venv/bin/dbt test --profiles-dir . \
    --select stg_orders_100knock mart_daily_sales_100knock
... 
N of M PASS positive_value_stg_orders_100knock_quantity ............... [PASS]
N of M PASS positive_value_stg_orders_100knock_unit_price ............. [PASS]
N of M PASS positive_value_mart_daily_sales_100knock_total_sales_amount [PASS]
Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

## manifest で引数を確認

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
test_node = m['nodes']['test.local_analytics.positive_value_mart_daily_sales_100knock_total_sales_amount']
print('test_metadata.kwargs:', test_node['test_metadata']['kwargs'])
"
test_metadata.kwargs: {'allow_zero': True, 'column_name': 'total_sales_amount', 'model': \"{{ get_where_subquery(ref('mart_daily_sales_100knock')) }}\"}
```

`'allow_zero': True` が記録されていれば成功。

## 引数を効かせる試験 (任意)

mart の `total_sales_amount` の 1 行を 0 にしてみる:

```sql
-- 一時的に売上 0 円の行を作る
UPDATE marts.mart_daily_sales_100knock SET total_sales_amount = 0
 WHERE order_date = (SELECT min(order_date) FROM marts.mart_daily_sales_100knock);
```

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select mart_daily_sales_100knock
... PASS positive_value_mart_daily_sales_100knock_total_sales_amount [PASS]
# allow_zero=true なので 0 は違反扱いされず PASS
```

ここで schema.yml の `arguments: allow_zero: true` を外して `dbt test` 再実行すると
**FAIL** に変わる (デフォルト False = `<= 0` 違反扱い)。引数 1 つで挙動が
切り替わることが体感できる。

戻す:

```sql
-- mart は table 物理化なので、dbt run --select mart_daily_sales_100knock で再生成
```

## 解説まとめ

- **なぜ厳しさを 2 段階用意するのか**:
  - **staging (= raw に直結)**: 入力データの不正を最も早く捕まえる場所。
    `quantity = 0` や `unit_price = 0` は raw 投入の不具合 → 厳しく弾く。
  - **mart (= 集計後)**: 業務として「0 になる瞬間」 が存在する。売上ゼロの日 /
    在庫ゼロの SKU / 0 件の問い合わせ。これらを「契約違反」 と扱うと test が
    赤になり続け、誰も注意しなくなる (= 警報疲れ)。
  - 同じロジックで **対象に応じて厳しさを変える** のが、本問のキモ。
- **なぜパラメータ付き generic test なのか**:
  - 「strict_positive_value」 と 「nonneg_value」 の **2 本作る**選択肢もあるが、
    DRY 違反 (両者の差分は `<` vs `<=` の 1 文字) かつ命名で意図が分かりにくい。
  - **同じ test に引数で挙動を切り替える**ほうが、「これは positive_value 系の
    制約」 と読み手に伝わる。Python の関数のデフォルト引数と同じ思想。
- **引数付き test の本領**:
  - `in_range(model, column_name, min_value, max_value)` のような **値域指定**
  - `recent_within(model, column_name, days=7)` のような **時間幅指定**
  - `accepted_values(model, column_name, values=[...])` も実は引数付き generic test
    (built-in)。同じ仕組みで `accepted_values` が動いていることが見える化する。
- **manifest 上の `test_metadata.kwargs`**: dbt が test 引数を構造化して
  manifest に残す。「どの test がどんな引数で呼ばれているか」を機械的に
  集計可能 → CI / コードレビュー / リネージュ可視化での品質ゲートに使える。
- **後方互換性の重要性**: 6-5 で書いた `quantity` / `unit_price` への適用が
  **無修正で動く**ことが、引数のデフォルト値の存在意義。本番運用中の test に
  「破壊的変更」を入れずに機能拡張できる設計の好例。
