# Exercise 03 解答例

## Step 1: `scripts/exercises/load_orders_increment.py`

学習者の手元に置く想定。リポジトリ管理対象外（生成 CSV と同じく一時的）。

```python
"""Load a single orders CSV into raw.orders_increment.

Usage:
    python scripts/exercises/load_orders_increment.py \
        --csv data/exercises/inbox/orders_2026-04-27.csv --mode replace
    python scripts/exercises/load_orders_increment.py \
        --csv data/exercises/inbox/orders_2026-04-28.csv --mode append
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

DDL = """
CREATE TABLE IF NOT EXISTS raw.orders_increment (
    order_id    BIGINT,
    order_date  DATE,
    customer_id BIGINT,
    product_id  BIGINT,
    store_id    BIGINT,
    quantity    INT,
    unit_price  NUMERIC(12, 2),
    loaded_at   TIMESTAMP
)
"""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--mode", choices=("replace", "append"), default="append")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env", override=False)
    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(f"CSV missing: {csv_path}", file=sys.stderr)
        return 1

    dsn = (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        if args.mode == "replace":
            cur.execute("DROP TABLE IF EXISTS raw.orders_increment CASCADE")
        cur.execute(DDL)

        copy_sql = "COPY raw.orders_increment FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        with cur.copy(copy_sql) as cp, csv_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)

        cur.execute("SELECT count(*) FROM raw.orders_increment")
        print(f"raw.orders_increment now has {cur.fetchone()[0]} rows (mode={args.mode})")
        conn.commit()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**ポイント**:

- `CREATE TABLE IF NOT EXISTS` + `DROP` を `mode=replace` のときだけ実行 → append モードでは既存行を保ったまま COPY で追加できる。
- 単一トランザクションで COPY → ロード途中失敗時に部分書き込みが残らない。

## Step 2: `dbt/models/exercises/03/sources.yml`

```yaml
version: 2

sources:
  - name: raw_exercise_03
    schema: raw
    description: "Daily-incremented orders inbox for Exercise 03."
    tables:
      - name: orders_increment
        description: "Per-day appended orders (PK: order_id)."
        columns:
          - name: order_id
            tests:
              - not_null
          - name: order_date
            tests:
              - not_null
          - name: loaded_at
            tests:
              - not_null
```

`unique` を `order_id` に付けないのは、source 段階で `\copy` のミスや CSV 重複で source test が落ちると incremental の検証ができなくなるため。重複検知は staging `stg_orders_inc.order_id` に `unique` テストを置くのが綺麗。

## Step 3: `dbt/models/exercises/03/stg_orders_inc.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='order_id',
        incremental_strategy='merge',
        on_schema_change='fail',
        schema='staging'
    )
}}

select
    order_id::bigint            as order_id,
    order_date::date            as order_date,
    customer_id::bigint         as customer_id,
    product_id::bigint          as product_id,
    store_id::bigint            as store_id,
    quantity::int               as quantity,
    unit_price::numeric(12, 2)  as unit_price,
    loaded_at::timestamp        as loaded_at
from {{ source('raw_exercise_03', 'orders_increment') }}

{% if is_incremental() %}
where loaded_at > (select coalesce(max(loaded_at), '1970-01-01'::timestamp) from {{ this }})
{% endif %}
```

**ポイント**:

- `materialized='incremental'`: dbt が「初回は CREATE、2 回目以降は MERGE / INSERT」を自動で振り分ける。
- `unique_key='order_id'`: `merge` strategy が PK 重複を `UPDATE`（実態は delete+insert）で吸収するために必須。
- `incremental_strategy='merge'`: postgres-adapter では内部的に「temp table 作って delete + insert」に展開される。
- `on_schema_change='fail'`: source CSV のスキーマが変わった場合に黙って崩れずに run を落とす保守的設定。
- `is_incremental()` ブロック: 初回（table が無い）と `--full-refresh` 時は False、それ以外で True。`max(loaded_at)` を high-water mark にして差分だけを引っ張る。
- `{{ this }}`: 現在ビルド中のモデル自身を指す jinja。`ref('stg_orders_inc')` だと自己参照で循環エラーになるので `{{ this }}` 必須。

## Step 4-5: 実行ログ例

### 1 日目

```bash
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-27 --rows 500
# Generated .../orders_2026-04-27.csv: 500 rows (date=2026-04-27)
.venv/bin/python scripts/exercises/load_orders_increment.py \
    --csv data/exercises/inbox/orders_2026-04-27.csv --mode replace
# raw.orders_increment now has 500 rows (mode=replace)

set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc
# 1 of 1 START sql incremental model staging.stg_orders_inc ............ [RUN]
# 1 of 1 OK created sql incremental model staging.stg_orders_inc ....... [CREATE TABLE in 0.20s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`psql`:

```sql
analytics=> SELECT count(*) FROM staging.stg_orders_inc;
 500
```

### 2 日目

```bash
cd ..
.venv/bin/python scripts/exercises/generate_03_new_orders.py --date 2026-04-28 --rows 500
.venv/bin/python scripts/exercises/load_orders_increment.py \
    --csv data/exercises/inbox/orders_2026-04-28.csv --mode append
# raw.orders_increment now has 1000 rows (mode=append)

cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc
# 1 of 1 START sql incremental model staging.stg_orders_inc ............ [RUN]
# 1 of 1 OK created sql incremental model staging.stg_orders_inc ....... [INSERT 0 500 in 0.10s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`INSERT 0 500` の `500` が「差分行数」。`raw.orders_increment` は 1000 行だが、`where loaded_at > '2026-04-27 23:59:59'` で 500 行だけが流れる。

```sql
analytics=> SELECT count(*) FROM staging.stg_orders_inc;
 1000
```

### Full refresh

```bash
../.venv/bin/dbt run --profiles-dir . --select stg_orders_inc --full-refresh
# 1 of 1 OK created sql incremental model staging.stg_orders_inc ....... [CREATE TABLE in 0.30s]
```

ログが `INSERT` ではなく `CREATE TABLE` に戻っているのが「full rebuild モード」の見分け方。件数は 1000（`raw.orders_increment` 全件）。

## Step 6: テスト

`dbt/models/exercises/03/schema.yml`:

```yaml
version: 2

models:
  - name: stg_orders_inc
    description: "Incremental staging of raw.orders_increment, merged on order_id."
    columns:
      - name: order_id
        description: "Primary key. Merge target."
        tests:
          - not_null
          - unique
      - name: order_date
        tests:
          - not_null
      - name: customer_id
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers')
                field: customer_id
      - name: product_id
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_products')
                field: product_id
      - name: store_id
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_stores')
                field: store_id
      - name: loaded_at
        tests:
          - not_null
```

`dbt test --select stg_orders_inc` が `PASS=8` などになれば成功。

## 解説まとめ

1. **incremental の本質**: `is_incremental()` 分岐で「初回 = full scan」「2 回目以降 = `where` で差分絞り込み」を 1 ファイルに表現できる。SQL の二重保守を防げるのが旨味。
2. **`unique_key` と strategy の組み合わせ**: postgres-adapter の `merge` は内部的に `delete + insert`。同一 `order_id` の更新が来ても上書きしてくれる。`append` だと重複が増えるので、再投入が起きうる運用なら `merge` を選ぶ。
3. **`{{ this }}` の意味**: 自分自身を参照する dbt jinja。`ref('stg_orders_inc')` だと DAG ループになる。
4. **`--full-refresh` の役割**: スキーマ変更や障害時の救済策。普段は incremental で動かしつつ、月次で `--full-refresh` を回す運用も多い。
5. **MVP の `stg_orders` は触っていない**: `raw.orders` (10,000 行) と `raw.orders_increment`（差分用）を物理的に分けたので、MVP の `dbt run` / `dbt test` には影響しない。次フェーズで本気で incremental 化する場合は `raw.orders` を 1 本化して `loaded_at` を後付けする検討が必要。
