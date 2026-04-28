# 2-2 解答例

## dbt/models/100-knock/topic-2/sources.yml

```yaml
version: 2

# Topic ② / Q2 — 100-knock 専用の raw source 宣言。
# MVP の dbt/models/sources.yml は `name: raw` を使っているので、
# ここでは `raw_100knock` という別名で同じ物理 schema (raw) を覗く。
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
          - name: customer_name
          - name: email
          - name: created_at

      - name: products
        description: "商品マスタ (100 行) — Topic ① 1-2 由来"
        columns:
          - name: product_id
          - name: product_name
          - name: category
          - name: unit_price

      - name: stores
        description: "店舗マスタ (20 行) — Topic ① 1-3 由来"
        columns:
          - name: store_id
          - name: store_name
          - name: prefecture

      - name: orders
        description: "注文トランザクション (10,000 行) — Topic ① 1-4〜1-7 由来"
        columns:
          - name: order_id
          - name: order_date
          - name: customer_id
          - name: product_id
          - name: store_id
          - name: quantity
          - name: unit_price
```

**ポイント**:

- `name: raw_100knock` で論理 source 名を確定。下流からは `{{ source('raw_100knock', 'customers') }}`
  で参照される。MVP の `name: raw` と物理 schema (`raw`) は同じだが、**dbt 視点では別の論理 source**。
  これで MVP の lineage を汚さずに 100-knock 用の DAG を並走できる。
- `database: analytics` は profiles.yml の `dbname` と同じ。**省略しても動く** が、明示しておくと
  マルチ DB 環境で何を見ているかが yaml だけで分かる。
- `schema: raw` が **物理境界**。dbt は manifest にこの値を持ち、staging が ref した時に `raw.customers`
  という物理テーブル名を組み立てる。
- `columns:` は `name:` だけ列挙。description / tests / freshness は **後の問で段階的に追加** する設計。
  ここで全部書いてしまうと 2-3 (description) / 2-4 (freshness) の演習がただのコピペになる。
- ファイルの置き場は `dbt/models/100-knock/topic-2/` 配下。`dbt_project.yml` の `model-paths: ["models"]`
  に含まれているので、サブディレクトリは自由に切れる。

## 実行ログ例

```
$ cd dbt && ../.venv/bin/dbt parse --profiles-dir .
12:30:01  Running with dbt=1.x.x
12:30:01  Registered adapter: postgres=1.x.x
12:30:01  Found 5 models, 8 tests, 4 sources, ...
12:30:01  Done.

$ ../.venv/bin/dbt ls --profiles-dir . --select source:raw_100knock.*
source:local_analytics.raw_100knock.customers
source:local_analytics.raw_100knock.products
source:local_analytics.raw_100knock.stores
source:local_analytics.raw_100knock.orders
```

## 解説まとめ

- **物理 ↔ 論理の分離**: `sources.yml` 1 ファイルだけが物理 schema/table 名を知っている。下流の staging
  以下は **物理を一切知らない** 状態を保てる。これが「raw が S3 に変わっても staging が無傷」の正体。
- **`name:` はユニーク制約**: dbt project 全体で source の `name:` は重複不可。だから複数 sources.yml
  を並走させる時は **必ず別名** (`raw` / `raw_100knock` / `raw_exercise` 等) を使う。
- **MVP を壊さない設計**: 既存ファイル (`dbt/models/sources.yml`) を編集する派 vs 新規ファイルを作る派。
  100-knock では後者を採用。学習者の試行錯誤が MVP の dbt build を壊さないことを最優先。
- **段階的に肉付ける**: 2-2 はガワだけ。次の 2-3 で description、2-4 で freshness、2-9 (sibling agent 担当)
  で tests を追加する。**1 問 1 概念** で yaml の各キーの意味を体に入れる狙い。
- **manifest との対応**: `source.local_analytics.raw_100knock.customers` のドット区切りは
  `source.<dbt_project_name>.<source_name>.<table_name>` の規約。`local_analytics` は dbt_project.yml の
  `name:` から来ている。
