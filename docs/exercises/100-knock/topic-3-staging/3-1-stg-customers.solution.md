# 3-1 解答例

## dbt/models/100-knock/topic-3/stg_customers_100knock.sql

```sql
{{ config(materialized='view', schema='staging') }}

-- Staging contract for raw_100knock.customers (Topic ③ Q1).
-- All columns are explicitly cast so that downstream models do not depend on
-- the raw CSV's text typing. Materialized as a view: zero storage, always
-- reflects the latest raw load.
select
    customer_id::bigint     as customer_id,
    customer_name::text     as customer_name,
    email::text             as email,
    created_at::date        as created_at
from {{ source('raw_100knock', 'customers') }}
```

**ポイント**:

- **`{{ config(materialized='view', schema='staging') }}` を明示**: `models/100-knock/topic-3/`
  は `dbt_project.yml` の `models.local_analytics.staging.+schema: staging` の
  パス指定 (`staging/`) には引っかからない。明示しないと target schema
  (`dbt_user` など) に流れて、後で `staging.stg_customers_100knock` を期待する
  下流 (sql_assert / mart) と取り違える。
- **`view` materialization の理由**: staging は raw を「型と命名だけ整えて
  パススルーする層」。物理 storage を持たせる必要はなく、view にしておけば
  raw 側の COPY が走った瞬間に staging も最新化される (refresh 不要)。
- **明示 cast を全列に**: raw 層の DDL が将来 `customer_id` を `int` から
  `bigint` に変えても、staging で `::bigint` と書いてあれば下流の集計が
  サイレントに壊れない。**型の境界を staging に集約する** のが staging contract の
  本質。
- **`as customer_id` の重複**: 列名を変えていないが、`<expr> as <name>` は
  「この staging が公開する列名は <name> である」 という宣言。raw の列名が
  将来変わってもここで吸収できる。

## dbt/models/100-knock/topic-3/schema.yml (この問の最小版)

```yaml
version: 2

models:
  - name: stg_customers_100knock
    description: "Type-cast staging view of raw.customers (100-knock topic-3)."
    columns:
      - name: customer_id
        description: "Primary key (bigint)."
        tests:
          - not_null
          - unique
      - name: customer_name
        description: "Customer display name."
      - name: email
        description: "Customer email (unique by raw 1-1 contract)."
      - name: created_at
        description: "Customer registration date (date)."
```

**ポイント**:

- 3-4 で本格的にテストを増やすので、ここでは PK の `not_null` + `unique` の
  2 件だけ。grader はこれで PASS する。
- `description:` を入れておくと `dbt docs generate` 時に lineage / catalog に
  説明が出る。staging contract = 「データ仕様書」を兼ねるので、description は
  最初から付ける癖をつける。

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
04:31:00  Running with dbt=1.11.x
04:31:01  Registered adapter: postgres=1.9.x
04:31:01  Found 9 models, 5 sources, 63 data tests, ...

$ ../.venv/bin/dbt run --profiles-dir . --select stg_customers_100knock
04:31:10  1 of 1 START sql view model staging.stg_customers_100knock ... [RUN]
04:31:10  1 of 1 OK   created sql view model staging.stg_customers_100knock [CREATE VIEW in 0.10s]
04:31:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_customers_100knock
04:31:20  1 of 2 START test not_null_stg_customers_100knock_customer_id [RUN]
04:31:20  1 of 2 PASS  not_null_stg_customers_100knock_customer_id ..... [PASS]
04:31:20  2 of 2 START test unique_stg_customers_100knock_customer_id . [RUN]
04:31:20  2 of 2 PASS  unique_stg_customers_100knock_customer_id ....... [PASS]
04:31:20  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
```

`psql` で物理化を確認:

```sql
analytics=> SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='staging' AND table_name='stg_customers_100knock'
            ORDER BY ordinal_position;
 column_name   | data_type
---------------+-----------
 customer_id   | bigint
 customer_name | text
 email         | text
 created_at    | date
```

`text` から `date` / `bigint` に正しく変換されているのが確認できる。

## 解説まとめ

- **staging contract = 列名 / 型 / 命名規約の最初の宣言**: 「raw は壊れているかも
  しれない」「アナリストは raw を見ない」という前提のもとで、`source()` から
  読んだ生データを **下流が信用できる形に整える** のが staging。
- **view を選ぶ理由**: storage 不要 / refresh 不要 / 常に最新。staging で
  storage を消費するのは原則アンチパターン (大規模なら incremental だが、
  staging は薄いので view で十分)。
- **明示 cast の効能 (3 つ)**:
  1. raw の型変更が下流に伝播しない (型の境界を staging に集約)
  2. CSV 由来の text 列を date / bigint に持ち上げる責務が staging に明確化
  3. `dbt docs` の catalog に正確な型が載る (アナリストが安心)
- **`stg_<table>_100knock` 命名**: MVP の `stg_customers` と同じ node 名にすると
  dbt が `Found duplicate model` で落ちる。100-knock 演習であることを示す suffix で
  名前空間を切り、MVP との並走を可能にする。
- **`source('raw_100knock', ...)` を使う**: `source()` を使わず直接 schema を
  書く (`from raw.customers`) こともできるが、それでは dbt が DAG 上で
  上流依存を認識できず、`dbt source freshness` も走らない。**source 経由が staging の
  必須作法**。
