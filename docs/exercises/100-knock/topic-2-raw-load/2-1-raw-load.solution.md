# 2-1 解答例

## scripts/100-knock/topic-2/load_raw.py

```python
"""Load 100-knock Topic ① CSVs into the ``raw`` schema.

Topic ② / Q1 — declares the **physical boundary** between the outside world
(CSV files) and the analytics warehouse. Each table is declared with an explicit
DDL (PK + types), then loaded via ``COPY ... FROM STDIN`` for speed.

Idempotency:
    Each table is dropped (``DROP ... CASCADE``) and recreated. Re-running the
    script produces the same final row counts. Downstream dbt models will rebind
    on the next ``dbt run``.

Auth:
    Reads connection params from ``.env`` (DB_HOST/DB_PORT/DB_NAME/DB_USER/
    DB_PASSWORD). The recommended user is ``dbt_user`` (owner of the ``raw``
    schema), but any role with CREATE / INSERT on ``raw`` works.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "100-knock" / "topic-1"
SCHEMA = "raw"


@dataclass(frozen=True)
class TableSpec:
    name: str
    csv_path: Path
    ddl: str


TABLES: list[TableSpec] = [
    TableSpec(
        name="customers",
        csv_path=DATA_DIR / "customers.csv",
        ddl="""
            CREATE TABLE raw.customers (
                customer_id   BIGINT PRIMARY KEY,
                customer_name TEXT,
                email         TEXT,
                created_at    DATE
            )
        """,
    ),
    TableSpec(
        name="products",
        csv_path=DATA_DIR / "products.csv",
        ddl="""
            CREATE TABLE raw.products (
                product_id   BIGINT PRIMARY KEY,
                product_name TEXT,
                category     TEXT,
                unit_price   NUMERIC(12, 2)
            )
        """,
    ),
    TableSpec(
        name="stores",
        csv_path=DATA_DIR / "stores.csv",
        ddl="""
            CREATE TABLE raw.stores (
                store_id   BIGINT PRIMARY KEY,
                store_name TEXT,
                prefecture TEXT
            )
        """,
    ),
    TableSpec(
        name="orders",
        csv_path=DATA_DIR / "orders.csv",
        ddl="""
            CREATE TABLE raw.orders (
                order_id    BIGINT PRIMARY KEY,
                order_date  DATE,
                customer_id BIGINT,
                product_id  BIGINT,
                store_id    BIGINT,
                quantity    INT,
                unit_price  NUMERIC(12, 2)
            )
        """,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_dsn() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing env vars: {', '.join(missing)}. Set them in .env."
        )
    return (
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


def _load_table(conn: psycopg.Connection, table: TableSpec) -> int:
    if not table.csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {table.csv_path}. Run Topic ① generators first."
        )
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table.name} CASCADE")
        cur.execute(table.ddl)
        copy_sql = (
            f"COPY {SCHEMA}.{table.name} "
            "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        )
        with cur.copy(copy_sql) as cp, table.csv_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)
        cur.execute(f"SELECT count(*) FROM {SCHEMA}.{table.name}")
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        dsn = _build_dsn()
    except RuntimeError as exc:
        print(f"[load_raw] config error: {exc}", file=sys.stderr)
        return 1

    counts: list[tuple[str, int]] = []
    try:
        with psycopg.connect(dsn) as conn:
            for table in TABLES:
                n = _load_table(conn, table)
                counts.append((f"{SCHEMA}.{table.name}", n))
            conn.commit()
    except (psycopg.Error, FileNotFoundError) as exc:
        print(f"[load_raw] load failed: {exc}", file=sys.stderr)
        return 1

    width = max(len(name) for name, _ in counts)
    print("Loaded raw tables:")
    for name, n in counts:
        print(f"  {name.ljust(width)}  {n:>6,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**ポイント**:

- `TableSpec` データクラスで `(name, csv_path, ddl)` を 1 セットにまとめ、ループで処理する。
  4 テーブル分の DDL がコードのトップに **宣言として並ぶ** 形になり、後で `sources.yml` を書く時に
  「ここに何があるか」が一目で分かる。
- `DROP TABLE IF EXISTS ... CASCADE` で冪等性を確保。CASCADE は依存 view (= dbt 由来) も一緒に落とすが、
  次回 `dbt run` で勝手に再構築される。これが MVP の運用前提 (詳細 ADR-0004)。
- `COPY ... FROM STDIN` を `cur.copy(copy_sql) as cp` の context manager で開き、CSV ファイルを
  バイナリ読みでチャンク (64KB) ずつ流し込む。テキスト decode/encode の往復を避けるので、日本語列
  (`customer_name` / `prefecture`) がエンコード事故で化けない。
- 4 テーブルを **同一 connection / 同一トランザクション** でロードし、最後に 1 回 `conn.commit()`。
  途中で 1 つでもコケれば全テーブルが rollback されるので、"中途半端な raw" が残らない。
- DSN 構築は `.env` を `python-dotenv` で defensively に読み込むパターン。CI 環境では `.env` が無くても
  既存の `os.environ` が使われるので動作が壊れない。

## 実行例

```
$ python3 scripts/100-knock/topic-2/load_raw.py
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows

$ psql -h localhost -U dbt_user -d analytics -c "SELECT count(*) FROM raw.orders;"
 count
-------
 10000
(1 row)
```

## 解説まとめ

- **物理境界の宣言**: `raw` schema の 4 テーブルが「dbt が触れる外側」の唯一の入口。ここを決めると、
  後の `sources.yml` は「**この 4 テーブルに別名を貼る**」だけの作業になる (Q2-2)。
- **PK は DDL で宣言**: `customer_id BIGINT PRIMARY KEY` のように DDL 段階で PK を打つことで、
  万が一 CSV に重複が混じっていれば COPY 自体が失敗する。Python 側 (Topic ①) と DB 側の二重防壁。
- **COPY の速さ**: 10,000 行が 1 秒未満で入る。`INSERT` ループだと数秒〜数十秒かかる。
  raw 投入は CI で毎回走らせるので、**速さ = 投資対効果**。
- **冪等性 = CI 友好性**: 「何度叩いても同じ結果」が保証されると、CI も学習者の手元も気兼ねなく再実行できる。
  `DROP CASCADE` は破壊的に見えるが、宣言型のデータパイプラインでは **状態を作り直す方が信頼できる**。
- **Topic ②全体の起点**: この 1 問が完了すると、以降の問は「raw に居る 4 テーブルに dbt から
  どう名前を付け、どう契約を結ぶか」だけを扱える。物理境界がブレなくなったご褒美。
