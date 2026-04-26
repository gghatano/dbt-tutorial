# task-002: generate_dummy_data.py

- Phase: 03
- Status: Done
- Owner: -
- Depends on: -（実装はrequirements.txtに依存しない、実行は依存）
- Parallelizable with: phase-03/task-001

## 目的
Faker で再現性ある4種のCSVを生成する。

## 入力 / 前提
- spec §5 / §11.1

## 成果物
- `scripts/generate_dummy_data.py`
- 実行後: `data/raw/customers.csv`(1,000) / `products.csv`(100) / `stores.csv`(20) / `orders.csv`(10,000)

## 受入条件
- 同一seedで2回実行し、CSVの内容が完全一致
- 件数がspec通り
- orders は customers/products/stores の id を参照（外部キー整合）
- products に `category` 列を含む（mart_product_sales で使用）
- orders に `order_date`, `quantity`, `unit_price` を含み、quantity > 0, unit_price > 0
- customers に `customer_name` を含む

## 実装メモ / 判断ログ
- seed: `Faker.seed(42)`, `random.seed(42)`、加えて `random.Random(42)` をローカルRNGとして併用
- order_date: 過去365日間でランダム
- unit_price: products から参照（orders.unit_priceは生成時点のスナップショット）
- ロケールは `ja_JP`（日本語名）デフォルト
- **reference date `2026-04-26` を採用**: spec の "現在日"（task実装日）に合わせ、`datetime.today()` ではなく固定日にすることで実行日に依存しない byte-identical な出力を保証する。
- **locale `ja_JP` 選定理由**: 顧客名・店舗名・店舗所在地（都道府県）が日本語マスタになる前提（spec §5 の "顧客マスタ/店舗マスタ"）。Faker `ja_JP` で `name()` / `last_name()` を生成。
- **unit_price スナップショット**: spec §11.1 の `Fakerで...注文データを生成する` と §8.3 の `sales_amount = quantity * unit_price` 仕様から、orders 側にも `unit_price` 列を保持。products からのスナップショットとして orders 生成時に `price_lookup[product_id]` で複製。後日 products の単価が変わっても過去注文金額が壊れない（FK モデルのスナップショット原則）。
- **customer_id を 1-indexed**: SQL/PK 慣習に揃え、`range(1, NUM+1)` で連番を保証。orders 側の FK 検査時に「ユニーク値の最大が `NUM_CUSTOMERS` 以下」だけ見れば整合チェックが済むため検証コストが低い。
- **products.unit_price は 100〜9,990 円の 10 円刻み**: spec で型のみ指定（正の数値）。リアルさより range の決定性を優先し `randint(10, 999) * 10`。
- **products.product_name は `{Faker.word()}_{id:03d}`**: locale `ja_JP` の `word()` だけでは重複しうるため、id を suffix にして UNIQUE を担保。
- **stores.store_name は `店舗{id:02d}_{Faker.last_name()}`**: 同上、id suffix で UNIQUE 担保。
- **prefectures は北海道〜長野の 20 件のみ列挙**: stores が 20 行 / 47 都道府県のサブセットでよい（spec §5 で内容指定なし）。
- **created_at / order_date は ISO 文字列で書き出し**: pandas の datetime serializer ではなく明示的な `date.isoformat()` を使うことで OS / pandas バージョン差で format が揺れない。
- **CSV エンコーディング `utf-8` (BOM 無し)**: spec §11.1 で指定なし、PostgreSQL の `COPY ... ENCODING 'UTF8'` と整合する素の utf-8 に統一。

## 実行ログ

### 行数（ヘッダ含む `wc -l`）

```
    1001 data/raw/customers.csv
   10001 data/raw/orders.csv
     101 data/raw/products.csv
      21 data/raw/stores.csv
```

データ行はそれぞれ customers=1,000 / products=100 / stores=20 / orders=10,000 で spec §5 と一致。

### 決定性（`shasum -a 256` を 2 回実行して比較）

run1 と run2 のハッシュが完全一致。

```
4c210fac43e7b6290f104463549684a01bbcad80f14a96f4c3a1092d1c4d6692  data/raw/customers.csv
9d4e3330e3039f54e869544d7f5672a4ea727b41fc5f5cc32833b70137c93679  data/raw/orders.csv
ce14a5bd87e62c4ae91d55d94b09263d25e7df50a88b56fd52ea5e9a2ede8f6d  data/raw/products.csv
7cb6b59e26c02c889a33bff956396d0bbe21785aea82013301c0b21f852c1695  data/raw/stores.csv
```

`diff run1_hashes run2_hashes` → 差分なし。

### FK 整合性（orders → customers / products / stores）

```
orders.customer_id  unique=1000  max=1000  (<= 1000 OK)
orders.product_id   unique=100   max=100   (<= 100  OK)
orders.store_id     unique=20    max=20    (<= 20   OK)
orders.quantity     min=1                 (> 0     OK)
products.unit_price min=250               (> 0     OK)
```

すべての FK が master 側の id 範囲内に収まっており、quantity / unit_price の正値制約も満たしている。

### 各 CSV の先頭 3 行（`head -4`）

`customers.csv`

```
customer_id,customer_name,email,created_at
1,佐藤 淳,tomoyatakahashi@example.org,2024-07-11
2,林 篤司,suzukitomoya@example.net,2026-01-02
3,木村 裕樹,lito@example.com,2026-04-01
```

`products.csv`

```
product_id,product_name,category,unit_price
1,トス_001,Apparel,1270
2,ピック_002,Beauty,6730
3,追放する_003,Household,9400
```

`stores.csv`

```
store_id,store_name,prefecture
1,店舗01_佐藤,富山県
2,店舗02_山田,福井県
3,店舗03_佐藤,青森県
```

`orders.csv`

```
order_id,order_date,customer_id,product_id,store_id,quantity,unit_price
1,2025-10-25,384,56,5,4,1050
2,2025-07-29,422,73,6,3,8960
3,2026-01-27,81,79,13,10,7240
```

### 検証環境

- 一時 venv: `uv venv --python 3.12 .venv-task002`（コミット前に `rm -rf` 済み）
- インストール: `faker==33.3.1`, `pandas==2.2.3`（spec §12 / §2 に準拠）
- 静的解析: `python3 -c "import ast; ast.parse(...)"` → `parse OK`
