# 7-2 解答例

## 入力データの準備

`data/exercises/inbox/products_v2.csv` を作る。Ex.04 用のジェネレータをそのまま
流用するのが最短:

```bash
.venv/bin/python scripts/exercises/generate_04_price_update.py
# Generated data/exercises/inbox/products_v2.csv: 100 rows
# (updated product_ids: [3, 7, 12, 18, 23, ...])
```

これで `data/raw/products.csv` (v1) と完全一致 + 20 行だけ unit_price が変化した
v2 CSV ができる。

## scripts/100-knock/topic-7/load_products_v2.py

```python
"""Replace raw.products with the v2 CSV for 100-knock Topic ⑦ Q2.

This script DROPs the existing raw.products (CASCADE so dependent views like
stg_products go too) and re-CREATEs / re-loads from products_v2.csv. The CSV
shares 80 rows with v1 and overwrites unit_price on 20 rows, so dbt snapshot's
``check`` strategy will detect 20 changes on the next run.

Idempotent: re-running with the same CSV is a no-op for the snapshot.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
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
    if not CSV.exists():
        print(f"CSV missing: {CSV}", file=sys.stderr)
        print("Hint: run scripts/exercises/generate_04_price_update.py first.", file=sys.stderr)
        return 1

    dsn = (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS raw.products CASCADE")
        cur.execute(DDL)
        with cur.copy(
            "COPY raw.products FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        ) as cp, CSV.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)
        cur.execute("SELECT count(*) FROM raw.products")
        print(f"raw.products refreshed: {cur.fetchone()[0]} rows from {CSV.name}")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**ポイント**:

- **`DROP ... CASCADE`** が必須。`stg_products` view が依存しているので、`CASCADE`
  なしだと「dependent objects exist」で落ちる。view は次の `dbt run` で復活する。
- DDL は Topic ② 2-1 の `raw.products` と完全に一致させる (`BIGINT PK` +
  `NUMERIC(12,2)`)。型がぶれると stg view の cast が壊れる。
- `psycopg.copy` で stream COPY。`pandas.read_csv → INSERT` より 1〜2 桁速い。
- このスクリプト単体は **冪等** (同じ CSV を何度流し込んでも同じ結果)。
  ただし下流の snapshot は 1 回目の流入時にだけ「変化検知」して履歴を切る。

## 実行ログ例

```text
$ .venv/bin/python scripts/100-knock/topic-7/load_products_v2.py
raw.products refreshed: 100 rows from products_v2.csv

$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
14:45:01  Running with dbt=1.11.x
14:45:02  1 of 1 START snapshot snapshots.snap_products_100knock ........ [RUN]
14:45:02  1 of 1 OK snapshotted snapshots.snap_products_100knock ........ [SELECT 20 in 0.18s]
14:45:02  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`SELECT 20` が「変化を検知して 20 行を新規 INSERT した」意味。同時に旧 20 行の
`dbt_valid_to` が UPDATE される (内部的には MERGE)。

## 物理確認

```sql
analytics=> SELECT count(*) AS total,
                  count(*) FILTER (WHERE dbt_valid_to IS NULL)     AS active,
                  count(*) FILTER (WHERE dbt_valid_to IS NOT NULL) AS expired
            FROM snapshots.snap_products_100knock;
 total | active | expired
-------+--------+---------
   120 |    100 |      20

analytics=> SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to
            FROM snapshots.snap_products_100knock
            WHERE product_id IN (
                SELECT product_id FROM snapshots.snap_products_100knock
                GROUP BY product_id HAVING count(*) > 1
            )
            ORDER BY product_id, dbt_valid_from
            LIMIT 6;
 product_id | unit_price |   dbt_valid_from    |    dbt_valid_to
------------+------------+---------------------+---------------------
          3 |     230.00 | 2026-04-26 14:30:02 | 2026-04-26 14:45:02
          3 |    8520.00 | 2026-04-26 14:45:02 |
          7 |    3980.00 | 2026-04-26 14:30:02 | 2026-04-26 14:45:02
          7 |     230.00 | 2026-04-26 14:45:02 |
         12 |     780.00 | 2026-04-26 14:30:02 | 2026-04-26 14:45:02
         12 |    6650.00 | 2026-04-26 14:45:02 |
```

旧版の `dbt_valid_to` が新版の `dbt_valid_from` と **一致** している
(境界連続性 = 半開区間 `[from, to)`)。これが SCD Type-2 の正しい姿。

## 解説まとめ

- **「上書き」を「追記」に変換**: raw 側は `DROP + CREATE + COPY` で一切履歴を
  持たない (常に最新状態のみ)。snapshot がその上に被さって「同じ unique_key で
  check_cols が変化したら新行を追加し、旧行に valid_to を入れる」変換を行う。
  これで raw を変えなくても歴史だけ snapshot 側に残せる。
- **`dbt_valid_to is null` = 「最新行」**: クエリ側はこのフィルタを付ければ
  「いま現在の有効データ」が取れる。`unique_key` ごとに **必ず 1 行だけ**
  この条件を満たす (snapshot の不変条件)。
- **半開区間 `[from, to)` の意味**: 旧版の `valid_to` が新版の `valid_from` に
  完全一致するので、`as_of` 時点の検索クエリは
  `valid_from <= as_of AND (as_of < valid_to OR valid_to IS NULL)` と書ける
  (7-6 で本格化)。`<= ... <=` だと境界の重複が起きるので NG。
- **2 回目 `SELECT N` の意味**: dbt snapshot のログにある `SELECT 20` は
  「source 側の変化検知で 20 行 INSERT した」という意味。`SELECT 0` なら no-op
  (source が変わっていない / check_cols が一致)。`SELECT 100` なら全行が
  「変化扱い」になっている (check_cols の指定ミスを疑う)。
- **MERGE 操作の効率**: 内部的には `MERGE INTO snapshots.snap_products_100knock
  USING (raw_data) ...` 的な単発 SQL で旧行 UPDATE + 新行 INSERT を同時に行う。
  Postgres には素の MERGE が無いので dbt は INSERT + UPDATE を別ステートメントで
  発行する。いずれにしてもユーザは「2 回目の dbt snapshot を叩く」だけで
  この MERGE 相当の挙動が得られる。
- **CI / cron での運用**: snapshot は冪等 (7-9 で確認) なので、実運用では
  「raw 投入直後に必ず叩く」のが安全。raw 投入と snapshot の間に他の write が
  挟まると、その間の変化が検知漏れになる可能性がある (snapshot は実行時の raw を
  見るので、それまでの中間状態は失われる)。
