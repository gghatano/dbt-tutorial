# 7-3 解答例

## Step 1: raw.products に updated_at を追加

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
ALTER TABLE raw.products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;
UPDATE raw.products SET updated_at = now() WHERE updated_at IS NULL;
SQL
```

スクリプト化したい場合は `scripts/100-knock/topic-7/add_updated_at_to_products.py`:

```python
"""Add updated_at column to raw.products for 100-knock Topic ⑦ Q3 (timestamp strategy)."""
from __future__ import annotations
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    dsn = (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "ALTER TABLE raw.products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"
        )
        cur.execute(
            "UPDATE raw.products SET updated_at = now() WHERE updated_at IS NULL"
        )
        cur.execute("SELECT count(*) FROM raw.products WHERE updated_at IS NOT NULL")
        print(f"raw.products.updated_at populated: {cur.fetchone()[0]} rows")
        conn.commit()


if __name__ == "__main__":
    main()
```

## Step 2: sources.yml に updated_at 追記

`dbt/models/100-knock/topic-2/sources.yml` の products テーブル定義に 1 行追加:

```yaml
- name: products
  description: "商品マスタ (100 行) — Topic ① 1-2 由来 + Topic ⑦ で updated_at 追加"
  columns:
    - name: product_id
    - name: product_name
    - name: category
    - name: unit_price
    - name: updated_at
      description: "raw 投入時刻 (Topic ⑦ で追加)"
```

## Step 3: dbt/snapshots/100-knock/topic-7/snap_products_ts_100knock.sql

```sql
{% snapshot snap_products_ts_100knock %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='timestamp',
        updated_at='updated_at',
    )
}}

-- 100-knock Topic ⑦ Q3: timestamp strategy 版。
-- raw.products.updated_at が前回 snapshot より新しい行だけを履歴化する。
-- 7-1 の check 版とは別 snapshot として並走させ、戦略の違いを比較する。
select
    product_id,
    product_name,
    category,
    unit_price,
    updated_at
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

**ポイント**:

- **`strategy='timestamp'`** + **`updated_at='updated_at'`**: timestamp strategy
  では `check_cols` を使わず、代わりに「どの列が更新時刻か」を string で 1 列指定。
  dbt は次回実行時に「source 側の updated_at > 既存 snapshot の updated_at」の
  行だけを変化扱いする。
- **`updated_at` 列を SELECT に含める**: snapshot は `dbt_valid_from` を
  自動生成するが、`updated_at` 列自体も保存対象として持っておくと、
  「どの時点で raw が変わったか」を後から完全に追える (`dbt_valid_from` は
  snapshot 実行時刻、`updated_at` は raw 側の論理時刻、という二重記録)。
- **snapshot 名 `_ts` suffix**: 7-1 の `snap_products_100knock` (check 版) と
  並走させるため。manifest 上は別 node (`snapshot.local_analytics.snap_products_ts_100knock`)
  になる。

## Step 4: 実行ログ例

```text
$ ../.venv/bin/dbt parse --profiles-dir .
14:50:01  Found 11 models, 6 sources, 2 snapshots, ...

$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_ts_100knock
14:50:10  1 of 1 START snapshot snapshots.snap_products_ts_100knock ..... [RUN]
14:50:10  1 of 1 OK snapshotted snapshots.snap_products_ts_100knock ..... [SELECT 100 in 0.10s]
14:50:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

## Step 5: 物理確認 (check 版との比較)

```sql
analytics=> SELECT 'check' AS strategy, count(*), count(DISTINCT product_id)
            FROM snapshots.snap_products_100knock
            UNION ALL
            SELECT 'timestamp', count(*), count(DISTINCT product_id)
            FROM snapshots.snap_products_ts_100knock;
 strategy  | count | count
-----------+-------+-------
 check     |   120 |   100
 timestamp |   100 |   100
```

`check` 版は 7-2 で 20 行追加されているので 120、`timestamp` 版は 1 回目しか
実行していないので 100。

```sql
analytics=> SELECT product_id, unit_price, updated_at, dbt_valid_from, dbt_valid_to
            FROM snapshots.snap_products_ts_100knock LIMIT 3;
 product_id | unit_price |     updated_at      |   dbt_valid_from    | dbt_valid_to
------------+------------+---------------------+---------------------+--------------
          1 |    1240.00 | 2026-04-26 14:48:00 | 2026-04-26 14:50:10 |
          2 |    8520.00 | 2026-04-26 14:48:00 | 2026-04-26 14:50:10 |
          3 |    8520.00 | 2026-04-26 14:48:00 | 2026-04-26 14:50:10 |
```

`updated_at` (raw 側のメタ列) と `dbt_valid_from` (snapshot 自動生成) が **両方
保存** されているのが timestamp 版の特徴。

## 解説まとめ

- **strategy 選択の境界条件**: source に「信頼できる更新時刻列」があれば
  `timestamp`、無ければ `check`。判定ルールはこれだけ。
- **計算量の差**: `check` は前回 snapshot 全行 vs source 全行を **値比較** する
  ので O(N) のフル比較。`timestamp` は `WHERE updated_at > <previous>` で
  source 側の差分だけを送ってくる O(差分件数)。100 万行規模になると桁違いに
  差が出る。
- **`timestamp` の落とし穴**: source 側の `updated_at` が **嘘** (例: アプリが
  更新を忘れた / バルク UPDATE で全行に同じ now() を入れる) だと、検知漏れや
  全行履歴化の事故が起きる。`updated_at` の信頼性が strategy の前提。
- **`check` の落とし穴**: `check_cols` に列を増やしすぎると検知すべきでない
  変化まで履歴化される (例: `product_name` の typo 修正で全 100 行が新版扱い)。
  `check_cols` は **「ビジネス上の歴史を切るべき列」** に絞る。
- **`dbt_valid_from` の精度差**: `check` 版の `dbt_valid_from` は **snapshot 実行
  時刻** (= raw が変わったタイミングと無関係)。`timestamp` 版は同じく実行時刻だが、
  `updated_at` 列を SELECT に含めれば **raw 側の論理時刻** も追える。「価格が
  本当に何時に変わったか」を厳密に知りたい用途では `timestamp` + `updated_at`
  保存が必須。
- **同じ source への複数 snapshot は OK**: 戦略の比較や、抽出列を変えた別観点の
  履歴 (例: `unit_price` だけ追跡 vs `category` も追跡) を並走させる用途で
  使う。snapshot 名 (= 物理テーブル名) が違えば衝突しない。
- **本問では 1 回目だけ実行**: 2 回目以降の挙動 (timestamp による差分検知) を
  本格的に体験するのは 7-9 (冪等性) や、updated_at を更新した後の手動実行で。
