# 2-4: `raw.orders` に `loaded_at` を持たせ、`freshness:` SLA を宣言する

## シナリオ

dbt は外部世界 (raw) の **鮮度** に対しても契約を結べる。`sources.yml` の `freshness:` ブロックに
`warn_after` / `error_after` を宣言しておくと、`dbt source freshness` で「raw が古過ぎる時に
warn / error を出す」ことができる。これを書いておけば、CI で「上流データが古いだけで run を弾く」
ことができ、**「最新の raw を使った」が暗黙の前提から契約に昇格する**。

本問では:

1. `raw.orders` に `loaded_at TIMESTAMPTZ` 列を追加 (2-1 のローダー改修)
2. `sources.yml` の `orders` テーブルに `loaded_at_field: loaded_at` と `freshness:` ブロックを追記
3. `dbt source freshness` を回して、warn 1 day / error 2 day の SLA が宣言通り動くことを確認

## 学べること

- source 側に **データ鮮度 SLA** を持たせる設計 (`freshness:` block)
- `loaded_at_field:` で freshness 判定に使う列を指定する宣言
- `warn_after:` / `error_after:` の period (`hour` / `day`) と count
- raw テーブルに `loaded_at` メタ列を持たせる ELT パターン (DEFAULT `now()`)
- `dbt source freshness` の exit code (warn でも 0 / error なら 1) の意味

## 前提

- 2-1 / 2-2 / 2-3 完了
- 学習者の `scripts/100-knock/topic-2/load_raw.py` を改修して `loaded_at` を追加できる状態
- `dbt parse` が緑

## 入力データ

直接の入力データはないが、`raw.orders` の DDL を **`loaded_at TIMESTAMPTZ DEFAULT now() NOT NULL`** で
拡張する必要がある。

## 課題

### Step 1: `load_raw.py` を改修して `raw.orders` に `loaded_at` を追加

`scripts/100-knock/topic-2/load_raw.py` の `orders` の DDL を以下のように変更:

```sql
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
```

`loaded_at` は `DEFAULT now()` なので、CSV に列が無くても `COPY` 後に自動で投入時刻が入る。
ただし `COPY` のターゲット列を明示する必要があるので、COPY 文も修正:

```python
copy_sql = (
    f"COPY {SCHEMA}.{table.name} ({csv_columns}) "
    "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
)
```

`csv_columns` は CSV のヘッダ列 (orders なら 7 列、`loaded_at` を含まない)。

### Step 2: 再ロード

```bash
set -a; source .env; set +a
python3 scripts/100-knock/topic-2/load_raw.py
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT loaded_at FROM raw.orders LIMIT 1;"
# => 現在時刻 (TIMESTAMPTZ) が表示される
```

### Step 3: `sources.yml` に freshness を追記

`dbt/models/100-knock/topic-2/sources.yml` の `orders` table に以下を追加:

```yaml
- name: orders
  description: "..."
  loaded_at_field: loaded_at
  freshness:
    warn_after: { count: 1, period: day }
    error_after: { count: 2, period: day }
  columns:
    - name: order_id
      ...
    - name: loaded_at
      description: "raw 投入時刻 (TIMESTAMPTZ)。dbt source freshness の判定に使う。"
```

### Step 4: `dbt source freshness` を実行

```bash
cd dbt
../.venv/bin/dbt source freshness --profiles-dir . --select source:raw_100knock.orders
# 期待: PASS (今ロードしたばかりなので 1 day 以内)
```

`Done.` で終わり、exit 0 が返れば OK。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-4-freshness-declare.grading.yaml
```

## 完了条件

- [ ] `sources.yml` に `freshness:` キーが含まれている
- [ ] `sources.yml` に `loaded_at_field:` キーが含まれている
- [ ] `sources.yml` に `warn_after:` キーが含まれている
- [ ] `sources.yml` に `error_after:` キーが含まれている
- [ ] `raw.orders` に `loaded_at` 列が存在し、TIMESTAMPTZ で NULL なし
- [ ] `dbt source freshness --select source:raw_100knock.orders` が exit 0 (PASS)

## ヒント (詰まったら)

- **`COPY` の列指定**: CSV 側に存在しない列を `DEFAULT` で埋めたい時は、`COPY table (col1, col2, ...) FROM STDIN`
  のように **挿入対象列を明示** する必要がある。これを書かないと `COPY` は全列を期待し、列数不一致でコケる。
- **`TIMESTAMPTZ` vs `TIMESTAMP`**: `freshness` はタイムゾーン込みで現在時刻と比較するので `TIMESTAMPTZ`
  推奨。`TIMESTAMP` (naive) で書くと、運用環境の TZ ずれで warn が誤発動する。
- **`warn_after` < `error_after`**: dbt は両者が逆転していても素直に動くが、意味的に warn が先、error が後。
  `warn 1 day / error 2 day` のように **段階を持たせる** のが standard。
- **`dbt source freshness` の exit code**: PASS = 0、WARN = 0 (! warn は警告で exit 0)、ERROR = 1。
  CI で「warn でも止めたい」場合は `--no-warn-error` の逆として `--warn-error` を付ける。
- **何故 source 側に freshness を**: staging 側に書いても freshness は **source ノードに紐付く** 概念。
  staging は raw が古いかどうかを知らないし、知るべきでない。SLA は **データの入口** で宣言する。

## 解答例

詳細は [`2-4-freshness-declare.solution.md`](2-4-freshness-declare.solution.md) を参照。
