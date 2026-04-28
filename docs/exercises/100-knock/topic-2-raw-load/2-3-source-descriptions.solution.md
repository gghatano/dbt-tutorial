# 2-3 解答例

## dbt/models/100-knock/topic-2/sources.yml (description 追加版)

```yaml
version: 2

# Topic ② / Q3 — 100-knock 専用 raw source 宣言、列ごとの description を追記。
# description は staging より上流 (raw レイヤー) に置く。staging 側は raw からの差分だけを語る。
sources:
  - name: raw_100knock
    description: "100-knock Topic ① で生成した CSV を 2-1 のローダーで投入した raw 層 (物理 schema = raw)"
    database: analytics
    schema: raw
    tables:
      - name: customers
        description: "顧客マスタ (1,000 行) — Topic ① 1-1 由来"
        columns:
          - name: customer_id
            description: "顧客の主キー (BIGINT)。1..1000 の連番。"
          - name: customer_name
            description: "顧客氏名 (日本語、Faker ja_JP 由来)。NULL 不可、ユニーク性は保証されない (同名別人あり)。"
          - name: email
            description: "顧客メールアドレス。Faker.unique.email() 由来でユニーク。NULL 不可。"
          - name: created_at
            description: "顧客登録日 (DATE)。基準日 2026-04-26 から過去 730 日のいずれか。"

      - name: products
        description: "商品マスタ (100 行) — Topic ① 1-2 由来"
        columns:
          - name: product_id
            description: "商品の主キー (BIGINT)。1..100 の連番。"
          - name: product_name
            description: "商品名 (日本語)。"
          - name: category
            description: "商品カテゴリ。'食品' / '日用品' / '衣料' / '家電' / '書籍' の 5 値 enum (Topic ① 1-2 で固定)。"
          - name: unit_price
            description: "商品単価 (円、NUMERIC(12,2))。Topic ① 1-2 の値域 100〜9990 円。"

      - name: stores
        description: "店舗マスタ (20 行) — Topic ① 1-3 由来"
        columns:
          - name: store_id
            description: "店舗の主キー (BIGINT)。1..20 の連番。"
          - name: store_name
            description: "店舗名 (日本語)。"
          - name: prefecture
            description: "店舗所在の都道府県 (47 都道府県のいずれか)。重複あり (同県に複数店舗)。"

      - name: orders
        description: "注文トランザクション (10,000 行) — Topic ① 1-4〜1-7 由来"
        columns:
          - name: order_id
            description: "注文の主キー (BIGINT)。1..10000 の連番。"
          - name: order_date
            description: "注文日 (DATE)。Topic ① 1-7 で 2025-01-01〜2026-04-30 の範囲に分散。"
          - name: customer_id
            description: "顧客への外部キー (raw_100knock.customers.customer_id)。Topic ① 1-6 で約 1% の休眠顧客を除外。"
          - name: product_id
            description: "商品への外部キー (raw_100knock.products.product_id)。"
          - name: store_id
            description: "店舗への外部キー (raw_100knock.stores.store_id)。"
          - name: quantity
            description: "注文数量 (個、INT)。1〜10。"
          - name: unit_price
            description: "注文時の単価 (円、NUMERIC(12,2))。Topic ① 1-5 で product_id から決定論的に算出 (同 product 同単価)。"
```

**ポイント**:

- description は **column の `name:` の直下** にネストする (tests と同階層)。これが dbt の標準。
- 最上流 (raw / source) で「この列が物理的に何か」を一度書ききる。staging 側は
  「raw から `lower(trim(...))` で正規化した」のような **差分** だけ書けば済む。**ドキュメントの DRY**。
- enum 列の description には **値域** を書くと、後で `accepted_values` テストを書く時の値リストが
  そのまま流用できる。
- 単位 (`円` / `個`) を必ず添える: 数値列の単位ミスは BI 側で気付くまで時間がかかる典型バグ。
  description で「円」と宣言しておけば、レビュアーが SQL を読まなくても誤りに気付ける。
- FK 列の description には参照先 (`raw_100knock.customers.customer_id`) を **論理名で** 書く。
  物理名 (`raw.customers`) を書くと、後で source 名を変えた時に description だけ古くなる罠。

## 実行ログ例

```
$ cd dbt && ../.venv/bin/dbt docs generate --profiles-dir .
12:40:01  Running with dbt=1.x.x
12:40:01  Found 5 models, 8 tests, 4 sources, ...
12:40:02  Concurrency: 4 threads
12:40:03  Building catalog
12:40:05  Catalog written to .../target/catalog.json
12:40:05  Done.

$ grep -c 'description' dbt/models/100-knock/topic-2/sources.yml
24

$ jq '.sources[]
       | select(.source_name=="raw_100knock")
       | .columns | to_entries[] | "\(.key): \(.value.description // "(none)")"' \
     dbt/target/manifest.json | head -10
"customer_id: 顧客の主キー (BIGINT)。1..1000 の連番。"
"customer_name: 顧客氏名 (日本語、Faker ja_JP 由来)。NULL 不可、..."
...
```

## 解説まとめ

- **description はコードのコメントより重い**: SQL のコメントは `dbt docs` に出ない。description は出る。
  チームで使うなら **description 側に書く** が原則。
- **最上流に書くのが正解**: 同じ説明を staging / mart で繰り返さない。raw に書けば catalog で
  各レイヤーから辿れる (dbt docs の lineage グラフ経由)。
- **`dbt docs generate` の中身**: `manifest.json` (構造) + `catalog.json` (DB から取った列メタ) を吐く。
  catalog は DB に問い合わせるので、2-1 のロードを済ませておかないと列の物理型が空になる。
- **チーム運用**: description は「列の意味」だけを書き、データ品質保証 (not_null / unique) は
  `tests:` で別途宣言する。「説明 = 人間用」「test = 機械用」の分業。
- **次の問への接続**: 2-4 ではこの sources.yml にさらに `freshness:` を追加する。
  description / freshness / tests が全部揃って、初めて source 宣言は **完全な契約** になる。
