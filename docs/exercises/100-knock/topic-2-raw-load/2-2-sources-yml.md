# 2-2: `sources.yml` で raw 4 テーブルに dbt 上の論理名を貼る

## シナリオ

2-1 で `raw` schema に物理テーブルが 4 つ並んだ。次は dbt 視点でそこに **論理 source 名** を
与え、`source('<source_name>', 'customers')` として下流から参照できる状態を作る。

ここがあると、後で raw が S3 や BigQuery に置き換わっても、staging 以下は **物理スキーマを
1 つも知らないまま動き続けられる**。dbt の最初のレイヤー分離が効くのは、この `sources.yml`
の宣言地点だけ。

注意: MVP の `dbt/models/sources.yml` は触らない。Topic ② 専用の sources を
`dbt/models/100-knock/topic-2/sources.yml` に新規で作る。`name:` は MVP の `raw` と
被らないように学習者の判断で別名を付ける (例: `raw_100knock`)。

## 学べること

- `dbt/models/.../sources.yml` の最小構造 (`version: 2` → `sources:` → `tables:`)
- `name:` (論理) と `schema:` / `identifier:` (物理) の **写像関係**
- 同一物理 schema を複数の論理 source 名から参照する **名前空間設計**
- `dbt parse` で source 宣言が manifest に登録されることの確認

## 前提

- 2-1 完了: `raw.customers` / `raw.products` / `raw.stores` / `raw.orders` がロード済み
- MVP の `dbt/dbt_project.yml` / `dbt/profiles.yml` は触らない (それらは MVP 用)
- `dbt parse` が現状緑

## 入力データ

データ自体は不要 (この問は YAML 宣言のみ)。物理側の前提は 2-1 完了状態。

## 課題

### Step 1: ディレクトリを切る

```bash
mkdir -p dbt/models/100-knock/topic-2
```

### Step 2: `sources.yml` を書く

`dbt/models/100-knock/topic-2/sources.yml` を新規作成する。

最低限以下を含めること:

- `version: 2`
- `sources:` 配下に **MVP の `name: raw` と衝突しない論理 source 名** を 1 つ宣言
  (推奨: `name: raw_100knock`、`schema: raw` で物理は同じ raw schema を指す)
- `tables:` に `customers` / `products` / `stores` / `orders` の 4 つ
- 各 table の `columns:` は最低でも `name:` を列挙 (description は次の問 2-3 で書く)

### Step 3: dbt parse で構文チェック

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
```

`Done.` で抜ければ OK。manifest に `source.local_analytics.raw_100knock.customers` が登録される。

### Step 4: source 一覧で見える状態を確認

```bash
../.venv/bin/dbt ls --profiles-dir . --select source:raw_100knock.*
# => source:local_analytics.raw_100knock.customers
#    source:local_analytics.raw_100knock.products
#    source:local_analytics.raw_100knock.stores
#    source:local_analytics.raw_100knock.orders
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-2-sources-yml.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-2/sources.yml` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest に source `customers` が登録されている (`source.local_analytics.raw_100knock.customers`)
- [ ] manifest に source `orders` が登録されている (`source.local_analytics.raw_100knock.orders`)
- [ ] 4 テーブル全てが宣言されている

## ヒント (詰まったら)

- **`name:` 衝突**: dbt は同一プロジェクト内で source の `name:` がユニークでないと parse 時に失敗する。
  MVP の `dbt/models/sources.yml` が `name: raw` を既に使っているので、本問では別名 (`raw_100knock` 等) にする。
- **`schema:` と `identifier:`**: `schema:` は物理 schema 名、`identifier:` はテーブル名 (省略時は `name:` と同じ)。
  本問は `identifier:` を省略して `name:` をそのまま物理テーブル名と一致させる構成で OK。
- **下流から参照する書き方**: 次のトピック (③ staging) では `{{ source('raw_100knock', 'customers') }}` で参照する。
  この **論理名** が `sources.yml` の `name:` で固まる。
- **何故 source を別ファイルに**: 既存 MVP の `sources.yml` を編集すると MVP の dbt run が壊れるリスクがある。
  Topic ②専用フォルダに切ることで「自分の練習」と「動いている MVP」を物理的に分離する設計。
- **manifest に出ない時**: `dbt parse` で警告が出ていたら、`yml` のインデント or `version: 2` の有無を確認。
  `dbt-core` は YAML 1.2 を期待しないので、tab を混ぜると沈黙して落ちることがある。

## 解答例

詳細は [`2-2-sources-yml.solution.md`](2-2-sources-yml.solution.md) を参照。
