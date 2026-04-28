# 4-4 解答例

## dbt/models/100-knock/topic-4/mart_compare_without_int.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- int を挟まずに staging 4 本から直接集計した版。
-- 同じ集計を mart_compare_with_int.sql でも書く (int を挟んだ版) ので、
-- lineage graph で上流ノードの数を見比べる。
-- 観察事項:
--   - SQL の長さ: JOIN 4 本 + sales_amount の式が mart 内に書かれる
--   - 上流ノード数: staging 4 本がそのまま direct upstream
select
    p.category,
    to_char(o.order_date, 'YYYY-MM')                  as order_year_month,
    sum(o.quantity)                                   as total_quantity,
    sum(o.quantity * o.unit_price)::numeric(18, 2)    as total_sales_amount
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
group by p.category, to_char(o.order_date, 'YYYY-MM')
```

## dbt/models/100-knock/topic-4/mart_compare_with_int.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- int_order_details_100knock を経由して同じ集計を作った版。
-- mart_compare_without_int.sql と結果は完全一致するはず。
-- 観察事項:
--   - SQL の長さ: 集計 1 本 + ref 1 本のみ。劇的に短い
--   - 上流ノード数: int_order_details_100knock 1 つだけ (= 中継 hub)
--   - sales_amount は int 側で計算済みなので、ここでは sum(sales_amount) するだけ
select
    category,
    to_char(order_date, 'YYYY-MM')   as order_year_month,
    sum(quantity)                    as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details_100knock') }}
group by category, to_char(order_date, 'YYYY-MM')
```

**ポイント (両方共通)**:

- **集計結果は完全一致する**: int は staging から「JOIN + 派生列計算」までを
  済ませただけで、行を捨てたり追加したりしない (= grain 保存変換)。だから
  `int_order_details_100knock` を集計しても、staging を直接集計しても、
  最終結果は同じ。これが int を挟む / 挟まないを純粋に「DAG の形」と
  「SQL の DRY」で判断できる根拠。
- **with_int 側が劇的に短い**: SQL の行数を比較すると `without_int` が
  10 行強、`with_int` が 5 行程度。同じ集計を **mart 2 本以上で書いたら**、
  この差がコピペ重複として効いてくる。
- **without_int は staging 4 本に直接依存**: manifest 上の `depends_on.nodes`
  の配列長が 4。with_int は 1 (int_order_details_100knock のみ)。これが
  本問の「lineage の形の違い」の本体。

## 動作確認

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select mart_compare_without_int mart_compare_with_int
06:31:00  1 of 2 START sql table model marts.mart_compare_without_int .. [RUN]
06:31:00  1 of 2 OK   created sql table model marts.mart_compare_without_int [SELECT 60 in 0.30s]
06:31:00  2 of 2 START sql table model marts.mart_compare_with_int ..... [RUN]
06:31:00  2 of 2 OK   created sql table model marts.mart_compare_with_int [SELECT 60 in 0.20s]
06:31:00  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
```

両方 60 行 (= category 5 種 × 月 12 か月 = 60、または時期次第で多少前後)。
**完全一致** が成立。

## lineage を CLI で比較

```bash
$ ../.venv/bin/dbt ls --select +mart_compare_without_int --profiles-dir .
source.local_analytics.raw_100knock.customers
source.local_analytics.raw_100knock.orders
source.local_analytics.raw_100knock.products
source.local_analytics.raw_100knock.stores
model.local_analytics.stg_customers_100knock
model.local_analytics.stg_orders_100knock
model.local_analytics.stg_products_100knock
model.local_analytics.stg_stores_100knock
model.local_analytics.mart_compare_without_int
# → mart の direct upstream は staging 4 本

$ ../.venv/bin/dbt ls --select +mart_compare_with_int --profiles-dir .
source.local_analytics.raw_100knock.customers
source.local_analytics.raw_100knock.orders
source.local_analytics.raw_100knock.products
source.local_analytics.raw_100knock.stores
model.local_analytics.stg_customers_100knock
model.local_analytics.stg_orders_100knock
model.local_analytics.stg_products_100knock
model.local_analytics.stg_stores_100knock
model.local_analytics.int_order_details_100knock
model.local_analytics.mart_compare_with_int
# → mart の direct upstream は int 1 本のみ。その先で staging 4 本に展開
```

## lineage を docs UI で見比べる (推奨)

```bash
$ ../.venv/bin/dbt docs generate --profiles-dir .
$ ../.venv/bin/dbt docs serve   --profiles-dir .
```

ブラウザで `http://localhost:8080`:

1. 左ペインで `mart_compare_without_int` を選択 → "Lineage Graph" タブ
   → mart のすぐ左隣に staging 4 本がぶら下がる「3 段の漏斗形」
2. 左ペインで `mart_compare_with_int` を選択 → "Lineage Graph" タブ
   → mart のすぐ左隣に `int_order_details_100knock` 1 本、その左に staging 4 本
   → 「4 段の砂時計形」

**砂時計の "くびれ" が intermediate**。中継 hub があると
- 下流 mart は hub 1 本を信じれば良い (上流変更の影響がカプセル化される)
- 同じ集計を 2 本以上の mart で再利用するとき、hub の SQL を再実行しない (mart は hub の table を読むだけ)

## 結果の同値性確認

```sql
analytics=> SELECT count(*) FROM marts.mart_compare_with_int;
 count
-------
    60

analytics=> SELECT count(*) FROM marts.mart_compare_without_int;
 count
-------
    60

-- 値の一致確認 (片方を引いて 0 行ならぴったり一致)
analytics=> SELECT * FROM marts.mart_compare_with_int
            EXCEPT
            SELECT * FROM marts.mart_compare_without_int;
(0 rows)
```

`EXCEPT` で 0 行 = 両 mart は完全一致。「int を挟むと結果が変わる」という
不安は消える。

## 解説まとめ

- **intermediate を切る判断軸 (本問でつかむもの)**:
  1. **SQL の DRY**: 同じ集計を書く mart が 2 本以上あるか?
     - 1 本なら int 不要 (重複なし、中継ノードを増やすデメリットだけ)
     - 2 本以上なら int 推奨 (hub に集約 = 1 箇所修正で全 mart に伝播)
  2. **上流変更の影響カプセル化**: staging に列が増えても、int があれば
     そこで吸収して mart には伝えない。int がないと mart 全部に列追加が必要
  3. **テストの集約点**: 4-2 で書いた grain test は int の grain を守る。
     int がないと、grain test を mart 個別に書くか、テストが書けなくなる
- **without_int の問題は単独 mart では見えない**: 本問では mart 1 本ずつ
  しか作っていないので、without_int も「短い SQL の方が読みやすい!」と
  感じるかもしれない。しかし mart が 5 本あって全部 staging 4 本を JOIN して
  集計するとどうなるか想像してほしい — `category` の `lower(trim(...))` を
  staging で 1 回吸収しているからまだ整合性が取れているが、もし staging を
  使わず raw を直接見ていたら **5 個の mart で同じ正規化を書く** ことになる。
  staging が「raw を 1 箇所に吸収する hub」なのと同じ理屈で、
  intermediate は「同じ JOIN + 派生計算を 1 箇所に吸収する hub」になる。
- **DAG の "形" を物理的な絵で覚える**: `dbt docs serve` の lineage graph で
  「砂時計形 (with int) と 漏斗形 (without int)」の違いを目で覚えると、
  以後の設計判断が自然になる。「mart を増やすたびに staging 4 本がぶら下がる」
  漏斗形は、複数 mart に拡張すると **狂ったように線が増える**。砂時計形なら
  下流が増えても hub のすぐ右に mart が並ぶだけ = 視覚的にもメンテしやすい。
- **本問の to_char vs date_trunc**: `to_char(order_date, 'YYYY-MM')` は文字列
  返り、`date_trunc('month', order_date)` は date (月初日) 返り。集計目的なら
  どちらでも、ソートの観点で文字列 'YYYY-MM' は ISO 形式なので辞書順 = 時系列順
  になる。BI で使うなら date 型のほうが扱いやすい。本問はどちらでも採点には
  影響しない。
- **次の問 (4-5)**: 本問の延長線。`int_order_details_100knock` を 2 本の mart
  から `ref()` する **fan-out** パターンを作って、「再利用 ≥ 2 が int を切る
  最低ライン」の経験則を体感する。
