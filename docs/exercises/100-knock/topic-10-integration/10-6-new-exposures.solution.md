# 10-6 解答例

## dbt/models/100-knock/topic-10/exposures.yml

```yaml
version: 2

exposures:
  # ----- 1. BI ダッシュボード -----
  - name: churn_dashboard_100knock
    label: "Churn KPI Dashboard (100-knock)"
    type: dashboard
    maturity: high
    url: http://localhost:3000/dashboard/10
    description: |
      Metabase ダッシュボード "Churn KPI"。
      mart_churn_summary_100knock の月次解約率 / 新規 / リテンションを
      経営定例 (毎週月曜 9:00) で参照。データ遅延は当日中に修復必須。
    owner:
      email: gakikame0405@gmail.com
      name: dbt-tutorial-learner
    depends_on:
      - ref('mart_churn_summary_100knock')
      - ref('mart_subscription_revenue_100knock')
    meta:
      sla_hours: 24
      slack_channel: "#exec-churn-kpi"
      reviewed_by: "data-platform-team"

  # ----- 2. reverse ETL (HighTouch 経由で Salesforce に同期) -----
  - name: active_subscribers_reverse_etl_100knock
    label: "Active Subscribers Sync to Salesforce (100-knock)"
    type: application
    maturity: high
    url: https://app.hightouch.com/syncs/123
    description: |
      mart_active_subscribers_100knock の行データを HighTouch 経由で
      Salesforce の Account オブジェクトに 1 時間ごとに同期。
      営業 / CS チームが「現在アクティブな契約者リスト」を Salesforce で
      検索できる。同期失敗 = 営業の活動データが古くなる。
    owner:
      email: gakikame0405@gmail.com
      name: dbt-tutorial-learner
    depends_on:
      - ref('mart_active_subscribers_100knock')
    meta:
      sla_hours: 1
      slack_channel: "#sales-ops-data-sync"
      sync_tool: "HighTouch"
```

**ポイント**:

- **`type: dashboard` vs `type: application`**: BI ツールは `dashboard`、reverse ETL は `application`。後者は「dbt の出力を他のソフトウェアが消費する」全般を指す慣習。MLflow でデプロイされたモデルなら `type: ml`、ad-hoc 分析なら `type: analysis`。
- **`maturity: high`**: 両方とも本番影響あり。`high` は dbt-checkpoint や独自 lint で「PR が `high` exposure 上流を変更したら slack で通知」などのフックポイント。
- **`depends_on` の複数 mart**: BI ダッシュボードは複数 mart を 1 画面で見せることが多いので、`mart_churn_summary` + `mart_subscription_revenue` を両方依存に書く。reverse ETL は 1 行データを 1 mart から取るのが普通なので 1 つだけ。
- **`meta.sla_hours`**: BI は日次 (24h)、reverse ETL は 1 時間。**SLA 差を data 構造に書き残す** ことで運用責任が明確化。
- **`url`**: BI は Metabase URL、reverse ETL は HighTouch / Census の sync URL。dbt docs から該当ツールに 1 click で飛べる UX。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
04:31:00  Running with dbt=1.11.x
04:31:01  Found N models, M sources, 2 exposures, ...   # exposure +2
```

manifest 確認:

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
for k, v in m['exposures'].items():
    if '_100knock' in k:
        print(f'{v[\"name\"]:50s} type={v[\"type\"]:12s} maturity={v[\"maturity\"]}')
"
churn_dashboard_100knock                           type=dashboard    maturity=high
active_subscribers_reverse_etl_100knock            type=application  maturity=high
```

`+exposure:` セレクタで上流確認:

```bash
$ ../.venv/bin/dbt ls --profiles-dir . --select +exposure:churn_dashboard_100knock
source:local_analytics.raw_100knock.subscriptions
source:local_analytics.raw_100knock.subscription_events
source:local_analytics.raw_100knock.customers
local_analytics.staging.stg_subscriptions_100knock
local_analytics.staging.stg_subscription_events_100knock
local_analytics.staging.stg_customers_100knock
local_analytics.intermediate.int_subscription_lifecycle_100knock
local_analytics.marts.mart_churn_summary_100knock
local_analytics.marts.mart_subscription_revenue_100knock
exposure:local_analytics.churn_dashboard_100knock
```

「ダッシュボードを支える 3 source + 3 staging + 1 intermediate + 2 mart + 1 exposure」が
一気に列挙される。reverse ETL も同様。

全 100-knock exposure 起点 build:

```bash
$ ../.venv/bin/dbt build --profiles-dir . --select +exposure:*_100knock
```

## 解説まとめ

- **なぜ exposure を BI と reverse ETL の 2 種類?**: dbt の出口は **人間が見る画面 (BI) だけではない**。reverse ETL = 「dbt の出力を他システムに書き戻す」 が近年の主要な出口。両方を `exposure:` で DAG に終端宣言することで、dbt が **「全社のデータ供給契約の集約点」** として機能する。
- **`type: application` の正体**: dbt 公式の type 一覧 (`dashboard / analysis / ml / application / notebook`) のうち、reverse ETL は明示的な type がないので慣習的に `application` を使う。コミュニティでは `type: application` + `meta.sync_tool: HighTouch` のような meta 補強で表現。
- **`maturity: high` の運用意義**:
  - `low`: 試作 / 個人ノート (壊れても誰も困らない)
  - `medium`: 通常運用 (壊れたら直す、急ぎではない)
  - `high`: **本番影響あり** (壊れたら slack 通知、誰かが起きる)
  - 5-5 で `medium` を使ったが、Topic ⑩ では「**新ドメインの主要出口は最初から high**」のスタンス。新ドメインの最初の exposure は経営定例 / 営業 SaaS 連携が多く、最初から本番品質を要求する設計。
- **複数 mart 依存の意味**: BI ダッシュボードは「Churn KPI」「MRR」「リテンション」を 1 画面に並べることが多い → 複数 mart 依存。reverse ETL は 1 sync が 1 行データ = 1 mart 依存が多い。**依存数の傾向の違い** が type の本質を反映している。
- **`+exposure:*` セレクタの威力**: CI で「全 exposure を起点に上流 build」 が `--select +exposure:*` 1 行で書ける。10-7 の CI スクリプトでこれを使う。
- **owner と meta による運用宣言**:
  - `owner.email`: PagerDuty / on-call の宛先になる
  - `meta.slack_channel`: build 失敗時の通知先
  - `meta.sla_hours`: SLA 差の宣言。BI = 24h vs reverse ETL = 1h を data 構造で残す
  - これらは `dbt docs` で表示され、後に Topic ⑤ の 5-8 (mart の meta) と一貫した運用契約になる
- **次の問への接続**: 10-7 で本問の `+exposure:*_100knock` を CI スクリプト 1 行にまとめる。10-8 / 10-9 / 10-10 では「本問で宣言した exposure を含む DAG 全体を **他者にレビューしてもらう / 引き継ぐ**」open-ended 問へ進む。
