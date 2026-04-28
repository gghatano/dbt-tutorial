# 4-5: int_order_details_100knock を 2 本の mart から ref する fan-out

## シナリオ

4-4 で「int あり vs int なし」の lineage を見比べた。今回は次の段階:
**1 つの int から下流 mart を 2 本ぶら下げる** (= **fan-out** パターン) を
実際に作って、「再利用 ≥ 2 が int を切る最低ライン」という経験則を体感する。

具体的には `int_order_details_100knock` を ref する mart を 2 本作る:

- `mart_daily_sales_100knock.sql`   — 日次集計 (1 行 = 1 order_date)
- `mart_product_sales_100knock.sql` — 商品集計 (1 行 = 1 product_id)

`dbt ls --select int_order_details_100knock+` (= int 自身 + すべての下流) で
mart 2 本が「下流ノード」として並んで見えれば成功。

これにより:

1. **int の SQL を 1 行修正したら、下流 mart 2 本に伝播する** (e.g. `sales_amount`
   の式に税を加味すると、両 mart の合計が同時に更新される)
2. **同じ JOIN を mart 2 本にコピペする必要がない** (DRY 達成)
3. **テストが int に集約できる** (4-2 の grain test が両 mart を間接的に守る)

これが intermediate 層を用意する核心的な利益。

## 学べること

- **fan-out** パターン: 1 中継ノード → N 下流。intermediate の代表的な形
- `dbt ls --select <node>+` で **下流方向** に DAG を辿る
- mart の集計 SQL は、int を ref していれば極めて短くなる (各 mart の SQL が
  数行で済む)
- 「再利用 ≥ 2」が intermediate 採用の最低ライン
- `manifest.child_map` から下流ノード集合を取り出す検証

## 前提

- 4-1 完了: `int_order_details_100knock` が物理化済み
- 4-4 完了: `mart_compare_*` が手元にあると比較が捗る (採点には不要)
- main HEAD が動く

## 入力データ

`int_order_details_100knock` (4-1)。これだけ。

## 課題

### Step 1: 日次売上 mart を書く

`dbt/models/100-knock/topic-4/mart_daily_sales_100knock.sql` を新規作成。

要件:

- `{{ config(materialized='table', schema='marts') }}`
- `int_order_details_100knock` のみを `ref()`
- 出力列: `order_date`, `order_count`, `customer_count`, `total_quantity`, `total_sales_amount`
- MVP の `mart_daily_sales` と「同じ集計の 100-knock 版」になる

```sql
{{ config(materialized='table', schema='marts') }}

-- 日次売上 mart (1 行 = 1 order_date)。
-- int_order_details_100knock の fan-out 下流 1 本目。
select
    order_date,
    count(*)                          as order_count,
    count(distinct customer_id)       as customer_count,
    sum(quantity)                     as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details_100knock') }}
group by order_date
order by order_date
```

### Step 2: 商品売上 mart を書く

`dbt/models/100-knock/topic-4/mart_product_sales_100knock.sql` を新規作成。

要件:

- 同じ `{{ config(...) }}`
- `int_order_details_100knock` のみを `ref()`
- 出力列: `product_id`, `product_name`, `category`, `order_count`, `total_quantity`, `total_sales_amount`

```sql
{{ config(materialized='table', schema='marts') }}

-- 商品売上 mart (1 行 = 1 product_id)。
-- int_order_details_100knock の fan-out 下流 2 本目。
select
    product_id,
    product_name,
    category,
    count(*)                          as order_count,
    sum(quantity)                     as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details_100knock') }}
group by product_id, product_name, category
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_daily_sales_100knock mart_product_sales_100knock
```

両 mart の table が `marts.` に物理化される。

### Step 4: fan-out が成立していることを確認

```bash
../.venv/bin/dbt ls --select int_order_details_100knock+ --profiles-dir .
```

期待出力 (順不同):

```
model.local_analytics.int_order_details_100knock
model.local_analytics.mart_daily_sales_100knock
model.local_analytics.mart_product_sales_100knock
test.local_analytics.assert_int_order_details_grain    # 4-2 で書いた test
test.local_analytics.unique_int_order_details_100knock_order_id
test.local_analytics.not_null_int_order_details_100knock_order_id
... (略)
```

`int_order_details_100knock+` の出力に **`mart_daily_sales_100knock` と
`mart_product_sales_100knock` が両方含まれる** = fan-out 成立。

### Step 5: int を 1 行修正したらどうなるか体感する (任意)

`int_order_details_100knock.sql` の `sales_amount` 式に税を足してみる:

```sql
-- 一時的に: (o.quantity * o.unit_price * 1.10)::numeric(14, 2) as sales_amount
```

```bash
../.venv/bin/dbt run --select int_order_details_100knock+ --profiles-dir .
# → int + 下流 mart 2 本が一気に再構築される
```

両 mart の `total_sales_amount` が一律 1.10 倍になる = **「上流 1 行修正 →
下流に自動伝播」** の DRY 効果が体感できる。確認後、税の追加は **必ず巻き戻す**。

## 完了条件

- [ ] `mart_daily_sales_100knock.sql` と `mart_product_sales_100knock.sql` が両方存在する
- [ ] `dbt parse` / `dbt run` が両 mart で成功する
- [ ] manifest に両 mart が登録される
- [ ] manifest の `child_map[int_order_details_100knock]` に **mart 2 本が両方含まれる**
- [ ] `dbt ls --select int_order_details_100knock+` の出力に mart 2 本が並ぶ

## ヒント (詰まったら)

- **`dbt ls --select <node>+` の意味**: `<node>+` は「自分 + すべての下流
  (model, test, snapshot 等含む)」。`<node>+1` なら「自分 + 1 hop 下流」。
  fan-out の確認では `+` (= 全下流) で十分。
- **`+<node>` (上流) と `<node>+` (下流) の混同**: `+` を **どっち側に書くか** で
  方向が変わる。`+mart_daily_sales_100knock` は上流 (= int + staging)、
  `int_order_details_100knock+` は下流 (= mart 2 本)。
- **manifest の `child_map`**: `target/manifest.json` を JSON で開くと
  `child_map[<node>]` に下流 node の配列がある。grader はここを見て fan-out を
  検証する (`upstream_min_count` の逆方向版が現状の checker にないため、
  代わりに mart 側の lineage で「両方とも int を上流に持つ」を見ている — これも
  fan-out の同値命題)。
- **MVP の `mart_daily_sales` と衝突しない?**: 衝突しない。MVP 側は
  `mart_daily_sales` で、本問は `mart_daily_sales_100knock`。`dbt ls --select mart_*`
  で 4 ノード (MVP 2 本 + 100-knock 2 本) が並ぶ。
- **行数の目安**: `mart_daily_sales_100knock` は order_date のユニーク数
  (= 約 480 日 / ダミーデータ次第)、`mart_product_sales_100knock` は 100 行
  (= product 100 種類)。合計 580 行前後。

## 解答例

詳細は [`4-5-int-fanout-to-marts.solution.md`](4-5-int-fanout-to-marts.solution.md) を参照。
