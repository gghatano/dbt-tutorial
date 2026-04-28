# 10-3: 新規 source を sources.yml に追加し、`description` / `loaded_at_field` / `freshness:` を宣言する

## シナリオ

10-1 で要件を、10-2 で ER 図を書いた。次は **dbt 上に「外部世界との物理境界」を宣言** する。新規ドメイン (subscriptions) の raw テーブル 2 本を `sources.yml` で論理 source 化し、各テーブルに **鮮度 SLA** (`freshness:`) を付ける。

10-1 で「`freshness: warn 24h / error 48h`」を要件として宣言した。本問はその要件を **YAML として実体化** するステップ。`dbt source freshness --select source:<...>` で SLA が機械的にチェックされる状態を作る。

> **本問の特殊事情**: 学習者の環境には実際の `raw.subscriptions` テーブルが無い (新規ドメインなので生成スクリプトもまだ無い)。そのため `dbt source freshness` 実行は **構文・宣言が正しいか** までを採点し、**データそのものが流れているか** は問わない。10-1 〜 10-7 全体で「source 宣言までは書く、データ実体は HANDOVER で次の人が作る」という運用想定。

## 学べること

- 新規 source ブロックを既存と衝突しない `name:` で立てる (`raw_100knock_subscriptions`)
- `description:` で「このテーブルは何か」をテーブル / 列の両レベルで宣言
- `loaded_at_field:` で freshness 判定対象列を指定 (10-2 ER 図の `loaded_at` を使う)
- `freshness: { warn_after: {...}, error_after: {...} }` の period (`hour` / `day`) と count
- `dbt parse` で source 宣言が壊れていないことを保証
- (任意) `dbt source freshness --select source:<...>` 実行で構文 OK を確認

## 前提

- 10-1 / 10-2 完了 (要件 + ER 図あり)
- `dbt parse` が緑 (既存 100-knock 演習が壊れていない)
- `dbt/models/100-knock/topic-10/` ディレクトリは無ければ新規作成

## 入力データ

不要。学習者が YAML を書くだけ。raw に物理テーブルが存在しなくても本問は成立する (構文採点のみ)。

## 課題

### Step 1: ディレクトリ作成

```bash
mkdir -p dbt/models/100-knock/topic-10
```

### Step 2: sources.yml を新規作成

`dbt/models/100-knock/topic-10/sources.yml`:

```yaml
version: 2

sources:
  - name: raw_100knock_subscriptions   # 既存 raw_100knock と衝突しない別名
    description: |
      Subscriptions ドメイン (10-1 の新規要件) の raw 層。
      物理 schema は raw、テーブルは subscriptions / subscription_events。
    database: analytics
    schema: raw
    loaded_at_field: loaded_at         # source 全体に default を付与 (各 table で上書き可)
    freshness:                         # source 全体の default freshness
      warn_after:  { count: 24, period: hour }
      error_after: { count: 48, period: hour }

    tables:
      - name: subscriptions
        description: "顧客 × プランの現行契約 (10-2 ER 図参照)。1 顧客 0..N 行。"
        loaded_at_field: loaded_at
        freshness:
          warn_after:  { count: 24, period: hour }
          error_after: { count: 48, period: hour }
        columns:
          - name: subscription_id
            description: "PK. bigint."
          - name: customer_id
            description: "FK to customers.customer_id. bigint."
          - name: plan_code
            description: "プランコード (basic/pro/enterprise の 3 値想定)。"
          - name: monthly_price
            description: "月額 (numeric(12,2))。プラン変更時に更新。"
          - name: subscribed_at
          - name: canceled_at
            description: "解約日時。アクティブ契約は NULL。"
          - name: loaded_at
            description: "raw 投入時刻 (TIMESTAMPTZ)。freshness 判定に使用。"

      - name: subscription_events
        description: "プラン変更・解約・再開ログ。1 subscription に 0..N 行。"
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
          - name: payload
            description: "イベント詳細 (jsonb)。event_type ごとに schema が異なる。"
          - name: loaded_at
            description: "raw 投入時刻 (TIMESTAMPTZ)。"
```

### Step 3: parse 確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# 期待: Found ... 2 sources (... + raw_100knock_subscriptions の 2 tables) ...
```

### Step 4: source ls で見える化

```bash
../.venv/bin/dbt ls --profiles-dir . --select 'source:raw_100knock_subscriptions.*'
# 期待:
# source:local_analytics.raw_100knock_subscriptions.subscriptions
# source:local_analytics.raw_100knock_subscriptions.subscription_events
```

### Step 5: (任意) freshness 実行

raw テーブルが物理に存在する場合のみ:

```bash
../.venv/bin/dbt source freshness --profiles-dir . \
  --select source:raw_100knock_subscriptions
```

物理テーブルが無いと `relation does not exist` で error。本問は **構文 OK までを採点** するので、物理テーブルが無くても合格できる。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-10-integration/10-3-new-source-freshness.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-10/sources.yml` が存在
- [ ] sources.yml に `name: raw_100knock_subscriptions` (または任意の新規 source 名) が宣言
- [ ] `freshness:` キーが含まれる
- [ ] `warn_after:` / `error_after:` がそれぞれ含まれる
- [ ] `loaded_at_field:` キーが含まれる
- [ ] `dbt parse` が exit 0 で成功
- [ ] sources.yml に `subscriptions` と `subscription_events` (または学習者選定ドメインの 2 テーブル) が含まれる

## ヒント (詰まったら)

- **既存 source 名と衝突させない**: 既存 100-knock は `name: raw_100knock` を使っているので、本問は **`raw_100knock_subscriptions`** のように suffix を付ける。dbt は project 全体で source `name:` の重複を許さない。
- **`loaded_at_field:` を source レベルと table レベル両方に書く意義**: source レベルが default、table レベルが override。テーブルごとに `loaded_at` 列名が違う場合 (e.g. 一部だけ `_load_ts`) に table 側で上書きできる。本問は全部 `loaded_at` で統一されているので、source 側だけでも OK。
- **`period:` の単位**: `minute` / `hour` / `day` の 3 つ。`day` だけで揃えると schema.yml が読みやすい。本問は `hour` で書いて `24h / 48h` を明示するスタイル (10-1 SLA に合わせる)。
- **`description:` を全列に書かなくてもよい**: dbt は parse error にしない。とは言え主要な PK / FK / 重要列には書く。本問は `subscription_id` / `customer_id` / `loaded_at` あたりに集中して書けば十分。
- **`dbt source freshness` が落ちる**: 物理テーブルが無い場合の `relation does not exist` は **想定内**。本問では parse 通過 (sources.yml の構文 OK) までを採点する。物理を作る話は HANDOVER (10-10) の領分。
- **`raw_100knock_subscriptions` という source 名にした理由**: 「raw_100knock = 既存 EC ドメイン」「raw_100knock_subscriptions = 新規ドメイン」という命名で **将来別ドメインを足す時もコンフリクトしない**。在庫を足す時は `raw_100knock_inventory`、配送なら `raw_100knock_shipping`。
- **dbt 1.10+ の `data_tests:`**: source の test ブロックは 1.7 までは `tests:`、1.8+ は `data_tests:` が推奨。本問では test まで踏み込まない (10-4 の staging contract で扱う) ので、`columns:` 配下に test を書かない。
- **「source description は staging より上に並ぶ」(2-3 の知見)**: docs サイト上で source の description は staging の description より上流に表示される。raw の段階で **意味を残しておく** ことが、後段のドキュメントをすべて支える。

## 解答例

詳細は [`10-3-new-source-freshness.solution.md`](10-3-new-source-freshness.solution.md) を参照。
