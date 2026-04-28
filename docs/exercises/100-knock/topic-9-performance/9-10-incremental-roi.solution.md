# 9-10 解答例

## ゴール再掲

- 10 万行の orders CSV 生成スクリプト + raw 投入
- `mart_orders_full_100knock` (table) と `mart_orders_incremental_100knock` (incremental, merge) を 5 回連続 run
- 計測スクリプトで時間を表化、md に「**x 倍速**」を数値で書く

## scripts/100-knock/topic-9/generate_large_orders.py

```python
"""Generate 100,000-row dummy orders CSV for Topic 9 / Q10 ROI measurement."""
from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 20
START_DATE = date(2024, 1, 1)
END_DATE = date(2026, 4, 26)
SPAN_DAYS = (END_DATE - START_DATE).days

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "100-knock" / "topic-9"


def _build_price_grid(seed: int = 420042) -> dict[int, float]:
    rng = random.Random(seed)
    return {pid: rng.randint(10, 999) * 10 for pid in range(1, NUM_PRODUCTS + 1)}


COLS = ["order_id", "order_date", "customer_id", "product_id", "store_id", "quantity", "unit_price", "loaded_at"]


def _generate(n_rows: int, seed: int = 91042) -> pd.DataFrame:
    rng = random.Random(seed)
    prices = _build_price_grid()
    rows = []
    for i in range(n_rows):
        pid = rng.randint(1, NUM_PRODUCTS)
        order_date = START_DATE + timedelta(days=rng.randint(0, SPAN_DAYS))
        rows.append({
            "order_id": i + 1,
            "order_date": order_date.isoformat(),
            "customer_id": rng.randint(1, NUM_CUSTOMERS),
            "product_id": pid,
            "store_id": rng.randint(1, NUM_STORES),
            "quantity": rng.randint(1, 10),
            "unit_price": prices[pid],
            "loaded_at": datetime.combine(order_date, time(23, 59, 59)).isoformat(timespec="seconds"),
        })
    return pd.DataFrame(rows, columns=COLS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large orders CSV (Topic 9 / Q10)")
    parser.add_argument("--rows", type=int, default=100_000)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = _generate(args.rows)
    out = OUTPUT_DIR / "large_orders.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"Generated {out}: {len(df)} rows")


if __name__ == "__main__":
    main()
```

## scripts/100-knock/topic-9/measure_incremental_roi.py

```python
"""Measure incremental vs table run time, 5 iterations each."""
from __future__ import annotations

import statistics
import subprocess
import time
from pathlib import Path

DBT_DIR = Path(__file__).resolve().parents[3] / "dbt"
DOC_OUT = Path(__file__).resolve().parents[3] / "docs" / "exercises" / "100-knock" / "topic-9-performance" / "incremental-roi.md"
ITERATIONS = 5


def _time_run(model: str, full_refresh: bool = False) -> float:
    cmd = ["../.venv/bin/dbt", "run", "--select", model, "--profiles-dir", ".", "--no-colors"]
    if full_refresh:
        cmd.append("--full-refresh")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=DBT_DIR, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"dbt run failed: {proc.stdout[-500:]}{proc.stderr[-500:]}")
    return time.perf_counter() - t0


def main() -> None:
    print("=== mart_orders_full_100knock (table, 全件再構築) ===")
    full_times = []
    for i in range(1, ITERATIONS + 1):
        t = _time_run("mart_orders_full_100knock")
        full_times.append(t)
        print(f"run {i}: {t:.2f}s")
    full_avg = statistics.mean(full_times)
    print(f"平均: {full_avg:.2f}s\n")

    print("=== mart_orders_incremental_100knock (incremental, merge) ===")
    inc_times = []
    # 1 回目だけ full-refresh で初回フル相当を演出
    t1 = _time_run("mart_orders_incremental_100knock", full_refresh=True)
    inc_times.append(t1)
    print(f"run 1: {t1:.2f}s   (初回フル / --full-refresh)")
    for i in range(2, ITERATIONS + 1):
        t = _time_run("mart_orders_incremental_100knock")
        inc_times.append(t)
        print(f"run {i}: {t:.2f}s   (差分 0)")
    inc_steady_avg = statistics.mean(inc_times[1:])
    print(f"平均 (2-{ITERATIONS} 回目): {inc_steady_avg:.3f}s")
    speedup = full_avg / inc_steady_avg if inc_steady_avg > 0 else float("inf")
    print(f"高速化倍率: {full_avg:.2f} / {inc_steady_avg:.3f} = {speedup:.1f} 倍速\n")

    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    with DOC_OUT.open("w", encoding="utf-8") as f:
        f.write("# 9-10 incremental の ROI 計測\n\n")
        f.write("| run | mart_orders_full (table) | mart_orders_incremental (merge) |\n")
        f.write("|---|---|---|\n")
        for i in range(ITERATIONS):
            note_inc = "(初回フル)" if i == 0 else "(差分 0)"
            f.write(f"| {i + 1} | {full_times[i]:.2f}s | {inc_times[i]:.2f}s {note_inc} |\n")
        f.write(f"| 平均 | {full_avg:.2f}s | {inc_steady_avg:.3f}s (2-{ITERATIONS}) |\n\n")
        f.write(f"## 高速化倍率\n\nincremental は table の **{speedup:.1f} 倍速** (2 回目以降)\n\n")
        f.write("## 損益分岐点\n\n")
        f.write("- 1 回目: incremental は merge オーバーヘッドで table と同等または若干遅い\n")
        f.write("- 2 回目以降: 差分 0 なら数百 ms で完了 → 1 回ごとに大幅な節約\n")
        f.write("- 結論: 2 回目で初回 overhead を回収、3 回目以降は完全に黒字\n")
    print(f"Wrote: {DOC_OUT}")


if __name__ == "__main__":
    main()
```

## 期待出力 (要旨)

```text
=== mart_orders_full_100knock (table) ===  run 1〜5 平均 2.23s
=== mart_orders_incremental_100knock ===   run 1: 2.45s (初回フル) / run 2-5 平均: 0.175s
高速化倍率: 12.7 倍速
Wrote: docs/exercises/100-knock/topic-9-performance/incremental-roi.md
```

## 解説まとめ

### なぜ incremental が圧倒的に速いのか

- `mart_orders_full_100knock` (table) は **毎回 DROP TABLE → CREATE TABLE AS SELECT** の全件再構築。10 万行を毎回フルスキャン + 新テーブル作成
- `mart_orders_incremental_100knock` (incremental, merge) は 1 回目だけ全件、2 回目以降は **`where loaded_at > max(loaded_at)` で差分 SELECT** → 0 行 → merge も走らない (no-op)
- 差分が 0 行なら DB に発行されるのは「最大値取得 SELECT 1 本」 + 「dbt のメタデータ更新」だけ。これが 0.18s の正体

### ROI を計測する意味

- 「incremental に書き換えると速い」だけでは説得力がない
- **数値で示す**: 「table 比 12.7 倍速、損益分岐は 2 回目で達成」 → 経営判断 / アーキテクチャ判断の材料に
- 大規模プロジェクトでは「**incremental 化することで日次 build が 30 分 → 5 分に短縮、CI コストが月 $200 削減**」のような可視化が重要

### 損益分岐点と incremental が向かないケース

- 初回 overhead: incremental の merge SQL は table の単純 INSERT より +Δ秒重い
- 2 回目以降の節約: 1 回ごとに `(table_time - incremental_steady)` 秒節約 → 本ケースは 1 回で元が取れる
- **incremental が向かないケース**: データが小さい (< 1k 行)、スキーマが頻繁に変わる、hard delete が多い、開発初期でデバッグ性を優先したい

### 注意 — 計測の罠

- 1 回目だけ遅い (DB cache が冷たい) → warm-up を 1 回挟む
- noise は ±10〜30%。中央値で評価
- CI 環境は CPU が貧弱で値がぶれる → 「5 倍速以上」のような緩いしきい値で十分

### Topic ⑨ 全体まとめ

| # | 武器 | 何を抑える宣言か |
|---|---|---|
| 9-1〜9-5 | materialization / strategy / hook | 物質化と差分処理 |
| 9-6 | dbt_project.yml 階層宣言 | レイヤー規約 |
| 9-7 | threads 並列度 | 並列性宣言 |
| 9-8 | state:modified+ | 差分 build |
| 9-9 | dbt build SKIP | 依存ガード |
| 9-10 | incremental ROI 計測 | 物質化戦略の数値化 |

= **物理コスト (時間 / ストレージ / リソース) を全て宣言で抑える** Topic ⑨ 完成
