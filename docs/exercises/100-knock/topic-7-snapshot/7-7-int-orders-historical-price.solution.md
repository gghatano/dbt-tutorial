# 7-7 解答例

## ゴール再掲

- `dbt/models/100-knock/topic-7/int_orders_with_historical_price_100knock.sql` を新規作成
- 主軸: `int_order_details_100knock` (10,000 行)
- range JOIN で `snap_products_100knock` から「**注文時点**の `unit_price`」を引く
- 行数は 10,000 のまま (1 注文 = 1 行を維持)

## dbt/models/100-knock/topic-7/int_orders_with_historical_price_100knock.sql

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id。
-- unit_price は注文時点 (= o.order_date) で有効だった snap_products_100knock の
-- 単価を range JOIN で引き当てたもの。historical_sales_amount は
-- quantity * 「注文時点の単価」で再計算した売上 = 価格改定の影響を排した売上。
select
    o.order_id,
    o.order_date,
    o.product_id,
    o.quantity,
    sp.unit_price                                              as unit_price,
    sp.unit_price                                              as unit_price_at_order,
    (o.quantity * sp.unit_price)::numeric(14, 2)               as historical_sales_amount
from {{ ref('int_order_details_100knock') }}     as o
inner join {{ ref('snap_products_100knock') }}   as sp
        on o.product_id = sp.product_id
       and o.order_date >= sp.dbt_valid_from::date
       and o.order_date <  coalesce(sp.dbt_valid_to::date, date '9999-12-31')
```

**ポイント**:

- **`ref('snap_products_100knock')` で snapshot を ref**: dbt 上 snapshot は
  model と同じく `ref()` で参照できる。manifest 上は
  `snapshot.local_analytics.snap_products_100knock` ノードとして登録され、
  本 model の `depends_on` に並ぶ。これで `dbt build --select +<this>` を
  叩けば snapshot → model の順に走る (= 7-8 の一気通貫が成立する)。
- **range JOIN の半開区間**: 7-6 で確認した `[from, to)` 規約をそのまま
  JOIN 条件に変換。`dbt_valid_to IS NULL` を `9999-12-31` で扱う coalesce が
  「現役行 (= まだ次の世代が来ていない)」を救う。
- **INNER JOIN の根拠**: 注文 1 件は **必ず** 当時の snapshot 行に対応する
  はず (snapshot 1 回目以降の注文に限るが、本演習データはそう)。LEFT JOIN
  にして `unit_price IS NULL` 行が出るのは設計バグ (= snapshot のカバレッジ不足)
  なので INNER で「存在しなければ落ちて気付く」設計にする。
- **`unit_price` と `unit_price_at_order` の両方を出す**: 列名 `unit_price`
  だけだと「これって int_order_details 側の単価? それとも snapshot 側?」
  と読み手が迷う。`unit_price_at_order` という説明的 alias を併記して、
  下流が選んで使えるようにする。

## dbt/models/100-knock/topic-7/schema.yml

```yaml
version: 2

models:
  - name: int_orders_with_historical_price_100knock
    description: |
      Grain: 1 row = 1 order_id.
      snap_products_100knock を range JOIN し、注文 1 件ずつに
      「その注文日時点で有効だった unit_price」を引き当てた intermediate。
      historical_sales_amount = quantity * 注文時点単価。
    columns:
      - name: order_id
        description: "Primary key (= grain key)。"
        tests: [not_null, unique]
      - name: order_date
        tests: [not_null]
      - name: product_id
        tests: [not_null]
      - name: unit_price
        description: "注文時点で有効だった snap_products の unit_price (numeric)。"
        tests: [not_null]
      - name: historical_sales_amount
        description: "quantity * unit_price (注文時点の価格で再計算)。"
        tests: [not_null]
```

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
06:00:00  Found ... models, ... snapshots, ...

$ ../.venv/bin/dbt run --profiles-dir . --select int_orders_with_historical_price_100knock
06:00:10  1 of 1 START sql view model intermediate.int_orders_with_historical_price_100knock ... [RUN]
06:00:10  1 of 1 OK   created sql view model intermediate.int_orders_with_historical_price_100knock [CREATE VIEW in 0.13s]
06:00:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select int_orders_with_historical_price_100knock
06:00:20  Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

DB 上で確認:

```sql
analytics=> SELECT count(*) FROM intermediate.int_orders_with_historical_price_100knock;
 count
-------
 10000

analytics=> SELECT order_id, count(*)
            FROM intermediate.int_orders_with_historical_price_100knock
            GROUP BY order_id HAVING count(*) > 1;
 order_id | count
----------+-------
(0 rows)

-- 価格改定で当時価格と現価格が違う注文があるか
analytics=> SELECT count(*)
            FROM intermediate.int_orders_with_historical_price_100knock h
            JOIN intermediate.int_order_details_100knock d USING (order_id)
            WHERE h.unit_price <> d.unit_price;
 count
-------
   ??     -- 改定された 20 商品 × その商品の注文数 だけ非ゼロになる想定
```

## 解説まとめ

1. **snapshot を ref できることが「DAG に組み込む」の意味**: snapshot は
   `dbt snapshot` で物理化された後、model から `ref()` で引ける = 通常の
   model と同じ DAG ノード。これにより `dbt build --select +<consumer>` で
   snapshot を含む DAG をまるごと整合させられる (= 7-8 の主題)。
2. **range JOIN は bitemporal の標準形**: 「あるイベント時刻ごとに、当時
   有効だったマスタを引く」需要は、価格改定 / 為替 / 税率 / 組織異動
   どれにも共通。パターンとして覚えると応用が広い。
3. **`int_order_details_100knock` を主軸にする理由**: orders 単独でなく
   「orders + master を JOIN 済み」の int を主軸にすると、本問の追加 JOIN
   1 つ (snap) で完結する。Topic ④ で int を切った投資の回収。
4. **`unit_price` と `unit_price_at_order` を両方出す DRY**: 同じ値を
   2 列にコピーするのは一見 DRY 違反だが、列名が「設計意図のコメント」
   になるので可読性投資としてアリ。下流 mart 側でどちらを ref()/select
   するかは消費側の責務。
5. **次の問 (7-8)**: ここで作った int を `dbt build --select +<this>` で
   呼び出し、snapshot → model → test まで 1 本のコマンドで通す
   一気通貫を確認する。snapshot を「孤立した別オペ」 にしない練習。
