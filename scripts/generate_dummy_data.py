"""Generate deterministic dummy CSVs for the local-data-platform raw layer.

This script produces four CSV files under ``data/raw/`` matching spec §5 / §11.1:

* ``customers.csv`` (1,000 rows): customer master
* ``products.csv``  (100 rows):   product master
* ``stores.csv``    (20 rows):    store master
* ``orders.csv``    (10,000 rows): order transactions

Determinism / re-runnable behavior
----------------------------------
Both ``random`` and ``Faker`` are seeded with ``42``. Re-running this script
overwrites the existing CSVs with byte-identical content, so downstream
``load_raw_data.py`` can be exercised idempotently.

Reference date
--------------
``order_date`` is drawn uniformly from the last 365 days *before* a fixed
reference date (``2026-04-26``) instead of ``datetime.today()``, so the output
is deterministic regardless of when the script is run.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
LOCALE = "ja_JP"
REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 365

NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20
NUM_ORDERS = 10_000

CATEGORIES = [
    "Food",
    "Beverage",
    "Household",
    "Beauty",
    "Electronics",
    "Stationery",
    "Apparel",
    "Toy",
]

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
]

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _generate_customers(fake: Faker, rng: random.Random) -> pd.DataFrame:
    rows = []
    for customer_id in range(1, NUM_CUSTOMERS + 1):
        name = fake.name()
        email = fake.unique.email()
        # created_at: somewhere within the last 2 years before the reference date.
        delta_days = rng.randint(0, 730)
        created_at = REFERENCE_DATE - timedelta(days=delta_days)
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": name,
                "email": email,
                "created_at": created_at.isoformat(),
            }
        )
    return pd.DataFrame(rows, columns=["customer_id", "customer_name", "email", "created_at"])


def _generate_products(fake: Faker, rng: random.Random) -> pd.DataFrame:
    rows = []
    for product_id in range(1, NUM_PRODUCTS + 1):
        # word() is locale-aware; combine to make a unique-looking product name.
        product_name = f"{fake.word()}_{product_id:03d}"
        category = rng.choice(CATEGORIES)
        # Unit price 100 - 9,999 yen, rounded to the nearest 10 yen.
        unit_price = rng.randint(10, 999) * 10
        rows.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "unit_price": unit_price,
            }
        )
    return pd.DataFrame(rows, columns=["product_id", "product_name", "category", "unit_price"])


def _generate_stores(fake: Faker, rng: random.Random) -> pd.DataFrame:
    rows = []
    for store_id in range(1, NUM_STORES + 1):
        store_name = f"店舗{store_id:02d}_{fake.last_name()}"
        prefecture = rng.choice(PREFECTURES)
        rows.append(
            {
                "store_id": store_id,
                "store_name": store_name,
                "prefecture": prefecture,
            }
        )
    return pd.DataFrame(rows, columns=["store_id", "store_name", "prefecture"])


def _generate_orders(rng: random.Random, products: pd.DataFrame) -> pd.DataFrame:
    # Build a quick lookup of unit_price by product_id for snapshotting.
    price_lookup = dict(zip(products["product_id"], products["unit_price"]))

    rows = []
    for order_id in range(1, NUM_ORDERS + 1):
        days_back = rng.randint(0, LOOKBACK_DAYS - 1)
        order_date = REFERENCE_DATE - timedelta(days=days_back)
        customer_id = rng.randint(1, NUM_CUSTOMERS)
        product_id = rng.randint(1, NUM_PRODUCTS)
        store_id = rng.randint(1, NUM_STORES)
        quantity = rng.randint(1, 10)
        unit_price = price_lookup[product_id]
        rows.append(
            {
                "order_id": order_id,
                "order_date": order_date.isoformat(),
                "customer_id": customer_id,
                "product_id": product_id,
                "store_id": store_id,
                "quantity": quantity,
                "unit_price": unit_price,
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
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Seed every RNG we touch. Faker carries its own internal RNG.
    random.seed(SEED)
    Faker.seed(SEED)
    rng = random.Random(SEED)
    fake = Faker(LOCALE)

    customers = _generate_customers(fake, rng)
    products = _generate_products(fake, rng)
    stores = _generate_stores(fake, rng)
    orders = _generate_orders(rng, products)

    outputs = [
        (OUTPUT_DIR / "customers.csv", customers),
        (OUTPUT_DIR / "products.csv", products),
        (OUTPUT_DIR / "stores.csv", stores),
        (OUTPUT_DIR / "orders.csv", orders),
    ]

    for path, df in outputs:
        df.to_csv(path, index=False, encoding="utf-8")

    print("Generated dummy data:")
    for path, df in outputs:
        print(f"  {path}: {len(df)} rows")


if __name__ == "__main__":
    main()
