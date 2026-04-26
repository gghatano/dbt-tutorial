"""Generate ``products_v2.csv`` for Exercise 04 (snapshot practice).

The script reads the existing ``data/raw/products.csv`` (produced by
``scripts/generate_dummy_data.py``), randomly selects 20 product_ids, and
writes a new CSV with their ``unit_price`` overwritten by a fresh random
value. The other 80 rows are passed through unchanged. Output goes to
``data/exercises/inbox/products_v2.csv``.

Determinism
-----------
Seed = 104. Re-running produces a byte-identical CSV.

Why generate from the existing CSV
----------------------------------
dbt snapshot's ``check`` strategy is meant to detect *value changes* in the
source. If we regenerated the whole table from a different RNG seed, every
row would look "changed" even when the price did not move. Re-using the MVP
products.csv guarantees that exactly the 20 selected rows differ in unit_price
between v1 and v2, which is the property the exercise wants to demonstrate.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

SEED = 104
NUM_UPDATES = 20

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CSV = REPO_ROOT / "data" / "raw" / "products.csv"
OUTPUT_CSV = REPO_ROOT / "data" / "exercises" / "inbox" / "products_v2.csv"


def _new_price(rng: random.Random, current: float) -> float:
    """Pick a different price than ``current`` (rounded to 10 yen)."""
    while True:
        candidate = rng.randint(10, 999) * 10
        if float(candidate) != float(current):
            return float(candidate)


def main() -> None:
    if not SOURCE_CSV.exists():
        raise SystemExit(
            f"Source CSV not found: {SOURCE_CSV}. "
            "Run scripts/generate_dummy_data.py first to produce it."
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SOURCE_CSV)

    rng = random.Random(SEED)
    target_ids = rng.sample(df["product_id"].tolist(), NUM_UPDATES)
    target_ids_sorted = sorted(target_ids)

    new_prices: dict[int, float] = {}
    for pid in target_ids_sorted:
        current = float(df.loc[df["product_id"] == pid, "unit_price"].iloc[0])
        new_prices[pid] = _new_price(rng, current)

    df["unit_price"] = df.apply(
        lambda row: new_prices.get(int(row["product_id"]), row["unit_price"]),
        axis=1,
    )

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Generated {OUTPUT_CSV}: {len(df)} rows (updated product_ids: {target_ids_sorted})")


if __name__ == "__main__":
    main()
