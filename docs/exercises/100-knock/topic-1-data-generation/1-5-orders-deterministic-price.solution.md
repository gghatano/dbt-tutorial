# Problem 1-5 解答例

## スクリプト全文

`scripts/100-knock/topic-1/generate_1_05_orders.py`:

```python
"""Generate orders.csv with deterministic per-product unit_price.

Reads products.csv (from problem 1-2) into a {product_id: unit_price} dict and
uses it to populate orders.unit_price, ensuring that the same product_id always
carries the same price across all 10,000 orders.
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 205
LOCALE = "ja_JP"

NUM_ORDERS = 10_000

# FK ranges (must match 1-1 / 1-2 / 1-3 outputs).
NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20

QUANTITY_MIN = 1
QUANTITY_MAX = 10

REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 365

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "100-knock" / "topic-1"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OUTPUT_PATH = DATA_DIR / "orders.csv"

COLUMNS = [
    "order_id",
    "order_date",
    "customer_id",
    "product_id",
    "store_id",
    "quantity",
    "unit_price",
]


# ---------------------------------------------------------------------------
# Lookup loader
# ---------------------------------------------------------------------------

def load_price_lookup(path: Path) -> dict[int, int]:
    """Read products.csv and return {product_id: unit_price}."""
    if not path.exists():
        print(
            f"products.csv not found at {path}.\n"
            "  Solve problem 1-2 first, or place a 2-column CSV with "
            "(product_id,unit_price) at that path.",
            file=sys.stderr,
        )
        sys.exit(1)

    lookup: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if "product_id" not in reader.fieldnames or "unit_price" not in reader.fieldnames:
            print(
                f"products.csv must contain product_id and unit_price columns; "
                f"got {reader.fieldnames}",
                file=sys.stderr,
            )
            sys.exit(1)
        for row in reader:
            pid = int(row["product_id"])
            price = int(row["unit_price"])
            lookup[pid] = price

    # Defensive check: every product_id in the FK range must be present.
    missing = [pid for pid in range(1, NUM_PRODUCTS + 1) if pid not in lookup]
    if missing:
        print(
            f"products.csv missing product_id values: {missing[:5]}{'...' if len(missing) > 5 else ''}",
            file=sys.stderr,
        )
        sys.exit(1)
    return lookup


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(rng: random.Random, price_lookup: dict[int, int]) -> list[list[object]]:
    rows: list[list[object]] = []
    for order_id in range(1, NUM_ORDERS + 1):
        days_back = rng.randint(0, LOOKBACK_DAYS - 1)
        order_date = REFERENCE_DATE - timedelta(days=days_back)
        customer_id = rng.randint(1, NUM_CUSTOMERS)
        product_id = rng.randint(1, NUM_PRODUCTS)
        store_id = rng.randint(1, NUM_STORES)
        quantity = rng.randint(QUANTITY_MIN, QUANTITY_MAX)
        # Deterministic: same product_id always yields the same unit_price.
        unit_price = price_lookup[product_id]
        rows.append(
            [
                order_id,
                order_date.isoformat(),
                customer_id,
                product_id,
                store_id,
                quantity,
                unit_price,
            ]
        )
    return rows


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    _ = fake  # kept for stylistic consistency with sibling scripts

    price_lookup = load_price_lookup(PRODUCTS_CSV)
    rows = generate(rng, price_lookup)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)

    print(
        f"wrote {OUTPUT_PATH}: {len(rows)} rows "
        f"(unique product_ids in orders: {len({r[3] for r in rows})}, "
        f"unique unit_prices: {len({r[6] for r in rows})})"
    )


if __name__ == "__main__":
    main()
```

## 実行例

```bash
.venv/bin/python scripts/100-knock/topic-1/generate_1_05_orders.py
# wrote /.../data/100-knock/topic-1/orders.csv: 10000 rows
#   (unique product_ids in orders: 100, unique unit_prices: <= 100)
```

関数性チェック:

```bash
awk -F, 'NR>1{print $4","$7}' data/100-knock/topic-1/orders.csv \
  | sort -u \
  | awk -F, '{print $1}' \
  | sort | uniq -c \
  | awk '$1!=1'
# (空出力 = 関数性 OK)
```

products.csv との一致 (Python での確認例):

```bash
.venv/bin/python - <<'PY'
import csv
from pathlib import Path

base = Path("data/100-knock/topic-1")
prod = {int(r["product_id"]): int(r["unit_price"])
        for r in csv.DictReader((base / "products.csv").open())}
mism = 0
with (base / "orders.csv").open() as fh:
    reader = csv.DictReader(fh)
    for r in reader:
        pid = int(r["product_id"])
        price = int(r["unit_price"])
        if prod[pid] != price:
            mism += 1
print(f"mismatches: {mism}")
PY
# mismatches: 0
```

## ポイント

- **`csv.DictReader` で辞書化**: `csv.reader` でもできるが、`DictReader` は
  ヘッダ名 (`product_id`) で参照できるので、列順序が変わっても壊れにくい。
- **`int()` キャスト必須**: `DictReader` は全フィールドを `str` で返す。
  辞書のキーを `str` にしたまま `lookup[product_id]` (int) を呼ぶと
  KeyError になる。lookup を作る側で `int()` 化する方が呼び出し側が楽。
- **欠損 product_id の防御**: products.csv が壊れている / 行数足りないと、
  生成中にランダム抽選で当たった瞬間に KeyError で落ちる。事前に
  `range(1, NUM_PRODUCTS + 1)` 全件揃っているか確認すると、エラーが
  「products.csv 側の問題」として早期に伝わる。
- **シード変更 (204 → 205)**: 1-4 と同じ seed にすると order_date /
  customer_id の列も同じになり、価格だけが変わった疑似的な「snapshot 差分」
  が出てしまう。本問題は別の生成回として扱うべきなので、明確に変える。

## 解説まとめ

### なぜ unit_price を **決定論的** にするのか

3 つの理由:

1. **データ契約**: 「商品の単価」は商品マスタが持つ属性。注文側で
   勝手にバラつかせると、`mart_product_sales` の集計 (例:
   `sum(quantity * unit_price)`) と `mart_product_revenue` (= `unit_price`
   を直接掛ける) が **同じ事実から違う値** を返してしまう。
2. **schema test の意義**: dbt で
   ```yaml
   - dbt_utils.expression_is_true:
       arguments:
         expression: "unit_price = (select unit_price from products where product_id = orders.product_id)"
   ```
   のようなテストを書くなら、生成側がそれを満たしている前提が要る。
   満たしていなければ毎回 dbt test が赤くなり、テスト側の信頼が落ちる。
3. **snapshot との分離 (Exercise 04 への伏線)**: 価格改定は別物として
   `dbt snapshot` で扱う。生成段階で価格をランダムに振ると、改定の有無が
   見えなくなり snapshot の練習が成立しない。

### 関数依存を awk で検証する筋

「`product_id → unit_price` の関数依存」は、関係代数では

```
π_product_id (orders) のサイズ == π_(product_id, unit_price) (orders) のサイズ
```

と言える。awk なら:

```bash
awk -F, 'NR>1{print $4","$7}' orders.csv | sort -u   # (product_id, unit_price) の distinct
| awk -F, '{print $1}' | sort | uniq -c              # product_id 単独でグループ化
| awk '$1!=1'                                         # 1 product_id で 2 種類以上の price がある = 違反
```

これが空出力なら関数依存 OK。SQL でいうと

```sql
select product_id from orders group by product_id having count(distinct unit_price) > 1;
```

と等価。出題者は **CSV 段階で SQL 不要に検証できる** 設計を意識すると、
採点が高速で済む (DB 起動不要)。

### 1-4 → 1-5 の学習設計

| 段階 | 状態 | 学習者の気づき |
|------|------|---------------|
| 1-4 | 雑な orders を作る | FK 範囲は宣言したが、price は気にしてなかった |
| 1-5 | products と join | 「マスタの値で fact を埋める」というパターンが要る |

これは Topic ② 以降の `mart_*` で「fact + dim を join する」発想と
表裏一体。Topic ① の段階で身につけておくと、後段でテスト失敗の意味を
正しく読めるようになる。
