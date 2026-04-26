"""Idempotently load raw CSVs into the ``raw`` schema of the analytics DB.

This script implements spec §11.2 of the local-data-platform: it reads
``data/raw/{customers,products,stores,orders}.csv`` and loads them into the
PostgreSQL ``raw`` schema using ``COPY ... FROM STDIN``.

Idempotency strategy
--------------------
Each target table is dropped (``DROP TABLE IF EXISTS ... CASCADE``) and then
recreated before loading. This guarantees that schema drift in the CSV is
reflected in the warehouse and that re-running the script produces the same
final row counts. dbt sources reference these tables by name only, so the
``CASCADE`` does not break downstream models — they will simply rebind on the
next ``dbt run``. See ``docs/decisions/0004-raw-load-strategy.md`` for the
trade-off versus ``TRUNCATE``.

Connection
----------
Connection parameters are read from the environment. ``python-dotenv`` is used
defensively to load ``.env`` if present, but pre-existing ``os.environ`` values
take precedence (so CI / containerised invocations work unchanged).

Loader role
-----------
We connect as ``dbt_user`` (not the superuser ``analytics_user``). ``dbt_user``
owns the ``raw`` schema and has ``CREATE``/``ALL`` on it via Terraform-managed
grants, which is exactly what is needed to ``DROP``/``CREATE``/``COPY``. Using
``dbt_user`` keeps the loader on the principle of least privilege and matches
the user that dbt itself will use later.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "raw"
SCHEMA = "raw"


@dataclass(frozen=True)
class TableSpec:
    """Definition of one table in the ``raw`` layer."""

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
    """Build a libpq DSN from environment variables.

    ``python-dotenv`` is loaded defensively: if ``.env`` does not exist or the
    relevant vars are already set, this is a no-op.
    """
    load_dotenv(REPO_ROOT / ".env", override=False)

    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env or export them in the shell."
        )

    return (
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


def _load_table(conn: psycopg.Connection, table: TableSpec) -> int:
    """Drop, recreate, and bulk-load a single table. Returns row count."""
    if not table.csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {table.csv_path}. "
            "Run scripts/generate_dummy_data.py first."
        )

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table.name} CASCADE")
        cur.execute(table.ddl)

        # Use binary mode so psycopg streams the file bytes verbatim into the
        # COPY pipe; this avoids any implicit text decoding/encoding round-trip
        # for non-ASCII content (Japanese names/prefectures live in this data).
        copy_sql = f"COPY {SCHEMA}.{table.name} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        with cur.copy(copy_sql) as cp, table.csv_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)

        cur.execute(f"SELECT count(*) FROM {SCHEMA}.{table.name}")
        row = cur.fetchone()
        assert row is not None  # count(*) always returns a row
        return int(row[0])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        dsn = _build_dsn()
    except RuntimeError as exc:
        print(f"[load_raw_data] config error: {exc}", file=sys.stderr)
        return 1

    counts: list[tuple[str, int]] = []
    try:
        with psycopg.connect(dsn) as conn:
            for table in TABLES:
                n = _load_table(conn, table)
                counts.append((f"{SCHEMA}.{table.name}", n))
            # Single transactional commit keeps the load atomic: either all
            # four tables are visible at the new contents, or none are.
            conn.commit()
    except (psycopg.Error, FileNotFoundError) as exc:
        print(f"[load_raw_data] load failed: {exc}", file=sys.stderr)
        return 1

    width = max(len(name) for name, _ in counts)
    print("Loaded raw tables:")
    for name, n in counts:
        print(f"  {name.ljust(width)}  {n:>6,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
