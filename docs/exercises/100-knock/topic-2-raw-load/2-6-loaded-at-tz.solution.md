# 2-6 解答例

## scripts/100-knock/topic-2/load_2_1_raw.py (関連部分の改修)

下記は 2-1 で書いた loader に `loaded_at` 列を追加するパッチ例。`orders` テーブルだけでなく、ついでに 4 テーブル全部に `loaded_at` を持たせるのが運用的に綺麗 (本問の採点対象は `orders` のみ)。

```python
"""Load raw CSVs with a batch loaded_at (UTC, timestamptz)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "100-knock" / "topic-2"
SCHEMA = "raw"

ORDERS_DDL = """
CREATE TABLE raw.orders (
    order_id    BIGINT PRIMARY KEY,
    order_date  DATE,
    customer_id BIGINT,
    product_id  BIGINT,
    store_id    BIGINT,
    quantity    INT,
    unit_price  NUMERIC(12, 2),
    loaded_at   TIMESTAMP WITH TIME ZONE NOT NULL
)
"""


def load_orders(conn: psycopg.Connection, csv_path: Path, batch_loaded_at: datetime) -> int:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS raw.orders CASCADE")
        cur.execute(ORDERS_DDL)

        # Step 1: COPY raw CSV (no loaded_at column) into a staging temp table,
        # then INSERT ... SELECT with the batch loaded_at value.
        cur.execute("""
            CREATE TEMP TABLE _orders_in (
                order_id    BIGINT,
                order_date  DATE,
                customer_id BIGINT,
                product_id  BIGINT,
                store_id    BIGINT,
                quantity    INT,
                unit_price  NUMERIC(12, 2)
            ) ON COMMIT DROP
        """)
        copy_sql = "COPY _orders_in FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        with cur.copy(copy_sql) as cp, csv_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)

        cur.execute(
            """
            INSERT INTO raw.orders
                (order_id, order_date, customer_id, product_id,
                 store_id, quantity, unit_price, loaded_at)
            SELECT order_id, order_date, customer_id, product_id,
                   store_id, quantity, unit_price, %s
            FROM _orders_in
            """,
            (batch_loaded_at,),
        )
        cur.execute("SELECT count(*) FROM raw.orders")
        return int(cur.fetchone()[0])


def main() -> int:
    # Single batch timestamp: every row in this load has the SAME loaded_at.
    batch_loaded_at = datetime.now(tz=timezone.utc)
    dsn = "..."  # build from env (see 2-1)
    with psycopg.connect(dsn) as conn:
        n = load_orders(conn, DATA_DIR / "orders.csv", batch_loaded_at)
        conn.commit()
    print(f"raw.orders: {n} rows, loaded_at={batch_loaded_at.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**ポイント**:

- **`datetime.now(tz=timezone.utc)` を 1 回だけ呼ぶ**: バッチ単位で同じ値を全行に入れるのが「loaded_at = この回のロード時刻」の正しい意味。各行で別々に `now()` を呼ぶと「同じバッチなのに行ごとに数 ms ずつズレる」という気持ち悪い状態になる。
- **TIMESTAMPTZ で受ける**: `TIMESTAMP WITHOUT TIME ZONE` だと naive な値として保存され、`dbt source freshness` の TZ 解釈に依存する。`TIMESTAMPTZ` なら絶対時刻として保存されて、どこから読んでも同じ瞬間に解決される。
- **temp table 経由**: 既存 CSV に列を足したくないので、CSV はそのまま `_orders_in` に COPY し、`INSERT ... SELECT` で `loaded_at` を付けて `raw.orders` に流す。CSV ファイルを汚さない。
- **`ON COMMIT DROP`**: temp table を明示的に消さなくても commit 時に自動で消える。冪等性のため。

## dbt/models/100-knock/topic-2/sources.yml (関連部分)

```yaml
version: 2

sources:
  - name: raw
    schema: raw
    tables:
      - name: orders
        description: "Order transactions with batch loaded_at (timestamptz, UTC)."
        loaded_at_field: loaded_at
        freshness:
          warn_after: {count: 24, period: hour}
          error_after: {count: 48, period: hour}
        columns:
          - name: order_id
            tests: [not_null, unique]
          - name: loaded_at
            description: "Batch load timestamp (UTC, timestamp with time zone)."
            tests:
              - not_null
```

**ポイント**:

- `loaded_at_field:` は文字列で「列名」しか書けないが、その契約を成立させるために **DDL 側で型 (TIMESTAMPTZ) と NOT NULL を保証** する責任は人間にある。dbt は宣言を信じるだけ。
- `tests: - not_null` を `loaded_at` 列に入れておくと、もしどこかで `loaded_at` が NULL のレコードが混入したら `dbt test` でも検知できる二重防御になる。

## 検証 SQL

```sql
-- 型の確認
SELECT data_type
FROM information_schema.columns
WHERE table_schema = 'raw' AND table_name = 'orders' AND column_name = 'loaded_at';
-- expected: timestamp with time zone

-- NULL がないことの確認
SELECT count(*) FROM raw.orders WHERE loaded_at IS NULL;
-- expected: 0

-- バッチ内の loaded_at がすべて同じであることの確認
SELECT count(DISTINCT loaded_at) FROM raw.orders;
-- expected: 1
```

## dbt source freshness の確認

```bash
cd dbt && ../.venv/bin/dbt source freshness --profiles-dir . --select source:raw.orders
# 11:34:56  Concurrency: 4 threads
# 11:34:56  1 of 1 START freshness of raw.orders
# 11:34:56  1 of 1 PASS freshness of raw.orders [PASS in 0.05s]
```

`PASS` が出れば、TZ 揃えが効いて `current_timestamp - loaded_at` が想定通り (数秒〜数十秒) に収まっていることを意味する。

## 解説まとめ

- **なぜ TZ を揃える？**: dbt の `source freshness` は内部で `select max({{ loaded_at_field }}) from {{ source }}` を実行し、warehouse の `current_timestamp` との差を取る。両者が同じ時刻軸 (UTC で aware) でないと、差分計算が壊れる。サーバ TZ が JST、Python が naive UTC を入れる、といった組み合わせだと `age` が `-9h` などになり、freshness が常に PASS してしまう (= 監視が効いていない)。
- **「型レベル契約」の意味**: `loaded_at_field: loaded_at` は「列名」しか書かないが、暗黙に「その列は時刻型」という前提を持つ。dbt は YAML を信じてクエリを組み立てるだけなので、DDL 側で型を保証しないと「文字列列を loaded_at と宣言」みたいな破綻が起きる。
- **`datetime.utcnow()` は非推奨**: Python 3.12 から `datetime.utcnow()` は deprecation warning が出る。`datetime.now(tz=timezone.utc)` を使うのが新しい標準。
- **バッチ単位の loaded_at**: 1 ロード = 同一 `loaded_at` 値を全行に流すのが原則。後で「いつのバッチで入ったか」を絞り込むときに `WHERE loaded_at = '...'` 1 本で抽出できる。incremental model の `is_incremental()` ブロックで使う `MAX(loaded_at)` も、行ごとにバラバラだと意味が薄れる。
- **後続トピックとの連結**: Topic ④ の incremental model で `WHERE loaded_at > (SELECT MAX(loaded_at) FROM {{ this }})` を書くとき、ここで揃えた TZ + 型がそのまま効いてくる。今やっておかないと Topic ④ で「なぜか incremental が全件再ロードする」事故になる。
