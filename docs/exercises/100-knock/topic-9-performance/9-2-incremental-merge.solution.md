# 9-2 解答例

## dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    on_schema_change='fail',
    schema='marts'
) }}

-- Grain: 1 row = 1 order_id (incremental mart)。
-- materialization=incremental: 差分 row だけ追加することでフル rebuild を回避。
-- unique_key=order_id: 同じ PK が来たら UPDATE、無ければ INSERT (= upsert)。
-- incremental_strategy=merge: PK で UPSERT する戦略。
--   Postgres adapter は内部で delete+insert に展開する。
-- on_schema_change=fail: 上流 schema が変わったら build 失敗 (= 安全装置)。
select
    order_id,
    order_date,
    customer_id,
    customer_name,
    product_id,
    product_name,
    category,
    store_id,
    quantity,
    unit_price,
    sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
-- 差分 run (2 回目以降): max(order_id) より大きい新規 PK だけを引き込む
where order_id > (select coalesce(max(order_id), 0) from {{ this }})
{% endif %}
```

**ポイント**:

- **`{% if is_incremental() %}` の where 句**: 初回 / `--full-refresh` のときは
  この句がスキップされ全件 SELECT、それ以外は **直前 build 以降の差分** だけに
  絞り込む。これが incremental の核心。
- **`{{ this }}` の意味**: 自分自身 (このモデル) を ref するマクロ。`this` を使うことで
  「今 build しようとしている mart の現在状態」を SELECT できる。
- **高水位線として `max(order_id)`**: 本問は連番 PK 前提なので OK。実務では
  `max(updated_at)` (loaded_at, created_at, etc.) を使うのが汎用的。

## scripts/100-knock/topic-9/generate_orders_diff.py

```python
"""Append N additional orders to raw.orders for Topic 9 / Q2 (incremental).

The script picks up the current max(order_id) from raw.orders and starts a new
contiguous PK range from there, then INSERTs N rows directly into raw.orders.

Usage:
    python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000

Notes:
- raw.orders schema must already exist (from main HEAD's bootstrap).
- Customer / product / store IDs are sampled from existing FK ranges (1..N).
- order_date is randomly within the last 7 days from "today".
"""

from __future__ import annotations

import argparse
import os
import random
from datetime import date, timedelta

import psycopg

NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 100
NUM_STORES = 5  # MVP は 5 店舗

DSN_TEMPLATE = "host={host} port={port} dbname={db} user={user} password={pw}"


def get_dsn() -> str:
    return DSN_TEMPLATE.format(
        host=os.environ["DBT_HOST"],
        port=os.environ.get("DBT_PORT", "5432"),
        db=os.environ.get("DBT_DBNAME", "analytics"),
        user=os.environ["DBT_USER"],
        pw=os.environ["DBT_PASSWORD"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Append N orders to raw.orders.")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2026_04_27)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    with psycopg.connect(get_dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT coalesce(max(order_id), 0) FROM raw.orders;")
        current_max = cur.fetchone()[0]

        rows = []
        today = date.today()
        for i in range(args.rows):
            pid = rng.randint(1, NUM_PRODUCTS)
            rows.append(
                (
                    current_max + 1 + i,                                # order_id
                    today - timedelta(days=rng.randint(0, 6)),          # order_date
                    rng.randint(1, NUM_CUSTOMERS),                      # customer_id
                    pid,                                                # product_id
                    rng.randint(1, NUM_STORES),                         # store_id
                    rng.randint(1, 10),                                 # quantity
                    rng.randint(10, 999) * 10,                          # unit_price
                )
            )

        cur.executemany(
            """
            INSERT INTO raw.orders
                (order_id, order_date, customer_id, product_id, store_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
        conn.commit()
        print(f"Appended {len(rows)} rows to raw.orders (PK {current_max+1}..{current_max+len(rows)})")


if __name__ == "__main__":
    main()
```

**ポイント**:

- **`max(order_id) + 1` から連番**: PK 衝突を防ぐ
- **APPEND のみ**: 既存 raw.orders は触らない (TRUNCATE しない)
- **psycopg を直叩き**: 学習者環境にすでに入っているはず
  (`requirements.txt` に `psycopg[binary]`)

## 実行例

```bash
# 初回 run (10000 行)
$ cd dbt && dbt run --select mart_orders_incremental_100knock --profiles-dir .
... 1 of 1 OK created sql incremental model marts.mart_orders_incremental_100knock ...

$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c \
    "SELECT count(*) FROM marts.mart_orders_incremental_100knock"
 count
-------
 10000

# 差分 1000 行 append
$ cd .. && python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000
Appended 1000 rows to raw.orders (PK 10001..11000)

# 上流から rebuild
$ cd dbt && dbt run --select +mart_orders_incremental_100knock --profiles-dir .
...
1 of 4 OK created sql view model staging.stg_orders_100knock ...
4 of 4 OK created sql incremental model marts.mart_orders_incremental_100knock ...

$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c \
    "SELECT count(*) FROM marts.mart_orders_incremental_100knock"
 count
-------
 11000
```

`target/run/local_analytics/models/100-knock/topic-9/mart_orders_incremental_100knock.sql`
の中身 (2 回目 run 時 / Postgres adapter):

```sql
-- back compat for old kwarg name
  
  begin;

      -- merge を delete + insert に展開する Postgres incremental パターン
      delete from "analytics"."marts"."mart_orders_incremental_100knock"
      where (order_id) in (
          select (order_id)
          from "mart_orders_incremental_100knock__dbt_tmp"
      );

      insert into "analytics"."marts"."mart_orders_incremental_100knock"
          ("order_id", "order_date", "customer_id", ..., "updated_at")
      select "order_id", "order_date", "customer_id", ..., "updated_at"
      from "mart_orders_incremental_100knock__dbt_tmp";

  commit;
```

→ Postgres は MERGE をネイティブサポートしないので、dbt が **`__dbt_tmp` テーブル
を一度作ってから DELETE + INSERT に展開** する。これが「PK で upsert する」の実装。

## 解説まとめ

- **なぜ incremental?**: フル rebuild が現実的でない規模 (100 万行 / 1 億行) になると、
  「**前回 build から増えた分だけ追加**」する戦略でないと毎晩のバッチが朝までに終わらない。
  incremental は dbt の中で最も「実運用での価値」が大きい materialization。
- **3 点セット**: incremental では `materialized` / `unique_key` / `incremental_strategy`
  の 3 つをセットで宣言する。どれか欠けると意図しない挙動になる。
  - `materialized='incremental'` だけ → unique_key 無いと **append** モードになり PK 重複
  - `unique_key='order_id'` 無し → merge / delete+insert で必須エラー
  - `incremental_strategy='merge'` → 「PK 重複なら UPDATE」を保証
- **`is_incremental()` の評価タイミング**: dbt が SQL を **コンパイル** する瞬間に評価。
  `if` の中身は **生成 SQL から消える** (where 句が削除される)。runtime で動くわけではない。
- **冪等性の確認**: 同じ差分データで 2 回 run しても結果が同じ (= 11000 行のまま) なら
  冪等。merge strategy はこれを保証する (PK 重複行は UPDATE で上書き)。append strategy
  だと冪等性が壊れる (9-3 で扱う)。
- **`--full-refresh` の出番**: `is_incremental()` を False に強制し、フル rebuild する。
  上流 schema が壊れた / 過去データを修正したい / 初期 backfill するときに使う。
  日次バッチで毎回付けてはいけない (incremental の意味がなくなる)。
- **高水位線の選び方**:
  - `order_id > max(order_id)`: PK が連番増加なら OK。本問はこれ
  - `loaded_at > max(loaded_at)`: 「いつ DB に積まれたか」 / 最も汎用的。Ex.03 で使った
  - `updated_at > max(updated_at)`: 行が更新されうる場合。merge strategy と相性 good
  - **絶対 NG**: `order_date > max(order_date)` (注文日 ≠ DB 投入日、過去日付の
    遅延注文を取りこぼす)
- **`target/run/` を読む習慣**: dbt は SQL を **コード生成** するので、開発者は
  `target/compiled/` (純粋 SQL) と `target/run/` (DDL 含む実 SQL) の 2 つを
  状況に応じて読み分ける。incremental の挙動を理解するには `run/` を見るのが正解。
