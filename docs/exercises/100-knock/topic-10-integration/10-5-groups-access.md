# 10-5: `groups:` + `access:` で intermediate model を `subscription_internal` の `private` にする

## シナリオ

10-4 で staging に契約を立てた。次は **DAG の公開範囲** を宣言で制御する。dbt 1.5+ の `groups:` + `access:` で:

- intermediate model `int_subscription_events_enriched_100knock` を **`group: subscription_internal`** に所属させる
- `access: private` を宣言する
- 別 group の model から `ref()` するとパースエラーになることを確認する

これにより「subscriptions ドメイン内部の中間 model は **subscription_internal group の中からしか参照できない**」状態を作る。下流の `mart_*_100knock` は同じ group なら参照可、別 group の model は参照不可 = **モジュラリティが build 時に強制される**。

10-1 で書いたステークホルダー (経営企画 / CS / 経理) は **group の owner** として記録する。「データに障害が起きたら誰に slack を飛ばすか」 が機械可読化される。

## 学べること

- `groups:` ブロックの YAML 文法 (`_groups.yml`)
- `config(group='subscription_internal', access='private')` の書き方
- `private` / `protected` / `public` の意味的違い (mesh vs project 内)
- `manifest.json` の `nodes.<id>.config.group` / `access` の確認
- 「別 group からの `ref()` で parse error」を **テスト用 fail model を一時作成 → parse → 削除** で確認する self-cleaning パターン

## 前提

- 10-4 完了 (`stg_subscriptions_100knock` が存在、`dbt parse` が緑)
- dbt 1.5+ (本リポジトリは 1.10+)

## 入力データ

不要。staging の上に int model を 1 つ作るだけ。

## 課題

### Step 1: `_groups.yml` を作成

`dbt/models/100-knock/topic-10/_groups.yml`:

```yaml
version: 2

groups:
  - name: subscription_internal
    owner:
      name: Subscriptions Data Squad
      email: gakikame0405@gmail.com   # 学習者自身の email
      slack: "#data-platform"
```

(`_groups.yml` の `_` prefix は dbt の慣習で「メタ定義」を表す)

### Step 2: int model を作成、`group:` + `access:` を宣言

`dbt/models/100-knock/topic-10/int_subscription_events_enriched_100knock.sql`:

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
-- group  : subscription_internal (10-5 で宣言)
-- access : private — 同じ group の model からしか ref() できない
-- grain  : 1 (subscription_id, event_at) で 1 行
-- ============================================================================

select
    e.event_id,
    e.subscription_id,
    s.customer_id,
    s.plan_code,
    s.monthly_price,
    e.event_type,
    e.event_at,
    e.payload
from {{ ref('stg_subscription_events_100knock') }} as e
left join {{ ref('stg_subscriptions_100knock') }} as s
    on e.subscription_id = s.subscription_id
```

(stg_subscription_events_100knock が無い場合は 10-4 解答例を参照して作成)

### Step 3: schema.yml に int model の宣言を追記

`dbt/models/100-knock/topic-10/schema.yml` の `models:` 配下に追加:

```yaml
  - name: int_subscription_events_enriched_100knock
    config:
      group: subscription_internal
      access: private
    description: |
      Subscription event を customer_id / plan_code で enrich した中間 model。
      access: private — subscription_internal group からのみ ref 可。
    columns:
      - name: event_id
        tests:
          - not_null
          - unique
      - name: subscription_id
        tests:
          - not_null
      - name: customer_id
      - name: plan_code
      - name: monthly_price
      - name: event_type
        tests:
          - not_null
      - name: event_at
        tests:
          - not_null
      - name: payload
```

### Step 4: parse 確認

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# Found ... 1 group, 1 new model (int_*) ...
```

### Step 5: 別 group からの `ref()` で fail することを確認 (self-cleaning)

**一時的に** test 用 fail model を作る:

```bash
cat > dbt/models/100-knock/topic-10/_test_cross_group.sql <<'EOF'
{{ config(
    materialized='view',
    schema='staging',
    group='marts_external'
) }}
-- 別 group (marts_external) から private model を ref する → parse error 期待
select * from {{ ref('int_subscription_events_enriched_100knock') }}
EOF

# marts_external group も追加宣言が必要 (未宣言 group の参照は別エラーになる)
cat >> dbt/models/100-knock/topic-10/_groups.yml <<'EOF'

  - name: marts_external
    owner:
      name: External BI Team
      email: external@example.com
EOF

../.venv/bin/dbt parse --profiles-dir . 2>&1 | tee /tmp/10-5-fail.log
# 期待:
# Compilation Error
#   Node model.local_analytics._test_cross_group attempted to reference node
#   model.local_analytics.int_subscription_events_enriched_100knock,
#   which is not allowed because the referenced node is private to the
#   subscription_internal group.

# 確認できたら必ず削除 (self-cleaning):
rm dbt/models/100-knock/topic-10/_test_cross_group.sql
# _groups.yml の marts_external 追記も手で消す (or git checkout で戻す)

# 再 parse で緑に戻ることを確認
../.venv/bin/dbt parse --profiles-dir .
# Done.
```

self-cleaning パターン: **試して → 確認して → 必ず削除**。
parse fail のログ (`/tmp/10-5-fail.log`) を `learner/10-5-private-violation-log.md` に貼っておくと 10-8 で再利用可能。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-10-integration/10-5-groups-access.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-10/_groups.yml` が存在し、`subscription_internal` group が宣言
- [ ] `dbt/models/100-knock/topic-10/int_subscription_events_enriched_100knock.sql` が存在
- [ ] manifest 上で int model の `config.group = subscription_internal` かつ `access = private`
- [ ] `dbt parse` が exit 0 で成功 (= self-cleaning 後の状態で緑)
- [ ] (任意) `learner/10-5-private-violation-log.md` に「別 group ref で parse error」のログ

## ヒント (詰まったら)

- **`access:` の 3 値**: `private` / `protected` / `public`。デフォルトは `protected` (同 project 内なら自由に ref)。`public` は cross-project (dbt mesh) で意味を持つので 1 project 環境では `protected` と機能的に同じ。`private` だけが「同じ group の中からしか ref 不可」という強い制約。
- **`group:` 宣言の置き場所**: SQL 内の `{{ config(group='...') }}` か、`schema.yml` の `models[*].config.group` か、`dbt_project.yml` の path-based config どれでも可。本問は **両方** に書く (SQL と schema.yml の二重宣言で可読性 UP)。
- **複数 group**: 1 model は 1 group にしか属せない (group は排他的所有権)。「複数チームで共有」したいなら public + tag 分類。
- **`Group 'X' is not defined' エラー**: `_groups.yml` に該当 group が無い、または別ディレクトリに書いてしまっている。本問は同ディレクトリの `_groups.yml` で完結させる。
- **self-cleaning パターンの意義**: 「fail することを確認するために fail させる」のは正しい学習だが、commit に残すと CI が常に red になる。**試して → 確認して → 削除** の 3 ステップを **1 つの作業** として身につける。
- **owner email を空白にしない**: dbt docs に表示される。本演習では学習者自身の email (`gakikame0405@gmail.com`) で OK。実務ではチームの mailing list / slack channel を書く。
- **stg は public のまま**: 10-4 で作った stg_* には `access:` 宣言を入れていない (= デフォルト `protected`)。staging は「下流に広く晒す」レイヤーなので protected が標準。private にするのは int / 一部 mart だけ。
- **mart の access**: 10-1 の要件で `mart_*_100knock` 3 本は `access: public` 想定。本問は int の private に集中するが、10-6 (sibling agent) で mart の access が再登場する流れ。
- **「private にすると mart からも見えなくなる？」**: いいえ。mart も同じ `subscription_internal` group に入れれば見える。本問では int だけ private、mart は別 group (= subscription_external など、10-6 で扱う) にする想定。**group 境界 = 公開範囲境界**。

## 解答例

詳細は [`10-5-groups-access.solution.md`](10-5-groups-access.solution.md) を参照。
