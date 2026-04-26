"""End-to-end smoke test for the local-data-platform.

This script implements spec §11.3 of the local-data-platform: it verifies that
the analytics PostgreSQL is reachable and that both the raw load and the dbt
mart layer produced non-empty results.

Required strict checks (spec §11.3 -- failure on any of these returns exit 1):

1. PostgreSQL is reachable with the credentials from the environment.
2. ``raw.orders`` has at least 1 row (raw load executed).
3. ``marts.mart_daily_sales`` has at least 1 row (dbt mart layer built).

In addition, two informational ("warn") checks run against ``staging.stg_orders``
and ``intermediate.int_order_details`` so that an empty intermediate layer is
visible in the smoke output. These are deliberately *not* exit-1 conditions:
spec §11.3 enumerates only the three strict checks, and we keep that contract
exact while still surfacing useful diagnostics. See
``docs/decisions/0008-smoke-test-strategy.md``.

Usage
-----
``.env`` must define ``DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD``,
or the equivalent environment variables must be exported in the shell
(``set -a; source .env; set +a``).

::

    .venv/bin/python scripts/smoke_test.py

Exit codes
----------
- ``0``: all strict checks passed.
- ``1``: configuration error (missing env var), connection failure, or any
  strict check failed. Warn-level checks never produce exit 1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

# Strict checks: each is (label, schema.table). Failure -> exit 1.
STRICT_TABLES: list[tuple[str, str]] = [
    ("raw.orders", "raw.orders"),
    ("marts.mart_daily_sales", "marts.mart_daily_sales"),
]

# Warn checks: each is (label, schema.table). Count == 0 -> WARN, not FAIL.
WARN_TABLES: list[tuple[str, str]] = [
    ("staging.stg_orders", "staging.stg_orders"),
    ("intermediate.int_order_details", "intermediate.int_order_details"),
]

# psycopg connection timeout. 5s is comfortably above any healthy local
# round-trip and well below typical CI step timeouts, so a hung Postgres
# fails fast instead of stalling the smoke run.
CONNECT_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _build_dsn() -> str:
    """Build a libpq DSN from environment variables.

    ``python-dotenv`` is loaded defensively: if ``.env`` does not exist or the
    relevant vars are already set, this is a no-op (``override=False`` ensures
    pre-existing env wins, which matches ``scripts/load_raw_data.py``).
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


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_connection(conn: psycopg.Connection) -> None:
    """Round-trip ``SELECT 1`` so a silent half-open socket is caught."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        row = cur.fetchone()
        if row is None or row[0] != 1:
            raise RuntimeError(f"unexpected response from SELECT 1: {row!r}")


def _count(conn: psycopg.Connection, qualified: str) -> int:
    """Return ``count(*)`` of the given fully-qualified ``schema.table``."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {qualified}")
        row = cur.fetchone()
        assert row is not None  # count(*) always yields a row
        return int(row[0])


def check_raw_orders(conn: psycopg.Connection) -> int:
    """Return ``count(*)`` of ``raw.orders``."""
    return _count(conn, "raw.orders")


def check_mart_daily_sales(conn: psycopg.Connection) -> int:
    """Return ``count(*)`` of ``marts.mart_daily_sales``."""
    return _count(conn, "marts.mart_daily_sales")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # --- config -----------------------------------------------------------
    try:
        dsn = _build_dsn()
    except RuntimeError as exc:
        # Keep the prefix uniform so log scrapers can grep "[FAIL] ".
        print(f"[FAIL] config: {exc}")
        return 1

    failed = False
    counts: dict[str, int] = {}

    # --- connection -------------------------------------------------------
    try:
        with psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS) as conn:
            try:
                check_connection(conn)
                print("[OK] connection: SELECT 1 succeeded")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[FAIL] connection: {exc}")
                return 1

            # --- strict checks --------------------------------------------
            for label, qualified in STRICT_TABLES:
                try:
                    n = _count(conn, qualified)
                except psycopg.Error as exc:
                    # Format: "what" : "how it failed". Single line so logs
                    # stay grep-friendly even when a stack of errors fires.
                    print(f"[FAIL] {label}: query failed ({exc.__class__.__name__}: {exc})".replace("\n", " "))
                    failed = True
                    continue

                counts[label] = n
                if n >= 1:
                    print(f"[OK] {label}: count={n}")
                else:
                    print(f"[FAIL] {label}: count is 0 (expected >= 1)")
                    failed = True

            # --- warn-level checks ----------------------------------------
            for label, qualified in WARN_TABLES:
                try:
                    n = _count(conn, qualified)
                except psycopg.Error as exc:
                    # Warn checks must never flip exit code: report and move on.
                    print(f"[WARN] {label}: query failed ({exc.__class__.__name__}: {exc})".replace("\n", " "))
                    continue

                if n >= 1:
                    print(f"[OK] {label}: count={n} (warn-level)")
                else:
                    print(f"[WARN] {label}: count is 0 (informational; not failing)")

    except psycopg.Error as exc:
        # Connection-level failure: bad host/port/credentials, server down, etc.
        # We deliberately catch psycopg.Error rather than bare Exception so
        # programming errors (e.g. NameError) still surface as tracebacks.
        print(f"[FAIL] connection: {exc.__class__.__name__}: {exc}".replace("\n", " "))
        return 1

    if failed:
        return 1

    raw_n = counts.get("raw.orders", 0)
    mart_n = counts.get("marts.mart_daily_sales", 0)
    print(
        f"[PASS] all smoke checks passed "
        f"(raw.orders={raw_n}, marts.mart_daily_sales={mart_n})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
