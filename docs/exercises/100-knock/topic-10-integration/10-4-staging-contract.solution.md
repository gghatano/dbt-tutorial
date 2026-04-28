# 10-4 解答例

> stg_subscriptions_100knock + stg_subscription_events_100knock を新規作成し、
> 全列に `data_type:` を宣言、`contract: enforced` を有効化する。
> 解答では 2 staging を提示するが、grading は最低 1 つ (subscriptions) で合格。

## dbt/models/100-knock/topic-10/stg_subscriptions_100knock.sql

```sql
{{ config(
    materialized='view',
    schema='staging',
    contract={'enforced': true}
) }}

-- ============================================================================
-- stg_subscriptions_100knock
-- ----------------------------------------------------------------------------
-- contract: enforced (Topic ⑩ 10-4)
--   全列の data_type を schema.yml で宣言済み。SQL の cast と data_type の
--   不一致は dbt run の Contract Error で fail。
-- grain     : 1 subscription_id 1 行 (再契約は別 subscription_id で別行)
-- upstream  : source('raw_100knock_subscriptions', 'subscriptions')
-- downstream: int_subscription_events_enriched_100knock (10-5 で作成)
-- ============================================================================

select
    subscription_id::bigint                       as subscription_id,
    customer_id::bigint                           as customer_id,
    plan_code::text                               as plan_code,
    monthly_price::numeric(12, 2)                 as monthly_price,
    subscribed_at::timestamp with time zone       as subscribed_at,
    canceled_at::timestamp with time zone         as canceled_at,
    (canceled_at is null)::boolean                as is_active,
    loaded_at::timestamp with time zone           as loaded_at
from {{ source('raw_100knock_subscriptions', 'subscriptions') }}
```

## dbt/models/100-knock/topic-10/stg_subscription_events_100knock.sql

```sql
{{ config(
    materialized='view',
    schema='staging',
    contract={'enforced': true}
) }}

-- ============================================================================
-- stg_subscription_events_100knock
-- contract: enforced
-- grain: 1 event_id 1 行
-- ============================================================================

select
    event_id::bigint                              as event_id,
    subscription_id::bigint                       as subscription_id,
    event_type::text                              as event_type,
    event_at::timestamp with time zone            as event_at,
    payload::jsonb                                as payload,
    loaded_at::timestamp with time zone           as loaded_at
from {{ source('raw_100knock_subscriptions', 'subscription_events') }}
```

## dbt/models/100-knock/topic-10/schema.yml

```yaml
version: 2

models:
  # --------------------------------------------------------------------------
  # stg_subscriptions_100knock — contract: enforced
  # --------------------------------------------------------------------------
  - name: stg_subscriptions_100knock
    config:
      contract:
        enforced: true
    description: |
      Staging for raw_100knock_subscriptions.subscriptions.
      contract: enforced で列名 + 列型を build 時に検証する。新規ドメインなので
      最初から契約付き (5-3 mart contract と同じ運用思想を staging に拡大)。
    columns:
      - name: subscription_id
        data_type: bigint
        description: "PK. Topic ① の generate_*.py で 1..N の連番を想定。"
        tests:
          - not_null
          - unique
      - name: customer_id
        data_type: bigint
        description: "FK to raw_100knock.customers.customer_id."
        tests:
          - not_null
      - name: plan_code
        data_type: text
        description: "プランコード。enum (basic/pro/enterprise)。値域チェックは int で実施。"
        tests:
          - not_null
      - name: monthly_price
        data_type: numeric(12,2)
        description: "月額。numeric(12,2) で精度を固定 (経理要件)。"
        tests:
          - not_null
      - name: subscribed_at
        data_type: timestamp with time zone
        description: "契約開始日時 (timestamptz)。"
        tests:
          - not_null
      - name: canceled_at
        data_type: timestamp with time zone
        description: "解約日時 (timestamptz)。NULL = アクティブ契約。"
      - name: is_active
        data_type: boolean
        description: "(canceled_at IS NULL) の派生列。CS が日次フィルタに使用。"
        tests:
          - not_null
      - name: loaded_at
        data_type: timestamp with time zone
        description: "raw 投入時刻。10-3 の freshness 判定列。"
        tests:
          - not_null

  # --------------------------------------------------------------------------
  # stg_subscription_events_100knock — contract: enforced
  # --------------------------------------------------------------------------
  - name: stg_subscription_events_100knock
    config:
      contract:
        enforced: true
    description: "Staging for subscription_events. 1 event_id 1 行。"
    columns:
      - name: event_id
        data_type: bigint
        tests:
          - not_null
          - unique
      - name: subscription_id
        data_type: bigint
        tests:
          - not_null
      - name: event_type
        data_type: text
        tests:
          - not_null
          - accepted_values:
              values: [plan_change, cancel, resume, pause]
      - name: event_at
        data_type: timestamp with time zone
        tests:
          - not_null
      - name: payload
        data_type: jsonb
      - name: loaded_at
        data_type: timestamp with time zone
        tests:
          - not_null
```

## わざと型を壊して run fail を体験 (Step 4)

```sql
-- stg_subscriptions_100knock.sql の monthly_price 1 行を変える
monthly_price::integer                        as monthly_price,
-- ↑ schema.yml は numeric(12,2) のまま
```

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select stg_subscriptions_100knock 2>&1 \
    | tee /tmp/10-4-violation.log
12:30:00  Concurrency: 1 threads (target='dev')
12:30:00  1 of 1 START sql view model staging.stg_subscriptions_100knock ... [RUN]
12:30:00  1 of 1 ERROR creating sql view model staging.stg_subscriptions_100knock ... [ERROR in 0.10s]

Contract Error in model stg_subscriptions_100knock (...)
  This model has an enforced contract that failed.
  Please ensure the name, data_type, and number of columns in your contract match the columns in your model's definition.

  | column_name   | definition_type | contract_type | mismatch_reason   |
  | ------------- | --------------- | ------------- | ----------------- |
  | monthly_price | INT4            | NUMERIC       | data type mismatch|

12:30:00  Done. PASS=0 WARN=0 ERROR=1 SKIP=0 TOTAL=1
```

`Done. PASS=0 ... ERROR=1` が確認できたら **必ず元に戻す** (`numeric(12, 2)`)。
ログを `learner/10-4-violation-log.md` に貼っておくと 10-8 の設計レビューで再利用可能。

## 実行ログ例 (修復後)

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
12:32:00  Found 7 models, 22 tests, 2 sources, 0 exposures, 0 metrics
12:32:00  Done.

# raw 物理テーブルがある環境:
$ ../.venv/bin/dbt run --profiles-dir . --select stg_subscriptions_100knock
12:32:10  1 of 1 START sql view model staging.stg_subscriptions_100knock ... [RUN]
12:32:10  1 of 1 OK   created sql view model staging.stg_subscriptions_100knock [in 0.10s]
12:32:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

manifest 確認:

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.stg_subscriptions_100knock']
print('contract:', node['config'].get('contract'))
print('all columns have data_type:',
      all(c.get('data_type') for c in node['columns'].values()))
"
contract: {'enforced': True, 'alias_types': True, 'checksum': '...'}
all columns have data_type: True
```

## 解説まとめ

- **なぜ staging に contract を付けるのか (mart ではなく)**: mart には Topic ⑤ 5-3 で既に付けた。Topic ⑩ では「**新規ドメインなら staging から契約付きにする**」という、より厳格な運用を学ぶ。理由は「新規ドメインの int / mart が同時並行で立ち上がる」「staging を変えると全員が同時に壊れる」 から。新規だから後付けの手戻りコストが無く、 **始める時に払うべき初期コスト**。
- **「全列 `data_type:`」が all-or-nothing**: 1 列でも欠けるとその列は契約から外れる。staging が 8 列あれば 8 列全部に書く。逆に「全部書く」が決まれば、ER 図 (10-2) → sources (10-3) → staging contract (10-4) を **1 度書いた列リストの直訳** で済む。
- **`timestamp with time zone` を使う理由**: dbt 1.5 では `timestamptz` の alias 扱いがアダプタ依存。Postgres では問題ないが、`timestamp with time zone` (ISO 標準形) で書いておくと alias_types の挙動を気にしなくてよい。SQL 側は `::timestamptz` で短く書ける (Postgres alias)。
- **`(canceled_at is null)::boolean as is_active` の理由**: bool 派生列は staging で計算する。下流が `where is_active` でフィルタする時、毎回 `where canceled_at is null` を書かなくて済む = **意味の凝集** が staging 1 箇所に集まる。
- **stg_ に `_100knock` suffix を付ける**: MVP の `stg_*` と衝突しない。`stg_subscriptions_100knock` のように **常に suffix を付ける** のが Topic ⑩ の規律 (= 100-knock 演習の規律)。
- **「壊して→落ちて→直す」の体験を log に残す**: Topic ⑤ 5-4 と同じ運用。Contract Error を 1 回見ておくと、半年後に CI で同じ error が出た時に「あ、これか」と 1 秒で原因が分かる。**実体験の蓄積** が contract の真価。
- **physical raw が無い時の救済策**: SQL を `select 1::bigint as subscription_id, 1::bigint as customer_id, 'basic'::text as plan_code, 9.99::numeric(12,2) as monthly_price, current_timestamp as subscribed_at, NULL::timestamp with time zone as canceled_at, true::boolean as is_active, current_timestamp as loaded_at` の dummy SELECT に置き換えれば run まで通る。10-7 で CI スクリプト化する時の参考。
- **`dbt parse` だけで採点できる理由**: `contract: enforced=true` の宣言は manifest に入る。`data_type:` も manifest に入る。**parse 通過 + manifest_config check** だけで本問の主旨の 80% は採点可能。run 検証は raw データ整備が必要なので付加点扱い。
- **次の 10-5 への接続**: 本問で stg を作った。10-5 では `int_subscription_events_enriched_100knock` (= int model) を新規に作り、それに `groups: subscription_internal` + `access: private` を付けて「内部用」と宣言する。stg は public 寄り、int は private、mart は public という **3 層の公開範囲** が DAG に現れる。
