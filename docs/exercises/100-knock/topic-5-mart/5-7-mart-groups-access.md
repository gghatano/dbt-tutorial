# 5-7: `mart_customer_lifetime_value_100knock` を新規作成し、`groups:` (1.5+) で `marts_finance` グループに所属させる

## シナリオ

ある程度 mart が増えてくると、「この mart は finance チームの管理下、こっちは marketing チームの管理下」という **オーナーシップ境界** をコードで表現したくなる。同時に「こっちの mart は外 (BI) からも `ref()` してよいが、こっちは内部用なので他チームから `ref()` させたくない」という **公開範囲** も切り分けたい。

dbt 1.5+ の `groups:` + `access:` がこの宣言を担う:

- **`groups:`**: 「この model 群は `marts_finance` という意味的グループに属する」と宣言。group には `owner:` (連絡先) を持たせられる
- **`access:`**: model ごとに `private` / `protected` / `public` を宣言
  - `private`: **同じ group 内からしか `ref()` できない** (他チーム model からの参照を build 時 fail で止める)
  - `protected`: 同じ project 内なら誰でも参照可 (デフォルト)
  - `public`: project 外 (cross-project ref / dbt mesh) からも参照可

このエクササイズでは `mart_customer_lifetime_value_100knock` (= 顧客 LTV mart、finance 管理) を新規に作り、`groups: marts_finance` に所属させ、`access: private` を付ける。これで「marketing チームの int / mart からこの LTV mart を `ref()` するとパースエラーで止まる」状態を作る。

## 学べること

- `groups:` ブロックの YAML 文法 (`models/100-knock/topic-5/_groups.yml`)
- `config(group='marts_finance', access='private')` の宣言方法
- `private` / `protected` / `public` の意味的違い
- `manifest.json` の `nodes.<id>.config.group` / `access` フィールドの確認
- 「他チームの mart を勝手に参照しない」を build 時に強制する設計

## 前提

- Topic ② ③ ④ + Topic ⑤ 5-1〜5-5 完了
- `int_customer_orders_100knock` (= 顧客 × 注文の int model、Topic ④ で作る想定) または `int_order_details_100knock` のいずれかが ref 可能
  - 上記 int が無い場合は `stg_orders_100knock` + `stg_customers_100knock` 直結でも本問の主旨は損なわれない
- dbt 1.5+ (本リポジトリは 1.10+)

## 入力データ

不要。既存 stg / int から集計。

## 課題

### Step 1: `_groups.yml` を作成

`dbt/models/100-knock/topic-5/_groups.yml`:

```yaml
version: 2

groups:
  - name: marts_finance
    owner:
      name: Finance Team
      email: finance@example.com
      slack: "#mart-finance"
```

(`_groups.yml` というファイル名は dbt 公式の命名慣習。アンダースコア prefix で「メタ的な定義」感を出す)

### Step 2: `mart_customer_lifetime_value_100knock.sql` を作成

`dbt/models/100-knock/topic-5/mart_customer_lifetime_value_100knock.sql`:

冒頭の `config()` で `group='marts_finance'`, `access='private'` を宣言。SQL 本体は customer_id 単位の集計で、列は最低限以下:

- `customer_id` (PK)
- `customer_name`
- `lifetime_order_count` (注文回数)
- `lifetime_sales_amount` (生涯売上、numeric(18,2))
- `first_order_date` / `last_order_date`
- `tenure_days` (`last - first` の日数差)

参照元は `stg_customers_100knock` + `stg_orders_100knock` (もしくは `int_order_details_100knock`)。

### Step 3: `dbt parse` で構文確認

```bash
cd dbt
dbt parse --profiles-dir .
```

`groups:` / `group:` / `access:` が正しいと黙って通る。誤字 (`marts_financee` など) があると "Group 'marts_financee' is not defined" で fail する (これも学習機会として体験するとよい)。

### Step 4: `dbt build` で実行

```bash
dbt build --select mart_customer_lifetime_value_100knock --profiles-dir .
```

PASS=1 で完了する。table が `marts.mart_customer_lifetime_value_100knock` に作成される。

### Step 5: (任意) `private` の効果を体験

別 group (例: `marts_marketing`、未定義でも temporarily で OK) の model で `{{ ref('mart_customer_lifetime_value_100knock') }}` してみる。`dbt parse` で:

```
Compilation Error in model marts_marketing.foo
  Node model.local_analytics.foo attempted to reference node
  model.local_analytics.mart_customer_lifetime_value_100knock,
  which is not allowed because the referenced node is private to the marts_finance group.
```

このエラーを見たら成功。試したらすぐ revert (採点には影響しない)。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-7-mart-groups-access.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/_groups.yml` が存在し、`marts_finance` group が定義されている
- [ ] `dbt/models/100-knock/topic-5/mart_customer_lifetime_value_100knock.sql` が存在
- [ ] model の `config()` に `group='marts_finance'` と `access='private'` が宣言されている
- [ ] `dbt parse` が PASS
- [ ] `dbt build --select mart_customer_lifetime_value_100knock` が PASS

## ヒント (詰まったら)

- **`groups:` のオーナー記法**: `owner:` は dict で `name` / `email` / `slack` などを持てる。`email` は dbt docs で表示される。
- **`access:` の 3 値**: `private` / `protected` / `public`。デフォルトは `protected` (同じ project 内なら誰でも `ref()`)。`public` は cross-project (dbt mesh) で意味を持つので 1 project 環境では `protected` と機能的に同じ。
- **`group:` 宣言の書き場所**: SQL 内の `{{ config(group='marts_finance') }}` か、`schema.yml` の `models[*].config.group` か、`dbt_project.yml` の path-based config どれでも可。本問は SQL 内の `config()` で完結させる方針。
- **複数 group**: 1 model は 1 group にしか属せない (group は排他的所有権)。「複数チームで共有」したいなら public にして tag で分類する設計に。
- **`Group 'X' is not defined' エラー**: `_groups.yml` の `groups:` ブロックに対象 group が無い。typo (例: `marts_financee`) や別ファイルに書いてしまっている等を確認。
- **ファイル名の `_` prefix**: dbt は `_*.yml` も `*.yml` も同じく読む。`_groups.yml` / `_models.yml` などは「メタ定義」「集約 yml」を表す慣習名。
- **オーナーシップを `meta:` で増強**: `owner` は group 単位だが、model 単位でさらに細かい運用情報 (sla_hours, dashboard URL) を持たせたい場合は `meta:` ブロックを使う (= 5-8 で扱う)。

## 解答例

詳細は [`5-7-mart-groups-access.solution.md`](5-7-mart-groups-access.solution.md) を参照。
