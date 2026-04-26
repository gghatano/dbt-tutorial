# Exercise 04 解答例

## 事前準備: snapshot schema を作る

MVP の Terraform は `raw / staging / intermediate / marts` の 4 schema しか作っていない。snapshot を `snapshots` schema に置くには事前に schema を作る:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;
SQL
```

`dbt_user` 自身が CREATE SCHEMA できる権限を持っているはず（Terraform で `CREATEDB` または DB 単位 `CREATE` を付けてあれば。MVP の `infra/terraform/main.tf` の grant 設計次第）。権限が無い場合は `analytics_user` で作って `OWNER TO dbt_user` を付ける。

## Step 1: `dbt/snapshots/exercises/snap_products.sql`

```sql
{% snapshot snap_products %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='check',
        check_cols=['unit_price'],
    )
}}

select
    product_id,
    product_name,
    category,
    unit_price
from {{ source('raw', 'products') }}

{% endsnapshot %}
```

**ポイント**:

- ファイルパスは `dbt/snapshots/` 配下なら任意（MVP は `dbt_project.yml` で `snapshot-paths: ["snapshots"]` を宣言済み）。`exercises/` サブディレクトリを切って MVP の今後の snapshot とぶつからないようにする。
- `target_schema='snapshots'`: MVP の `get_custom_schema.sql` が `custom_schema_name` をそのまま返すので、結果として `snapshots.snap_products` テーブルになる。
- `strategy='check'` + `check_cols=['unit_price']`: source 側の `unit_price` が変わったら新行を発生させ、旧行に `dbt_valid_to` を埋める。
- `unique_key='product_id'`: 「行同一性」を判定するキー。

## Step 2: 1 回目

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products
# 1 of 1 START snapshot snapshots.snap_products .................. [RUN]
# 1 of 1 OK snapshotted snapshots.snap_products .................. [SELECT 100 in 0.10s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

```sql
analytics=> SELECT count(*), count(*) FILTER (WHERE dbt_valid_to IS NULL) AS active
            FROM snapshots.snap_products;
 count | active
-------+--------
   100 |    100
```

全 100 行が「現役」(valid_to NULL)。

## Step 3: raw.products を v2 で更新

```bash
.venv/bin/python scripts/exercises/generate_04_price_update.py
# Generated .../products_v2.csv: 100 rows (updated product_ids: [3, 7, 12, ...])
```

`scripts/exercises/load_products_v2.py` を学習者の手元で書く:

```python
"""Replace raw.products with data/exercises/inbox/products_v2.csv."""
from __future__ import annotations
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV = REPO_ROOT / "data" / "exercises" / "inbox" / "products_v2.csv"

DDL = """
CREATE TABLE raw.products (
    product_id   BIGINT PRIMARY KEY,
    product_name TEXT,
    category     TEXT,
    unit_price   NUMERIC(12, 2)
)
"""

def main() -> int:
    load_dotenv(REPO_ROOT / ".env", override=False)
    dsn = (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )
    if not CSV.exists():
        print(f"CSV missing: {CSV}", file=sys.stderr)
        return 1
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS raw.products CASCADE")
        cur.execute(DDL)
        with cur.copy("COPY raw.products FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as cp, CSV.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)
        cur.execute("SELECT count(*) FROM raw.products")
        print(f"raw.products refreshed: {cur.fetchone()[0]} rows")
        conn.commit()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

実行:

```bash
.venv/bin/python scripts/exercises/load_products_v2.py
# raw.products refreshed: 100 rows
```

**注意**: `DROP TABLE IF EXISTS raw.products CASCADE` で既存テーブルを破棄するため、`stg_products` view が一旦無効化される。次の `dbt run` で復活するので問題は無いが、MVP の dbt build 中に並行で叩くのは避ける。

## Step 4: 2 回目

```bash
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products
# 1 of 1 OK snapshotted snapshots.snap_products .................. [SELECT 20 in 0.15s]
```

`SELECT 20` が「変化を検知して 20 行を新規 INSERT した」意味。同時に旧 20 行の `dbt_valid_to` が UPDATE される。

```sql
analytics=> SELECT count(*) AS total,
                  count(*) FILTER (WHERE dbt_valid_to IS NULL) AS active,
                  count(*) FILTER (WHERE dbt_valid_to IS NOT NULL) AS expired
            FROM snapshots.snap_products;
 total | active | expired
-------+--------+---------
   120 |    100 |      20
```

## Step 5: 履歴の確認

```sql
analytics=> SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to
            FROM snapshots.snap_products
            WHERE product_id IN (
                SELECT product_id
                FROM snapshots.snap_products
                GROUP BY product_id
                HAVING count(*) > 1
            )
            ORDER BY product_id, dbt_valid_from
            LIMIT 6;

 product_id | unit_price |   dbt_valid_from    |    dbt_valid_to
------------+------------+---------------------+---------------------
          3 |    1240.00 | 2026-04-26 10:00:00 | 2026-04-26 10:05:00
          3 |    8520.00 | 2026-04-26 10:05:00 |
          7 |    3980.00 | 2026-04-26 10:00:00 | 2026-04-26 10:05:00
          7 |     230.00 | 2026-04-26 10:05:00 |
         12 |     780.00 | 2026-04-26 10:00:00 | 2026-04-26 10:05:00
         12 |    6650.00 | 2026-04-26 10:05:00 |
```

旧版の `dbt_valid_to` が新版の `dbt_valid_from` と一致している（境界連続性）。これが SCD Type-2。

## Step 6 (任意): 当時の価格で注文を再評価

`dbt/models/exercises/04/int_orders_with_historical_price.sql`:

```sql
{{ config(materialized='view', schema='intermediate') }}

select
    o.order_id,
    o.order_date,
    o.product_id,
    o.quantity,
    sp.unit_price                                            as historical_unit_price,
    o.unit_price                                             as snapshotted_at_order_time,
    (o.quantity * sp.unit_price)::numeric(14, 2)             as historical_sales_amount
from {{ ref('stg_orders') }} o
left join {{ ref('snap_products') }} sp
       on o.product_id = sp.product_id
      and o.order_date >= sp.dbt_valid_from::date
      and o.order_date <  coalesce(sp.dbt_valid_to::date, date '9999-12-31')
```

- `ref('snap_products')` は dbt が snapshot を ref として解決してくれる（`snapshots.snap_products` をバインド）。
- `dbt_valid_to` が NULL の最新行は `coalesce(... , '9999-12-31')` で「無限大」として扱う。
- `o.unit_price`（注文時にコピーされた価格）と `sp.unit_price`（履歴上の有効価格）が違う行があれば、価格改定後の注文がそれを反映していないことが分かる。

## 解説まとめ

1. **schema 事前作成が必要**: `snapshots` schema は Terraform 管理外なので、最初の `dbt snapshot` 前に手動で `CREATE SCHEMA snapshots AUTHORIZATION dbt_user` する。Production では Terraform に追加するか、`pre-hook` で自動作成する設計にする。
2. **`check` vs `timestamp` strategy**: ソースに `updated_at` があれば `timestamp` の方が効率的。今回の `raw.products` は履歴系の列を持たないので `check` 一択。`check_cols` は最小限の「変更を検知したい列」だけにすると無駄な履歴化を抑えられる。
3. **`dbt_valid_to` の半開区間**: `[valid_from, valid_to)` の半開区間で扱うのが定石。Step 6 の JOIN 条件で `<` と `<=` を使い分ける理由。
4. **macro override との相性**: MVP の `get_custom_schema.sql` が `target_schema` をそのまま透過するので、`+target_schema: snapshots` は本当に `snapshots` schema になる。標準 dbt 挙動だと `<target_schema>_snapshots` になっていたはず — ADR-0005 で override した恩恵がここでも効く。
