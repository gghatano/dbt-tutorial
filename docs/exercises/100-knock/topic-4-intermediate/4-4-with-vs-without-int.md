# 4-4: int を切る版・切らない版を両方書いて lineage を比較する

## シナリオ

intermediate を切るべきか / staging から直接 mart で良いか — これが
モデリング層の最大の意思決定。「とりあえず int を挟む」は SQL が長くなって
DRY 違反になり、「int を切らない」は同じ JOIN を mart 複数本に重複
コピペすることになる。

判断軸を **言葉ではなく目で覚える** ために、本問では **同じ集計を 2 通りに
書く**:

- `mart_compare_without_int.sql` — staging 4 本を直接 JOIN して集計 (int を挟まない)
- `mart_compare_with_int.sql`    — `int_order_details_100knock` を ref して集計 (int を挟む)

両方を `dbt run` で物理化したあと `dbt docs generate` → `dbt docs serve` で
lineage graph を見比べる。「int あり = mart の上流ノードが 1 つ
(`int_order_details_100knock`)、int なし = mart の上流ノードが 4 つ
(staging 4 本)」が一目で分かる。

これが「intermediate の存在意義 = mart の上流を 1 ノードに集約する」の
体感問題。

## 学べること

- intermediate を切る / 切らない で lineage graph がどう変わるか
- 同じ集計を 2 通りに書いたときの SQL の長さ・読みやすさの差
- `manifest_lineage` で「上流ノード数」をプログラム的に検証する手法
- 「再利用 ≥ 2 が int を切る最低ライン」という経験則の前振り (4-5 で完結)
- `dbt ls --select +<model>` で上流を辿る selector の使い方

## 前提

- 4-1 完了: `int_order_details_100knock` が物理化済み
- Topic ③ 完了: `stg_*_100knock` 4 本が物理化済み
- main HEAD が動く

## 入力データ

- `stg_orders_100knock` / `stg_customers_100knock` / `stg_products_100knock` /
  `stg_stores_100knock` (Topic ③)
- `int_order_details_100knock` (4-1)

集計内容は両 mart で同一: **「商品カテゴリ × 月の売上合計」**。
出力列: `category`, `order_year_month`, `total_sales_amount`, `total_quantity`。

## 課題

### Step 1: int を挟まない版 mart を書く

`dbt/models/100-knock/topic-4/mart_compare_without_int.sql` を新規作成。

要件:

- `{{ config(materialized='table', schema='marts') }}`
- staging 4 本を直接 `ref()` して JOIN し、`category × month` で `group by`
- `order_year_month` は `to_char(order_date, 'YYYY-MM')` または
  `date_trunc('month', order_date)` のどちらでも (両者の差は本問では問わない)

```sql
{{ config(materialized='table', schema='marts') }}

-- int を挟まずに staging 4 本から直接集計した版。
-- 同じ集計を mart_compare_with_int.sql でも書く (int を挟んだ版) ので、
-- lineage graph で上流ノードの数を見比べる。
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

### Step 2: int を挟んだ版 mart を書く

`dbt/models/100-knock/topic-4/mart_compare_with_int.sql` を新規作成。

要件:

- 同じ `{{ config(...) }}`
- `int_order_details_100knock` のみを `ref()` して集計

```sql
{{ config(materialized='table', schema='marts') }}

-- int_order_details_100knock を経由して同じ集計を作った版。
-- mart_compare_without_int.sql と結果は完全一致するはず。
-- lineage graph では上流ノードが 1 つ (int_order_details_100knock) のみになる。
select
    category,
    to_char(order_date, 'YYYY-MM')   as order_year_month,
    sum(quantity)                    as total_quantity,
    sum(sales_amount)::numeric(18, 2) as total_sales_amount
from {{ ref('int_order_details_100knock') }}
group by category, to_char(order_date, 'YYYY-MM')
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_compare_without_int mart_compare_with_int
```

両方 PASS=2 で完了するはず。

### Step 4: lineage graph を見比べる

```bash
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve   --profiles-dir .   # http://localhost:8080
```

UI で `mart_compare_with_int` と `mart_compare_without_int` をそれぞれ選択し、
**Lineage Graph** タブを開く:

- `mart_compare_with_int`: 上流に `int_order_details_100knock` が 1 つだけ
  (さらにその上流に staging 4 本)
- `mart_compare_without_int`: 上流に staging 4 本が直接ぶら下がる

CLI でも確認できる:

```bash
../.venv/bin/dbt ls --select +mart_compare_with_int    --profiles-dir .
# → mart 自分 + int_order_details_100knock + stg_*_100knock 4 本 = 6 ノード

../.venv/bin/dbt ls --select +mart_compare_without_int --profiles-dir .
# → mart 自分 + stg_*_100knock 4 本 = 5 ノード (中継 int がない)
```

### Step 5: 結果が一致することを確認

```sql
-- 両 mart の集計結果が完全一致するはず
analytics=> SELECT count(*) FROM marts.mart_compare_with_int;
analytics=> SELECT count(*) FROM marts.mart_compare_without_int;
-- → 同じ行数

analytics=> SELECT category, sum(total_sales_amount) FROM marts.mart_compare_with_int    GROUP BY category;
analytics=> SELECT category, sum(total_sales_amount) FROM marts.mart_compare_without_int GROUP BY category;
-- → 同じ値
```

## 完了条件

- [ ] `mart_compare_with_int.sql` と `mart_compare_without_int.sql` が両方存在する
- [ ] `dbt parse` / `dbt run` が両 mart で成功する
- [ ] manifest に両 mart が登録される
- [ ] manifest 上、`mart_compare_without_int` の direct upstream が staging 4 本 (4 ノード)
- [ ] manifest 上、`mart_compare_with_int` の direct upstream が `int_order_details_100knock` 1 ノードのみ
- [ ] `dbt docs serve` で 2 つの lineage を実際に見て、形の違いを確認できる

## ヒント (詰まったら)

- **`docs serve` がポート競合**: 既に 8080 で何か動いているなら
  `dbt docs serve --port 8081`。
- **両 mart の集計結果が一致しない**: `category` の正規化 (3-2 で `lower(trim(...))`)
  が staging で効いているか。int を挟むと staging の正規化を一度吸収して
  使うので、without_int 側と一致する。一致しないなら int 経由 / 直接 経由で
  片方だけ正規化が漏れている可能性。
- **"中継ノード" の数え方**: `manifest.json` の `nodes[<mart>].depends_on.nodes` を
  見れば direct upstream の **配列長** が出る。`with_int` は 1、
  `without_int` は 4 になる。これが採点でも見ている観点。
- **「結局 int は切るべき?」**: 本問はあえて結論を出さない。重要な気づきは
  **「下流 mart が 1 本しかないなら、int を切るメリットはほぼ無い」** と
  **「下流 mart が 2 本以上あるなら、int を切ると共通集計の重複が消える」**。
  4-5 でこの境界線を実演する。
- **`dbt run` で "Found duplicate model" エラー**: 既存 model と名前衝突
  していないか確認。`mart_compare_*` という名前は他で使っていないはずだが、
  万一あれば `_100knock` を足す。

## 解答例

詳細は [`4-4-with-vs-without-int.solution.md`](4-4-with-vs-without-int.solution.md) を参照。
