# 10-5 解答例

> subscriptions ドメインに `subscription_internal` group を立て、新規 int model を
> `access: private` にする。stg は protected (デフォルト)、int は private、
> mart は public (10-6 で扱う) という 3 層の公開範囲を作る。

## dbt/models/100-knock/topic-10/_groups.yml

```yaml
version: 2

# ============================================================================
# Subscriptions ドメインの group 宣言 (10-5)
#   subscription_internal: ドメイン内部 model 用。int は private にする。
#   subscription_public:   外部公開 model 用 (mart, exposure)。10-6 で参照。
# ============================================================================

groups:
  - name: subscription_internal
    owner:
      name: Subscriptions Data Squad
      email: gakikame0405@gmail.com
      slack: "#data-platform"

  # 10-6 で mart 側から使う想定。本問は宣言のみで、mart の所属は 10-6 で行う。
  - name: subscription_public
    owner:
      name: Subscriptions Analytics Team
      email: gakikame0405@gmail.com
      slack: "#analytics-subscription"
```

## dbt/models/100-knock/topic-10/int_subscription_events_enriched_100knock.sql

```sql
{{ config(
    materialized='view',
    schema='intermediate',
    group='subscription_internal',
    access='private'
) }}

-- ============================================================================
-- int_subscription_events_enriched_100knock
-- ----------------------------------------------------------------------------
-- group  : subscription_internal
-- access : private
--   subscription_internal group の model からしか ref() できない。
--   別 group (e.g. marts_external) からの ref() は dbt parse で fail する。
--
-- grain     : 1 (event_id) で 1 行
-- upstream  : stg_subscription_events_100knock + stg_subscriptions_100knock
-- downstream: mart_subscription_mrr_100knock 他 (10-6 で作成想定)
-- ============================================================================

select
    e.event_id,
    e.subscription_id,
    s.customer_id,
    s.plan_code,
    s.monthly_price,
    e.event_type,
    e.event_at,
    e.payload,
    e.loaded_at
from {{ ref('stg_subscription_events_100knock') }} as e
left join {{ ref('stg_subscriptions_100knock') }} as s
    on e.subscription_id = s.subscription_id
```

## dbt/models/100-knock/topic-10/schema.yml (int 部分の追加)

```yaml
# 既存 stg_* の宣言の続きに追加:

  - name: int_subscription_events_enriched_100knock
    config:
      group: subscription_internal
      access: private
    description: |
      Subscription event を customer_id / plan_code / monthly_price で enrich した中間 model。
      group: subscription_internal / access: private — 同 group の mart からのみ ref 可。
    columns:
      - name: event_id
        description: "PK"
        tests:
          - not_null
          - unique
      - name: subscription_id
        tests:
          - not_null
      - name: customer_id
        description: "ref から引いた顧客 ID"
      - name: plan_code
      - name: monthly_price
      - name: event_type
        tests:
          - not_null
      - name: event_at
        tests:
          - not_null
      - name: payload
      - name: loaded_at
```

## Step 5: 別 group からの ref を試す (self-cleaning)

```bash
# 1. 一時 fail model を作成
$ cat > dbt/models/100-knock/topic-10/_test_cross_group.sql <<'EOF'
{{ config(
    materialized='view',
    schema='staging',
    group='marts_external'
) }}
select * from {{ ref('int_subscription_events_enriched_100knock') }}
EOF

# 2. _groups.yml に marts_external を一時追記
$ cat >> dbt/models/100-knock/topic-10/_groups.yml <<'EOF'

  - name: marts_external
    owner:
      email: external@example.com
EOF

# 3. parse 実行 → 期待: parse error
$ ../.venv/bin/dbt parse --profiles-dir . 2>&1 | tee /tmp/10-5-fail.log

Compilation Error
  Node model.local_analytics._test_cross_group attempted to reference node
  model.local_analytics.int_subscription_events_enriched_100knock,
  which is not allowed because the referenced node is private to the
  subscription_internal group.

# 4. log を learner ディレクトリに保存 (10-8 用)
$ cp /tmp/10-5-fail.log \
    docs/exercises/100-knock/topic-10-integration/learner/10-5-private-violation-log.md

# 5. self-cleaning: 試行用ファイルを必ず削除
$ rm dbt/models/100-knock/topic-10/_test_cross_group.sql
$ # _groups.yml の marts_external 追記を手で削除 (or git checkout で戻す)
$ git checkout dbt/models/100-knock/topic-10/_groups.yml

# 6. 再 parse で緑に戻ることを確認
$ ../.venv/bin/dbt parse --profiles-dir .
12:35:00  Found 8 models, 25 tests, 2 sources, 0 exposures, 0 metrics, 2 groups
12:35:00  Done.
```

## 実行ログ例 (修復後 = 通常状態)

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
12:30:00  Found 8 models, 25 tests, 2 sources, 0 exposures, 0 metrics, 2 groups
12:30:00  Done.
```

manifest 確認:

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.int_subscription_events_enriched_100knock']
print('group:',  node['config'].get('group'))
print('access:', node.get('access'))
print('group_owner:',
      next((g for g in m.get('groups', {}).values()
            if g['name'] == 'subscription_internal'), {}).get('owner'))
"
group: subscription_internal
access: private
group_owner: {'name': 'Subscriptions Data Squad', 'email': 'gakikame0405@gmail.com', 'slack': '#data-platform'}
```

## 解説まとめ

- **なぜ `groups:` + `access:` を新規ドメインで使うか**: 新規ドメインは「内部用」「外部用」の境界が **設計時に決められる絶好の機会**。既存ドメインに後付けすると「実は別チームから ref されていた」が大量に出てきて手戻りになる。新規だから低コスト。
- **3 層の公開範囲モデル**:
  - **stg** (デフォルト protected): ドメイン内外問わず ref 可。型契約 (10-4) はあるが access は緩め
  - **int** (`access: private`): subscription_internal 内部からのみ ref 可。中間集計の凝集を破壊から守る
  - **mart** (`access: public` を 10-6 で宣言): BI / reverse_etl など外部から ref 可
- **`subscription_internal` という group 名**: ドメイン名 + 役割 (`internal` / `public`)。`marts_finance` のような部門名でなく **ドメイン名で割る** のが本ドメインの特徴。「経理が見る = mart は public」「内部の派生計算 = int は private」と意味で分かれる。
- **owner の email**: docs に表示される。「データに障害が起きた時 / 仕様変更したい時の連絡先」が `_groups.yml` に書かれている = **半年後の自分が誰に slack を投げればいいか分かる**。実運用では mailing list / slack channel が望ましい。
- **`config()` の SQL と schema.yml の二重宣言**: SQL 側 (`{{ config(group=..., access=...) }}`) と schema.yml 側 (`config: group: ... access: ...`) の両方に書ける。本解答では両方書いた (SQL を読む人が config() で気付ける + schema.yml を読む人が config: で気付ける、双方に対する可読性)。**値が一致していれば dbt はエラーにしない**。
- **self-cleaning の意義**: 「fail を確認するために fail させる」のは学習として正しいが、コミットに残すと CI が常に red。**試行 → ログを残す → 削除** を 1 つの作業ユニットにする。git checkout で戻す癖を付ける。
- **「mart も private にしないのか？」**: mart の本質は **外部公開**。private にすると Metabase / reverse_etl から `ref()` できなくなる (実際には Metabase は SQL 直叩きなので ref しないが、dbt mesh に乗せた時に詰む)。mart は public が原則。
- **`access: protected` をいつ使うか**: 「同 project 内なら誰でも ref 可。dbt mesh で他 project からは ref 不可」。本リポジトリは 1 project なので protected と private 以外の差は事実上 public との境目だけ。学習段階では「private vs protected = 同 group 制約あり/なし」「protected vs public = mesh 制約あり/なし」 と覚えれば十分。
- **次の 10-6 への接続 (sibling agent 担当)**: 10-6 では `mart_*_100knock` を新規作成し、`subscription_public` group + `access: public` を付ける。本問で立てた `subscription_internal` group は int 専用、`subscription_public` は mart 専用 という **2 group 構成** がドメインの公開範囲を決める。
- **dbt mesh を視野に入れた設計**: `access: public` は dbt mesh (project 間 ref) で本領発揮。本リポジトリは 1 project で完結するが、将来 `subscription` project を切り離す時に「public な mart だけ他 project から見える」が無料で実現する。**今の設計が将来の分割の容易さを決める**。
