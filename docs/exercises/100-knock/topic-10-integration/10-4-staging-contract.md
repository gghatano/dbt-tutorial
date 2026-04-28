# 10-4: staging 層に `contract: enforced` (1.5+) + 全列 `data_type:` を宣言、型違反で run が落ちることを確認

## シナリオ

10-3 で source を宣言した。次は **staging 層** で **dbt 1.5+ の `contract: enforced`** を有効化し、新規ドメインの最初の staging から「型契約付きで生まれる」状態を作る。

通常 (Topic ⑤ 5-3) は **mart にだけ** contract を付けるのが定石だが、Topic ⑩ では「**新規ドメインなら staging から契約付きにする**」という、より厳格な運用を学ぶ。理由:

- 新規ドメインは下流 (intermediate / mart) の利用者が **複数同時に立ち上がる** ため、staging の列が変わると全員が同時に壊れる
- 既存の MVP / 100-knock 既存 staging には付いていないが、新規ドメインなら `data_type:` を最初から書く負担を「初期コストとして払う」 価値がある (= 半年後に列を変えると CI で必ず気付ける)
- 逆に既存 staging には後付けで付けると `numeric` precision の検証で大量の手戻りが出る (新規だから低コスト)

本問では `stg_subscriptions_100knock` を新規作成し、`config(contract={'enforced': true})` + schema.yml の全列 `data_type:` 宣言までを完成させる。最後に **わざと型を壊して run が fail すること** を log に残す。

## 学べること

- staging で `contract: enforced` を立てる時の注意点 (mart との違い)
- `data_type:` を ER 図 (10-2) → sources (10-3) → staging contract と直訳する設計
- Postgres 型の正確な書き方 (`bigint` vs `integer`、`numeric(12,2)` の precision)
- contract 違反時の `Contract Error` が `dbt run` で起きる挙動
- 「壊して落ちて直す」の 1 サイクルを log に残す習慣 (5-4 と同じ運用)

## 前提

- 10-3 完了 (`dbt/models/100-knock/topic-10/sources.yml` が parse 通過)
- dbt 1.5+ (本リポジトリは 1.10+ なので OK)
- raw に `subscriptions` 物理テーブルが無くても本問は parse + 1 run で fail を確認する形で完結 (raw が無い場合は SQL を `select 1::bigint as subscription_id, ...` のような骨組み select で代用 OK)

## 入力データ

不要。staging SQL の参照元は `{{ source('raw_100knock_subscriptions', 'subscriptions') }}` だが、source の物理テーブルが無くても **`config()` と schema.yml の宣言** までは parse できる。run の検証は採点対象外 (raw 物理テーブルが無いため)。

## 課題

### Step 1: stg_subscriptions_100knock.sql を作成

`dbt/models/100-knock/topic-10/stg_subscriptions_100knock.sql`:

```sql
{{ config(
    materialized='view',
    schema='staging',
    contract={'enforced': true}
) }}

-- ============================================================================
-- stg_subscriptions_100knock
-- ----------------------------------------------------------------------------
-- contract: enforced (10-4)
-- 全列 data_type を schema.yml で宣言済み。SQL の cast と data_type が
-- 不一致だと dbt run が Contract Error で落ちる。
--
-- upstream  : source('raw_100knock_subscriptions', 'subscriptions')
-- downstream: int_subscription_events_enriched_100knock (10-5 で作成想定)
-- ============================================================================

select
    subscription_id::bigint                  as subscription_id,
    customer_id::bigint                      as customer_id,
    plan_code::text                          as plan_code,
    monthly_price::numeric(12, 2)            as monthly_price,
    subscribed_at::timestamptz               as subscribed_at,
    canceled_at::timestamptz                 as canceled_at,
    (canceled_at is null)::boolean           as is_active,
    loaded_at::timestamptz                   as loaded_at
from {{ source('raw_100knock_subscriptions', 'subscriptions') }}
```

### Step 2: schema.yml に contract + data_type を全列宣言

`dbt/models/100-knock/topic-10/schema.yml`:

```yaml
version: 2

models:
  - name: stg_subscriptions_100knock
    config:
      contract:
        enforced: true
    description: |
      Staging for raw_100knock_subscriptions.subscriptions.
      contract: enforced で列名 + 列型を build 時に検証する。
    columns:
      - name: subscription_id
        data_type: bigint
        description: "PK"
        tests:
          - not_null
          - unique
      - name: customer_id
        data_type: bigint
        description: "FK to customers"
        tests:
          - not_null
      - name: plan_code
        data_type: text
        description: "プランコード"
        tests:
          - not_null
      - name: monthly_price
        data_type: numeric(12,2)
        description: "月額"
        tests:
          - not_null
      - name: subscribed_at
        data_type: timestamp with time zone
        description: "契約開始日時"
        tests:
          - not_null
      - name: canceled_at
        data_type: timestamp with time zone
        description: "解約日時。NULL ならアクティブ。"
      - name: is_active
        data_type: boolean
        description: "canceled_at IS NULL の派生列"
        tests:
          - not_null
      - name: loaded_at
        data_type: timestamp with time zone
        description: "raw 投入時刻"
        tests:
          - not_null
```

### Step 3: parse 確認

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# Found ... 1 new model (stg_subscriptions_100knock) ...
```

### Step 4: (任意) わざと型を壊して run fail を体験

`stg_subscriptions_100knock.sql` の 1 列を **わざと別の型に変える**:

```sql
-- 変更前:
monthly_price::numeric(12, 2)            as monthly_price,

-- 変更後 (壊す):
monthly_price::integer                   as monthly_price,
```

```bash
../.venv/bin/dbt run --profiles-dir . --select stg_subscriptions_100knock 2>&1 \
  | tee /tmp/10-4-violation.log
# Contract Error in model stg_subscriptions_100knock (...)
#   data type mismatch
# Done. PASS=0 ... ERROR=1
```

確認できたら **必ず元に戻す** (`numeric(12, 2)`)。
このログを `docs/exercises/100-knock/topic-10-integration/learner/10-4-violation-log.md` に残しておくと 10-8 の設計レビューで再利用可能。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-10-integration/10-4-staging-contract.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-10/stg_subscriptions_100knock.sql` が存在
- [ ] `dbt/models/100-knock/topic-10/schema.yml` が存在
- [ ] manifest 上で `model.local_analytics.stg_subscriptions_100knock` の `config.contract.enforced = true`
- [ ] schema.yml の `stg_subscriptions_100knock` の `columns:` 全列に `data_type:` が宣言されている
- [ ] `dbt parse` が exit 0 で成功
- [ ] (任意) Contract Error の 1 回体験ログ `learner/10-4-violation-log.md` がある (採点対象外、自己研鑽用)

## ヒント (詰まったら)

- **「全列に `data_type:` を書く」が必須**: 1 列でも欠けるとその列は contract から外れる。dbt は WARN ログで「unverified contract」と出すが、`enforced: true` の意義が薄れる。**all-or-nothing**。
- **`timestamp with time zone` vs `timestamptz`**: dbt + Postgres では同じ型のはずだが、dbt 1.5/1.6 では文字列マッチが厳格な場合がある。schema.yml で `timestamp with time zone` (フル名) を使うのが最も安全。SQL の `::timestamptz` は alias なので Postgres は同一視する。
- **`numeric(12,2)` の空白**: 表記揺れに注意。`numeric(12,2)` / `numeric(12, 2)` どちらでも parse は通るが、SQL 側の cast と schema.yml の表記を **完全に揃える** のが安全 (dbt 1.5 の厳格モード対策)。
- **派生列 `is_active` の data_type**: `(canceled_at is null)::boolean as is_active` のように右辺で `::boolean` を明示しておくと、dbt が型推定で迷わない。schema.yml は `data_type: boolean`。
- **新規 staging ディレクトリ**: `dbt/models/100-knock/topic-10/` は新規。`dbt_project.yml` の `model-paths: ["models"]` 配下なので追加設定は不要。
- **mart に contract を付けるのとの違い**: mart は consumer が外部 (BI) なので「型を変えると BI が壊れる」という直感が働きやすい。staging は内部だが、新規ドメインで **複数の int / mart が同時に立ち上がる** 想定なら、staging で型を凍結する方が DAG 全体の安定性が上がる。**設計判断問** として 10-8 で再考対象。
- **既存 staging に後付けしない理由**: MVP の `stg_orders` などに後付けすると、`numeric` の precision 検証で「実は precision が違っていた」が大量に出てくる。**新規だから低コスト** という機会を逃さない。
- **physical raw が無い時の動かし方**: `dbt parse` までは raw が無くても通る。`dbt run` を試したい場合は SQL を `select 1::bigint as subscription_id, 1::bigint as customer_id, 'basic'::text as plan_code, ...` のような **dummy SELECT** に一時的に差し替えると Contract Error 体験までできる (試したら戻す)。

## 解答例

詳細は [`10-4-staging-contract.solution.md`](10-4-staging-contract.solution.md) を参照。
