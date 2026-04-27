# 4-5 解答例

## dbt/models/100-knock/topic-4/mart_daily_sales_100knock.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- 日次売上 mart (1 行 = 1 order_date)。
-- int_order_details_100knock の fan-out 下流 1 本目。
-- materialization は table: 下流 BI / レポートが頻繁に読むので table 化で I/O 節約。
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

## dbt/models/100-knock/topic-4/mart_product_sales_100knock.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- 商品売上 mart (1 行 = 1 product_id)。
-- int_order_details_100knock の fan-out 下流 2 本目。
-- product_name / category は int 経由で staging から既に enrich 済み = ここでは追加 JOIN 不要。
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

**ポイント (両方共通)**:

- **どちらも `from {{ ref('int_order_details_100knock') }}` の 1 ref のみ**:
  staging 4 本との JOIN は int で済んでいるので、mart は集計 grain と
  集計関数だけ書けば良い。SQL が極めて短い。
- **`sales_amount` を mart 側で再計算していない**: int で `quantity * unit_price`
  を済ませている。仮に税の式が変わっても **int 1 行の修正で両 mart が同時に
  追従する** = DRY の核心。
- **`product_name` / `category` を mart で改めて JOIN していない**: int 経由で
  staging から enrich 済み。`category` の `lower(trim(...))` 正規化も staging
  → int → mart と「上流で 1 回吸収すれば下流で再吸収不要」の流れ。
- **MVP `mart_daily_sales` / `mart_product_sales` の 100-knock 版**: 同じ集計を
  100-knock 名前空間で再実装。`_100knock` suffix で MVP との並走を担保。

## 動作確認

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock mart_product_sales_100knock
06:41:00  1 of 2 START sql table model marts.mart_daily_sales_100knock . [RUN]
06:41:00  1 of 2 OK   created sql table model marts.mart_daily_sales_100knock [SELECT 480 in 0.30s]
06:41:00  2 of 2 START sql table model marts.mart_product_sales_100knock [RUN]
06:41:00  2 of 2 OK   created sql table model marts.mart_product_sales_100knock [SELECT 100 in 0.20s]
06:41:00  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
```

行数 (480 / 100) はダミーデータ次第だが、`order_date` のユニーク数 / `product_id` の
ユニーク数と一致するのが正しい。

## fan-out の確認

```bash
$ ../.venv/bin/dbt ls --select int_order_details_100knock+ --profiles-dir .
model.local_analytics.int_order_details_100knock
model.local_analytics.mart_daily_sales_100knock
model.local_analytics.mart_product_sales_100knock
test.local_analytics.assert_int_order_details_grain
test.local_analytics.unique_int_order_details_100knock_order_id
test.local_analytics.not_null_int_order_details_100knock_order_id
test.local_analytics.not_null_int_order_details_100knock_order_date
test.local_analytics.not_null_int_order_details_100knock_customer_id
test.local_analytics.not_null_int_order_details_100knock_product_id
test.local_analytics.not_null_int_order_details_100knock_sales_amount
```

**`mart_daily_sales_100knock` と `mart_product_sales_100knock` が両方** 出力に
含まれる = `int_order_details_100knock` の **fan-out 成立** (= int の下流が
mart 2 本に分岐している)。

## manifest 上の child_map で見る

```bash
$ python3 -c "
import json
m = json.load(open('dbt/target/manifest.json'))
node = 'model.local_analytics.int_order_details_100knock'
children = m['child_map'].get(node, [])
marts = [c for c in children if c.startswith('model.local_analytics.mart_')]
print(f'int の下流 model: {marts}')
"
int の下流 model: ['model.local_analytics.mart_daily_sales_100knock',
                   'model.local_analytics.mart_product_sales_100knock']
```

`child_map[int_order_details_100knock]` に **mart 2 本が両方** 入っている = fan-out の
データ構造的根拠。

## docs UI での見え方

```bash
$ ../.venv/bin/dbt docs generate --profiles-dir .
$ ../.venv/bin/dbt docs serve   --profiles-dir .
```

UI で `int_order_details_100knock` を選択 → "Lineage Graph":

- 中央: `int_order_details_100knock`
- 左: staging 4 本 (上流)
- 右: **`mart_daily_sales_100knock` と `mart_product_sales_100knock` が枝分かれ** (= fan-out)

「ハブ 1 点に 4 線が集まり、右に 2 線が伸びる」星形の中央に int がいる構図が見える。

## 「int を 1 行修正したら下流 2 mart に伝播する」体感

`int_order_details_100knock.sql` を一時的に変更:

```sql
-- 変更前
(o.quantity * o.unit_price)::numeric(14, 2) as sales_amount

-- 変更後 (税 10% を加味)
(o.quantity * o.unit_price * 1.10)::numeric(14, 2) as sales_amount
```

```bash
$ ../.venv/bin/dbt run --select int_order_details_100knock+ --profiles-dir .
06:50:00  1 of 3 START sql view model intermediate.int_order_details_100knock ... [RUN]
06:50:00  1 of 3 OK   created sql view model intermediate.int_order_details_100knock [CREATE VIEW in 0.10s]
06:50:00  2 of 3 START sql table model marts.mart_daily_sales_100knock .. [RUN]
06:50:00  2 of 3 OK   created sql table model marts.mart_daily_sales_100knock [SELECT 480 in 0.30s]
06:50:00  3 of 3 START sql table model marts.mart_product_sales_100knock . [RUN]
06:50:00  3 of 3 OK   created sql table model marts.mart_product_sales_100knock [SELECT 100 in 0.20s]
06:50:00  Done. PASS=3 WARN=0 ERROR=0 SKIP=0 TOTAL=3
```

両 mart の `total_sales_amount` が一律 1.10 倍に。**1 ファイル変更で
DAG の下流が一気に再構築されて整合性が保たれる** のが fan-out の利益。

```sql
analytics=> SELECT sum(total_sales_amount) FROM marts.mart_daily_sales_100knock;
-- 修正前と比べてちょうど 1.10 倍
```

確認後、`int_order_details_100knock.sql` を **必ず元に戻して `dbt run` を
再実行**。

## 解説まとめ

- **fan-out の本質**: int 1 本 → mart N 本。N=1 なら int を切る価値が薄いが、
  N≥2 になった瞬間に **「同じ JOIN を mart N 本に書く重複」が発生し得る**。
  intermediate を切ることでその重複を消し、修正コストを 1/N に圧縮する。
- **「再利用 ≥ 2 が int を切る最低ライン」の経験則**: 4-4 で「単独 mart に
  int を挟むと冗長」を見せた上で、本問で「mart 2 本になった瞬間に int の
  価値が出る」を見せる。**設計判断の閾値が "2"** という記憶に残る数字
  になる。
- **fan-out が嬉しい 3 つの場面**:
  1. **DRY 修正**: int 1 行の式変更 → 下流 N mart に自動伝播 (本問 Step 5 で体感)
  2. **テスト集約**: 4-2 の `assert_int_order_details_grain` は int 1 本に
     紐付くが、その grain 契約は下流 mart N 本にも間接的に効く (mart は
     int を信じて `ref()` するだけ)
  3. **物理化集約**: int を view (storage 0) にしておけば、mart 側の table 化
     コストだけ払えば済む。staging を直接 mart で集計すると mart 側で
     毎回大きな JOIN が走る
- **fan-out が成立しているかの 3 つの確認方法**:
  1. `dbt ls --select <int>+` の出力に下流 mart が並ぶ (CLI で素早く)
  2. `manifest.json` の `child_map[<int>]` に mart 2 本が入っている (プログラム的)
  3. `dbt docs serve` の lineage graph で右に枝分かれが見える (視覚的)
- **`+` の方向の覚え方**: 「**+ は時間の矢のような向き**」。
  - `+<node>` = この node に **流れ込む** 方向 = 上流
  - `<node>+` = この node から **流れ出す** 方向 = 下流
  - dbt の `<selector><degree>+<degree>` 記法で、両側に数字を付けると hop 数を
    制御できる (`int+1` = 1 hop 下流のみ)
- **Topic ④ 全体での到達点**: 4-1 で grain 宣言、4-2 で grain test、4-3 で
  異なる grain の int を派生、4-4 で int あり/なしの lineage 比較、4-5 で
  fan-out 体感。これでモデリング層の核心 (「分析対象の grain を中継 hub に
  集約する」) を体で覚えた状態になる。Topic ⑤ ではこの int を起点とする mart
  をさらに洗練していく。
