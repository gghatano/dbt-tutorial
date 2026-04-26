"""Generate a deterministic ``reviews.csv`` for Exercise 01.

The CSV is written to ``data/exercises/inbox/reviews.csv`` with 2,000 rows.
Each row references existing ``raw.customers`` (1..1000) and ``raw.products``
(1..100) so that the learner's staging model can pass ``relationships`` tests
against ``stg_customers`` / ``stg_products``.

Determinism
-----------
``random`` is seeded with ``101`` and a fixed reference date (2026-04-26)
is used for ``posted_at`` so that re-running the script produces a byte-
identical file.

Schema
------
Column         Type      Notes
review_id      bigint    1..2000
customer_id    bigint    1..1000   (FK to raw.customers)
product_id     bigint    1..100    (FK to raw.products)
rating         int       1..5
comment        text      ~10% null, otherwise short Faker sentence
posted_at      datetime  ISO 8601, last 180 days from REFERENCE_DATE
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 101
LOCALE = "ja_JP"
REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 180

NUM_REVIEWS = 2_000
NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100

OUTPUT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "exercises" / "inbox" / "reviews.csv"
)


def _generate(rng: random.Random, fake: Faker) -> pd.DataFrame:
    rows = []
    for review_id in range(1, NUM_REVIEWS + 1):
        days_back = rng.randint(0, LOOKBACK_DAYS - 1)
        posted_dt = datetime.combine(
            REFERENCE_DATE - timedelta(days=days_back),
            time(hour=rng.randint(0, 23), minute=rng.randint(0, 59), second=rng.randint(0, 59)),
        )
        # ~10% of reviews leave the comment blank.
        comment: str | None
        if rng.random() < 0.1:
            comment = None
        else:
            comment = fake.sentence(nb_words=8)

        rows.append(
            {
                "review_id": review_id,
                "customer_id": rng.randint(1, NUM_CUSTOMERS),
                "product_id": rng.randint(1, NUM_PRODUCTS),
                "rating": rng.randint(1, 5),
                "comment": comment,
                "posted_at": posted_dt.isoformat(timespec="seconds"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "review_id",
            "customer_id",
            "product_id",
            "rating",
            "comment",
            "posted_at",
        ],
    )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)
    Faker.seed(SEED)
    rng = random.Random(SEED)
    fake = Faker(LOCALE)

    df = _generate(rng, fake)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH}: {len(df)} rows")


if __name__ == "__main__":
    main()
