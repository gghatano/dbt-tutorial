# Exercise 01 解答例

## Step 1: CSV 生成

```bash
.venv/bin/python scripts/exercises/generate_01_reviews.py
# Generated /.../data/exercises/inbox/reviews.csv: 2000 rows

wc -l data/exercises/inbox/reviews.csv
#     2001 data/exercises/inbox/reviews.csv
```

## Step 2: raw ロード script

`scripts/exercises/load_reviews.py` を作る（学習者の手元に置く想定、リポジトリには含めない）。

```python
"""Load data/exercises/inbox/reviews.csv into raw.reviews."""
from __future__ import annotations
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "exercises" / "inbox" / "reviews.csv"

DDL = """
CREATE TABLE raw.reviews (
    review_id   BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    product_id  BIGINT NOT NULL,
    rating      INT    NOT NULL,
    comment     TEXT,
    posted_at   TIMESTAMP NOT NULL
)
"""

def main() -> int:
    load_dotenv(REPO_ROOT / ".env", override=False)
    dsn = (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )
    if not CSV_PATH.exists():
        print(f"CSV missing: {CSV_PATH}", file=sys.stderr)
        return 1

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS raw.reviews CASCADE")
        cur.execute(DDL)
        copy_sql = "COPY raw.reviews FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        with cur.copy(copy_sql) as cp, CSV_PATH.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)
        cur.execute("SELECT count(*) FROM raw.reviews")
        print(f"raw.reviews loaded: {cur.fetchone()[0]} rows")
        conn.commit()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

実行:

```bash
set -a; source .env; set +a
.venv/bin/python scripts/exercises/load_reviews.py
# raw.reviews loaded: 2000 rows
```

**ポイント**:

- `DROP ... CASCADE` → `CREATE` は MVP の `load_raw_data.py` と同じ冪等性戦略 (ADR-0004)。
- `COPY ... FROM STDIN WITH (FORMAT CSV, HEADER TRUE)` で CSV をストリームコピー。空フィールド `,,` は NULL として解釈されるので `comment` の null 行も自然に入る。
- ロード後に `count(*)` でセルフチェック → 学習中の安心材料になる。

## Step 3: `dbt/models/exercises/01/sources.yml`

```yaml
version: 2

sources:
  - name: raw_exercise
    schema: raw
    description: "Raw layer for exercises (separate logical source name to avoid clashing with MVP `raw`)."
    tables:
      - name: reviews
        description: "Customer reviews CSV (data/exercises/inbox/reviews.csv)."
        columns:
          - name: review_id
            tests:
              - not_null
              - unique
          - name: customer_id
            tests:
              - not_null
          - name: product_id
            tests:
              - not_null
          - name: rating
            tests:
              - not_null
          - name: posted_at
            tests:
              - not_null
```

**ポイント**:

- `name: raw_exercise` と分けてあるので、MVP 側 `name: raw` と並存できる。
- raw 段階では `relationships` テストはあえて書かない（CSV の事故的な FK 違反は staging で検知する方が責務分離が綺麗）。

## Step 4: `dbt/models/exercises/01/stg_reviews.sql`

```sql
{{ config(materialized='view', schema='staging') }}

select
    review_id::bigint               as review_id,
    customer_id::bigint             as customer_id,
    product_id::bigint              as product_id,
    rating::int                     as rating,
    comment::text                   as comment,
    posted_at::timestamp            as posted_at,
    (posted_at::timestamp)::date    as posted_date
from {{ source('raw_exercise', 'reviews') }}
```

**ポイント**:

- `schema='staging'` を明示しているが、MVP の `dbt_project.yml` では `models.local_analytics.staging.+schema: staging` が定義済み。`models/exercises/01/` は `local_analytics.exercises.01` 名前空間に解決されるので、そのままだと target schema (`staging`) にフォールバックしてしまう。明示すれば取り違えが起きない。
- 派生 `posted_date` を作っておくと Exercise 02 の集計（最終レビュー日など）で楽になる。
- `comment` は NULL 許容のままパススルー。

## Step 5: `dbt/models/exercises/01/schema.yml`

```yaml
version: 2

models:
  - name: stg_reviews
    description: "Type-cast view of raw.reviews. posted_date is derived from posted_at."
    columns:
      - name: review_id
        description: "Primary key (bigint)."
        tests:
          - not_null
          - unique
      - name: customer_id
        description: "FK to stg_customers.customer_id."
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers')
                field: customer_id
      - name: product_id
        description: "FK to stg_products.product_id."
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_products')
                field: product_id
      - name: rating
        description: "1..5 integer star rating."
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: [1, 2, 3, 4, 5]
      - name: comment
        description: "Free-text review body. Nullable when the customer left no comment."
      - name: posted_at
        tests:
          - not_null
      - name: posted_date
        description: "Calendar date derived from posted_at. Useful for downstream daily aggregates."
        tests:
          - not_null
```

**ポイント**:

- `relationships` の `arguments:` ネスト形式は dbt 1.11 から推奨。MVP の `staging/schema.yml` も同じ形式 (ADR-0005 関連)。
- `accepted_values` の `values:` は数値を渡してよい。dbt が SQL に展開する際にリテラルとして展開される。

## Step 6: 実行例

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select stg_reviews
# Running with dbt=1.11.x
# Found 8 models, 2 sources, 65 tests, ...
# Concurrency: 4 threads (target='dev')
# 1 of 1 START sql view model staging.stg_reviews ............. [RUN]
# 1 of 1 OK created sql view model staging.stg_reviews ........ [CREATE VIEW in 0.10s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 1 of 7 START test accepted_values_stg_reviews_rating .......... [PASS]
# 2 of 7 START test not_null_stg_reviews_customer_id ............ [PASS]
# 3 of 7 START test not_null_stg_reviews_posted_at .............. [PASS]
# ...
# Done. PASS=7 WARN=0 ERROR=0 SKIP=0 TOTAL=7
```

`psql` 確認:

```sql
analytics=> SELECT count(*), min(posted_date), max(posted_date) FROM staging.stg_reviews;
 count | min        | max
-------+------------+------------
  2000 | 2025-10-29 | 2026-04-26
```

## 解説まとめ

1. **source の論理名を分ける**: `raw` source は MVP で既に占有されているので、Exercise 用には `raw_exercise` のような別名を切る。schema は同じ `raw` を指していて OK。
2. **派生列は staging で出す**: `posted_date` のような汎用変換は staging で済ませると、Exercise 02 以降のマートが薄くなる。
3. **テスト 4 種をフル活用**: `not_null` / `unique` / `accepted_values` / `relationships` を全て使う最初の練習問題。生成 CSV の seed が固定なので毎回同じ件数で安定して PASS する。
