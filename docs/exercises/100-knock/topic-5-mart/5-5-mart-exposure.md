# 5-5: mart_daily_sales_100knock に exposure: で Metabase ダッシュボードを宣言

## シナリオ

5-3 / 5-4 で `mart_daily_sales_100knock` に **列契約** (data type) を宣言した。
これで「列を勝手に変えると build red」までは守れる。

しかし dbt 側からはまだ「**この mart は誰が使っているか**」が見えない。
誰かが `mart_daily_sales_100knock` を削除した瞬間に、
Metabase の "Daily Sales" ダッシュボードが消える。dbt の lineage に
**BI ダッシュボードを終端ノードとして宣言** することで、`dbt docs` の
DAG 上で `mart_*_100knock` → `Daily Sales Dashboard` のエッジが描かれ、
影響範囲が機械可読になる。

これが Topic ⑤ で揃える 3 点セットの最後 — **「誰が使っているかの宣言」**。

## 学べること

- `exposures:` の YAML 宣言フォーマット (Ex.06 の 100-knock 版)
- `depends_on: [ref('mart_*_100knock')]` で dbt DAG に組み込む
- `dbt parse` で manifest に `exposure.local_analytics.<name>` が出る
- `dbt ls --select +exposure:<name>` で「ダッシュボードが依存する全 model」が出る
- mart は **列契約 + grain + exposure** の 3 点セットで初めて完成

## 前提

- 5-1 / 5-2 / 5-3 完了:
  - `mart_top_rated_products_100knock` (5-1)
  - `mart_monthly_sales_by_category_100knock` (5-2)
  - `mart_daily_sales_100knock` (5-3, contract enforced)
- main HEAD で MVP の Metabase が動いている (動いていなくても本問は parse で
  完結するので問題なし)

## 入力データ

なし。既存の 3 mart を参照するだけ。

## 課題

### Step 1: exposures.yml を作る

`dbt/models/100-knock/topic-5/exposures.yml` を新規作成。

要件:

- `version: 2` ヘッダ
- 1 つの exposure:
  - `name: daily_sales_dashboard_100knock` (MVP の `sales_overview` と
    衝突回避のため `_100knock` suffix)
  - `type: dashboard`
  - `url:` (Metabase のダッシュボード URL。学習者の環境のものを書く。
    例: `http://localhost:3000/dashboard/3`)
  - `owner:` に `email:` と `name:`
  - `description:` 1〜2 行で何を可視化しているか
  - `maturity: medium`
  - `depends_on:` で 5-3 の `mart_daily_sales_100knock` を ref で参照
    (任意で 5-1 / 5-2 の mart も追加可)

### Step 2: parse で manifest に登録される

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
```

`target/manifest.json` に
`"exposure.local_analytics.daily_sales_dashboard_100knock"` が現れる。

### Step 3: 上流依存を ls で確認

```bash
../.venv/bin/dbt ls --profiles-dir . --select +exposure:daily_sales_dashboard_100knock
```

期待される出力 (順不同、最低限):

```text
source:raw_100knock.orders
source:raw_100knock.customers
source:raw_100knock.products
source:raw_100knock.stores
local_analytics.staging.stg_orders_100knock
local_analytics.staging.stg_customers_100knock
local_analytics.staging.stg_products_100knock
local_analytics.staging.stg_stores_100knock
local_analytics.intermediate.int_order_details_100knock
local_analytics.marts.mart_daily_sales_100knock
exposure:local_analytics.daily_sales_dashboard_100knock
```

「ダッシュボードを支える全 model + source」が一望できるのが exposure の本質。

### Step 4: docs で lineage を見る (任意)

```bash
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve --profiles-dir .
```

ブラウザで <http://localhost:8080> → lineage グラフから
`daily_sales_dashboard_100knock` ノードを探し、`mart_daily_sales_100knock`
からエッジが伸びていることを確認。

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/exposures.yml` が存在
- [ ] `dbt parse` が成功
- [ ] manifest に `exposure.local_analytics.daily_sales_dashboard_100knock` が登録
- [ ] exposure の `depends_on` に `model.local_analytics.mart_daily_sales_100knock`
      が含まれる (manifest_lineage で確認)
- [ ] `dbt ls --select +exposure:daily_sales_dashboard_100knock` で
      `mart_daily_sales_100knock` が列挙される

## ヒント (詰まったら)

- **exposure はモデルではない**: `dbt run` の対象ではない。`dbt build` でも
  実行されない。あくまで「DAG 上の終端メタデータ」。`dbt docs` と
  `dbt ls` で恩恵を受ける。
- **`depends_on` の書き方**: YAML 文字列の中に Jinja を書く:
  `- ref('mart_daily_sales_100knock')`。クオートに注意。
- **node 名衝突**: MVP の `dbt/models/exposures/exposures.yml` (Ex.06) で
  `sales_overview` という exposure があるため、本問は `_100knock` suffix を
  付ける。同じ name の exposure を 2 つ宣言すると dbt parse が `Found duplicate
  exposure` で落ちる。
- **配置場所**: `dbt/models/100-knock/topic-5/exposures.yml` 以外でも parse は
  通るが (例: `dbt/exposures/`)、100-knock 演習を 1 ディレクトリにまとめる
  方針に沿うのが望ましい。
- **URL を正しく書く意義**: lineage UI 上で exposure をクリックしたとき
  Metabase に飛べる。BI と dbt docs を相互リンクする運用にすると、
  「BI で気になる数字 → dbt の上流 model → SQL」の往復が早くなる。
- **5-1 / 5-2 の mart も入れる？**: `daily_sales_dashboard_100knock` という
  名前は日次売上に絞った想定なので `mart_daily_sales_100knock` だけで
  自然。複数 mart をまとめる場合は exposure 名を `kpi_overview_100knock` 等に
  リネームするのが筋。本問は 1 mart 依存で十分。

## 解答例

詳細は [`5-5-mart-exposure.solution.md`](5-5-mart-exposure.solution.md) を参照。
