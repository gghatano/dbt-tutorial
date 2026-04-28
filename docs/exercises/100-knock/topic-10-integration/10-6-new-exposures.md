# 10-6: 新ドメインに対する exposure を 2 つ宣言 (dashboard + reverse_etl) 、maturity: high

## シナリオ

10-1〜10-5 で新ドメイン (subscriptions など) の **要件定義 → ER → source → staging contract → groups/access** を揃えた。
ここまでで「上流の宣言」は完成しているが、**「下流が誰に消費されているか」** はまだ DAG に書かれていない。

本問で `exposures.yml` に **2 種類の終端ノード** を宣言する:

1. **dashboard 用** (Metabase / Looker / Tableau など BI ツール) — 経営定例で見られる
2. **reverse_etl 用** (HighTouch / Census 経由で SaaS に書き戻す) — 営業 / マーケが Salesforce / HubSpot で参照

両方とも `maturity: high` を付ける。**`high` は「壊したら本番影響あり、CI で守れ」のシグナル** で、後の dbt-checkpoint や独自 lint で検出される運用契約になる。

5-5 で 1 個の exposure を宣言した経験を、**「BI と reverse ETL の 2 種類の終端」** として再訪する。dbt の DAG が「BI ダッシュボードのため」だけでなく **「他システムへのデータ供給契約」** の集約点になる体験。

## 学べること

- exposure の `type` の使い分け: `dashboard` / `application` / `analysis` / `ml` / `notebook`
- `reverse_etl` 相当は `type: application` で表現する慣習
- `maturity: high` の運用上の意味 (壊れたら誰が困るかの宣言)
- 1 つの mart が **複数の exposure** に終端するパターン (BI と reverse ETL で同じ mart を参照)
- `dbt ls --select +exposure:<name>` で起点 build を 1 コマンドで実現
- `--select +exposure:*` で全 exposure 起点の影響範囲を一括取得

## 前提

- 10-1 〜 10-5 完了
  - 新規 source (例: `raw.subscriptions`, `raw.subscription_events`) と staging / mart が存在
  - 想定する mart 例 (10-1 / 10-5 で学習者が定義したものに合わせる):
    - `mart_churn_summary_100knock` (解約 KPI)
    - `mart_subscription_revenue_100knock` (MRR)
    - `mart_active_subscribers_100knock` (アクティブ契約者一覧、reverse ETL 用)
- 5-5 (mart_daily_sales_100knock の exposure 宣言) を経験済み

## 入力データ

なし。既存 mart を参照するだけ。

## 課題

### Step 1: exposures.yml を作る

`dbt/models/100-knock/topic-10/exposures.yml` を新規作成。

要件:

- `version: 2` ヘッダ
- 2 つの exposure:
  1. **`name: churn_dashboard_100knock`**
     - `type: dashboard`
     - `url:` Metabase ダッシュボード URL (例: `http://localhost:3000/dashboard/10`)
     - `owner:` `email` + `name`
     - `description:` 解約 KPI を可視化
     - **`maturity: high`**
     - `depends_on:` で `mart_churn_summary_100knock` (+ 任意で他の mart) を `ref()` で参照
  2. **`name: active_subscribers_reverse_etl_100knock`**
     - `type: application` (reverse_etl の慣習表現)
     - `url:` HighTouch / Census の sync URL を想定 (例: `https://app.hightouch.com/syncs/123`)
     - `owner:` `email` + `name`
     - `description:` 営業ツール (Salesforce 等) に同期するアクティブ契約者リスト
     - **`maturity: high`**
     - `depends_on:` で `mart_active_subscribers_100knock` を `ref()` で参照

### Step 2: parse で manifest に登録

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
```

`target/manifest.json` に以下 2 つが現れる:

- `exposure.local_analytics.churn_dashboard_100knock`
- `exposure.local_analytics.active_subscribers_reverse_etl_100knock`

### Step 3: 起点 build できることを確認

```bash
../.venv/bin/dbt ls --profiles-dir . --select +exposure:churn_dashboard_100knock
../.venv/bin/dbt ls --profiles-dir . --select +exposure:active_subscribers_reverse_etl_100knock
```

それぞれ「ダッシュボード / アプリケーション を支える全 source + staging + mart」 が列挙される。

`+exposure:*` で全 exposure 起点の build も可能:

```bash
../.venv/bin/dbt build --profiles-dir . --select +exposure:*_100knock
```

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-10-integration/10-6-new-exposures.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-10/exposures.yml` が存在
- [ ] `dbt parse` が成功
- [ ] manifest に 2 つの exposure が登録される
- [ ] 両方とも `maturity: high` (manifest_config で検証)
- [ ] `dbt ls --select +exposure:churn_dashboard_100knock` で `mart_churn_summary_100knock` が列挙される

## ヒント (詰まったら)

- **なぜ BI と reverse ETL の 2 種類?**: dbt の出口は「人間が見る画面 (BI)」だけではない。**「他システムにデータを書き戻す」reverse ETL** も dbt の終端の一種。両方を exposure として宣言することで、「mart_active_subscribers が消えたら Salesforce の同期も死ぬ」が DAG から読める。
- **`type: application` の慣習**: dbt は `reverse_etl` という type を持っていない。HighTouch / Census のような外部アプリへの供給は `type: application` で表す。dbt 公式の `type` 一覧は `dashboard / analysis / ml / application / notebook` の 5 種。
- **`maturity: high` の意味**: `low` → 試作、`medium` → 通常、`high` → 本番影響あり。`high` は **「壊したら誰かが困る」のシグナル**。dbt-checkpoint 等で「`high` exposure に影響する PR は人間レビュー必須」 のような lint を組める。
- **mart 名は学習者の 10-1 / 10-5 で決めたものに合わせる**: 上記の `mart_churn_summary_100knock` などはあくまで例。subscriptions ドメインを採用しなかった場合 (在庫 / 配送) は学習者の mart 名に置き換える。
- **owner.email は学習者自身**: 演習なので `gakikame0405@gmail.com` のような自分のアドレスで OK。実務では team alias (`data-platform@example.com`) を書く。
- **同じ mart を 2 つの exposure が参照しても OK**: 例えば `mart_churn_summary_100knock` を BI ダッシュボードと CS チームの reverse ETL の両方が依存することは普通。dbt はこれを許容、`dbt ls --select +exposure:*` で両方が浮かぶ。

## 解答例

詳細は [`10-6-new-exposures.solution.md`](10-6-new-exposures.solution.md) を参照。
