# Exercise 06 解答例

## Step 1: `dbt/models/exposures/exposures.yml`

```yaml
version: 2

exposures:
  - name: sales_overview
    label: "Sales Overview (Metabase)"
    type: dashboard
    url: http://localhost:3000/dashboard/2
    maturity: medium
    description: |
      Metabase dashboard `Sales Overview`.
      Three cards backed by daily / customer / product sales marts.
      Bootstrapped by scripts/metabase_bootstrap.py.

    owner:
      name: Local Admin
      email: admin@local.test

    depends_on:
      - ref('mart_daily_sales')
      - ref('mart_customer_sales')
      - ref('mart_product_sales')
```

**ポイント**:

- `name` は dbt graph 上の識別子で、英数 / underscore のみ。`label` が UI 上に表示される人間向けの名前。
- `type` は `dashboard` / `notebook` / `analysis` / `ml` / `application` から選ぶ。BI ダッシュボードは `dashboard`。
- `url` は exposure ノードをクリックしたときに開く先。Metabase の dashboard ID は環境ごとに変わるので、`scripts/metabase_bootstrap.py` の最後の出力を見て合わせる。
- `depends_on` 内の `ref()` は **文字列内の Jinja 式** として評価される。dbt がパース時に展開する。

## Step 2: parse 確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# 04:32:11  Running with dbt=1.11.8
# 04:32:11  Registered adapter: postgres=1.10.0
# 04:32:11  Found 1 exposure, 8 models, 4 sources, 4 snapshots, ... (count varies)
# 04:32:11  Performance info: ...
```

`Found 1 exposure` が出れば構文 OK。`target/manifest.json` を確認:

```bash
grep -o '"exposure.local_analytics.sales_overview"' target/manifest.json | head -1
# "exposure.local_analytics.sales_overview"
```

## Step 3: lineage 生成と確認

```bash
../.venv/bin/dbt docs generate --profiles-dir .
# 04:33:01  Building catalog
# 04:33:02  Catalog written to .../dbt/target/catalog.json

../.venv/bin/dbt docs serve --profiles-dir .
# Serving docs at 0.0.0.0:8080
# Press Ctrl+C to exit.
```

ブラウザで <http://localhost:8080> → 左下の lineage graph アイコン → 検索ボックスに `+exposure:sales_overview` を入力すると、以下のような DAG が表示される:

```
raw.orders ─▶ stg_orders ─┐
raw.customers ─▶ stg_customers ─┤
raw.products ─▶ stg_products ─┼─▶ int_order_details ─▶ mart_daily_sales ──┐
raw.stores ─▶ stg_stores ─┘                       │                       ▼
                                                   ├─▶ mart_customer_sales ─▶ [sales_overview]
                                                   └─▶ mart_product_sales ──┘
```

exposure ノードは紫の楕円で描かれる。

## Step 4: selector で依存解析

```bash
../.venv/bin/dbt ls --profiles-dir . --select +exposure:sales_overview --resource-type model
# local_analytics.staging.stg_customers
# local_analytics.staging.stg_orders
# local_analytics.staging.stg_products
# local_analytics.staging.stg_stores
# local_analytics.intermediate.int_order_details
# local_analytics.marts.mart_customer_sales
# local_analytics.marts.mart_daily_sales
# local_analytics.marts.mart_product_sales
```

8 model が列挙されたら成功。

```bash
../.venv/bin/dbt run --profiles-dir . --select +exposure:sales_overview
# 8 of 8 OK created sql model ...
# Done. PASS=8 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8
```

## 解説まとめ

- exposure は **DAG の終端メタデータ**。dbt の build には参加しないが、`dbt docs` の lineage と `dbt ls --select +exposure:` の selector で「BI が依存している model」を機械的に追跡できるようになる。
- 実運用では BI ダッシュボードを増やすほど、`mart_*` の変更が「どの BI を壊しうるか」が分からなくなる。exposure を全 BI に貼っておくと、PR 時に `dbt ls --select state:modified+,exposure:high` のような selector で「high maturity の BI を壊す変更」だけ警告できる。
- 学習プロジェクトとしてはダッシュボード 1 件で十分だが、本番では Tableau ワークブック / Looker LookML / Streamlit アプリなども `type` に合わせて exposure 化できる。

## 拡張アイデア

- `maturity: high` に変えて、本 exposure を「壊してはいけないもの」に格上げする
- `tags: [bi, daily-refresh]` を追加して、exposure を分類できる
- 第 2 の exposure を Streamlit / Notebook 用に追加し、`type: notebook` を試す
