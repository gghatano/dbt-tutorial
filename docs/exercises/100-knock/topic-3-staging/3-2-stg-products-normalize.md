# 3-2: stg_products で category 列を正規化

## シナリオ

raw 層の `products.category` には CSV 由来の表記揺れ
(`"Electronics"` / `"electronics "` / `"  ELECTRONICS"`) が混入する **可能性** がある。
今回 Topic ① 1-2 で生成した CSV は綺麗だが、運用に乗せた瞬間に手入力 / 別システム由来の
混入は避けられない。**staging 層で正規化を 1 度だけ書いておけば、下流の
`accepted_values` テストや GROUP BY 集計が表記揺れに振り回されない**。

ここで覚える「`lower(trim(...))` で文字列を正規化する」というイディオムは、
staging 全般で使い回せる定番。

## 学べること

- 文字列正規化の典型 `lower(trim(category))` を staging で 1 度だけ書く意義
- 正規化を staging に置く責務分離 (raw は CSV のまま、下流は綺麗な前提で集計)
- 正規化の効きを `sql_assert` で **データ側から** 検証するテスト設計
- staging で派生列を作るときの命名 (元列を残すか潰すか)

## 前提

- 3-1 完了: `stg_customers_100knock.sql` が動いており、Topic ③ の作法
  (config block + source 経由 + 明示 cast) を 1 本書いた経験がある
- Topic ② 2-1〜2-5 完了: `raw.products` 100 行 + `raw_100knock.products` source 宣言
- Topic ① 1-2 完了 (`category` は 5 値の enum で生成済み)

## 入力データ

`raw.products` (Topic ② で投入済み):

| 列              | 型      | 備考                                |
|-----------------|---------|-------------------------------------|
| `product_id`    | bigint  | PK 1..100                           |
| `product_name`  | text    | 商品名                              |
| `category`      | text    | 5 値の enum (Topic ① 1-2 で固定)    |
| `unit_price`    | int     | 100〜9990                           |

## 課題

### Step 1: staging model を作る

`dbt/models/100-knock/topic-3/stg_products_100knock.sql` を新規作成。

要件:

- `{{ config(materialized='view', schema='staging') }}`
- `source('raw_100knock', 'products')` から SELECT
- 全列に明示型 cast
- `category` 列は **`lower(trim(category))::text as category`** に置き換える
  (元列を上書きする / 元の表記を残したい場合は `category_raw` を残してもよい)
- `unit_price` は `numeric(10,2)` に持ち上げ (3-3 と整合)

### Step 2: schema.yml を補強

`dbt/models/100-knock/topic-3/schema.yml` に `stg_products_100knock` のブロックを
追記:

```yaml
  - name: stg_products_100knock
    description: "Type-cast staging view of raw.products. category は lower(trim(...)) で正規化済み。"
    columns:
      - name: product_id
        tests:
          - not_null
          - unique
      - name: category
        description: "正規化済み (lower + trim) のカテゴリ。"
        tests:
          - not_null
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run  --profiles-dir . --select stg_products_100knock
../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
```

### Step 4: 正規化が効いているか自前確認

```sql
-- 1. 表記揺れが残っていないか (このクエリの結果が 0 なら正規化成功)
SELECT count(*) FROM staging.stg_products_100knock
WHERE category != lower(trim(category));

-- 2. distinct カテゴリの一覧 (5 値で揃っているか目視)
SELECT category, count(*) FROM staging.stg_products_100knock
GROUP BY category ORDER BY 1;
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/stg_products_100knock.sql` が存在する
- [ ] manifest に `model.local_analytics.stg_products_100knock` が登録されている
- [ ] `dbt parse` 成功 / `dbt run --select stg_products_100knock` PASS
- [ ] `SELECT count(*) FROM staging.stg_products_100knock WHERE category != lower(trim(category))` が **0**
- [ ] `dbt test --select stg_products_100knock` が PASS

## ヒント (詰まったら)

- **`category` 列を上書きする vs 残す**: 「元の表記を分析で見たい」ケースが将来あるなら、
  `category::text as category_raw, lower(trim(category))::text as category` の 2 列出しも
  選択肢。今回は単純化のため `category` 1 列だけ持って、上書きでよい。
- **`trim()` は何を消すのか**: デフォルトでは前後の空白文字。タブや全角スペースは
  消えないので、必要なら `regexp_replace(category, '\s+', '', 'g')` のような正規表現が要る。
- **`lower()` の locale 依存**: Postgres の `lower()` は ASCII では確定動作だが、
  日本語カテゴリ (例: `"家電"`) は変化しない。今回 5 値が英字だけなら無視してよい。
- **正規化は staging で 1 度だけ**: 下流のマートで毎回 `lower(trim(...))` を書くのは
  DRY 違反 + パフォーマンス悪化。staging で 1 度書いて、以降は綺麗な前提で参照する。

## 解答例

詳細は [`3-2-stg-products-normalize.solution.md`](3-2-stg-products-normalize.solution.md) を参照。
