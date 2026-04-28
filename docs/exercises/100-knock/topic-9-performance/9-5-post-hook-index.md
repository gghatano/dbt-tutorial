# 9-5: post_hook で incremental mart に index を貼り、cost を比較

## シナリオ

`mart_orders_incremental_100knock` (12000+ 行) ができたので、BI からは
**`WHERE order_date BETWEEN ... AND ...`** で日付範囲フィルタを掛けて読むのが普通。
だが table が大きくなる (10 万 / 100 万行) と、`order_date` に **index がない**
状態では全件 scan になり SELECT が遅くなる。

dbt の **`post_hook`** は「**model build 直後に追加 SQL を発行する**」フック。
ここで `CREATE INDEX IF NOT EXISTS` を書けば、「**model 定義の隣に index 定義が
寄り添う**」状態を作れる。コードと index の二重管理 (= 「model 変えたけど index は
DBA が手動で作る」みたいな運用) をなくせるのが本問のポイント。

`{{ this }}` は dbt の **「自分自身を ref する」** マクロで、`post_hook` の中で
これを使うと「今 build したばかりの table」に index を張れる。

最後に `EXPLAIN ANALYZE` で「index 有無で scan cost がどう変わるか」を実測し、
`index-comparison.md` に記録する。

## 学べること

- `post_hook` の書き方 (`config()` 内 + `{{ this }}` で自身を参照)
- `CREATE INDEX IF NOT EXISTS` (冪等な DDL = 何度 run しても OK)
- `EXPLAIN ANALYZE` の cost / scan type / 実行時間の読み方
- 「**コードと一緒に index 定義を置く**」 = SRE / DBA との分業をなくす設計
- `pg_indexes` で index の存在確認

## 前提

- 9-2 完了 (`mart_orders_incremental_100knock` が存在、incremental + merge)
- main HEAD の MVP `dbt run` が緑
- `psql` が `analytics` DB に接続できる

## 入力データ

新規データなし。9-2 / 9-4 で作った mart に index を追加するだけ。

## 課題

### Step 1: post_hook を mart_orders_incremental_100knock に追加

`dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql` の `config()` に
`post_hook` を追加:

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    merge_exclude_columns=['updated_at'],
    on_schema_change='fail',
    schema='marts',
    post_hook=[
        "create index if not exists ix_orders_order_date on {{ this }} (order_date)"
    ]
) }}

-- ... SQL 本体は 9-4 と同じ ...
```

> **注**: `post_hook` は **list** で渡すと複数の SQL を順に発行できる。今回は 1 つ。

### Step 2: index 無しの cost をベースラインで測る

まず既存 index を削除 (もし以前作っていたら):

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
DROP INDEX IF EXISTS marts.ix_orders_order_date;
"
```

`EXPLAIN ANALYZE` で日付範囲 SELECT のコストを測る:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
EXPLAIN ANALYZE
SELECT count(*) FROM marts.mart_orders_incremental_100knock
WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30';
"
```

期待される結果 (index 無し):

```
Aggregate  (cost=345.12..345.13 rows=1 width=8) (actual time=2.345..2.346 rows=1)
  ->  Seq Scan on mart_orders_incremental_100knock  (cost=...) (actual time=0.012..2.123 rows=N)
        Filter: ((order_date >= '2026-04-01'::date) AND (order_date <= '2026-04-30'::date))
        Rows Removed by Filter: M
Planning Time: 0.123 ms
Execution Time: 2.456 ms
```

→ **`Seq Scan`** (= 全件 scan) が走っている。`cost` と `Execution Time` をメモ。

### Step 3: dbt run で post_hook を発火

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --select mart_orders_incremental_100knock --profiles-dir .
```

ログに以下のような post_hook 発火行が出る:

```
... 1 of 1 OK created sql incremental model marts.mart_orders_incremental_100knock ...
... 1 of 1 START hook ... [RUN]
... 1 of 1 OK hook  ... [SQL CREATE INDEX in 0.04s]
```

### Step 4: index が作成されたことを確認

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT schemaname, tablename, indexname FROM pg_indexes
WHERE indexname = 'ix_orders_order_date';
"
```

期待:

```
 schemaname | tablename                          | indexname
------------+------------------------------------+----------------------
 marts      | mart_orders_incremental_100knock   | ix_orders_order_date
```

### Step 5: index 有りの cost を測る

同じ EXPLAIN ANALYZE を再度実行:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
EXPLAIN ANALYZE
SELECT count(*) FROM marts.mart_orders_incremental_100knock
WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30';
"
```

期待される結果 (index 有り):

```
Aggregate  (cost=12.45..12.46 rows=1 width=8) (actual time=0.234..0.235 rows=1)
  ->  Bitmap Heap Scan on mart_orders_incremental_100knock  ...
        Recheck Cond: ((order_date >= '2026-04-01'::date) AND (order_date <= '2026-04-30'::date))
        ->  Bitmap Index Scan on ix_orders_order_date  (cost=...) ...
              Index Cond: ((order_date >= '...') AND (order_date <= '...'))
Planning Time: 0.156 ms
Execution Time: 0.345 ms
```

→ **`Index Scan`** (or `Bitmap Index Scan`) に変わり、**cost と Execution Time が 1/5
〜 1/10** に。

### Step 6: index-comparison.md に記録

`docs/exercises/100-knock/topic-9-performance/index-comparison.md` を新規作成:

- index 無し / 有り両方の `EXPLAIN ANALYZE` 出力 (cost と Execution Time)
- 比較表 (`Seq Scan` vs `Index Scan`、cost の倍率)
- 「いつ index を貼るべきか」の判断軸 (1〜2 段落)

形式は自由。30〜80 行を目安。

### Step 7: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-9-performance/9-5-post-hook-index.grading.yaml
```

> **採点時の最終 state**: `mart_orders_incremental_100knock` の config に `post_hook`
> が含まれ、`pg_indexes` に `ix_orders_order_date` が存在すること。

## 完了条件

- [ ] `mart_orders_incremental_100knock.sql` の config に `post_hook` で
      `create index if not exists ix_orders_order_date` 宣言
- [ ] `dbt run` 後、`pg_indexes` に `ix_orders_order_date` が存在
- [ ] `index-comparison.md` に `EXPLAIN ANALYZE` の前後比較あり
- [ ] manifest 上 `post_hook` 設定が読める

## ヒント (詰まったら)

- **`{{ this }}` が展開されない**: `post_hook` の文字列内で `{{ this }}` を使うとき、
  外側の `config()` が文字列として渡している場合は **二重 jinja** になる。dbt は
  これを自動で 1 段展開してくれるので、シンプルに `"create index if not exists ix_X
  on {{ this }} (col)"` で OK。
- **`CREATE INDEX IF NOT EXISTS` が冪等**: 既に index がある場合に CREATE INDEX を
  やると ERROR で落ちるが、`IF NOT EXISTS` を付ければ既存ならスキップ。post_hook で
  「DDL を毎回 run」する設計なら **冪等性** が必須。
- **post_hook がなぜ良いか**: 同じことを「DBA が手動で `psql` から CREATE INDEX」
  でやってもよいが、その場合 **コードと運用が分離** する。post_hook で書いておくと:
  - リポジトリだけ見れば「この mart にはこの index がある」が分かる
  - 別環境 (staging / dev) でも同じ index が自動で作られる (= 環境差を生まない)
  - PR レビューで「この index 必要?」を議論できる
- **`pre_hook` との違い**: `pre_hook` は **build 前**、`post_hook` は **build 後** に
  発行。CREATE INDEX は build 後 (table が出来上がった後) でないと貼れないので
  post_hook 一択。ANALYZE 統計更新も同様。
- **incremental の post_hook 発火タイミング**: 初回 build / 差分 run 両方で発火する
  (= 毎 run 毎に CREATE INDEX が走る)。`IF NOT EXISTS` を付けないと 2 回目で fail する
  ので必ず付ける。
- **EXPLAIN と EXPLAIN ANALYZE の違い**: `EXPLAIN` は plan のみ、`EXPLAIN ANALYZE` は
  **実際にクエリを実行して** plan + 実時間を返す。本問は ANALYZE 必須 (実時間で
  比較するため)。

## 解答例

詳細は [`9-5-post-hook-index.solution.md`](9-5-post-hook-index.solution.md) を参照。
