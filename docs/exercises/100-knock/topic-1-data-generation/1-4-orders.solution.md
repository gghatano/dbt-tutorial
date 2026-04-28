# Problem 1-4 解答例

## スクリプト全文

`scripts/100-knock/topic-1/generate_1_04_orders.py`:

```python
"""Generate orders.csv (10,000 rows) for 100-knock Topic 1, Problem 1-4.

Pre-declares FK ranges (customer/product/store IDs) at the top of the file so
that the same constants can later be used by `relationships` tests and the
1-5 deterministic-price refactor.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# ---------------------------------------------------------------------------
# Configuration  --- FK ranges are declared here as the single source of truth.
# ---------------------------------------------------------------------------

SEED = 204
LOCALE = "ja_JP"

NUM_ORDERS = 10_000

# FK ranges (must match 1-1 / 1-2 / 1-3 outputs).
NUM_CUSTOMERS = 1_000   # customer_id in [1, NUM_CUSTOMERS]
NUM_PRODUCTS = 100      # product_id  in [1, NUM_PRODUCTS]
NUM_STORES = 20         # store_id    in [1, NUM_STORES]

QUANTITY_MIN = 1
QUANTITY_MAX = 10
UNIT_PRICE_MIN = 100      # round to nearest 10 yen
UNIT_PRICE_MAX = 9_990

REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 365

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "100-knock" / "topic-1"
OUTPUT_PATH = OUTPUT_DIR / "orders.csv"

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
# Generator
# ---------------------------------------------------------------------------

def generate(rng: random.Random) -> list[list[object]]:
    rows: list[list[object]] = []
    for order_id in range(1, NUM_ORDERS + 1):
        days_back = rng.randint(0, LOOKBACK_DAYS - 1)
        order_date = REFERENCE_DATE - timedelta(days=days_back)
        customer_id = rng.randint(1, NUM_CUSTOMERS)
        product_id = rng.randint(1, NUM_PRODUCTS)
        store_id = rng.randint(1, NUM_STORES)
        quantity = rng.randint(QUANTITY_MIN, QUANTITY_MAX)
        # Round to nearest 10 yen for readability. 1-5 will replace this with
        # a deterministic per-product price.
        unit_price = rng.randint(UNIT_PRICE_MIN // 10, UNIT_PRICE_MAX // 10) * 10
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Seed both random and Faker (Faker isn't strictly needed here but is
    # initialised so the script template carries over to other topic-1 problems).
    rng = random.Random(SEED)
    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    _ = fake  # silence linter; kept for stylistic consistency with siblings.

    rows = generate(rng)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)

    print(f"wrote {OUTPUT_PATH}: {len(rows)} rows")


if __name__ == "__main__":
    main()
```

## 実行例

```bash
.venv/bin/python scripts/100-knock/topic-1/generate_1_04_orders.py
# wrote /.../data/100-knock/topic-1/orders.csv: 10000 rows

wc -l data/100-knock/topic-1/orders.csv
#    10001 data/100-knock/topic-1/orders.csv

head -3 data/100-knock/topic-1/orders.csv
# order_id,order_date,customer_id,product_id,store_id,quantity,unit_price
# 1,2025-08-13,712,42,9,3,2890
# 2,2025-12-04,158,77,2,7,1240
```

FK 範囲チェック:

```bash
awk -F, 'NR>1{print $3}' data/100-knock/topic-1/orders.csv | sort -n | tail -1
# => 1000 (or below)

awk -F, 'NR>1{print $4}' data/100-knock/topic-1/orders.csv | sort -n | tail -1
# => 100 (or below)

awk -F, 'NR>1{print $5}' data/100-knock/topic-1/orders.csv | sort -n | tail -1
# => 20  (or below)
```

## ポイント

- **FK 範囲はモジュール先頭の定数**: `NUM_CUSTOMERS = 1_000` のように
  名前付き定数で書き残す。`rng.randint(1, 1000)` とリテラル直書きすると、
  あとで 1-1 の行数を変えたときに参照漏れが起きる。
- **`random.Random(SEED)` の自前インスタンス**: モジュールレベル
  `random.seed()` を使うと、テストハーネスや他ライブラリが `random` を
  消費した瞬間に再現性が壊れる。自分専用 `Random` を持つのがベストプラクティス。
- **`Faker.seed_instance()`**: ここでは Faker をほぼ使っていないが、
  他の問題 (1-1, 1-8 など) で `fake.name()` / `fake.text()` を呼ぶときに
  クラス共有の seed 状態 (`Faker.seed()`) を汚さないよう、インスタンス
  seed を採用する習慣をつけておく。
- **`csv.writer` を使う理由**: pandas でも書けるが、10,000 行程度なら
  標準ライブラリで十分高速。依存を 1 つ減らせるので CI も軽い。

## 解説まとめ

### なぜ FK 範囲を **先に宣言** するのか

dbt の `relationships` test は「実データの FK が `to:` で指定したテーブルの
PK 集合に含まれるか」を SQL で検証する。Python 側で

```python
customer_id = rng.randint(1, 1000)
```

と書いているのに、`relationships` test 側では `to: ref('stg_customers')` の
1..1500 を参照させてしまうと、**テストはたまたま通るが、実は仕様の食い違いが
潜んでいる** ことに気付けない。

逆に、生成側と検証側が同じ「1..1000」を参照するように書けば:

- データ仕様 (Python) と契約 (dbt test) が **同一ソース** から導かれる
- 仕様変更 (例: customers を 1500 行に拡張) も Python の定数 1 箇所だけ
  触ればよい

これが「Faker をデータ仕様の DSL として使う」の意味。Faker は単なる
ダミー文字列ジェネレータではなく、**データ契約を Python で表現するための
DSL** として扱う。

### `unit_price` の扱い (1-5 への伏線)

ここでは `unit_price` は order ごとにランダムにしている。これは
「同じ product_id でも order ごとに値段が違う」という現実にはありえない
状態。1-5 でこれを直す: products.csv を読み込んで `{product_id: unit_price}`
辞書を作り、order 行ごとに `price_lookup[product_id]` を引く。

つまり 1-4 → 1-5 の流れで、学習者は
「最初は雑に作って、テストが赤くなる箇所を後から直す」という TDD 的な
データ設計の進め方を体得する。
