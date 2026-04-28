# 5-2: mart_monthly_sales_by_category_100knock を複合 grain で新規作成

## シナリオ

経営会議向けに「月 × カテゴリ別の売上推移」を Metabase の折れ線グラフで
出したい。`mart_daily_sales` (日次) や `mart_product_sales` (商品単位) は
あるが、**月とカテゴリの 2 軸でクロス集計した mart** はまだない。

ここでは **複合 grain** (= grain が単一列ではなく複数列の組合せ) を持つ
mart の作り方を学ぶ。複合 grain の場合、PK は単一列ではないので
`dbt_utils.generate_surrogate_key()` で**サロゲートキー**を作って
unique test を貼るのが定石。「mart の grain は BI が GROUP BY する単位」を
体感する回。

## 学べること

- 複合 grain (`month` × `category`) の宣言と、サロゲートキー設計
- `dbt_utils.generate_surrogate_key(['month', 'category'])` でハッシュ PK
- `date_trunc('month', order_date)` で月次集約
- `tests: [unique]` を **サロゲートキー列に貼る** ことで grain を機械検証
- BI の「GROUP BY 月, GROUP BY カテゴリ」を mart 側に焼き込む意味

## 前提

- Topic ② ③ ④ 完了:
  - `dbt/models/100-knock/topic-4/int_order_details_100knock.sql` (Topic ④ で
    実装済み。MVP の `int_order_details` と同じ列を持つ想定)
  - 未実装なら `int_order_details` (MVP) を ref しても可
- **dbt-utils が必須**: `dbt/packages.yml` に `dbt-utils` を追加して
  `dbt deps` 済み。MVP には未導入のため、本問の Step 1 で追加する

## 入力データ

新規データなし。既存:

- `intermediate.int_order_details_100knock` (or MVP `int_order_details`)
  - 列: `order_id`, `order_date`, `product_id`, `category`, `quantity`,
    `unit_price`, `sales_amount` 等

## 課題

### Step 1: dbt-utils を packages.yml に追加

`dbt/packages.yml` を編集:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.0.0", "<2.0.0"]
```

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

`dbt_packages/dbt_utils/` が作られる。

### Step 2: mart を作る

`dbt/models/100-knock/topic-5/mart_monthly_sales_by_category_100knock.sql`:

要件:

- 冒頭コメントで grain を宣言: `grain: 1 month × 1 category 1 row`
- `date_trunc('month', order_date)::date as month` で月の頭日に揃える
- `category` でも GROUP BY
- 集計列: `order_count`, `total_quantity`, `total_sales_amount`
- **サロゲート PK** を先頭列に:
  `{{ dbt_utils.generate_surrogate_key(['month', 'category']) }} as monthly_category_id`
- materialization は `table` (mart のデフォルト)、`schema='marts'` 明示

### Step 3: schema.yml に PK + grain 検証を書く

`dbt/models/100-knock/topic-5/schema.yml` に追記:

- `monthly_category_id`: `not_null` + `unique` (= 複合 grain の機械検証)
- `month`: `not_null`
- `category`: `not_null`
- 各集計列: `not_null`

### Step 4: 実行

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_monthly_sales_by_category_100knock
../.venv/bin/dbt test --profiles-dir . --select mart_monthly_sales_by_category_100knock
```

`unique` test が PASS すれば「`(month, category)` の組合せが mart 内で
1 回しか出ない」 = grain 宣言が正しいことが証明される。

## 完了条件

- [ ] `dbt/packages.yml` に `dbt-utils` が追加されている
- [ ] `dbt deps` が成功する
- [ ] `dbt/models/100-knock/topic-5/mart_monthly_sales_by_category_100knock.sql` が存在
- [ ] manifest に `model.local_analytics.mart_monthly_sales_by_category_100knock` が登録
- [ ] `unique` test on `monthly_category_id` が PASS
- [ ] 全行で `month` と `category` の組合せが unique (sql_assert で検証)

## ヒント (詰まったら)

- **なぜサロゲートキー？** PK は理屈上 `(month, category)` の複合 PK で表せるが、
  BI ツールや exposure / FK 参照では「単一列の ID」の方が扱いやすい。
  `generate_surrogate_key` は引数列を `||` で連結して `md5()` するだけの
  シンプルな macro なので、生成ロジックは透明。
- **`date_trunc('month', ...)` の戻り型**: Postgres では timestamp 型が返る。
  日付軸の mart で扱いたいので `::date` で cast しておく。
- **`order_date` がない場合**: Topic ④ で `int_order_details_100knock` を
  作っていなければ MVP の `int_order_details` をそのまま ref してよい。
  ただし採点 CI が確認する node 名は学習者の mart 自身なので、ref 先がどちらでも
  PASS する。
- **dbt_utils が未導入エラー**: `Compilation Error: ... 'dbt_utils' is undefined`
  が出たら `dbt deps` を忘れている。`packages.yml` 編集 → `dbt deps` の順を
  必ず守る。
- **categoryの値域**: MVP の `accepted_values` で 8 種類に絞られている前提。
  本 mart は category 列を grain に含めるが、accepted_values の再宣言は
  上流で済んでいるので不要。

## 解答例

詳細は [`5-2-mart-monthly-by-category.solution.md`](5-2-mart-monthly-by-category.solution.md) を参照。
