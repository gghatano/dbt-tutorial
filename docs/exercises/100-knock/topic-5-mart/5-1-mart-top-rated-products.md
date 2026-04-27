# 5-1: mart_top_rated_products_100knock を grain と業務しきい値の宣言付きで再構築

## シナリオ

マーケ部門から「平均評価が高くて、かつレビュー数も十分な商品ランキングが
欲しい。Metabase に出して毎週見る」と依頼が来た。Exercise 02 で MVP の
`mart_top_rated_products` を一度作っているが、Topic ⑤ の方針 — **mart は
grain と業務ルールを冒頭で宣言する** — に沿って、100-knock 版として
再構築する。

ここで身につけるのは「mart を作るときに最初に書くべきはコメント (grain と
しきい値の宣言) であり、SQL はその次」という順序感覚。BI から見たときに
「この mart は 1 product 1 行で、`avg_rating>=4 AND review_count>=10` で
絞り込んだもの」とすぐ分かる状態を作る。

## 学べること

- mart 冒頭での **grain 宣言** (1 product 1 行) と **業務しきい値の宣言**
- staging / intermediate からの集約結果に対する WHERE フィルタの位置
- `int_product_reviews_100knock` を Topic ④ で実装済みと仮定した参照
- MVP `mart_top_rated_products` と node 名衝突を避ける `mart_<name>_100knock` 命名
- `manifest_lineage` で「依存する上流が宣言通りか」を採点 CI が見ること

## 前提

- Topic ② ③ ④ 完了:
  - `dbt/models/100-knock/topic-3/stg_products_100knock.sql`
  - `dbt/models/100-knock/topic-3/stg_reviews_100knock.sql` (Ex.01 / Topic ② で
    `raw_100knock.reviews` を投入し、Topic ③ で staging 化済みと想定)
  - `dbt/models/100-knock/topic-4/int_product_reviews_100knock.sql`
    (Topic ④ で集計層を実装済み。未実装なら `stg_reviews_100knock` から
    直接集計しても可。その場合は本問の lineage check の `upstream_must_include`
    は staging 側に読み替えること)
- main HEAD で MVP の `mart_product_sales` が動いている (この問の上流参照に使う)

## 入力データ

新規データなし。既存:

- `intermediate.int_product_reviews_100knock` (`product_id`, `review_count`,
  `avg_rating`, `last_review_date`)
- `staging.stg_products_100knock` (`product_id`, `product_name`, `category`)
- `marts.mart_product_sales` (MVP 側、`total_sales_amount` を引っ張る)

## 課題

### Step 1: mart を作る

`dbt/models/100-knock/topic-5/mart_top_rated_products_100knock.sql` を新規作成。

要件:

- ファイル先頭の **コメントで grain と業務しきい値を宣言**
  - `grain: 1 product 1 row`
  - `business filter: avg_rating >= 4.0 AND review_count >= 10`
- `int_product_reviews_100knock` を起点に、`stg_products_100knock` で master を
  enrich、MVP `mart_product_sales` で売上を付与
- WHERE フィルタは CTE 後段で `avg_rating>=4 AND review_count>=10`
- materialization は `table` (mart のデフォルト)、`schema='marts'` を明示

### Step 2: schema.yml に PK + 業務契約を書く

`dbt/models/100-knock/topic-5/schema.yml` (既存 or 新規) に
`mart_top_rated_products_100knock` の columns を宣言:

- `product_id`: `not_null` + `unique` (= grain の宣言と整合)
- `avg_rating`: `not_null`
- `review_count`: `not_null`

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_top_rated_products_100knock
../.venv/bin/dbt test --profiles-dir . --select mart_top_rated_products_100knock
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/mart_top_rated_products_100knock.sql` が存在
- [ ] manifest に `model.local_analytics.mart_top_rated_products_100knock` が登録
- [ ] 上流に `int_product_reviews_100knock` と `mart_product_sales` の両方が
      `depends_on` として現れる (manifest_lineage で確認)
- [ ] `dbt test --select mart_top_rated_products_100knock` が PASS
- [ ] `marts.mart_top_rated_products_100knock` の全行が `avg_rating>=4 AND
      review_count>=10` を満たす (sql_assert で 0 件確認)

## ヒント (詰まったら)

- **grain と filter を SQL の先頭にコメントで書く意味**: 6 ヶ月後に自分が
  読み返したとき、「この mart の 1 行が何を表すか」「なぜこの WHERE があるか」を
  即座に思い出せる。BI 担当が dbt docs を読むときも、`description:` だけでは
  伝えきれない設計意図が SQL 自身に残る。
- **`int_product_reviews_100knock` がまだない場合**: Topic ④ をまだ完了して
  いない学習者は、`stg_reviews_100knock` から直接 `count(*) / avg(rating)` で
  集計してもこの問の構造は満たせる。ただし lineage check の
  `upstream_must_include` が変わるので、自分の解答に合わせて grading.yaml を
  読み替える。
- **WHERE か HAVING か**: 集計を CTE で済ませてから WHERE をかけるパターンが
  読みやすい。`HAVING avg_rating>=4` でも同じ結果になるが、複数しきい値を
  追加する未来を考えると CTE 方式が拡張しやすい。
- **MVP `mart_product_sales` を ref する理由**: 100-knock 内で完結させるなら
  `int_order_details_100knock` から自前で売上集計してもよいが、本問の主眼は
  「grain の宣言」なので、依存先は MVP のものを再利用して節約。

## 解答例

詳細は [`5-1-mart-top-rated-products.solution.md`](5-1-mart-top-rated-products.solution.md) を参照。
