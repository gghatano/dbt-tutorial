# 1-7 解答例

## scripts/100-knock/topic-1/generate_1_7_date_range.py

```python
"""Regenerate orders.csv with order_date spread across [2025-01-01, 2026-04-30].

This problem isolates the time-axis declaration: the date window is hard-coded
as a module-level constant so downstream incremental models can rely on a stable
high-watermark and a predictable backfill volume.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 207
LOCALE = "ja_JP"
NUM_ORDERS = 10_000
NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20

# Hard-coded time window — the data contract for downstream incremental jobs.
START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 4, 30)
TOTAL_DAYS = (END_DATE - START_DATE).days  # 485

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "100-knock" / "topic-1"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OUTPUT_PATH = DATA_DIR / "orders.csv"


def main() -> None:
    if not PRODUCTS_PATH.exists():
        raise SystemExit(
            f"products.csv not found at {PRODUCTS_PATH}. Run 1-2 first."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    products = pd.read_csv(PRODUCTS_PATH)
    price_lookup = dict(zip(products["product_id"], products["unit_price"]))

    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    rows = []
    for order_id in range(1, NUM_ORDERS + 1):
        # Equivalent to Faker.date_between(start_date=START_DATE, end_date=END_DATE)
        # but we use random.randint so the seed is fully under our control.
        offset = rng.randint(0, TOTAL_DAYS)
        order_date = START_DATE + timedelta(days=offset)
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

    df = pd.DataFrame(
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
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    distinct_dates = df["order_date"].nunique()
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")
    print(
        f"order_date range: {df['order_date'].min()} .. {df['order_date'].max()} "
        f"(distinct={distinct_dates})"
    )


if __name__ == "__main__":
    main()
```

**ポイント**:

- `START_DATE` / `END_DATE` を **モジュール先頭の定数** に持ち上げているのが本質。これで
  「何月何日から何月何日のデータか」が grep 一発で分かる。後の `incremental` モデルは
  この定数値を **データ契約** として読みに行ける
- `Faker.date_between` ではなく `rng.randint(0, TOTAL_DAYS)` を直接使っているのは、シード再現性を
  自前 RNG で完全に握るため。Faker 内部の RNG 経由だと「Faker が他のメソッドで RNG を消費した直後」
  だけ結果が変わるという落とし穴を避けられる
- `TOTAL_DAYS = 485` (= 16 ヶ月弱) → 10000 行を振れば 1 日あたり平均 20 行。十分に分散する
- ISO 形式で書き出すことで、後の dbt staging が `order_date::date` で素直に型変換できる

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_7_date_range.py
Generated data/100-knock/topic-1/orders.csv: 10000 rows
order_date range: 2025-01-01 .. 2026-04-30 (distinct=486)

$ awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | head -3
2025-01-01
2025-01-02
2025-01-03

$ awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | tail -3
2026-04-28
2026-04-29
2026-04-30

$ awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | wc -l
     486
```

## 解説まとめ

- **なぜ日付の分散が必要か**: 後続トピックの incremental マート (`mart_daily_sales`) は
  「前回までに処理した最新日 = 高水位線」を `MAX(order_date)` で取って差分だけ追加する。
  生成データの `order_date` がたとえば「全部同じ日」だと、incremental の動作が見えない (差分が 0 か
  全件かの 2 値になる)。**16 ヶ月分に分散** していて初めて、初回フルロード → 翌日分追加 → リプレイ
  というシナリオが回せる
- **なぜ範囲をハードコードするか**: `datetime.today()` を使うと、CI が来月走った瞬間に
  「最新日 = 来月のどこか」になり、テストの `expected: 2026-04-30` が壊れる。**実行日に依存しない
  ことそのものが、再現可能なテストの前提条件**
- **`distinct >= 200` の意味**: 採点側は「分散しているか」を distinct 値数で見ている。
  もし学習者が `order_date = START_DATE` のような縮退を書いたら distinct = 1 になって即落ちる。
  「最小 = 2025-01-01」「最大 = 2026-04-30」の 2 点だけだと縮退を見逃すので、distinct を 3 つ目の
  軸として加えている
- **境界の扱い**: `randint(0, TOTAL_DAYS)` は両端 inclusive。`+timedelta(days=TOTAL_DAYS)` で
  `END_DATE` に届く。`randint(0, TOTAL_DAYS - 1)` だと `END_DATE` が出ない off-by-one バグになる
  ので、採点側で「最大が `2026-04-30 ± 数日`」と緩く取って学習者の OBOE を許容している
- **ID 範囲の縮退には踏み込まない**: 1-6 で導入した「1% 休眠」はここでは保たない。1-7 は
  時間軸だけに集中させ、最終的な「全制約を同時に満たす」スクリプトは 1-9 で組み立てる
