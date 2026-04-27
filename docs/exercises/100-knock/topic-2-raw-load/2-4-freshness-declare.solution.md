# 2-4 解答例

## 改修版 scripts/100-knock/topic-2/load_raw.py (orders 部分)

`TABLES` 配列の `orders` の DDL を差し替える:

```python
TableSpec(
    name="orders",
    csv_path=DATA_DIR / "orders.csv",
    ddl="""
        CREATE TABLE raw.orders (
            order_id    BIGINT PRIMARY KEY,
            order_date  DATE,
            customer_id BIGINT,
            product_id  BIGINT,
            store_id    BIGINT,
            quantity    INT,
            unit_price  NUMERIC(12, 2),
            loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """,
),
```

そして `_load_table` の `COPY` 部分を「CSV ヘッダから列リストを動的に拾う」形に変更:

```python
def _load_table(conn: psycopg.Connection, table: TableSpec) -> int:
    if not table.csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {table.csv_path}")

    # Read CSV header to know which columns the file actually carries.
    with table.csv_path.open() as fh:
        header = fh.readline().strip()
    csv_cols = header  # e.g. "order_id,order_date,...,unit_price"

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table.name} CASCADE")
        cur.execute(table.ddl)
        copy_sql = (
            f"COPY {SCHEMA}.{table.name} ({csv_cols}) "
            "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        )
        with cur.copy(copy_sql) as cp, table.csv_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                cp.write(chunk)
        cur.execute(f"SELECT count(*) FROM {SCHEMA}.{table.name}")
        return int(cur.fetchone()[0])
```

これで CSV に無い `loaded_at` 列は `DEFAULT now()` で自動的に埋まる。
他のテーブルも CSV ヘッダ列だけが対象になるので、副作用なし。

## dbt/models/100-knock/topic-2/sources.yml (freshness 追加版・抜粋)

```yaml
version: 2

sources:
  - name: raw_100knock
    description: "100-knock Topic ① で生成した CSV を 2-1 のローダーで投入した raw 層 (物理 schema = raw)"
    database: analytics
    schema: raw
    tables:
      # ... customers / products / stores は description 追加版のまま (省略) ...

      - name: orders
        description: "注文トランザクション (10,000 行) — Topic ① 1-4〜1-7 由来"
        # freshness 判定に使う列。物理列の名前を指定する。
        loaded_at_field: loaded_at
        # 鮮度 SLA: 1 日経過で warn、2 日経過で error。CI で error は exit 1。
        freshness:
          warn_after: { count: 1, period: day }
          error_after: { count: 2, period: day }
        columns:
          - name: order_id
            description: "注文の主キー (BIGINT)。1..10000 の連番。"
          - name: order_date
            description: "注文日 (DATE)。Topic ① 1-7 で 2025-01-01〜2026-04-30 の範囲に分散。"
          - name: customer_id
            description: "顧客への外部キー (raw_100knock.customers.customer_id)。"
          - name: product_id
            description: "商品への外部キー (raw_100knock.products.product_id)。"
          - name: store_id
            description: "店舗への外部キー (raw_100knock.stores.store_id)。"
          - name: quantity
            description: "注文数量 (個、INT)。1〜10。"
          - name: unit_price
            description: "注文時の単価 (円、NUMERIC(12,2))。Topic ① 1-5 で決定論的に算出。"
          - name: loaded_at
            description: "raw 投入時刻 (TIMESTAMPTZ)。dbt source freshness の SLA 判定に使う。"
```

**ポイント**:

- `loaded_at_field:` は **物理列名** (`loaded_at`)。ここで指定した列に対して dbt は `MAX(loaded_at)` を発行し、
  現在時刻との差分で freshness を判定する。
- `freshness:` の `count` / `period` は分かりやすい辞書形式 (`{ count: 1, period: day }`)。
  period は `minute` / `hour` / `day` が使える。
- `warn_after` < `error_after` の段階設計: 1 日遅れは「ちょっと心配」、2 日遅れは「明確に違反」。
  どちらの閾値も **データ運用ポリシー** として yaml に書き残しているので、誰でも変更履歴が追える。
- `loaded_at` 列を `description:` 付きで明示しておくと、docs サイトでも「これは freshness 用」と一目で分かる。
- raw 側に `freshness:` を持たせるのは、**「鮮度は raw の入口で判定するもの」** という設計判断。
  staging に書くと「staging が遅延したのか raw が遅延したのか」の切り分けが難しくなる。

## 実行ログ例

```
$ python3 scripts/100-knock/topic-2/load_raw.py
Loaded raw tables:
  raw.customers   1,000 rows
  raw.products      100 rows
  raw.stores         20 rows
  raw.orders     10,000 rows

$ psql -h localhost -U dbt_user -d analytics \
    -c "SELECT loaded_at FROM raw.orders LIMIT 1;"
         loaded_at
-------------------------------
 2026-04-26 12:50:23.123456+00

$ cd dbt && ../.venv/bin/dbt source freshness --profiles-dir . \
    --select source:raw_100knock.orders
12:51:01  Concurrency: 4 threads
12:51:02  1 of 1 START freshness of raw_100knock.orders ........ [RUN]
12:51:02  1 of 1 PASS freshness of raw_100knock.orders ......... [PASS in 0.10s]
12:51:02  Done.
$ echo $?
0
```

## 解説まとめ

- **freshness は契約**: 「raw は 24 時間以内に更新されている」という運用上の暗黙ルールを、yaml に
  宣言として書き残す。誰かが手で SLA を確認しなくても、CI が `dbt source freshness` で毎回検証する。
- **段階的アラート**: warn は通知のみ、error は CI を落とす。本番運用では「warn → Slack 通知 / error → PagerDuty」
  のように接続する。
- **`loaded_at` の意味**: 「データが warehouse に入った時刻」。データソース側の `created_at` (= 業務発生時刻) と
  混ぜないこと。freshness が見たいのは **パイプラインの遅延** (warehouse 到達遅延) で、業務側の遅延ではない。
- **Topic ②全体の到達点に近づく**: ここまでで sources.yml は「論理名 + 列ドキュメント + 鮮度 SLA」を持つ。
  あと 2-5 で実際に warn を踏み抜く体験を加えれば、source 契約の体感として完成。
- **CI 接続のヒント**: `dbt source freshness` を `dbt build` の **前段** に挟むと、古い raw でモデルを
  作る事故を防げる (詳細は Topic ② 2-10、sibling agent 担当)。
