# 3-3: stg_orders で order_date / unit_price を明示 cast

## シナリオ

`raw.orders` は CSV から COPY された結果、列の型が DDL に依存している。特に
`order_date` (text 由来) と `unit_price` (整数で入った値) は、下流のマート
(`mart_daily_sales` のような日次集計 / `numeric` 演算) で型を厳密に揃えたい。
**staging で `date` / `numeric(10,2)` に持ち上げて、下流の SQL がカジュアルに
`SUM(unit_price)` や `WHERE order_date BETWEEN ...` を書けるようにする** のが今回のゴール。

このパターンは「staging で型契約を最終確定させる」 という考え方の典型例。

## 学べること

- `order_date::date` で text を date 型に持ち上げる
- `unit_price::numeric(10, 2)` で整数を「金額として正しい型」に持ち上げる
- なぜ金額に `numeric` を使うのか (`float` の丸め誤差を避ける)
- `information_schema.columns` を使って **staging が公開する型** を SQL で検証する
- staging contract の「型」 が manifest だけでなく実 DB の物理型として効いていることを採点で確認

## 前提

- 3-1 / 3-2 完了: Topic ③ の作法を 2 回書いた (config block / source / 明示 cast)
- Topic ② 2-1〜2-5 完了: `raw.orders` 10,000 行 + `raw_100knock.orders` source 宣言
- Topic ① 1-4, 1-5, 1-7 完了 (orders.csv が決定論的に生成済み)

## 入力データ

`raw.orders` (Topic ② で投入済み):

| 列              | raw 型      | staging で持ち上げる先 |
|-----------------|-------------|------------------------|
| `order_id`      | bigint      | bigint                 |
| `order_date`    | text        | **date**               |
| `customer_id`   | bigint      | bigint                 |
| `product_id`    | bigint      | bigint                 |
| `store_id`      | bigint      | bigint                 |
| `quantity`      | int         | int                    |
| `unit_price`    | int         | **numeric(10, 2)**     |

## 課題

### Step 1: staging model を作る

`dbt/models/100-knock/topic-3/stg_orders_100knock.sql` を新規作成。

要件:

- `{{ config(materialized='view', schema='staging') }}`
- `source('raw_100knock', 'orders')` から SELECT
- 全列に明示型 cast を書く
- `order_date::date as order_date`
- `unit_price::numeric(10, 2) as unit_price`
- 他の列も `::bigint` / `::int` で型を確定

### Step 2: schema.yml を補強

`dbt/models/100-knock/topic-3/schema.yml` に `stg_orders_100knock` ブロックを追記:

```yaml
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders. order_date は date, unit_price は numeric(10,2)。"
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      - name: order_date
        tests:
          - not_null
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run  --profiles-dir . --select stg_orders_100knock
../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
```

### Step 4: 物理型を SQL で確認

```sql
-- order_date が date 型になっているか
SELECT data_type FROM information_schema.columns
WHERE table_schema='staging' AND table_name='stg_orders_100knock'
  AND column_name='order_date';
-- => date

-- unit_price が numeric(10, 2) になっているか
SELECT data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema='staging' AND table_name='stg_orders_100knock'
  AND column_name='unit_price';
-- => numeric / 10 / 2
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/stg_orders_100knock.sql` が存在する
- [ ] manifest に `model.local_analytics.stg_orders_100knock` が登録されている
- [ ] `dbt parse` 成功 / `dbt run --select stg_orders_100knock` PASS
- [ ] `information_schema` で `order_date` の `data_type` が `date`
- [ ] `information_schema` で `unit_price` の `data_type` が `numeric` (precision=10, scale=2)
- [ ] `dbt test --select stg_orders_100knock` が PASS

## ヒント (詰まったら)

- **`'2025-08-13'::date` は OK だが `'2025/8/13'::date` は ERROR**: ISO 8601
  (`YYYY-MM-DD`) なら Postgres が確実に date 型に持ち上げてくれる。Topic ① 1-7 の
  生成スクリプトが `YYYY-MM-DD` で出していれば問題なし。
- **`numeric(10, 2)` の意味**: 「整数部含めて全 10 桁、うち小数 2 桁」。
  `99,999,999.99` まで表現可能。EC の単価には十分な精度。
- **金額に `float` / `double` を使ってはいけない**: 浮動小数は二進数表現の都合で
  `0.1 + 0.2 != 0.3` になる。集計を SUM したときに 1 円ずれる事故が起きる。
  金額は **必ず `numeric` / `decimal`**。
- **3-1 / 3-2 で書いた config を流用**: `{{ config(materialized='view', schema='staging') }}`
  は Topic ③ の全 model で同じ。コピペ OK。
- **`information_schema` クエリは Postgres の標準機能**: dbt は関係ない。
  「staging の物理型がどうなってるか」を直接見る癖をつけると、cast 忘れに即気付ける。

## 解答例

詳細は [`3-3-stg-orders-cast.solution.md`](3-3-stg-orders-cast.solution.md) を参照。
