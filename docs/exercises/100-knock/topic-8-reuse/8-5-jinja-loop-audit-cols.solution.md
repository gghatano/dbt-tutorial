# 8-5 解答例

## dbt/macros/100-knock/topic-8/add_audit_columns.sql

```jinja
{#-
    Topic ⑧ 8-5: 4 staging テーブルに last_updated_at 列を冪等に追加 + 更新する macro。

    なぜ macro 化するか:
      - 4 staging に同じ ALTER TABLE / UPDATE を書くと DRY 違反 (4 model 改修)
      - macro 1 ファイルに集約すれば、対象テーブル list の追加 / 削除が 1 行差分で済む

    使い方 (model 側 config):
        {{ config(
            materialized='table',
            schema='staging',
            pre_hook=["{{ add_audit_columns() }}"]
        ) }}

    冪等性:
      - ADD COLUMN IF NOT EXISTS で 2 回目以降の dbt run でもエラーにならない
      - UPDATE は毎回走るので、last_updated_at は最新 dbt run の時刻になる
-#}
{% macro add_audit_columns() %}
    {%- set tables = [
        ('staging', 'stg_orders_100knock'),
        ('staging', 'stg_customers_100knock'),
        ('staging', 'stg_products_100knock'),
        ('staging', 'stg_stores_100knock'),
    ] -%}
    {%- for schema, tbl in tables %}
        ALTER TABLE {{ schema }}.{{ tbl }}
            ADD COLUMN IF NOT EXISTS last_updated_at timestamptz DEFAULT current_timestamp;
        UPDATE {{ schema }}.{{ tbl }} SET last_updated_at = current_timestamp;
    {%- endfor %}
{% endmacro %}
```

**ポイント**:

- **`{%- ... -%}` のハイフン**: 前後の空白を削るマーカー。SQL 出力をクリーンに保つ。
  無くても動くが、compiled SQL を読む時に空行だらけだと辛い。
- **`tables` list を `{% set %}` で先頭宣言**: 「対象テーブル list」 が macro 内
  最上部にあるのが重要。staging が増えた時 (例: `stg_reviews_100knock` を追加)、
  この list に 1 行足すだけで pre_hook 経由で audit 列が付く。
- **`(schema, tbl)` の tuple unpacking**: Jinja は Python 同様 tuple unpacking が
  効くので `{% for schema, tbl in tables %}` と書ける。可読性が上がる。
- **`ADD COLUMN IF NOT EXISTS`**: PostgreSQL 9.6+ の機能。これで `dbt run` を
  何度叩いても列追加は **1 回目のみ実行、2 回目以降は no-op**。冪等性の鉄則。
- **`DEFAULT current_timestamp`**: 列追加時に既存行の値を初期化。新規行も自動で
  current_timestamp が入る。
- **`UPDATE ... SET ... = current_timestamp`**: 「dbt run のたびに更新」 を強制する
  ための明示 UPDATE。DEFAULT だけでは既存行は更新されないので必要。

## 4 staging の config 改修

### dbt/models/100-knock/topic-3/stg_orders_100knock.sql (先頭の config のみ)

```sql
{{ config(
    materialized='table',
    schema='staging',
    pre_hook=["{{ add_audit_columns() }}"]
) }}

select
    order_id::bigint                            as order_id,
    -- ... (8-1 の cast_money 適用後の SELECT 本体は変えない)
from {{ source('raw_100knock', 'orders') }}
```

### dbt/models/100-knock/topic-3/stg_customers_100knock.sql (config 部分)

```sql
{{ config(
    materialized='table',
    schema='staging',
    pre_hook=["{{ add_audit_columns() }}"]
) }}
-- (SELECT 本体は変えない)
```

### dbt/models/100-knock/topic-3/stg_products_100knock.sql (config 部分)

```sql
{{ config(
    materialized='table',
    schema='staging',
    pre_hook=["{{ add_audit_columns() }}"]
) }}
-- (SELECT 本体は変えない)
```

### dbt/models/100-knock/topic-3/stg_stores_100knock.sql (config 部分)

```sql
{{ config(
    materialized='table',
    schema='staging',
    pre_hook=["{{ add_audit_columns() }}"]
) }}
-- (SELECT 本体は変えない)
```

**ポイント**:

- **4 model に同じ config**: 「同じ pre_hook を 4 箇所書く」 のは DRY 違反だが、
  本問は **「pre_hook を model 個別 config で持つ作法」 を体験** が目的。
  実務的には `dbt_project.yml` の `models: 100-knock: topic-3: +pre_hook: [...]`
  でディレクトリ単位に統一する案もある (発展課題、Topic ⑧ 後半 or Topic ⑨ で再登場可能)。
- **`materialized='table'` への変更**: view では ALTER TABLE が効かない。table に
  切り替えることで storage は使うが、`last_updated_at` を永続化できる。Topic ⑨ で
  「storage コスト vs 観測性」 のトレードオフを再考する。
- **SELECT 本体は変えない**: Topic ⑧ 8-1 で書き換えた `cast_money` 呼び出しは
  そのまま温存。本問の改修は config 部分のみ。

## 実行例

```text
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 1 macro (add_audit_columns), ...

$ ../.venv/bin/dbt run --profiles-dir . --select \
    stg_orders_100knock stg_customers_100knock stg_products_100knock stg_stores_100knock
1 of 4 START sql table model staging.stg_orders_100knock ......... [RUN]
1 of 4 PRE  hook running ALTER TABLE ... + UPDATE ...               [OK]
1 of 4 OK created sql table model staging.stg_orders_100knock ..... [SELECT 10000 in 0.30s]
2 of 4 START sql table model staging.stg_customers_100knock ........ [RUN]
2 of 4 PRE  hook running ALTER TABLE ... + UPDATE ...               [OK]
2 of 4 OK created sql table model staging.stg_customers_100knock .. [SELECT 1000 in 0.10s]
... (3 of 4, 4 of 4 同様) ...
Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

> **注**: pre_hook が 4 model 全部で走るので、合計 4 回 macro が呼ばれている。
> 各 macro 呼び出しが 4 staging 全部に対して ALTER + UPDATE するので **計 16 回**
> SQL が走るが、ADD COLUMN IF NOT EXISTS が冪等なので結果は同じ。

物理確認:

```sql
analytics=> SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='staging'
              AND column_name='last_updated_at'
            ORDER BY table_name;
       table_name        |   column_name    |          data_type
-------------------------+------------------+--------------------------------
 stg_customers_100knock  | last_updated_at  | timestamp with time zone
 stg_orders_100knock     | last_updated_at  | timestamp with time zone
 stg_products_100knock   | last_updated_at  | timestamp with time zone
 stg_stores_100knock     | last_updated_at  | timestamp with time zone

analytics=> SELECT max(last_updated_at) FROM staging.stg_orders_100knock;
       max
-------------------------------
 2026-04-26 14:30:02.345+09
```

`last_updated_at` が直近 dbt run の時刻になっている (`UPDATE` が効いた証拠)。

## compiled SQL の確認

```bash
$ cat target/compiled/local_analytics/models/100-knock/topic-3/stg_orders_100knock.sql
-- (model 本体)

# pre_hook の compile 結果は target/run/.../stg_orders_100knock.sql の方に出る
$ cat target/run/local_analytics/models/100-knock/topic-3/stg_orders_100knock.sql | head -30
ALTER TABLE staging.stg_orders_100knock
    ADD COLUMN IF NOT EXISTS last_updated_at timestamptz DEFAULT current_timestamp;
UPDATE staging.stg_orders_100knock SET last_updated_at = current_timestamp;
ALTER TABLE staging.stg_customers_100knock
    ADD COLUMN IF NOT EXISTS last_updated_at timestamptz DEFAULT current_timestamp;
UPDATE staging.stg_customers_100knock SET last_updated_at = current_timestamp;
... (4 staging 全部) ...

create table "analytics"."staging"."stg_orders_100knock" as
( -- model 本体 SELECT )
;
```

`{% for %}` loop が「4 ペアの ALTER + UPDATE」 に展開されて、その後に model 本体の
CREATE TABLE が続く構造。

## 解説まとめ

- **Jinja `{% for %}` の本質**: SQL を **テンプレート的に繰り返し生成** できる。
  「同じパターンを N 回書く」 が 1 行 list の追加で済む = DRY の極限形。
  list を別ファイル / `dbt_project.yml` の `vars:` に外出しすれば「対象テーブル
  リストをコード以外で管理」 もできる (発展課題)。
- **`pre_hook` / `post_hook` / `on-run-start` / `on-run-end` の使い分け**:

  | hook              | タイミング                        | 用途                          |
  |-------------------|-----------------------------------|-------------------------------|
  | `pre_hook`        | model 1 つの build 直前           | model 個別の前処理 (権限付与, snapshot 等) |
  | `post_hook`       | model 1 つの build 直後           | model 個別の後処理 (`GRANT`, ANALYZE) |
  | `on-run-start`    | `dbt run` 全体の最初 (1 回)       | run 全体の前処理 (audit log INSERT 等) |
  | `on-run-end`      | `dbt run` 全体の最後 (1 回)       | run 全体の後処理 (notification 等) |

  本問は **「macro を試したい」 + 「model 単位で hook を持つ作法を学ぶ」** で
  `pre_hook` を選択。実務的には全 staging に 1 回でいいので `on-run-start` の
  方が効率的 (発展課題)。
- **冪等性の重要性**: `ADD COLUMN IF NOT EXISTS` を忘れて何度も `dbt run` を
  叩くと、2 回目で `column "last_updated_at" already exists` エラー。本番運用では
  「冪等な hook」 が前提。`UPDATE` 側は冪等でなくてもよい (毎回上書きが意図通り)。
- **macro = 開発ロジックの依存元**: 4 staging が `add_audit_columns` macro に
  「依存」 している。macro 1 ファイルを修正すれば 4 staging に波及する。
  これが `dbt-utils` のような外部パッケージ macro と全く同じ構造 (8-2 の伏線)。
- **`{% set %}` での「定数 list」**: macro 内で `tables` list を `{% set %}` で
  宣言する作法は jinja 流の「定数定義」。Python の `TABLES = [...]` モジュール定数
  と同じ感覚。
- **MVP との関係**: MVP の `stg_orders` (Ex.01) には `last_updated_at` を付けない。
  本演習は **100-knock の staging だけ** を対象にしている = `tables` list で対象を
  絞っているのが効いている。
- **発展**: `on-run-start` に切り替える / `vars` で対象 list を外出し / `dbt_project.yml`
  の `models: ... +pre_hook` でディレクトリ統一 / `{% if execute %}` で parse 安全化…
  と拡張ネタは尽きない。8-5 はその入り口。
