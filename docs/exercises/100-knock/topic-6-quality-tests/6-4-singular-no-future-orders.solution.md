# 6-4 解答例

## dbt/tests/100-knock/topic-6/assert_no_future_orders.sql

```sql
-- ============================================================================
-- Singular test: assert_no_future_orders
-- ----------------------------------------------------------------------------
-- 業務不変条件: 注文日付は『遠未来』 (current_date + 90 日以降) であってはならない。
--
-- 設計ノート:
--   - 単発の業務ルールなので generic test にしない (再利用先が無い)。
--   - {{ ref('stg_orders_100knock') }} で staging を参照することで、
--     この test 自体が DAG に組み込まれ、`dbt build --select +stg_orders_100knock`
--     のような上流選択で一緒に走る。
--   - dbt の test 評価ルールは「行が 1 件でも返れば FAIL」。よって
--     『違反行を SELECT で抜き出す』 形で書く (アサーション風ではない)。
--   - 90 日のバッファは『業務的に絶対あり得ない領域』 を保守的に切る指標。
--     『未来は一切 NG』 なら + interval '90 days' を取り去って current_date 単体に。
-- ============================================================================
select
    order_id,
    order_date
from {{ ref('stg_orders_100knock') }}
where order_date > current_date + interval '90 days'
```

**ポイント**:

- **`select order_id, order_date`**: dbt は「返ってきた行数」 だけで成否を
  判定するが、log にダンプされる中身は学習者が「**どの注文行が違反か**」 を
  読み解く材料になる。`select *` でもよいが、必要列に絞るとデバッグしやすい。
- **`{{ ref(...) }}`**: 直接 `from staging.stg_orders_100knock` でも動くが、
  ref を使うと test が DAG に組み込まれる。再 build 時の依存解決が自動化。
- **`current_date + interval '90 days'`**: Postgres 構文。`current_date` は
  予約語 (括弧不要)、`interval` は SQL 標準。
- **コメントの厚み**: singular test は generic と違って「**何のための test か**」
  をコードに残しておかないと、半年後の自分が読み解けない。設計ノート
  をブロックコメントで詳しく書く。

## 実行例

### parse + test

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 76 data tests ...

$ ../.venv/bin/dbt test --profiles-dir . --select test_name:assert_no_future_orders
1 of 1 PASS assert_no_future_orders ........................ [PASS in 0.04s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### 上流選択で一緒に走らせる (DAG 統合の確認)

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select +stg_orders_100knock
... 
N of M PASS assert_no_future_orders .................. [PASS]
... 
Done. PASS>=N+1 WARN=0 ERROR=0 SKIP=0 TOTAL>=N+1
```

`+stg_orders_100knock` は staging とその上流 + **依存している test**
(自作 singular 含む) を全部選択する。singular test が DAG に統合されている
証拠。

## わざと FAIL を体感

### 1. 遠未来日付を仕込む

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET order_date = '2099-12-31' WHERE order_id = 1;
SQL
UPDATE 1
```

### 2. test を実行 → FAIL

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select test_name:assert_no_future_orders
1 of 1 FAIL 1 assert_no_future_orders ........................ [FAIL 1 in 0.05s]
Failure in test assert_no_future_orders (tests/100-knock/topic-6/assert_no_future_orders.sql)
  Got 1 result, configured to fail if != 0

  compiled Code at target/compiled/local_analytics/tests/100-knock/topic-6/assert_no_future_orders.sql
```

### 3. コンパイル後の SQL を読む

```bash
$ cat target/compiled/local_analytics/tests/100-knock/topic-6/assert_no_future_orders.sql
```

```sql
select
    order_id,
    order_date
from "analytics"."staging"."stg_orders_100knock"
where order_date > current_date + interval '90 days'
```

`{{ ref(...) }}` が `"analytics"."staging"."stg_orders_100knock"` (フル
クォート参照) に展開されている。

### 4. 失敗行を直接確認

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "SELECT order_id, order_date FROM staging.stg_orders_100knock WHERE order_date > current_date + interval '90 days'"
 order_id | order_date
----------+------------
        1 | 2099-12-31
(1 row)
```

`order_id=1` の遠未来行が見える = 違反対象が特定できる。

### 5. 戻す

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET order_date = '2026-04-15' WHERE order_id = 1;"

$ ../.venv/bin/dbt test --profiles-dir . --select test_name:assert_no_future_orders
1 of 1 PASS assert_no_future_orders ...
```

## 解説まとめ

- **singular test = 1 ファイル 1 SQL の業務ルール**: `dbt/tests/` 配下の
  任意の `.sql` を dbt が自動で拾う。テンプレートは不要、`SELECT` 1 文で
  「**違反行を返すクエリ**」 を書くだけ。
- **`{{ ref(...) }}` で DAG 統合**: 直接スキーマ参照しても動くが、`ref()` を
  使うと test 自体が manifest 上で「どの model に依存しているか」 が記録され、
  `dbt build --select +stg_orders_100knock` で一緒に走る。test と model の
  ライフサイクルが揃う。
- **「行が返れば FAIL」 ルール (再掲)**: dbt test の宇宙ではこのルールが
  generic / singular に共通。`assert col > 0` のような Java/Python 風の
  アサーションではなく、**データ駆動** で「違反行を抜く SELECT」 を書く。
- **generic vs singular の判断 (実用基準)**:
  - 「正数チェックを 5 列に貼りたい」 → generic (1 ファイル → 5 適用)
  - 「未来日付の注文がない」 → singular (1 モデル限定 / 日付ロジック特殊)
  - 「3 mart の合計が一致」 → singular (UNION ALL で串刺し集計)
  - 「列 A と列 B の組み合わせが unique」 → 引数付き generic か
    `dbt_utils.unique_combination_of_columns`
- **コメントを厚く書く**: singular は generic より「何のため」 が分かりにくい。
  ファイル冒頭にブロックコメントで設計ノート (業務ルール / 計算根拠 / 緩和
  の理由) を残すと、半年後の自分とレビューアが救われる。
- **MVP との並走**: MVP の `dbt/tests/assert_*.sql` (4 本) は**フラット配置**、
  100-knock 側は `dbt/tests/100-knock/topic-6/` のように **サブディレクトリ
  配置**。dbt は再帰的に拾うので両立可能。100-knock の test を増やしても
  MVP の test 構造に影響しない。
- **拡張アイデア**: `assert_no_orders_before_first_customer.sql` (注文日が
  顧客登録日より前にならない)、`assert_revenue_decline_under_50pct.sql`
  (前月比減少率が 50% を超えない) のような **複数列 / 複数モデルにまたがる
  ルール** は singular の独壇場。Topic ⑥ 後半 (6-9〜6-10) のテスト運用
  ポリシーと組み合わせると本格的なデータ品質ガバナンスになる。
