# 1-6 解答例

## scripts/100-knock/topic-1/generate_1_6_dormant_customers.py

```python
"""Regenerate orders.csv with 1% dormant customers (no orders) for 100-knock Topic 1 / Q6.

Customers 991..1000 are intentionally excluded from the customer_id lottery,
so that ~1% of the customer master never shows up in orders. This mirrors a
real-world FK coverage gap and seeds future LEFT JOIN exercises.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 206
LOCALE = "ja_JP"
NUM_ORDERS = 10_000
NUM_CUSTOMERS = 1_000
DORMANT_CUSTOMERS = 10  # last 10 IDs are dormant (= 1%)
ACTIVE_CUSTOMER_MAX = NUM_CUSTOMERS - DORMANT_CUSTOMERS  # = 990
NUM_PRODUCTS = 100
NUM_STORES = 20
REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 365

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
        days_back = rng.randint(0, LOOKBACK_DAYS - 1)
        order_date = REFERENCE_DATE - timedelta(days=days_back)
        # The single line that implements "1% dormant": narrow the lottery.
        customer_id = rng.randint(1, ACTIVE_CUSTOMER_MAX)
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

    seen = set(df["customer_id"].unique().tolist())
    all_ids = set(range(1, NUM_CUSTOMERS + 1))
    dormant = sorted(all_ids - seen)
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")
    print(f"Distinct customer_id in orders: {len(seen)} (dormant: {len(dormant)})")


if __name__ == "__main__":
    main()
```

**ポイント**:

- 「1% を休眠にする」を **抽選母集団そのものを狭める** ことで実装している (`rng.randint(1, 990)`)。
  「先に 1..1000 で振って後から 991..1000 を 1..990 に置き換える」のような事後加工をしないことで、
  「データ仕様 = 1 行のコード」という宣言性が保てる
- `DORMANT_CUSTOMERS = 10` を定数化することで、後で「3% にしたい」「100 行ぐらいにしたい」という
  仕様変更が 1 行差分で済む
- 起動時に `products.csv` の存在を `SystemExit` で早期チェック。1-2 が走っていない場合に
  分かりやすいエラーで止められる
- 末尾の `print` で「実際に何人が休眠になったか」を出すことで、学習者がシード差や境界
  ケースを目視確認できる (採点側でも同じ計算をする)

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_6_dormant_customers.py
Generated data/100-knock/topic-1/orders.csv: 10000 rows
Distinct customer_id in orders: 990 (dormant: 10)

$ python3 -c "
import csv
with open('data/100-knock/topic-1/orders.csv') as f:
    seen = {int(row['customer_id']) for row in csv.DictReader(f)}
all_ids = set(range(1, 1001))
print('dormant:', sorted(all_ids - seen))
"
dormant: [991, 992, 993, 994, 995, 996, 997, 998, 999, 1000]
```

## 解説まとめ

- **なぜ 1% を休眠にするのか**: 後続トピックで `mart_customer_sales` を作るとき、`customers LEFT JOIN orders`
  すると休眠顧客は `total_amount IS NULL` になる。**この行を見落とさず取り扱える** マートかどうかは
  ダッシュボードの正しさに直結する。生成段階でちゃんと「LEFT になる側」を作っておくことで、
  下流テストが「ハッピーパス専用」にならず本物の品質チェックになる
- **`relationships` テストの片方向性**: dbt の `relationships` テストは「子表の FK が親表の PK 集合の
  部分集合か」を見る (= `orders.customer_id ⊆ customers.customer_id` は OK)。
  逆向き (`customers.customer_id ⊆ orders.customer_id`) は **そもそも書かない** のが正解。1-6 の
  データはこの片方向性を体感する素材になる
- **Python 側で範囲を絞る vs SQL 側で除外する**: 両方できるが、「データ仕様としての宣言」は
  生成スクリプトに置くのが筋。SQL 側の `WHERE customer_id <= 990` は「分析の都合での絞り込み」と
  混ざってしまい、後で読み手が **どちらが意図的か** を区別できなくなる
- **冪等性は維持**: シードを `206` で固定しているので、再実行で完全に同じ orders.csv が出る。
  1-4 → 1-5 → 1-6 と上書きしても、最後の 1-6 を 2 回回せば同じバイト列に収束する
