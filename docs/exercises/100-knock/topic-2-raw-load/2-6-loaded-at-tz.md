# 2-6: source の `loaded_at_field` と Python 側 `loaded_at` 列の型・タイムゾーンを揃える

## シナリオ

2-4 で `raw.orders` に `freshness:` を宣言したが、その「鮮度計算」は `loaded_at_field` で指す列の **型と TZ** に依存する。Python 側で `datetime.now()` (naive) を入れている一方、source 側で `loaded_at_field: loaded_at` を宣言していると、warehouse によっては「TZ 未設定」「実は UTC でなくサーバ TZ」といったズレが入り込み、`dbt source freshness` の `age` 計算が静かに数時間ずれる。

ここでは 2-1 で書いた loader (`scripts/100-knock/topic-2/load_2_1_raw.py`) を改修し、`loaded_at` 列を `datetime.now(tz=timezone.utc)` で生成、DDL 側も `TIMESTAMP WITH TIME ZONE` で受ける。さらに `sources.yml` の `loaded_at_field:` 宣言と整合させて、「Python 側で書く時刻 ↔ DDL の型 ↔ dbt の freshness 計算」が同じ時刻軸で揃う状態を作る。

## 学べること

- `datetime.now()` と `datetime.now(tz=timezone.utc)` の違い (naive vs aware) と、それが PostgreSQL の `TIMESTAMP` / `TIMESTAMPTZ` にどう写るか
- `loaded_at_field:` は **「列名」だけでなく「その列の型」が契約の一部** であること
- `information_schema.columns` で列の `data_type` を SQL から検証する方法
- 「Python 仕様 ↔ DDL ↔ source 宣言」を 3 重に揃えることで初めて freshness が信用できる、という整合性の重要性

## 前提

- 2-1 で `scripts/100-knock/topic-2/load_2_1_raw.py` (psycopg + COPY の loader) を完了済み
- 2-2 で `dbt/models/100-knock/topic-2/sources.yml` を作成済み (`name: raw` の 4 テーブル宣言)
- 2-4 で `raw.orders` に `freshness:` ブロックと `loaded_at_field: loaded_at` を宣言済み
- ローカル Postgres が起動している (`docker compose up -d postgres`)
- `.env` が読める状態

## 入力データ

2-1 で生成した `data/100-knock/topic-2/orders.csv` に **`loaded_at` 列を後付けする** か、loader 側で COPY 後に `UPDATE` で埋めるかは学習者の選択。本問の評価対象は最終的に warehouse の `raw.orders.loaded_at` が **TZ 付きタイムスタンプとして書かれていること** だけ。

## 課題

### Step 1: loader を改修

`scripts/100-knock/topic-2/load_2_1_raw.py` を編集し、`raw.orders` の DDL に `loaded_at TIMESTAMP WITH TIME ZONE` を追加。投入時に `datetime.now(tz=timezone.utc)` の単一値を 1 つ生成し、全行に同じ値を入れる (バッチ単位の "loaded_at")。

要件:

- DDL: `loaded_at TIMESTAMPTZ NOT NULL` を `raw.orders` に追加
- Python: `from datetime import datetime, timezone` で `loaded_at = datetime.now(tz=timezone.utc)` を 1 回計算
- COPY 後に `UPDATE raw.orders SET loaded_at = %s` で全行に流し込む (もしくは CSV を一時テーブル経由でロード後に列追加)
- 1 バッチ = 同一 `loaded_at` 値 (1 ロードでバラバラの時刻にしない)

### Step 2: sources.yml を整える

`dbt/models/100-knock/topic-2/sources.yml` の `raw.orders` 側で `loaded_at_field: loaded_at` がすでに 2-4 で書かれているはず。**型** が `timestamp with time zone` であることを念のため `description` に追記しておく:

```yaml
- name: orders
  loaded_at_field: loaded_at
  freshness:
    warn_after: {count: 24, period: hour}
    error_after: {count: 48, period: hour}
  columns:
    - name: loaded_at
      description: "Batch load timestamp (UTC, timestamp with time zone)."
```

### Step 3: 実行

```bash
.venv/bin/python scripts/100-knock/topic-2/load_2_1_raw.py
psql "$DATABASE_URL" -c "SELECT loaded_at, pg_typeof(loaded_at) FROM raw.orders LIMIT 1;"
# loaded_at | pg_typeof
# 2026-04-26 12:34:56+00 | timestamp with time zone
cd dbt && ../.venv/bin/dbt source freshness --profiles-dir . --select source:raw.orders
```

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-6-loaded-at-tz.grading.yaml
```

## 完了条件

- [ ] `raw.orders` テーブルに `loaded_at` 列が存在する
- [ ] その型が `timestamp with time zone` (timestamptz) である
- [ ] `sources.yml` に `loaded_at_field: loaded_at` の記述がある
- [ ] `loaded_at` 列に NULL がない (NOT NULL 制約 or 全行に値あり)
- [ ] `dbt source freshness --select source:raw.orders` が exit 0 で終わる

## ヒント (詰まったら)

- **naive vs aware**: `datetime.now()` は TZ 情報を持たない (naive)。これを `TIMESTAMPTZ` 列に入れると、PostgreSQL は接続の `TimeZone` 設定で UTC に変換する。サーバ TZ が JST なら 9 時間ズレる。`datetime.now(tz=timezone.utc)` を使えば aware で書けて、どんな接続設定でも同じ瞬間が記録される。
- **型の確認 SQL**: `SELECT data_type FROM information_schema.columns WHERE table_schema='raw' AND table_name='orders' AND column_name='loaded_at';` → `timestamp with time zone` が返れば OK。
- **CSV 経由で入れたい場合**: ISO 8601 の `2026-04-26T12:34:56+00:00` 形式で書いておけば、PostgreSQL の `COPY` は `TIMESTAMPTZ` に直接入る。CSV を編集したくないなら、`COPY` 後に `UPDATE raw.orders SET loaded_at = %s` で 1 回で埋める方が楽。
- **freshness 計算の罠**: dbt の freshness は `current_timestamp - max(loaded_at)` で `age` を計算する。両者の TZ が揃っていないと `age` がマイナスになって warn が出っぱなしになる、という事故が起きる。TZ を統一しておくのが唯一の正解。

## 解答例

詳細は [`2-6-loaded-at-tz.solution.md`](2-6-loaded-at-tz.solution.md) を参照。
