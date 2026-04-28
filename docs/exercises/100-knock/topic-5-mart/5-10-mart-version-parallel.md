# 5-10: `int_order_details_100knock` v2 を参照する `mart_daily_sales_with_tax_100knock` を新規作成し、v1 mart と並走させる

## シナリオ

Topic ④ #4-10 で `int_order_details_100knock` を `versions:` (1.5+) で v1 (税抜) と v2 (税込列を追加) の **2 バージョンに分岐** させた。これは「下流を壊さずに schema を進化させる」ための機構で、既存 mart は引き続き `ref('int_order_details_100knock')` (= v1 デフォルト) を使い、新 mart だけが `ref('int_order_details_100knock', v=2)` で税込列にアクセスできる。

このエクササイズでは、その v2 を参照する **新 mart** `mart_daily_sales_with_tax_100knock` を作る。既存 `mart_daily_sales_100knock` (5-3 で contract: enforced 化したもの、v1 ref) は **そのまま残す**。これで:

- 旧系統: `int_order_details_100knock` v1 → `mart_daily_sales_100knock` (税抜) → 既存 BI ダッシュボード (5-5 の exposure)
- 新系統: `int_order_details_100knock` v2 → `mart_daily_sales_with_tax_100knock` (税込) → 新 BI ダッシュボード (将来の exposure)

の **二系統 DAG** が共存する。BI 側は段階的に新 mart に切り替えればよく、旧 mart を消すのは「全 exposure が新 mart 参照に切り替わった後」。これが「BI を壊さずに段階移行」の具体的手順。

## 学べること

- `{{ ref('xxx', v=2) }}` の書き方 (model versions の参照側)
- 旧 mart と新 mart を同じ schema (`marts`) に並走させる設計
- DAG が二系統 (旧経路 + 新経路) に分岐していく見え方
- 「v2 を作る側 (Topic ④ 4-10)」と「v2 を消費する側 (本問)」の責務分離
- 「税抜 → 税込」のような業務変更を、SQL 1 本変えるのではなく **新 model を追加** で対応する設計

## 前提

- Topic ② ③ ④ + Topic ⑤ 5-1〜5-5 完了
- **Topic ④ #4-10 完了済み**: `int_order_details_100knock` の v1 / v2 が `versions:` で宣言されており、v2 は `unit_price_with_tax` (= `unit_price * 1.10`) と `sales_amount_with_tax` (= `quantity * unit_price * 1.10`) の 2 列を追加で持つ
- `mart_daily_sales_100knock` (5-3) が稼働している (= v1 系統の旧 mart)

## 入力データ

不要。既存 v2 int model から集計するだけ。

## 課題

### Step 1: `mart_daily_sales_with_tax_100knock.sql` を新規作成

`dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql`:

冒頭の `config()` で `materialized='table'`, `schema='marts'` を宣言。`from {{ ref('int_order_details_100knock', v=2) }}` で v2 を参照し、以下の列を持つ daily mart にする:

- `order_date` (PK)
- `order_count`
- `customer_count`
- `total_quantity`
- `total_sales_amount` (税抜、numeric(18,2))
- `total_sales_amount_with_tax` (税込、numeric(18,2))
- `tax_amount` (= `with_tax - amount`)

業務的には「経理部門が税込ベースで日次売上を見たい」というニーズを想定。

### Step 2: `dbt parse` で `ref(..., v=2)` 解決確認

```bash
cd dbt
dbt parse --profiles-dir .
```

`int_order_details_100knock` v2 が見つからないと `Unknown reference 'int_order_details_100knock' v2` で fail する。Topic ④ 4-10 の `versions:` 宣言が完了していることが前提。

### Step 3: `dbt build` で v2 mart を作成

```bash
dbt build --select mart_daily_sales_with_tax_100knock --profiles-dir .
```

PASS=1 で完了。`marts.mart_daily_sales_with_tax_100knock` table が作成される。

### Step 4: 旧 mart と並走することを確認

```bash
dbt ls --select +mart_daily_sales_100knock --profiles-dir .              # 旧経路
dbt ls --select +mart_daily_sales_with_tax_100knock --profiles-dir .     # 新経路
```

旧経路は `int_order_details_100knock` (v1 デフォルト) → `mart_daily_sales_100knock` のチェーン。新経路は `int_order_details_100knock.v2` → `mart_daily_sales_with_tax_100knock`。両方が `marts` schema に table として残る。

### Step 5: SQL で「税込列が税抜より大きい」ことを確認

```sql
SELECT
  order_date,
  total_sales_amount,
  total_sales_amount_with_tax,
  (total_sales_amount_with_tax - total_sales_amount) AS tax_diff
FROM marts.mart_daily_sales_with_tax_100knock
ORDER BY order_date
LIMIT 5;
```

`tax_diff > 0` が全行で成立すれば、v2 ref で税込列が確かに引き取れている証拠。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-10-mart-version-parallel.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql` が存在
- [ ] SQL 内に `{{ ref('int_order_details_100knock', v=2) }}` または `version=2` 形式の v2 参照がある
- [ ] `dbt parse` PASS
- [ ] `dbt build --select mart_daily_sales_with_tax_100knock` が PASS
- [ ] `marts.mart_daily_sales_with_tax_100knock.total_sales_amount_with_tax` 列が存在し、`total_sales_amount` より大きい
- [ ] 旧 `mart_daily_sales_100knock` は **削除されておらず**、両方の table が `marts` schema に存在

## ヒント (詰まったら)

- **`ref(..., v=2)` 構文**: `{{ ref('int_order_details_100knock', v=2) }}` または `{{ ref('int_order_details_100knock', version=2) }}` どちらでも可。v は int (string ではない) で渡す。
- **v2 が無いとエラー**: Topic ④ 4-10 完了が前提。`int_order_details_100knock_v2.sql` または `versions:` ブロックが存在することを `dbt ls --select int_order_details_100knock --output json` で確認。
- **schema 衝突**: 旧 `mart_daily_sales_100knock` と並走するので、新 mart は **別名** (`_with_tax_` を含む) を必ず付ける。同名で v2 を作ろうとすると table 衝突。
- **税率は v2 の int 側で持つ**: `unit_price_with_tax = unit_price * 1.10` のようなロジックは v2 の int で 1 度計算済み。mart 側は `sum(sales_amount_with_tax)` で集計するだけにする (= 税率のハードコードは int に閉じ込める)。
- **`total_sales_amount`(税抜) も並べる**: 比較を見せたいので税抜と税込を両方列に出す。BI で「税抜売上」「税込売上」「税額」の 3 メトリクスを並べて確認できる。
- **DAG を視覚化**: `dbt docs generate && dbt docs serve` でブラウザを開き、`mart_daily_sales_with_tax_100knock` の Lineage タブで二系統を見る (旧 mart と新 mart が同じ int v1/v2 から枝分かれ)。
- **旧 mart 削除タイミング**: 本問では削除しない。実運用では「全 BI exposure が `mart_daily_sales_with_tax_100knock` に切り替わった」後に旧 mart を消し、その時点で v1 も非推奨化する。

## 解答例

詳細は [`5-10-mart-version-parallel.solution.md`](5-10-mart-version-parallel.solution.md) を参照。
