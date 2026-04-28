# 3-6 解答例

## dbt/models/100-knock/topic-3/schema.yml

3-4 で作った `schema.yml` を以下のように **description を全 model / 全 column に追加** した形に書き換える。`tests:` 等は 3-4 / 3-5 で書いたものをそのまま残す。

```yaml
version: 2

models:
  - name: stg_customers_100knock
    description: |
      raw_100knock.customers を型 cast + 軽い正規化した staging view。
      下流 (intermediate / mart) はこのモデル経由でしか raw を参照しない。
    columns:
      - name: customer_id
        description: "顧客の主キー (bigint)。raw 由来の 1..1000 の連番。"
        tests:
          - not_null
          - unique
      - name: customer_name
        description: "顧客の表示名。Faker の ja_JP で生成された全角文字列。"
      - name: email
        description: "顧客メールアドレス。一意性は raw 側で保証されないため staging では unique 検査しない。"
      - name: created_at
        description: "顧客の登録日 (date 型)。タイムゾーン情報なし。"

  - name: stg_products_100knock
    description: "raw_100knock.products を型 cast + category を lower(trim()) 正規化した staging view。"
    columns:
      - name: product_id
        description: "商品の主キー (bigint)。raw 由来の 1..100 の連番。"
        tests:
          - not_null
          - unique
      - name: product_name
        description: "商品名。Faker 生成の文字列。表記揺れは正規化していない。"
      - name: category
        description: "商品カテゴリ。raw の表記揺れを lower(trim()) で吸収済み。5 値 enum。"
      - name: unit_price
        description: "商品単価 (numeric(12,2))。日本円・税抜き想定。3-5 の positive_value test で正値を保証。"
        tests:
          - not_null

  - name: stg_stores_100knock
    description: "raw_100knock.stores を型 cast した staging view。store の物理属性を保持する起点モデル。"
    columns:
      - name: store_id
        description: "店舗の主キー (bigint)。raw 由来の 1..20 の連番。"
        tests:
          - not_null
          - unique
      - name: store_name
        description: "店舗名。'店舗01_姓' のような形式で Topic ① で生成。"
      - name: prefecture
        description: "店舗所在地の都道府県。47 都道府県のいずれか。重複可。"

  - name: stg_orders_100knock
    description: |
      raw_100knock.orders を型 cast した staging view。トランザクション 1 行 = 1 注文。
      下流 mart の grain (注文単位 / 顧客単位 / 日次) を分岐させる起点。
    columns:
      - name: order_id
        description: "注文の主キー (bigint)。日付ごとに 10,000 件分のレンジ予約 (Topic ① 1-9 設計)。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date 型)。2025-01-01 〜 2026-04-30 の範囲。"
        tests:
          - not_null
      - name: customer_id
        description: "FK to stg_customers_100knock.customer_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers_100knock')
                field: customer_id
      - name: product_id
        description: "FK to stg_products_100knock.product_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_products_100knock')
                field: product_id
      - name: store_id
        description: "FK to stg_stores_100knock.store_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_stores_100knock')
                field: store_id
      - name: quantity
        description: "注文数量 (integer)。1..10 の範囲。3-5 の positive_value test で正値を保証。"
        tests:
          - not_null
      - name: unit_price
        description: "注文時点の商品単価 (numeric(12,2))。stg_products_100knock.unit_price と同期 (Topic ① 1-5 設計)。"
        tests:
          - not_null
```

**ポイント**:

- **description キー数**: 4 model + 17 column = **21 個** の description キーを追加。採点はこれを `grep -c '^\s*description:'` で確認。
- **model description は 1〜2 行**: テーブルが「何を表すか」「どこから来てどこへ流れるか」を書く。長すぎるとカタログサイトで折りたたまれて読まれない。
- **FK 列は `FK to xxx` を必ず明記**: `customer_id` の説明が「顧客 ID」だけだと「どの customer table か」が docs から判別できない。staging モデルが複数あるプロジェクトでは特に重要。
- **金額列の単位を書く**: `unit_price: 1000` が「1000 円」なのか「1000 銭」なのかは列名から読み取れない。**通貨 + 桁数 + 税込/税抜** の 3 点を書く。
- **block scalar (`|`)**: 改行を含む長文は `description: |` で書くと YAML パーサが改行を保持する。1 行なら不要。

## 実行例

```
$ cd dbt
$ dbt parse --profiles-dir .
12:00:00  Found 8 models, 4 sources, 21 tests, ...

$ dbt docs generate --profiles-dir .
12:00:05  Building catalog
12:00:08  Catalog written to .../target/catalog.json

$ python3 -c "
import json
with open('target/manifest.json') as f:
    m = json.load(f)
for nid, n in m['nodes'].items():
    if 'stg_' in nid and '100knock' in nid:
        print(nid, '->', n.get('description', '')[:60])
"
model.local_analytics.stg_customers_100knock -> raw_100knock.customers を型 cast + 軽い正規化した staging view
model.local_analytics.stg_products_100knock -> raw_100knock.products を型 cast + category を lower(trim()) 正規化した staging view
model.local_analytics.stg_stores_100knock   -> raw_100knock.stores を型 cast した staging view
model.local_analytics.stg_orders_100knock   -> raw_100knock.orders を型 cast した staging view

$ grep -c '^\s*description:' models/100-knock/topic-3/schema.yml
21
```

## 解説まとめ

- **なぜ description？**: `manifest.json` は「機械が読むカタログ」、docs サイトは「人間が読むカタログ」。test は前者、description は後者の責務。両方ないと「test は通るが意味不明な model」が量産される。
- **column description は本気でやる**: テーブル description が雑でも列名から推測できることは多い。だが column description が無いと「FK 関係」「単位」「null の意味」が誰にも伝わらない。staging こそ「列の意味を真面目に書く最初で最後の場所」。
- **description は git diff で見える**: docs サイトを開かなくても、PR レビュー時に description の追加が diff に出る。「列が増えた」だけでなく「列の意味が変わった」もレビュー対象にできる。
- **manifest.json の description フィールド**: `dbt parse` で `nodes[<id>].description` (model 全体) と `nodes[<id>].columns[<col>].description` (列ごと) の 2 階層に格納される。manifest を読む下流ツール (datafold / Elementary / dbt docs サイト) が全てここを起点にする。
- **`dbt docs serve` で読める**: `cd dbt && dbt docs serve --profiles-dir .` で localhost:8080 にカタログが立つ。description が乗っていれば日本語で説明が読める。
