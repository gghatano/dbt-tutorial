# 6-5: 自作 generic test `positive_value` を 3 列に再利用

## シナリオ

3-5 で `dbt/tests/generic/test_positive_value.sql` を作り、
`stg_orders_100knock.quantity` / `unit_price` の 2 列に適用した
(または Ex.08 で同じものを既に書いている)。本問では **「同じ generic test
を 3 列以上に横展開する」** ことで、generic test の **再利用性 (DRY)** の
威力を体感する。

具体的には:

1. 既存の `dbt/tests/generic/test_positive_value.sql` を再利用 (= 新規作成不要、
   3-5 か Ex.08 で書いてあれば OK)
2. `stg_orders_100knock.quantity` / `stg_orders_100knock.unit_price` /
   `mart_monthly_sales_by_category_100knock.total_sales_amount` の **3 列**
   に `tests: [positive_value]` を貼る
3. `dbt test --select stg_orders_100knock mart_monthly_sales_by_category_100knock`
   で 3 件の `positive_value` test が **PASS** することを確認

## 学べること

- generic test の **横展開** (1 ファイル → N 適用) の DRY 性
- 同じ test を **staging と mart の両層** に貼る使い方 (層を超えた再利用)
- マージされる schema.yml (1.6+): topic-3 と topic-5 の両方に `positive_value`
  を書けば自動でマージされる
- なぜ generic test が singular test より DRY かの数値的な実感
  (singular だと 3 ファイル必要、generic は 1 ファイル + YAML 3 行)

## 前提

- Topic ② ③ ④ ⑤ 完了
- 3-5 または Ex.08 で `dbt/tests/generic/test_positive_value.sql` を作成済み
  (本問で新規作成しても OK、上書き可)
- Topic ⑤ 5-2 で `mart_monthly_sales_by_category_100knock` (`total_sales_amount`
  列を持つ) が物理化済み

## 入力データ

- `staging.stg_orders_100knock` 10,000 行 (`quantity` 1〜10, `unit_price` 100〜9990)
- `marts.mart_monthly_sales_by_category_100knock` (~80 行 = 月数 × カテゴリ数)
  の `total_sales_amount` (numeric(18, 2), 全行 > 0 のはず)

## 課題

### Step 1: generic test を確認 (or 新規作成)

`dbt/tests/generic/test_positive_value.sql`:

```sql
{% test positive_value(model, column_name) %}
    select *
    from {{ model }}
    where {{ column_name }} is null
       or {{ column_name }} <= 0
{% endtest %}
```

3-5 / Ex.08 で書いていればそのまま再利用。本問の採点は `file_exists` で
存在を確認するだけ。

### Step 2: schema.yml に `positive_value` を 3 列適用

#### 2a. topic-3 側 (stg_orders_100knock の 2 列)

`dbt/models/100-knock/topic-3/schema.yml` の `stg_orders_100knock` ブロック:

```yaml
      - name: quantity
        description: "数量 (int, must be > 0)。"
        tests:
          - not_null
          - positive_value         # ← 適用 (3-5 で既に書いていれば再利用)
      - name: unit_price
        description: "単価 (numeric(10,2), must be > 0)。"
        tests:
          - not_null
          - positive_value         # ← 適用
```

#### 2b. topic-5 側 (mart_monthly_sales_by_category_100knock.total_sales_amount)

`dbt/models/100-knock/topic-5/schema.yml` の
`mart_monthly_sales_by_category_100knock` ブロックに追記:

```yaml
  - name: mart_monthly_sales_by_category_100knock
    columns:
      # ... 既存列 (monthly_category_id / month / category) ...
      - name: total_sales_amount
        description: "Sum of sales_amount for the month/category, numeric(18,2). 必ず > 0。"
        tests:
          - not_null
          - positive_value         # ← 追加
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_monthly_sales_by_category_100knock
../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock mart_monthly_sales_by_category_100knock
```

期待出力 (抜粋):

```
N of M PASS positive_value_stg_orders_100knock_quantity ........... [PASS]
N of M PASS positive_value_stg_orders_100knock_unit_price ......... [PASS]
N of M PASS positive_value_mart_monthly_sales_by_category_100knock_total_sales_amount ... [PASS]
Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

`positive_value_*` で始まる test が **3 件以上 PASS** していれば成功。

### Step 4: schema.yml に positive_value が 3 件以上書かれていることを確認

```bash
grep -n 'positive_value' dbt/models/100-knock/topic-3/schema.yml dbt/models/100-knock/topic-5/schema.yml | wc -l
# => 3 以上 (定義行のみカウント)
```

## 完了条件

- [ ] `dbt/tests/generic/test_positive_value.sql` が存在する
      (`{% test positive_value(...) %}` 構文)
- [ ] schema.yml (topic-3 / topic-5) に `positive_value` が **3 ヶ所以上**
      書かれている
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select stg_orders_100knock mart_monthly_sales_by_category_100knock`
      で `positive_value_*` test が 3 件以上 PASS
- [ ] manifest に以下 3 つの test node が登録される:
  - `test.local_analytics.positive_value_stg_orders_100knock_quantity`
  - `test.local_analytics.positive_value_stg_orders_100knock_unit_price`
  - `test.local_analytics.positive_value_mart_monthly_sales_by_category_100knock_total_sales_amount`

## ヒント (詰まったら)

- **「3 列に適用」 のコスト比較**:
  - generic 方式: `test_positive_value.sql` 1 本 + schema.yml に
    `- positive_value` 3 行 = **計 4 行追加**
  - singular 方式: `assert_positive_quantity.sql` /
    `assert_positive_unit_price.sql` / `assert_positive_total_sales_amount.sql`
    の 3 ファイル = **計 ~20 行 + 3 ファイル**
  - これが DRY の威力。列数が増えるほど差が開く。
- **schema.yml が複数ファイルに跨る**: dbt 1.6+ では `models:` 配下の
  同名 model は **マージされる**。topic-3 / topic-5 で別 model に書くので
  そもそもマージ問題は起きない。同じ model に同じ test を 2 回書くと
  「duplicate test definition」 エラー。
- **`{{ model }}` / `{{ column_name }}` は固定引数**: dbt が自動で渡す。
  `{{ ref(...) }}` を test 本体に書く必要は **ない** (むしろ書くと壊れる)。
- **`positive_value` の test 名規則**:
  `positive_value_<model>_<column>` の自動命名。`name:` で明示すれば任意名に
  上書き可能 (本問では使わない)。
- **mart 側で test を貼る意味**: staging で `quantity > 0` を保証していても、
  mart の `SUM(sales_amount)` が常に正とは限らない (returns / 値引で
  負数になる業務もある)。**mart 層でも改めて契約を貼る** ことで、上流の
  契約変更が下流に伝播していないバグを早期検知できる。
- **`dbt test --select` の selector**: 複数モデルを並列指定するときは
  半角スペース区切り。`--select stg_orders_100knock mart_monthly_sales_by_category_100knock`
  で両方の test を一括実行。
- **MVP との並走 (再掲)**: MVP の `dbt/tests/` には `assert_positive_quantity.sql`
  (singular) があるが、100-knock 側は generic で同じ役割を果たす。
  両者は独立に動く。

## 解答例

詳細は [`6-5-positive-value-reuse.solution.md`](6-5-positive-value-reuse.solution.md) を参照。
