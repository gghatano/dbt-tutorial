# 1-1 解答例

## scripts/100-knock/topic-1/generate_1_1_customers.py

```python
"""Generate customers.csv (1,000 rows) for 100-knock Topic 1 / Q1.

PK: customer_id (1..1000), seeded for byte-stable re-runs.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 42
LOCALE = "ja_JP"
NUM_CUSTOMERS = 1_000
REFERENCE_DATE = date(2026, 4, 26)
LOOKBACK_DAYS = 730  # 2 years

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "data" / "100-knock" / "topic-1" / "customers.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fake = Faker(LOCALE)
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    rows = []
    for customer_id in range(1, NUM_CUSTOMERS + 1):
        delta = rng.randint(0, LOOKBACK_DAYS)
        created_at = REFERENCE_DATE - timedelta(days=delta)
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": fake.name(),
                "email": fake.unique.email(),
                "created_at": created_at.isoformat(),
            }
        )

    df = pd.DataFrame(
        rows,
        columns=["customer_id", "customer_name", "email", "created_at"],
    )
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(df)} rows")


if __name__ == "__main__":
    main()
```

**ポイント**:

- `Faker.seed_instance(SEED)` + `random.Random(SEED)` の **2 系統シード**: Faker 内部 RNG と純 random の両方を固定しないと、生成順が日替わりで変わる落とし穴がある。
- `REFERENCE_DATE` を `datetime.today()` ではなくハードコードしているのは、**実行日に依存させない** ため。CI で何ヶ月後に走らせても同じ CSV が出る。
- `pd.DataFrame(..., columns=[...])` で列順を明示固定。dict 順は CPython 3.7+ で保証されているが、将来 pandas が再ソートするリスクをここで殺す。
- `fake.unique.email()`: 1000 件規模なら衝突確率は無視できるが、`unique` をつけると衝突時に明示エラー → 静かなデータ重複を未然に検知する **テスト相当の宣言** になる。

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_1_customers.py
Generated data/100-knock/topic-1/customers.csv: 1000 rows

$ wc -l data/100-knock/topic-1/customers.csv
    1001 data/100-knock/topic-1/customers.csv

$ head -3 data/100-knock/topic-1/customers.csv
customer_id,customer_name,email,created_at
1,中島 京助,kondoyumiko@example.com,2025-04-13
2,佐々木 千代,xokamoto@example.org,2024-07-22
```

## 解説まとめ

- **再現性 = 信頼性**: シード固定により「昨日と今日で CSV が違う」事故を防ぐ。これが後続トピックで `dbt test` の安定 PASS につながる。
- **PK は連番で発番**: 1..N の連番にしておくと、後続問で FK (`orders.customer_id`) を `randint(1, NUM_CUSTOMERS)` で安全に振れる。
- **基準日のハードコード**: `today()` を使わないことで「実行日依存のテスト失敗」というアンチパターンを最初から避ける。
- **列順固定**: CSV の列順は契約。`to_csv` の出力が DataFrame の列順そのままなので、`columns=[...]` で宣言する。
- **`unique`・NULL 禁止は生成時に保証**: 採点側 (`csv_assert.expect_unique` / `expect_no_nulls`) で確認する形にすると、生成スクリプトの仕様違反が即検知される。
