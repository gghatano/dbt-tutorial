# 6-5 解答例

## dbt/tests/generic/test_positive_value.sql

3-5 / Ex.08 で書いたものと同じ (再掲):

```sql
{#-
    Generic test: column value must be > 0 (and not NULL).

    Usage in schema.yml:
        columns:
          - name: quantity
            tests:
              - positive_value
-#}
{% test positive_value(model, column_name) %}

    select *
    from {{ model }}
    where {{ column_name }} is null
       or {{ column_name }} <= 0

{% endtest %}
```

**ポイント (再掲)**:

- **`{% test name(model, column_name) %}`**: dbt が自動で `model` (relation
  オブジェクト) と `column_name` (文字列) を渡す。
- **「行が返れば FAIL」**: `is null or <= 0` を満たす行を返す。1 行でも
  返れば test FAIL。
- **`select *`**: 違反行の中身全体を log にダンプして学習者がデバッグ可能に。

## dbt/models/100-knock/topic-3/schema.yml (該当ブロック)

`stg_orders_100knock` の `quantity` / `unit_price` に適用 (3-5 完成形のまま):

```yaml
  - name: stg_orders_100knock
    columns:
      # ... 他列省略 ...
      - name: quantity
        description: "数量 (int, must be > 0)。"
        tests:
          - not_null
          - positive_value
      - name: unit_price
        description: "単価 (numeric(10,2), must be > 0)。"
        tests:
          - not_null
          - positive_value
```

## dbt/models/100-knock/topic-5/schema.yml (該当ブロックに追記)

`mart_monthly_sales_by_category_100knock.total_sales_amount` に適用:

```yaml
version: 2

models:
  # ... mart_top_rated_products_100knock など他 mart 省略 ...

  - name: mart_monthly_sales_by_category_100knock
    description: "月次 × カテゴリ別の売上集計マート。1 (month, category) = 1 row。"
    columns:
      - name: monthly_category_id
        description: "Surrogate PK (md5 of month + category)。"
        tests:
          - not_null
          - unique
      - name: month
      - name: category
      - name: total_sales_amount
        description: "Sum of sales_amount, numeric(18, 2)。必ず > 0 (返品なしモデル)。"
        tests:
          - not_null
          - positive_value         # ← 追加 (3 つ目の positive_value 適用)
```

**ポイント**:

- **mart 層でも positive_value を貼る**: staging で `unit_price > 0` を
  契約していても、mart の `SUM(sales_amount)` が常に正とは限らない
  (返品 / 値引 / 通貨換算で負数になる業務もある)。**層を超えて改めて
  契約を貼る** ことで、上流契約の変更や bug が下流に伝播していないかを
  早期検知できる。
- **同じ test を 3 列に貼った**: generic test 1 本 + YAML 3 行で 3 列
  カバー。singular だと 3 ファイル必要だった。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 78 data tests ...

$ ../.venv/bin/dbt run --profiles-dir . --select mart_monthly_sales_by_category_100knock
1 of 1 OK created sql table model marts.mart_monthly_sales_by_category_100knock ... [OK]

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock mart_monthly_sales_by_category_100knock
1 of N PASS not_null_stg_orders_100knock_order_id ...
2 of N PASS unique_stg_orders_100knock_order_id ...
... 
N of M PASS positive_value_stg_orders_100knock_quantity ........... [PASS in 0.05s]
N of M PASS positive_value_stg_orders_100knock_unit_price ......... [PASS in 0.05s]
N of M PASS positive_value_mart_monthly_sales_by_category_100knock_total_sales_amount ... [PASS in 0.05s]
... 
Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

## manifest 上で 3 件の test node を確認

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
for k in sorted(m['nodes']):
    if k.startswith('test.local_analytics.positive_value_'):
        print(k)
"
test.local_analytics.positive_value_mart_monthly_sales_by_category_100knock_total_sales_amount
test.local_analytics.positive_value_stg_orders_100knock_quantity
test.local_analytics.positive_value_stg_orders_100knock_unit_price
```

3 件登録されていれば成功。

## わざと FAIL を体感 (任意)

### staging 側 (quantity を負数に)

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET quantity = -1 WHERE order_id = 1;"
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
N of M FAIL 1 positive_value_stg_orders_100knock_quantity ...
```

### mart 側 (mart テーブルに直接負数を仕込む)

mart は table materialization なので **直接 UPDATE** でも一時的に壊せる
(次回 `dbt run` で再生成されると元に戻る):

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE marts.mart_monthly_sales_by_category_100knock SET total_sales_amount = -100 WHERE month = (SELECT MIN(month) FROM marts.mart_monthly_sales_by_category_100knock);"
$ ../.venv/bin/dbt test --profiles-dir . --select mart_monthly_sales_by_category_100knock
N of M FAIL 1 positive_value_mart_monthly_sales_by_category_100knock_total_sales_amount ...
```

戻す:

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select mart_monthly_sales_by_category_100knock
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET quantity = 1 WHERE order_id = 1;"
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock mart_monthly_sales_by_category_100knock
... 全 PASS に戻る
```

## DRY のコスト比較 (具体的に)

### 同じことを singular でやると…

```text
dbt/tests/100-knock/topic-6/
├── assert_positive_stg_orders_quantity.sql        ← 7 行
├── assert_positive_stg_orders_unit_price.sql      ← 7 行
└── assert_positive_mart_monthly_total.sql         ← 7 行
合計: 3 ファイル / 21 行
```

各ファイルの中身は:

```sql
select * from {{ ref('stg_orders_100knock') }} where quantity is null or quantity <= 0
```

のように **モデル名 / 列名だけ違う、ほぼ同じ SQL の繰り返し** = DRY 違反。

### generic test だと

```text
dbt/tests/generic/
└── test_positive_value.sql                         ← 7 行 (1 ファイル)

dbt/models/100-knock/topic-3/schema.yml             ← 2 行追記
dbt/models/100-knock/topic-5/schema.yml             ← 1 行追記
合計: 1 ファイル / 7 + 3 行
```

**1/3 のコード量で同等の契約を表現** できる。さらに 4 列目 / 5 列目に
広げるとき、generic は **YAML 1 行追加** で済む (singular は 7 行追加)。

## 解説まとめ

- **generic test の本領 = 横展開**: 1 つの不変条件ロジックを多数の列に
  YAML 1 行で適用できる。「**契約を増やすコストが O(1) に近づく**」 のが
  generic 方式の価値。
- **層を超えた再利用 (staging × mart)**: 同じ generic test を staging と
  mart の両方に貼ると、層を超えて同じ契約が走る。staging で守られた
  値が mart で壊れた瞬間 (集計バグ / 算術オーバーフロー) を即検知できる
  二段構え。
- **schema.yml がマージされる (1.6+)**: 同じ model 名を別ファイルに書くと
  test がマージされる (重複 test 定義はエラー)。100-knock 側で test を
  追加するときに MVP の schema.yml を触らずに済む安全装置。
- **MVP との並走**: MVP の `dbt/tests/assert_positive_*.sql` (singular) と
  100-knock 側の `dbt/tests/generic/test_positive_value.sql` (generic) は
  共存可能。学習者は同じ業務ルールを 2 つの方式で書いて比較できる。
- **「context-free な不変条件」 を generic 化する判断基準**: 「列名 / モデル名
  以外に context 依存が無い」 ロジックは generic 化すると DRY が効く。
  逆に「日付ロジック特殊」「複数列の組み合わせ」 のような context 依存が強い
  ものは singular のまま (6-4 がその例)。
- **拡張アイデア (6-6 への伏線)**: `positive_value` を `(model, column_name,
  allow_zero=False)` 引数付きに拡張すると、`mart_*.total_sales_amount` が
  「0 円の月は許す (= まだ売上が立っていない月)」 のような業務要件にも
  対応できる。これは 6-6 で扱う「**パラメータ付き契約**」 への自然な発展。
- **採点設計**: 本問は (a) generic test ファイル存在、(b) schema.yml に
  positive_value が 3 ヶ所以上、(c) 3 件の test node が manifest に登録、
  (d) `dbt test` で 3 件 PASS、の 4 観点を組み合わせて 100 点。「適用
  範囲を計測する」 = 「generic の再利用度を採点する」 という設計。
