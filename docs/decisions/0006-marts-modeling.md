# ADR 0006: intermediate / marts のモデリング方針

- 日付: 2026-04-26
- ステータス: Accepted
- コンテキスト: phase-05/task-001, task-002
- 関連: spec §8.3, §8.4, §9.1, ADR-0005

## 背景

phase-05 では staging 層の上に `int_order_details`（intermediate）と `mart_daily_sales` / `mart_customer_sales` / `mart_product_sales`（marts）を構築する。spec §9.1 で要求される built-in テスト 4 種（`not_null`, `unique`, `relationships`, `accepted_values`）のうち、`accepted_values` を phase-05 のどこに配置するかも併せて判断する必要があった。

## 決定

### 1. `int_order_details` は INNER JOIN で構築する

`stg_orders` の `customer_id` / `product_id` / `store_id` には `relationships` テストが既にかかっており、各 staging FK は対応するマスタに必ず存在する。したがって INNER JOIN しても OUTER JOIN しても結果集合の cardinality は変わらず、INNER の方が semantics が明示的（マスタ欠損は staging テストが落とす）。

### 2. `sales_amount` は `numeric(14,2)` にキャストする

`unit_price` は staging で `numeric(12,2)`、`quantity` は `int`。掛け算結果は Postgres 既定でも `numeric` になるが、明示キャストで scale を 2 桁に固定し下流マートでの再丸めを不要にする。`numeric(14,2)` は `quantity` 上限 10、`unit_price` 上限 9,990 を考えれば十分なヘッドルーム。

### 3. mart 3 本は `materialized: table`

- spec §8 の設計上 BI/分析用途。集計は GROUP BY を含み view にすると参照のたびに再計算される。
- 行数は max でも 1000（mart_customer_sales）と小さく、フル refresh も <1s でストレージ・実行時間ともに無視できる。
- `dbt_project.yml` の `marts: +materialized: table` 設定に揃える。

### 4. `customer_count` の DISTINCT 解釈

`mart_daily_sales.customer_count` は「その日に注文した実顧客数（重複除外）」と解釈し、`count(distinct customer_id)` を採用する。`order_count`（=`count(*)`）は注文行数（同じ顧客の複数注文を区別する）と分けて意味を持たせる。

### 5. `accepted_values` は `mart_product_sales.category` に適用する

spec §9.1 は built-in tests の 4 種を「実装する」とのみ指定し、対象列は明示していない。phase-05 で扱うデータの中で「取りうる値が静的に確定しているカラム」を探した結果:

- `mart_product_sales.category`: `scripts/generate_dummy_data.py` の `CATEGORIES = ["Food", "Beverage", "Household", "Beauty", "Electronics", "Stationery", "Apparel", "Toy"]` で固定列挙されており、`accepted_values` の対象として最も自然。
- `stg_stores.prefecture` も生成側では 47 都道府県のうち 20 件に固定されているが、ビジネス上は将来追加されうる「マスタ値」であり制約として固定するのは過剰。

よって `mart_product_sales.category` に `accepted_values` を 1 件だけ配置する。staging 段階で同じ制約を入れていないのは、staging はあくまで raw を写しただけの層で「ビジネス制約は下流で表現する」という方針に揃えたため（精緻化はマートの責務）。

## 検討した案

### `int_order_details` の結合方式

| 案 | 説明 | 採否 |
|---|---|---|
| A. INNER JOIN | マスタ欠損行は出さない | **採用** |
| B. LEFT JOIN (orders 起点) | マスタ欠損も保持 | 不採用（staging テストでマスタ欠損は捕捉済み） |

### mart の materialization

| 案 | 説明 | 採否 |
|---|---|---|
| A. `table` | 集計を物質化 | **採用** |
| B. `view` | 参照ごとに再集計 | 不採用（集計コスト/BI 用途） |
| C. `incremental` | 差分更新 | 不採用（スコープ外、行数小） |

### `accepted_values` 配置先

| 案 | 説明 | 採否 |
|---|---|---|
| A. `mart_product_sales.category` | 静的 CATEGORIES と整合 | **採用** |
| B. `stg_stores.prefecture` | 生成は 20/47 都道府県 | 不採用（マスタ拡張余地） |
| C. 無し（次 phase で追加） | spec §9.1 を未消化 | 不採用 |

## 採用理由

1. **INNER JOIN**: stg レイヤの `relationships` テストが「FK 完全性」を担保しているので OUTER の必要が無い。INNER の方が「事実テーブル＝結合済みのみ」という意図が明確。
2. **NUMERIC(14,2)**: 下流マートで再キャストせず一貫したスケールにできる。
3. **mart=table**: ローカル DWH のサイズ感（10k 行 fact）で集計コストよりも参照コスト最小化が優先。
4. **customer_count = COUNT(DISTINCT)**: 「ユニーク顧客数」と「注文件数」は別 KPI であり、両方を別カラムで提示する方が分析価値が高い。
5. **accepted_values @ mart_product_sales.category**: 生成スクリプト内に静的列挙が存在するカラムが他に無く、spec §9.1 を満たす最小・最自然な置き場所。

## 不採用案の理由

- `stg_stores.prefecture` の `accepted_values`: 都道府県マスタは将来 47 件全てに広がる可能性が高く、テストで lock すると拡張コストが上がる。
- mart の view 化: 集計再計算が毎参照で走るのは BI 文脈と相性が悪い。
- `incremental`: 行数が小さく、phase-05 のスコープにも入っていない。

## 関連する決定

- ADR-0005 (dbt 設定): schema 解決と dbt_utils 不採用方針。
- staging/schema.yml の `relationships` 形式（`arguments:` ネスト）に倣い、intermediate/schema.yml も同形式。
