# 1-2 解答例

## scripts/100-knock/topic-1/generate_1_2_products.py

```python
"""Generate products.csv (100 rows) for 100-knock Topic 1 / Q2.

`category` is constrained to a closed 5-value enum so that downstream
`accepted_values` tests have something real to enforce.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 42
LOCALE = "ja_JP"
NUM_PRODUCTS = 100

# Closed enum: the single source of truth for valid categories.
CATEGORIES = ("food", "electronics", "clothing", "home", "sports")

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "data" / "100-knock" / "topic-1" / "products.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    rows = []
    for product_id in range(1, NUM_PRODUCTS + 1):
        product_name = f"{fake.word()}_{product_id:03d}"
        category = rng.choice(CATEGORIES)
        unit_price = rng.randint(10, 999) * 10  # 100..9990 yen, 10-yen step
        rows.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "unit_price": unit_price,
            }
        )

    df = pd.DataFrame(
        rows,
        columns=["product_id", "product_name", "category", "unit_price"],
    )
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")


if __name__ == "__main__":
    main()
```

**ポイント**:

- `CATEGORIES` を **モジュール先頭のタプル定数** として置くことで、enum を「コード内の唯一の真実」に。後で 6 値に増やしたくなったらここを編集するだけ → grading.yaml の正規表現も同時に直す、という運用が自然になる。
- `f"{fake.word()}_{product_id:03d}"` で `product_name` を作るのは MVP の `scripts/generate_dummy_data.py` と同じパターン。完全一致の重複は避けられるが、`unique` テストはあえてつけない (商品名は世の中で同名があり得る)。
- `unit_price = rng.randint(10, 999) * 10` で 100〜9990 円・10 円単位を保証。生成側で値域を縛ることで、`unit_price > 0` のような sql_assert が後段で簡単に書ける。
- enum の抽選順序が seed 依存 → 100 件あれば 5 値すべて登場する (実測: seed=42 では `food=24, electronics=18, clothing=20, home=18, sports=20` 程度に分散)。

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_2_products.py
Generated data/100-knock/topic-1/products.csv: 100 rows

$ wc -l data/100-knock/topic-1/products.csv
     101 data/100-knock/topic-1/products.csv

$ awk -F, 'NR>1 {print $3}' data/100-knock/topic-1/products.csv | sort -u
clothing
electronics
food
home
sports
```

採点 shell_command の例 (grading.yaml に組み込み済み):

```bash
# distinct categories が 5 値のみで構成されているか
awk -F, 'NR>1 {print $3}' data/100-knock/topic-1/products.csv | sort -u
# 出力 5 行 / 全て enum
```

## 解説まとめ

- **enum を Python 定数で宣言**: dbt の `accepted_values` テストは「実データに enum 違反がないか」を見るが、生成側が enum を守る限り絶対に落ちない。これが「契約をコードで二重保証する」設計。
- **値域を生成側で固定**: `unit_price` を 100〜9990 円に縛ることで、後段 `sql_assert` で `min/max` をチェックする際の期待値が決まる。
- **採点で shell_command + awk**: csv_assert は値の集合チェックを直接サポートしないので、`awk + sort -u` の出力を `expect_stdout_match` で正規表現照合する。これは grader の 9 種チェックを **組み合わせて** 同等機能を作る発想。
- **shell_command の正規表現は厳密に**: `^(food|electronics|clothing|home|sports)$` を全行マッチさせるのではなく、distinct 結果の 5 行が **その 5 値だけ** であることを `\A` / `\z` を使って固定する。
- **拡張を見越す**: `CATEGORIES` を増やしたくなったら、定数 + grading.yaml の正規表現の 2 箇所を更新する運用にする。
