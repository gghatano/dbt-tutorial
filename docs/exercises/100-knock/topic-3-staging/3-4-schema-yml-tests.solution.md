# 3-4 解答例

## dbt/models/100-knock/topic-3/schema.yml (完成形)

```yaml
version: 2

models:
  # ----- Customers -----
  - name: stg_customers_100knock
    description: "Type-cast staging view of raw.customers (100-knock topic-3)."
    columns:
      - name: customer_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: customer_name
        description: "顧客名 (Faker ja_JP)。"
      - name: email
        description: "顧客メール (raw 1-1 で unique 保証)。"
        tests:
          - not_null
      - name: created_at
        description: "登録日 (date)。"
        tests:
          - not_null

  # ----- Products -----
  - name: stg_products_100knock
    description: "Type-cast staging view of raw.products. category は lower(trim(...)) で正規化済み。"
    columns:
      - name: product_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: product_name
      - name: category
        description: "正規化済み category (lower + trim)。"
        tests:
          - not_null
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null

  # ----- Orders -----
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders。order_date は date, unit_price は numeric(10,2)。"
    columns:
      - name: order_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date)。"
        tests:
          - not_null
      - name: customer_id
        description: "FK → stg_customers_100knock.customer_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers_100knock')
                field: customer_id
      - name: product_id
        description: "FK → stg_products_100knock.product_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_products_100knock')
                field: product_id
      - name: store_id
        description: "FK → stg_stores_100knock.store_id (3-6 で sibling 問題が定義予定)。"
        tests:
          - not_null
      - name: quantity
        description: "数量 (int)。"
        tests:
          - not_null
      - name: unit_price
        description: "単価 (numeric(10,2))。"
        tests:
          - not_null
```

**ポイント**:

- **PK には `not_null` + `unique` のセット** で「主キーらしさ」を宣言する。
  `not_null` だけだと NULL は弾けるが重複は素通し、`unique` だけだと NULL が
  複数行入ってしまう (Postgres の `UNIQUE` は NULL 複数許容)。**両方セット**が staging の作法。
- **FK には `not_null` + `relationships` のセット**: `not_null` だけだと値はあるが
  親に存在しないかもしれない、`relationships` だけだと NULL は素通しになる。
  ECサイトの `orders.customer_id` は NULL が許されない (注文には必ず顧客がいる) ので、
  両方セット。
- **`store_id` の relationships は意図的に省略**: 3-6 で `stg_stores_100knock` を
  sibling agent が作るまでは参照先がない。dbt は manifest に存在しない `ref()` を
  見つけるとビルド時にエラーで落ちるので、ここでは `not_null` だけにとどめる。
  3-6 完了後に `relationships` を追記する流れ。
- **`description:` を全列に**: docs generate 時にカタログとして読める。
  staging contract が「コードで表現された **データ仕様書**」になる。
- **`arguments:` ネスト形式**: dbt 1.11+ で `relationships` / `accepted_values` の
  パラメータ渡しが `arguments:` 配下に整理された。古い形式 (トップレベル `to:`) も
  動くが、新規プロジェクトでは新形式に揃える。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 73 data tests ...

$ ../.venv/bin/dbt test --profiles-dir . --select stg_customers_100knock stg_products_100knock stg_orders_100knock
1 of N PASS not_null_stg_customers_100knock_customer_id ........... [PASS]
2 of N PASS unique_stg_customers_100knock_customer_id ............. [PASS]
3 of N PASS not_null_stg_customers_100knock_email ................. [PASS]
4 of N PASS not_null_stg_customers_100knock_created_at ............ [PASS]
5 of N PASS not_null_stg_products_100knock_product_id ............. [PASS]
6 of N PASS unique_stg_products_100knock_product_id ............... [PASS]
7 of N PASS not_null_stg_products_100knock_category ............... [PASS]
8 of N PASS not_null_stg_products_100knock_unit_price ............. [PASS]
9 of N PASS not_null_stg_orders_100knock_order_id .................. [PASS]
10 of N PASS unique_stg_orders_100knock_order_id ................... [PASS]
11 of N PASS not_null_stg_orders_100knock_order_date ............... [PASS]
12 of N PASS not_null_stg_orders_100knock_customer_id .............. [PASS]
13 of N PASS relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_ [PASS]
14 of N PASS not_null_stg_orders_100knock_product_id ................ [PASS]
15 of N PASS relationships_stg_orders_100knock_product_id__product_id__ref_stg_products_100knock_ [PASS]
16 of N PASS not_null_stg_orders_100knock_store_id .................. [PASS]
17 of N PASS not_null_stg_orders_100knock_quantity .................. [PASS]
18 of N PASS not_null_stg_orders_100knock_unit_price ................ [PASS]
Done. PASS=18 WARN=0 ERROR=0 SKIP=0 TOTAL=18
```

## わざと壊して FAIL を体感する

```sql
-- FK を破壊 (customers に存在しない customer_id をセット)
UPDATE raw.orders SET customer_id = 99999 WHERE order_id = 1;
```

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... PASS ...
N of M FAIL 1 relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_ [FAIL 1]
... 
Failure in test relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_
  Got 1 result, configured to fail if != 0
```

戻す:

```sql
UPDATE raw.orders SET customer_id = 1 WHERE order_id = 1;
```

## 解説まとめ

- **schema.yml はデータ契約の宣言面**: SQL ファイル (`stg_*.sql`) が
  「物理的な変換」 を書く面なら、`schema.yml` は「**データが満たすべき不変条件**」を
  YAML で宣言する面。両方セットで staging contract が完成する。
- **PK セット (`not_null` + `unique`)**: NULL を許す UNIQUE / 重複を許す NOT NULL の
  抜け穴を塞ぐ二段構え。staging で必ず両方付ける。
- **FK セット (`not_null` + `relationships`)**: 「FK は親に必ずいる」 を **dbt が
  実 SQL で検査** する。raw への CSV 投入ミスや、source 系のデグレを **下流の集計
  バグになる前に** stagingで止める。
- **`relationships` の SQL 展開**: dbt は内部で
  `SELECT child.fk FROM child LEFT JOIN parent ON ... WHERE parent.pk IS NULL` を
  生成する。1 行でも返れば test FAIL。学習者は SQL を書かずに **YAML 4 行** で済む。
- **generic test の優位性**: `not_null` / `unique` / `relationships` /
  `accepted_values` は dbt 組み込みの **generic test**。同じロジックを別の列に
  繰り返し使えるので、singular test (個別 SQL ファイル) より圧倒的に省コード。
  自作 generic test は 3-5 で扱う。
- **schema.yml が docs を兼ねる**: `description:` を書くと `dbt docs generate` で
  カタログ化される。データ基盤の「セルフサービス化」 (アナリストが自分で意味を
  調べられる) の出発点になる。
