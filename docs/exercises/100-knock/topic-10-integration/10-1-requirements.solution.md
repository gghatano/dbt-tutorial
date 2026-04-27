# 10-1 解答例

> 本解答では新規ドメインとして **subscriptions (顧客の月額課金)** を採用する。10-2 〜 10-7 でも同じドメインを使い続けるので、ここで書いた要件が **後続のすべての設計判断のリファレンス** になる。

## docs/exercises/100-knock/topic-10-integration/learner/requirements.md

```markdown
# Subscriptions ドメイン 要件定義

> 100-knock Topic ⑩ 10-1 の成果物。新規ドメインとして「顧客の月額課金 (サブスクリプション)」を選定。
> 既存 EC ドメインの `customers` を FK 参照する形で接続する。

## ステークホルダー

| 役割 | 何の判断にこの DAG を使うか | 接触頻度 |
|---|---|---|
| 経営企画 | 週次の MRR (月次経常収益) レビュー、四半期予算策定 | 週 1 (月曜 9:00) |
| カスタマーサクセス (CS) | チャーン顧客リストで日次フォロー (解約予兆対応) | 日 1 (毎朝 10:00) |
| 経理 | 月次決算で MRR を会計報告に転記、収益認識 | 月 1 (月初 5 営業日以内) |
| プロダクトマネージャ | 機能リリース後 30 日の解約率比較 (機能 ROI 評価) | 月 2〜3 |

ステークホルダー全 4 役割。**経営企画 + CS + 経理** がコア利用者で、ここを満たすことを最優先。

## KPI 3 つ

1. **MRR (Monthly Recurring Revenue)** — 月次経常収益
   - 定義: アクティブな subscription の `monthly_price` を月単位で合計
   - 粒度: 1 行 = 1 (年, 月)
   - 更新頻度: 日次バッチ (前日分まで反映)、ただし **会計確定値は月初 3 営業日後**

2. **Churn Rate** — 月次解約率
   - 定義: その月に `cancel` イベントが発生した顧客数 / 月初時点でアクティブだった顧客数
   - 粒度: 1 行 = 1 (年, 月)
   - 更新頻度: 日次バッチ。月途中の中間値も参照可

3. **ARPU (Average Revenue Per User)** — 顧客あたり平均収益
   - 定義: その月の MRR / その月の月末時点アクティブ顧客数
   - 粒度: 1 行 = 1 (年, 月)
   - 更新頻度: 日次バッチ

## 提供したい mart 3 本

1. **`mart_subscription_mrr_100knock`** — 月次 MRR
   - grain: `(year, month)` の組合せで 1 行
   - 主要列: `year`, `month`, `mrr_amount` (numeric(18,2)), `active_customer_count` (bigint)
   - access: `public` (Metabase / 経営定例で参照)

2. **`mart_subscription_churn_100knock`** — 顧客 × 月の解約フラグ
   - grain: `(customer_id, year, month)` で 1 行
   - 主要列: `customer_id`, `year`, `month`, `was_active_start`, `was_active_end`, `churned_in_month`
   - access: `public` (CS が顧客リストとして参照)

3. **`mart_subscription_active_100knock`** — 顧客の最新スナップショット
   - grain: `customer_id` で 1 行
   - 主要列: `customer_id`, `current_plan`, `current_monthly_price`, `subscribed_at`, `last_event_at`, `is_active`
   - access: `public` (CS が日次でフィルタ)

中間 model `int_subscription_events_enriched_100knock` は **`access: private`** の予定 (10-5 で扱う)。

## 想定アクセス頻度

- **Metabase ダッシュボード経由**: 1 日あたり 50〜100 read (経営 + CS の合計)
- **直接 SQL**: 経理が月初に `mart_subscription_mrr_100knock` を CSV エクスポート (月 1 回)
- **API 経由 (将来)**: reverse_etl で Salesforce に顧客の `is_active` を sync する予定 (10-6 で exposure 宣言)
- **ピーク時間帯**: 月曜朝 9:00 (経営定例)、毎朝 10:00 (CS デイリーミーティング)

DB 負荷的には軽量だが、**ピーク前 1 時間以内に最新化されている** ことが必須。

## SLA

- **データ鮮度**:
  - `freshness: warn_after = 24h, error_after = 48h` (10-3 で `sources.yml` に宣言)
  - raw (subscriptions / subscription_events) が 24 時間更新されないと WARN、48 時間で ERROR
- **障害時連絡先**: `#data-platform` slack channel (`subscription_internal` group の owner、10-5 で宣言)
- **復旧目標時間 (RTO)**: 4 時間 (経営定例の朝 9:00 開始までに復旧)
- **データ保持**: raw 5 年、mart 3 年 (経理の監査要件に合わせる)
- **障害時の代替手段**: mart が古い場合は **前日値を使う** ことを Metabase 側で許容 (1 日遅れまでは経営判断に影響しない)

## 設計上の前提

- 既存 `customers` テーブルとの FK: `subscriptions.customer_id → customers.customer_id` (10-2 ER 図で明示)
- raw の物理 schema: `raw` (既存と同じ)
- 論理 source 名: `raw_100knock_subscriptions` (既存 `raw_100knock` と区別、10-3 で宣言)
- staging に dbt 1.5+ の `contract: enforced` を全列で付与 (10-4 で実装)
- 中間 model に `groups: + access: private` (10-5 で実装)
```

文字数: 約 1,400 文字 (本文のみ)。要求 800 字を十分に満たす。

## 解説まとめ

- **なぜ「要件定義」から始めるのか**: SQL から書き始めると、半年後に「なぜこの mart があるのか」「誰が見ているか」「いつまでに更新されるべきか」が消える。要件定義 1 ページが残っていれば、10-8 (設計レビュー) と 10-10 (HANDOVER) の出発点として再利用できる。**書き出す行為そのものが、設計の解像度を上げる**。
- **KPI を 3 つに絞る理由**: 「全部入り」mart は誰のものでもない mart になる。MRR / Churn / ARPU の **3 つに絞る** ことで、各 mart の grain と consumer が一意に決まる。10-3 〜 10-5 の設計が一気に楽になる。
- **mart の grain を要件で先に決める意義**: `(year, month)` / `(customer_id, year, month)` / `customer_id` の **3 種類の grain** が要件段階で確定していると、10-4 (staging contract) で「何の列を残すべきか」が機械的に決まる。grain は SQL ではなく **要件文書で確定する** のが本流。
- **SLA を最初に書く意義**: `freshness: warn 24h / error 48h` を要件段階で決めておくと、10-3 で `sources.yml` に書く `freshness:` ブロックの数字が一意に決まる。SLA を後から決めると「とりあえず 24h」で曖昧になり、運用に乗せられない。
- **ステークホルダーを `役割` で書く**: 「田中さん」ではなく「経営企画」と書くことで、人事異動があっても文書が腐らない。これは Topic ⑩ 全体の運用思想 (= 「他者が読める成果物を残す」) の最小単位。
- **subscriptions を選ぶメリット**: `customers` との FK が自然で、既存 DAG を破壊せずに新規ドメインを足せる。10-2 の ER 図でも「`subscriptions ↔ customers` の N:1」を 1 行で書ける。在庫 / 配送 / 広告でも本質は変わらないので、学習者の興味で選んで OK。
- **「KPI と mart は 1:1 ではない」**: 本解答では KPI 3 つ + mart 3 本だが、実務では 1 mart が複数 KPI を支えることが多い (e.g. `mart_subscription_mrr_100knock` から MRR と ARPU の両方が出る)。本問では学習者が混乱しないよう **1:1 で揃える** ことを推奨。10-8 (設計レビュー) で「1:多 / 多:1 への変更」を再考する余地として残す。
- **次の 10-2 への接続**: ここで書いた `subscriptions ↔ customers` の FK / `subscription_events ↔ subscriptions` の 1:N を、次の 10-2 で **Mermaid `erDiagram`** として図示する。要件文書の N:1 / 1:N 表記が ER 図のシンタックスに直訳される設計。
