# 2-5 解答例

## scripts/100-knock/topic-2/age_orders.py

```python
"""Forcibly age raw.orders.loaded_at into the past, to trigger dbt source freshness WARN.

Topic ② / Q5 — proves that the freshness contract declared in Q4 actually
fires. Sets every row's ``loaded_at`` to ``now() - interval '36 hours'``,
which is past the ``warn_after: 1 day`` threshold but before the
``error_after: 2 day`` threshold. So a subsequent ``dbt source freshness``
should print WARN (and still exit 0, because warn is just a warning).

Usage:
    python3 scripts/100-knock/topic-2/age_orders.py

Reset:
    python3 scripts/100-knock/topic-2/load_raw.py   # re-load with DEFAULT now()
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
AGE_INTERVAL = "36 hours"  # 1 day < 36h < 2 day → WARN region


def _build_dsn() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
    return (
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


def main() -> int:
    try:
        dsn = _build_dsn()
    except RuntimeError as exc:
        print(f"[age_orders] config error: {exc}", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            # Use a parameterised interval-as-text so we don't have to splice
            # an unsanitised string into SQL. ``CAST(... AS interval)`` keeps
            # the type stable.
            cur.execute(
                "UPDATE raw.orders "
                "SET loaded_at = now() - CAST(%s AS interval)",
                (AGE_INTERVAL,),
            )
            n = cur.rowcount
            conn.commit()
    except psycopg.Error as exc:
        print(f"[age_orders] update failed: {exc}", file=sys.stderr)
        return 1

    print(f"Aged {n} rows in raw.orders by {AGE_INTERVAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**ポイント**:

- `AGE_INTERVAL = "36 hours"` を上に出す。1 day と 2 day の間を狙うのが本問の本質なので、
  この定数の意味を script のドキュメントとして可視化する。
- `CAST(%s AS interval)` で interval を **パラメータ化**: 文字列スプライスを避けて SQL injection
  の余地をゼロに。本問は学習用だが「文字列を SQL に直接挟まない」習慣を最初に付ける。
- `cur.rowcount` で件数を出す。10,000 が出れば全行が "古い" 状態。
- 成功したら `conn.commit()` で確定。失敗 (`psycopg.Error`) なら自動 rollback で元の `loaded_at` が残る。
- `2-1` の `_build_dsn` と同じパターンを再利用。共通化したいなら `scripts/100-knock/topic-2/_db.py`
  に切り出すと尚良いが、本問はサブ目的なのでコピペで十分。

## 実行ログ例

```
$ python3 scripts/100-knock/topic-2/age_orders.py
Aged 10000 rows in raw.orders by 36 hours

$ psql -h localhost -U dbt_user -d analytics \
    -c "SELECT now() - max(loaded_at) AS age FROM raw.orders;"
       age
-----------------
 1 day 12:00:00.123

$ cd dbt && ../.venv/bin/dbt source freshness --profiles-dir . \
    --select source:raw_100knock.orders 2>&1 | tee /tmp/freshness.log
13:00:01  Concurrency: 4 threads
13:00:02  1 of 1 START freshness of raw_100knock.orders ........ [RUN]
13:00:02  1 of 1 WARN freshness of raw_100knock.orders ......... [WARN in 0.10s]
13:00:02  Done.

$ echo $?
0

$ grep -c WARN /tmp/freshness.log
1
```

## 解説まとめ

- **契約の検証 = "失敗パスを意図的に踏む"**: 単に PASS を見るだけでは「契約が動いている」とは言えない。
  わざと違反データを入れて WARN / ERROR を出して初めて、契約が "活きている" と確信できる。
- **WARN と ERROR の段階**: WARN は通知、ERROR は CI 停止。本問は WARN を狙ったが、`AGE_INTERVAL`
  を `"3 days"` に変えれば ERROR を踏める (exit 1)。両方試してみると体感が深まる。
- **exit code の罠**: WARN 時は exit 0 なので、「コマンドが成功した」だけでは warn を見落とす。
  本問の採点では `grep -q WARN` で **stdout 文字列** をチェックすることでこの罠を可視化している。
- **`--warn-error` フラグ**: 本番運用で「warn でも止めたい」場合は `dbt source freshness --warn-error`
  で warn → ERROR に昇格できる。"許容できる遅延 SLA" の感度はチームの判断。
- **後片付けの大切さ**: テストで弄ったデータをそのまま残すと後の問が壊れる。`load_raw.py` を再実行すれば
  `DEFAULT now()` で `loaded_at` が現在時刻に戻り、PASS 状態に復帰する。
- **Topic ② を貫く思想**: 2-1 (物理) → 2-2 (論理名) → 2-3 (description) → 2-4 (freshness 宣言) →
  **2-5 (freshness の実検証)**。宣言 → 実証の往復で、source 契約が紙の上の概念から
  「実データが守らせるルール」に昇華する。
