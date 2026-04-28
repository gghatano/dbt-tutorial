# 10-3 解答例

> subscriptions ドメインの raw 2 テーブル + 任意で `plans` (10-2 ER 図に登場) を
> `dbt/models/100-knock/topic-10/sources.yml` で論理 source 化する。

## dbt/models/100-knock/topic-10/sources.yml (完全版)

```yaml
version: 2

# ============================================================================
# Topic ⑩ / 10-3 — 新規ドメイン (subscriptions) の raw source 宣言。
#
# 本ファイルは「外部世界 (raw schema) と dbt の境界面」の宣言。
# 物理 schema = raw、論理 source 名 = raw_100knock_subscriptions
# (既存 raw_100knock と衝突しない別名)
#
# 各テーブルに freshness SLA を宣言:
#   warn_after  24h  (10-1 要件「1 日以内に最新化」)
#   error_after 48h  (10-1 要件「2 日経過したら CI red」)
#
# 採点 (10-3 grading.yaml) では構文と必須キーの存在のみを確認する。
# 実データは 10-7 / 10-10 の HANDOVER 段階で投入想定。
# ============================================================================

sources:
  - name: raw_100knock_subscriptions
    description: |
      Subscriptions ドメイン (10-1 の新規要件) の raw 層。
      物理 schema は既存と同じ raw、論理 source 名は raw_100knock_subscriptions。
      対象テーブル: subscriptions / subscription_events / plans
      consumers: stg_subscriptions_100knock / stg_subscription_events_100knock (10-4)
    database: analytics
    schema: raw

    # source 全体の default freshness。各 table で上書き可。
    loaded_at_field: loaded_at
    freshness:
      warn_after:  { count: 24, period: hour }
      error_after: { count: 48, period: hour }

    tables:
      # ----------------------------------------------------------------------
      # subscriptions: 顧客 × プランの現行契約
      #   grain: 1 (customer_id, subscribed_at) で 1 行 (再契約は別行)
      # ----------------------------------------------------------------------
      - name: subscriptions
        description: |
          顧客 × プランの現行契約。10-2 ER 図参照。
          1 顧客 0..N 行 (休眠あり、再契約は別行)。
          canceled_at が NULL ならアクティブ。
        loaded_at_field: loaded_at
        freshness:
          warn_after:  { count: 24, period: hour }
          error_after: { count: 48, period: hour }
        columns:
          - name: subscription_id
            description: "PK. bigint. Topic ① の generate スクリプトで 1..N の連番。"
          - name: customer_id
            description: "FK to raw_100knock.customers.customer_id. bigint."
          - name: plan_code
            description: "FK to plans.plan_code. text. enum (basic/pro/enterprise)。"
          - name: monthly_price
            description: "月額 (numeric(12,2))。プラン変更時に履歴行で更新。"
          - name: subscribed_at
            description: "契約開始日時 (timestamptz)。"
          - name: canceled_at
            description: "解約日時 (timestamptz)。NULL ならアクティブ。"
          - name: loaded_at
            description: "raw 投入時刻 (timestamptz)。freshness 判定に使用。"

      # ----------------------------------------------------------------------
      # subscription_events: プラン変更/解約/再開ログ
      # ----------------------------------------------------------------------
      - name: subscription_events
        description: |
          subscription に対する変更ログ。1 subscription に 0..N 行。
          event_type ∈ {plan_change, cancel, resume, pause}。
        loaded_at_field: loaded_at
        freshness:
          warn_after:  { count: 24, period: hour }
          error_after: { count: 48, period: hour }
        columns:
          - name: event_id
            description: "PK. bigint."
          - name: subscription_id
            description: "FK to subscriptions.subscription_id."
          - name: event_type
            description: "plan_change / cancel / resume / pause のいずれか。"
          - name: event_at
            description: "イベント発生時刻 (timestamptz)。"
          - name: payload
            description: |
              イベント詳細 (jsonb)。event_type ごとに schema が異なる:
                plan_change: {old_plan_code, new_plan_code}
                cancel:      {reason}
                resume:      {}
                pause:       {pause_until}
          - name: loaded_at
            description: "raw 投入時刻 (timestamptz)。"

      # ----------------------------------------------------------------------
      # plans: プラン マスタ (将来 seed 化候補)
      #   行数が 5〜10 と少ないが、現段階では raw に置いて source 経由で参照。
      #   freshness は緩め (1 週間)。マスタは頻繁には更新されない。
      # ----------------------------------------------------------------------
      - name: plans
        description: "プラン マスタ。5〜10 行。将来 seed 化候補。"
        loaded_at_field: loaded_at
        freshness:
          warn_after:  { count: 7,  period: day }
          error_after: { count: 14, period: day }
        columns:
          - name: plan_code
            description: "PK. text. basic/pro/enterprise 等。"
          - name: plan_name
          - name: monthly_price
            description: "プランの基準月額 (numeric(12,2))。"
          - name: is_active
            description: "プランが現役か (bool)。false なら新規契約不可。"
          - name: loaded_at
```

## 実行ログ例

```bash
$ cd dbt && ../.venv/bin/dbt parse --profiles-dir .
12:30:01  Running with dbt=1.10.x
12:30:01  Registered adapter: postgres=1.x.x
12:30:01  Found 5 models, 12 tests, 2 sources, 0 exposures, 0 metrics
12:30:01  Done.

$ ../.venv/bin/dbt ls --profiles-dir . --select 'source:raw_100knock_subscriptions.*'
source:local_analytics.raw_100knock_subscriptions.subscriptions
source:local_analytics.raw_100knock_subscriptions.subscription_events
source:local_analytics.raw_100knock_subscriptions.plans
```

(物理テーブルが無い状態で `dbt source freshness` を呼ぶと:)

```bash
$ ../.venv/bin/dbt source freshness --profiles-dir . \
    --select source:raw_100knock_subscriptions
12:35:00  Running with dbt=1.10.x
12:35:01  1 of 3 START freshness of raw_100knock_subscriptions.subscriptions ... [RUN]
12:35:01  1 of 3 ERROR STALE freshness of raw_100knock_subscriptions.subscriptions ... [ERROR in 0.05s]
12:35:01  Database Error
  relation "raw.subscriptions" does not exist
12:35:01  Done. PASS=0 WARN=0 ERROR=3 SKIP=0 TOTAL=3
```

これは **想定された結果**: raw に物理テーブルが無いだけで、宣言自体は正しい。
本問の grading では parse 通過と必須キーの存在までを採点対象にする。

## 解説まとめ

- **なぜ source 宣言から始めるのか**: 「raw に何が居るか」を `sources.yml` に書き起こさないと、後段の staging が `{{ source(...) }}` で参照できない。**raw → staging の最初のエッジ** が DAG に現れる起点。
- **なぜ `freshness:` を最初から付けるのか**: 後付けで `freshness:` を付けると、運用に乗ってから「鮮度がどれくらい必要か」を考え始める = 既に手遅れ。10-1 で SLA を要件として書いた瞬間に、対応する `freshness:` を YAML に書いてしまう。**要件 → SLA → freshness ブロック** の 3 段リンクを作る。
- **`loaded_at_field:` を source レベルにも書く意義**: source 全体の default を 1 箇所で宣言すると、新しい table を追加する時に `loaded_at_field:` を書き忘れても source default が効く = 安全側に倒れる。
- **`raw_100knock_subscriptions` という source 名**: 「`raw_<project>_<domain>`」のパターン。将来 `raw_100knock_inventory` / `raw_100knock_shipping` を足す時に **コンフリクトしないし命名も統一できる**。
- **plans を sources に入れるか seed にするか**: 行数が 5〜10 と少ないので、本来は **`dbt seed`** (= リポジトリにマスタを CSV で持つ) が筋。本問では 10-7 (CI スクリプト) と独立に解けるよう source として宣言したが、本来は `dbt/seeds/100-knock/plans.csv` 化が望ましい。10-8 (設計レビュー) の論点候補。
- **物理テーブルが無くても採点が通る理由**: `dbt parse` は SQL を実行しないので、raw に物理テーブルが無くても sources.yml の構文と node 登録だけ確認できる。これが「**宣言と実体を分離できる**」 dbt の強み。実体の準備は 10-10 HANDOVER で次の人 (= 自分) に委譲する設計。
- **`description: |` の複数行記法**: YAML の literal block scalar (`|`)。改行を保持してくれるので、長い説明を Markdown 風に書ける。dbt docs にも改行付きで表示される。
- **次の 10-4 への接続**: ここで宣言した `subscriptions` / `subscription_events` の **列リスト** を、次の 10-4 で `stg_subscriptions_100knock` / `stg_subscription_events_100knock` の `data_type:` 宣言に **そのまま直訳** する。10-2 ER 図 → 10-3 sources → 10-4 staging contract の **列定義のトレーサビリティ** が貫通する。
