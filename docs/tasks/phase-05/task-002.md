# task-002: marts 3本（daily / customer / product）

- Phase: 05
- Status: Done
- Owner: -
- Depends on: phase-05/task-001
- Parallelizable with: -

## 目的
分析・BI向けの3つのマートを作成する。

## 入力 / 前提
- spec §8.4

## 成果物
- `dbt/models/marts/mart_daily_sales.sql`
- `dbt/models/marts/mart_customer_sales.sql`
- `dbt/models/marts/mart_product_sales.sql`
- `dbt/models/marts/schema.yml`

## 受入条件
- `dbt run --select marts --profiles-dir .` が成功
- 各列が spec §8.4 通り
- 全マートで not_null / unique（PK列）テストが通る
- `total_sales_amount >= 0` テストが通る（phase-06 で singular test として実装予定。phase-05 では not_null + 集計の SUM が非負で運用上保証される）
- mart_daily_sales が1件以上存在

## 実装メモ / 判断ログ
- materialization: table（spec §8.4 / §13 が分析・BI 用途を前提。集計を view にすると参照のたびに再計算され BI クエリのレスポンスが悪化。行数は最大 1000 と小さく、テーブル化のストレージコストは無視できる）
- mart_daily_sales: PK = `order_date`
- mart_customer_sales: PK = `customer_id`
- mart_product_sales: PK = `product_id`
- `customer_count`: `COUNT(DISTINCT customer_id)`（=その日に注文した実顧客数）。`order_count = count(*)` は注文行数（同顧客の複数注文も区別）と意味を分ける。
- `total_sales_amount` は `sum(sales_amount)::numeric(18,2)` にキャストして scale 揃え。
- `accepted_values` テストは `mart_product_sales.category` に配置:
  - 採用根拠: `scripts/generate_dummy_data.py` の `CATEGORIES` リスト（`Food`, `Beverage`, `Household`, `Beauty`, `Electronics`, `Stationery`, `Apparel`, `Toy`）が静的に列挙されているため、テストで lock 可能。
  - `stg_stores.prefecture` も候補だったが、都道府県マスタは将来 47 件に拡張されうるためテスト固定は過剰と判断（不採用）。
- 詳細は `docs/decisions/0006-marts-modeling.md` を参照。

## 実行ログ

### `dbt run --profiles-dir .` (全モデル)
```
Done. PASS=8 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8
```
- mart_daily_sales: 365 行（1 年分）
- mart_customer_sales: 1,000 行
- mart_product_sales: 100 行

### `dbt test --profiles-dir .`
```
Done. PASS=57 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=57
```
（うち mart 系: not_null × 14, unique × 3, accepted_values × 1）

### DB 確認
```
\dt marts.*
 Schema | Name                | Type  | Owner
 marts  | mart_customer_sales | table | dbt_user
 marts  | mart_daily_sales    | table | dbt_user
 marts  | mart_product_sales  | table | dbt_user

SELECT count(*) FROM marts.mart_daily_sales;     -- 365
SELECT count(*) FROM marts.mart_customer_sales;  -- 1000
SELECT count(*) FROM marts.mart_product_sales;   -- 100

SELECT * FROM marts.mart_daily_sales ORDER BY order_date DESC LIMIT 3;
 order_date | order_count | customer_count | total_quantity | total_sales_amount
 2026-04-26 |          30 |             28 |            162 |          897350.00
 2026-04-25 |          37 |             37 |            201 |          974340.00
 2026-04-24 |          19 |             19 |             96 |          545630.00
```
