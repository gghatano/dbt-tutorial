"""Generate a deterministic per-day orders CSV for Exercise 03.

Writes ``data/exercises/inbox/orders_<date>.csv`` containing N new orders for
the given calendar date. The seed is derived deterministically from the date
string so repeated runs for the same date produce byte-identical output.

CLI
---
    python scripts/exercises/generate_03_new_orders.py --date 2026-04-27
    python scripts/exercises/generate_03_new_orders.py --date 2026-04-28 --rows 500

Schema (matches raw.orders + extra ``loaded_at`` for incremental hint)
----------------------------------------------------------------------
order_id     bigint     starts at 100001 + offset(date)*N to keep PKs unique
order_date   date       == --date
customer_id  bigint     1..1000   (FK to raw.customers)
product_id   bigint     1..100    (FK to raw.products)
store_id     bigint     1..20     (FK to raw.stores)
quantity     int        1..10
unit_price   numeric    re-derived from product_id (matches existing seed grid)
loaded_at    datetime   end of the order_date (used as incremental high-watermark)
"""

from __future__ import annotations

import argparse
import hashlib
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "exercises" / "inbox"


def _seed_for_date(d: date) -> int:
    """Derive a stable 32-bit seed from the date string."""
    digest = hashlib.sha1(d.isoformat().encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _date_offset(d: date) -> int:
    """Stable non-negative offset for picking a unique-ish PK starting block."""
    # Days since project reference date (2026-04-26). Negative offsets are clamped.
    base = date(2026, 4, 26)
    return max(0, (d - base).days)


def _build_price_grid() -> dict[int, float]:
    """Re-derive a price grid that matches scripts/generate_dummy_data.py.

    The MVP generator seeds random with 42 and assigns unit_price = randint(10, 999) * 10
    for product_id 1..100 in order. We do NOT import that module to avoid a hard
    dependency, but we replicate the loop with the same seeding semantics.
    """
    # NOTE: scripts/generate_dummy_data.py shares ``rng`` between customers/products/orders,
    # so reproducing the exact prices requires running customers first. To keep this script
    # decoupled we use a separate, deterministic price grid that lives in [100, 9990].
    rng = random.Random(420042)
    return {pid: rng.randint(10, 999) * 10 for pid in range(1, NUM_PRODUCTS + 1)}


def _generate(target_date: date, n_rows: int) -> pd.DataFrame:
    seed = _seed_for_date(target_date)
    rng = random.Random(seed)
    price_lookup = _build_price_grid()

    pk_start = 100_000 + _date_offset(target_date) * 10_000 + 1

    rows = []
    end_of_day = datetime.combine(target_date, time(23, 59, 59))
    for i in range(n_rows):
        product_id = rng.randint(1, NUM_PRODUCTS)
        rows.append(
            {
                "order_id": pk_start + i,
                "order_date": target_date.isoformat(),
                "customer_id": rng.randint(1, NUM_CUSTOMERS),
                "product_id": product_id,
                "store_id": rng.randint(1, NUM_STORES),
                "quantity": rng.randint(1, 10),
                "unit_price": price_lookup[product_id],
                "loaded_at": end_of_day.isoformat(timespec="seconds"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "order_id",
            "order_date",
            "customer_id",
            "product_id",
            "store_id",
            "quantity",
            "unit_price",
            "loaded_at",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-day orders CSV (Exercise 03).")
    parser.add_argument("--date", required=True, help="Order date in ISO format, e.g. 2026-04-27")
    parser.add_argument("--rows", type=int, default=500, help="Number of orders (default 500)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = _generate(target_date, args.rows)
    out_path = OUTPUT_DIR / f"orders_{target_date.isoformat()}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Generated {out_path}: {len(df)} rows (date={target_date.isoformat()})")


if __name__ == "__main__":
    main()
