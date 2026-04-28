# 1-9 解答例

## scripts/100-knock/topic-1/generate_1_9_orders_cli.py

```python
"""Generate per-date orders CSV with --rows / --date CLI for 100-knock Topic 1 / Q9.

Output: data/100-knock/topic-1/orders_<date>.csv
- Same args -> byte-identical output (idempotent).
- Different --date -> different file (no overwrite).
"""
from __future__ import annotations

import argparse
import hashlib
import random
from datetime import date
from pathlib import Path

import pandas as pd
from faker import Faker

NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20
LOCALE = "ja_JP"
REFERENCE_DATE = date(2026, 4, 26)
PK_BLOCK_SIZE = 10_000  # reserve PK range per day so daily merges don't collide

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "data" / "100-knock" / "topic-1"


def _seed_for_date(d: date) -> int:
    """Stable 32-bit seed derived from the date string (sha1 -> first 4 bytes)."""
    digest = hashlib.sha1(d.isoformat().encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _date_offset(d: date) -> int:
    """Stable non-negative day-offset from REFERENCE_DATE for PK block allocation."""
    return max(0, (d - REFERENCE_DATE).days)


def _build_price_grid(seed: int) -> dict[int, int]:
    """Per-product unit_price (deterministic given seed). 100..9990 yen grid."""
    rng = random.Random(seed ^ 0xA17EA17E)  # decoupled but still seed-dependent
    return {pid: rng.randint(10, 999) * 10 for pid in range(1, NUM_PRODUCTS + 1)}


def _generate(target_date: date, n_rows: int) -> pd.DataFrame:
    seed = _seed_for_date(target_date)
    rng = random.Random(seed)
    fake = Faker(LOCALE)
    fake.seed_instance(seed)  # not strictly needed here, but keeps the contract uniform

    price_lookup = _build_price_grid(seed)
    pk_start = 100_000 + _date_offset(target_date) * PK_BLOCK_SIZE + 1

    rows = []
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-date orders CSV (100-knock 1-9).")
    parser.add_argument("--date", required=True, help="Order date in ISO format, e.g. 2026-04-15")
    parser.add_argument("--rows", type=int, default=1_000, help="Number of orders (default 1000)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = _generate(target_date, args.rows)
    out_path = OUTPUT_DIR / f"orders_{target_date.isoformat()}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Generated {out_path.relative_to(REPO_ROOT)}: {len(df)} rows (date={target_date.isoformat()})")


if __name__ == "__main__":
    main()
```

**ポイント**:

- **日付派生 seed**: `hashlib.sha1(date_str).digest()[:4]` を 32-bit 整数化することで、同じ日付なら必ず同じ seed、違う日付なら別 seed が出る。`hash()` を使うと Python の起動時 PYTHONHASHSEED の影響を受けて壊れるので NG。
- **PK ブロック予約**: `pk_start = 100_000 + offset_days * 10_000 + 1` で日付ごとに 10,000 件分の `order_id` 帯域を予約。1 日分が PK_BLOCK_SIZE を超えない限り、後で日次 CSV を全件 UNION しても PK 衝突しない。
- **冪等性の核**: `random.Random(seed)` を 1 本作って使い回す + `pd.DataFrame(..., columns=[...])` で列順固定 + `to_csv(index=False)` で index 列を出さない。この 3 点で「同じ引数 → md5 同一」が保証される。
- **`datetime.now()` を一切使わない**: `loaded_at` のような実行時刻列は意図的に削除した。実行時刻を入れたいなら `--loaded-at` を CLI 引数に追加して、それも決定論的に外から渡す設計にする。
- **強い参考**: `scripts/exercises/generate_03_new_orders.py` は同じ思想で書かれた MVP 同梱の参照実装。argparse の構成・seed 導出・PK 衝突回避ロジックがほぼ同じパターン。

## 実行例

```
$ python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-15 --rows 500
Generated data/100-knock/topic-1/orders_2026-04-15.csv: 500 rows (date=2026-04-15)

$ md5sum data/100-knock/topic-1/orders_2026-04-15.csv
e3b0c44298fc1c149afbf4c8996fb924  data/100-knock/topic-1/orders_2026-04-15.csv

$ python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-15 --rows 500
Generated data/100-knock/topic-1/orders_2026-04-15.csv: 500 rows (date=2026-04-15)

$ md5sum data/100-knock/topic-1/orders_2026-04-15.csv
e3b0c44298fc1c149afbf4c8996fb924  data/100-knock/topic-1/orders_2026-04-15.csv   # 同じ

$ python3 scripts/100-knock/topic-1/generate_1_9_orders_cli.py --date 2026-04-16 --rows 500
$ ls data/100-knock/topic-1/orders_*.csv
data/100-knock/topic-1/orders_2026-04-15.csv
data/100-knock/topic-1/orders_2026-04-16.csv
```

## 解説まとめ

- **なぜ冪等性が必要？**: 後続トピックで `dbt run --full-refresh` や CI 上での再実行を安全に回すため。上流 CSV が「実行ごとに微妙に違う」状態だと、下流の `dbt test` が「データ起因の偽陽性」で落ちる。再現性のないテストは長期的にミュートされ、最終的にテスト全体の信頼が崩壊する (典型的なアンチパターン)。
- **日付派生 seed の意義**: 「シードを定数 `42` に固定」だと全日付で同じデータが出てしまう。「日付ごとに別データ・かつ同じ日付なら必ず同じ」を両立させるのが日付派生 seed の役割。Git の commit hash と同じ思想 (内容→決定論的 ID)。
- **`--full-refresh` の前提条件**: dbt の incremental model は「上流が冪等であること」を暗黙に仮定している。`--full-refresh` で全量再構築したとき、上流 CSV が変わっていれば下流テーブルも変わる。これが意図せぬ差分を生まないために、上流側で「同じ引数なら同じ出力」を保証する必要がある。
- **PK ブロック予約の意義**: 日次ファイルを後で `cat orders_*.csv` で結合しても `order_id` がユニークであることを保証。PK 設計は「1 ファイル単位ではなく時系列で見たときのユニーク性」で考えるのが本筋。
- **`datetime.now()` 禁止令**: 「現在時刻」が出力に混ざると即座に冪等性が壊れる。時刻が必要なら CLI 引数として外から注入する (`--loaded-at`) のが定石。これは Twelve-Factor App の "Logs as event streams" / "Backing services" の発想に近い。
