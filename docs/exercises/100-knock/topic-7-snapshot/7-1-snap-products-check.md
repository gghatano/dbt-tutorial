# 7-1: snap_products を check strategy で書く

## シナリオ

`raw_100knock.products` の `unit_price` はマーチャンダイザの判断で時々改定される。
改定すると raw 側は **新しい値で上書き** されるため、過去の注文に「当時の価格」を
紐づける手段が一切無くなってしまう。これを救うのが dbt snapshot で、対象 source を
SCD Type-2 として履歴化し、`dbt_valid_from` / `dbt_valid_to` 列で「いつから
いつまで有効だったか」を持たせる。

Topic ⑦ の最初の 1 問は、その snapshot ファイルを `check` strategy で書き、
1 回目の `dbt snapshot` を成功させることに集中する。strategy の選定理由・
custom schema macro との相性・snapshot 専用 schema を事前に手動作成する理由まで
ここで一気に押さえる。

## 学べること

- `{% snapshot %}` ブロックの構文 (config / SELECT 本体)
- `strategy='check'` + `check_cols=['unit_price']` の宣言意味
- `unique_key='product_id'` で「行同一性」を定義
- `target_schema='snapshots'` と custom `generate_schema_name` macro の組み合わせ
- snapshot 用 schema を **事前に手動作成** する運用 (Terraform 管理外)
- snapshot 命名規約 `snap_<name>_100knock` で MVP との衝突回避

## 前提

- Topic ② 2-1〜2-2 完了: `raw_100knock` source 宣言済み、`raw.products` (100 行) 投入済み
- main HEAD MVP が動く (`dbt run` / `dbt test` 緑)
- snapshots schema が Postgres 上にまだ無い状態 (Step 0 で作成)

## 課題

### Step 0: snapshots schema を作る

Terraform は raw / staging / intermediate / marts の 4 schema しか作っていない。
snapshot を `snapshots` schema に置くには事前に手で作る:

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -c "CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;"
```

本番運用なら Terraform に schema を追加するべきだが、本演習では学習目的で
手動作成にとどめる。

### Step 1: snapshot 定義を書く

`dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql` を新規作成。

要件:

- `{% snapshot snap_products_100knock %}` ブロック (snapshot 名 = ファイル名)
- 上部 `config()` で:
  - `target_schema='snapshots'`
  - `unique_key='product_id'`
  - `strategy='check'`
  - `check_cols=['unit_price']`
- SELECT 本体は `source('raw_100knock', 'products')` から `product_id`,
  `product_name`, `category`, `unit_price` の 4 列を投影
- `{% endsnapshot %}` で閉じる

### Step 2: 1 回目の `dbt snapshot`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
```

完了の見え方:

- `snapshots.snap_products_100knock` テーブルが作られて `count(*) = 100`
- `dbt_valid_from` は今の timestamp、`dbt_valid_to` は **全 100 行で NULL** (最新行)
- `dbt_scd_id` も自動で全行に振られる

### Step 3: psql で確認

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE dbt_valid_to IS NULL) AS active
FROM snapshots.snap_products_100knock;
-- total=100, active=100
```

## 完了条件

- [ ] `dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest に `snapshot.local_analytics.snap_products_100knock` が登録される
- [ ] `dbt snapshot --select snap_products_100knock` が PASS=1 で完了
- [ ] `snapshots.snap_products_100knock` が 100 行ある

## ヒント (詰まったら)

- **`snapshot is missing schema_name` エラー**: `target_schema='snapshots'` を
  config に必ず指定する。`dbt_project.yml` の `snapshots:` 一括指定でも可だが、
  本問はファイル側に書く方針 (7-10 で project 側に集約する)。
- **schema が `<target>_snapshots` になる**: 本リポジトリの `dbt/macros/get_custom_schema.sql`
  が `generate_schema_name` を override して「`custom_schema_name` をそのまま返す」
  仕様。なので `target_schema='snapshots'` がそのまま `snapshots` schema に物理化される
  (schema 自体は Step 0 で作成済み)。
- **strategy の選択**: `timestamp` は source に `updated_at` 列があれば最も
  効率的だが、`raw_100knock.products` には無い。`check` strategy なら任意の列の
  値変化を検知してくれる。`check_cols=['unit_price']` のように **追跡したい列を
  最小限** にすると無駄な履歴化を抑えられる。
- **snapshot 名の衝突**: `snap_products` だと将来 MVP `dbt/snapshots/snap_products.sql`
  (Ex.04) と node 名が衝突する可能性がある。100-knock 演習であることを示す
  `_100knock` suffix で名前空間を切る。
- **source('raw_100knock', 'products')**: `raw` (MVP) ではなく `raw_100knock`
  (Topic ② 2-2 で宣言した名前) を使う。物理 schema は同じ `raw` だが、dbt 上の
  論理 source 名は別。

## 解答例

詳細は [`7-1-snap-products-check.solution.md`](7-1-snap-products-check.solution.md) を参照。
