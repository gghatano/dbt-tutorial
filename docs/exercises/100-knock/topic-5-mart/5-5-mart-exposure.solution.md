# 5-5 解答例

## dbt/models/100-knock/topic-5/exposures.yml

```yaml
version: 2

exposures:
  - name: daily_sales_dashboard_100knock
    label: "Daily Sales Dashboard (100-knock)"
    type: dashboard
    maturity: medium
    url: http://localhost:3000/dashboard/3
    description: |
      Metabase ダッシュボード "Daily Sales" の dbt 側宣言。
      mart_daily_sales_100knock の order_date / total_sales_amount を
      折れ線グラフで日次トレンド表示。
      経営定例 (毎週月曜) で参照される。

    owner:
      email: gakikame0405@gmail.com
      name: dbt-tutorial-learner

    depends_on:
      - ref('mart_daily_sales_100knock')

    meta:
      sla_hours: 24
      slack_channel: "#exec-daily-kpi"
      reviewed_by: "data-platform-team"
```

**ポイント**:

- **`name: daily_sales_dashboard_100knock`**: MVP Ex.06 の `sales_overview`
  exposure と衝突回避のため `_100knock` suffix。dbt は同名 exposure を
  許さない (parse で `Found duplicate exposure` エラー)。
- **`type: dashboard`**: 他の選択肢は `analysis` / `application` / `ml` /
  `notebook`。Metabase / Looker / Tableau など BI ツールの URL を持つ
  ダッシュボードは `dashboard`。
- **`maturity: medium`**: `low` / `medium` / `high` の 3 段階。`high` 設定の
  exposure を支える model に破壊的変更があったとき CI で警告を出す
  運用 (dbt-checkpoint や独自スクリプト) と組み合わせて使う。学習時は
  `medium` で十分。
- **`url:` は学習者の環境のものを書く**: `scripts/metabase_bootstrap.py` で
  `Sales Overview` ダッシュボードが ID 2 で作られる前提なら、新規追加分は
  3 から始まることが多い。Metabase に手動で作ったダッシュボードの URL でも OK。
- **`depends_on` は YAML の文字列内 Jinja**: `ref('mart_daily_sales_100knock')`
  の引用符を忘れない。dbt が Jinja 評価して manifest の `depends_on.nodes` に
  `model.local_analytics.mart_daily_sales_100knock` として記録する。
- **`meta:`** に `sla_hours`, `slack_channel`, `reviewed_by` を追加: 5-8
  (将来) で扱う運用 meta の予習。dbt docs で表示される。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
04:31:00  Running with dbt=1.11.x
04:31:01  Found 12 models, 5 sources, 1 exposure, ...   # exposure が +1
```

manifest 確認:

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
exp = m['exposures']['exposure.local_analytics.daily_sales_dashboard_100knock']
print('name:', exp['name'])
print('type:', exp['type'])
print('depends_on:', exp['depends_on']['nodes'])
"
name: daily_sales_dashboard_100knock
type: dashboard
depends_on: ['model.local_analytics.mart_daily_sales_100knock']
```

`+exposure:` セレクタで上流を確認:

```bash
$ ../.venv/bin/dbt ls --profiles-dir . --select +exposure:daily_sales_dashboard_100knock
source:local_analytics.raw_100knock.customers
source:local_analytics.raw_100knock.orders
source:local_analytics.raw_100knock.products
source:local_analytics.raw_100knock.stores
local_analytics.staging.stg_customers_100knock
local_analytics.staging.stg_orders_100knock
local_analytics.staging.stg_products_100knock
local_analytics.staging.stg_stores_100knock
local_analytics.intermediate.int_order_details_100knock
local_analytics.marts.mart_daily_sales_100knock
exposure:local_analytics.daily_sales_dashboard_100knock
```

「ダッシュボードを支える 4 source + 4 staging + 1 intermediate + 1 mart」が
一気に列挙される = exposure を介して **影響範囲が機械可読** になった。

## docs lineage の見え方 (任意 Step 4)

```bash
$ ../.venv/bin/dbt docs generate --profiles-dir .
$ ../.venv/bin/dbt docs serve --profiles-dir .
```

ブラウザで <http://localhost:8080> → 左下の lineage アイコン →
`daily_sales_dashboard_100knock` を選択。

```text
[raw_100knock.orders] ─┐
                        ├─→ [stg_orders_100knock] ─┐
[raw_100knock.customers] ─→ [stg_customers_100knock] ─┐
[raw_100knock.products]  ─→ [stg_products_100knock]  ─┼─→ [int_order_details_100knock] ─→ [mart_daily_sales_100knock] ─→ [daily_sales_dashboard_100knock]
[raw_100knock.stores]    ─→ [stg_stores_100knock]    ─┘
```

ダッシュボードノードがグラフの右端 (= DAG の終端) にいて、上流の SQL 群が
全部それを支えている図が描かれる。

## 解説まとめ

- **mart は 3 点セットで完成**: Topic ⑤ の方針として、mart には
  - **grain 宣言** (5-1 / 5-2 で実装) — 1 行が何を表すか
  - **列契約** (5-3 で実装) — 列名と型の対外公開
  - **exposure 宣言** (5-5 で実装) — 誰が使っているか
  の 3 つを揃えて初めて「公開可能な mart」になる、というメンタルモデル。
- **exposure が解決する問題**: 「誰かがこの mart を消したら何が壊れるか」を
  dbt の DAG だけ見ても分からなかった問題を、`exposure:` 宣言が解決する。
  消す前に `dbt ls --select +exposure:foo` で影響範囲を出せる = **削除前の
  事前周知** が機械化される。
- **exposure は run されない**: `dbt run` / `dbt build` の対象外。
  `dbt parse` で manifest に登録されるだけ。だが `dbt docs` のグラフ /
  `dbt ls` の selector / 外部ツール (dbt Cloud / dbt-checkpoint) との連携で
  巨大な価値を生む。
- **owner / sla_hours / slack_channel の意義**: dbt docs で表示される運用情報。
  「この mart が遅延したら誰に slack 飛ばすか」が機械可読化される。
  `dbt-checkpoint` 等のツールで「PR が exposure に影響するか」を判定する
  運用にもつながる。
- **MVP との `_100knock` suffix の徹底**: model 名 / exposure 名 / dashboard 名
  と、すべての名前空間で `_100knock` を付けて MVP と並走可能にしている。
  100-knock 演習がリポジトリ全体を壊さない設計。
- **次の問への接続**: 5-6 (grants) / 5-7 (groups + access) / 5-8 (meta) では、
  contract / exposure に加えて「権限 / オーナーシップ / 運用 SLA」を mart に
  紐づけていく。Topic ⑤ 全体で「mart は技術的契約 + 運用契約の二重宣言」 の
  メンタルモデルを完成させる流れ。
