# task-001: custom tests

- Phase: 06
- Status: Done
- Owner: -
- Depends on: phase-05/task-002
- Parallelizable with: phase-06/task-002

## 目的
spec §9.2 の独自テストを実装する。

## 入力 / 前提
- spec §9

## 成果物
- `dbt/tests/assert_positive_sales_amount.sql`（singular: int_order_details の sales_amount >= 0）
- `dbt/tests/assert_positive_quantity.sql`（singular: stg_orders.quantity > 0）
- `dbt/tests/assert_marts_total_sales_non_negative.sql`（singular: 各マートの total_sales_amount >= 0）
- `dbt/tests/assert_daily_sales_not_empty.sql`（singular: mart_daily_sales 件数 > 0）

## 受入条件
- `dbt test --profiles-dir .` が全件成功

## 実行ログ

### `dbt test --profiles-dir .`（全件）

```
Found 8 models, 61 data tests, 4 sources, 466 macros

Concurrency: 4 threads (target='dev')

... (61 PASS lines omitted) ...

Finished running 61 data tests in 0 hours 0 minutes and 0.41 seconds (0.41s).

Completed successfully

Done. PASS=61 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=61
```

既存 57 件の generic test（unique / not_null / relationships / source）に
新規 4 件の singular test を加え、合計 **61 件すべて PASS**。

### `dbt test --select test_type:singular --profiles-dir .`（singular のみ）

```
Found 8 models, 61 data tests, 4 sources, 466 macros

Concurrency: 4 threads (target='dev')

1 of 4 START test assert_daily_sales_not_empty ................................. [RUN]
2 of 4 START test assert_marts_total_sales_non_negative ........................ [RUN]
3 of 4 START test assert_positive_quantity ..................................... [RUN]
4 of 4 START test assert_positive_sales_amount ................................. [RUN]
3 of 4 PASS assert_positive_quantity ........................................... [PASS in 0.03s]
1 of 4 PASS assert_daily_sales_not_empty ....................................... [PASS in 0.03s]
4 of 4 PASS assert_positive_sales_amount ....................................... [PASS in 0.03s]
2 of 4 PASS assert_marts_total_sales_non_negative .............................. [PASS in 0.03s]

Finished running 4 data tests in 0 hours 0 minutes and 0.11 seconds (0.11s).

Done. PASS=4 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=4
```

### 各テストファイルの内容要約

| ファイル | 違反条件（行が返ったら fail） | 参照モデル |
| --- | --- | --- |
| `assert_positive_sales_amount.sql` | `sales_amount < 0` | `int_order_details` |
| `assert_positive_quantity.sql` | `quantity <= 0` | `stg_orders` |
| `assert_marts_total_sales_non_negative.sql` | 3 マートいずれかで `total_sales_amount < 0`（UNION ALL） | `mart_daily_sales` / `mart_customer_sales` / `mart_product_sales` |
| `assert_daily_sales_not_empty.sql` | `count(*) = 0` のとき定数行 1 件を返す（CTE） | `mart_daily_sales` |

## 実装メモ / 判断ログ
- singular tests は「失敗行が返ってきたら失敗」なので、各SQLは `SELECT ... WHERE <違反条件>` の形にする。
- **SELECT 戦略**: 4 ファイルすべて「不変条件に違反する行を SELECT する」形式に統一。
  generic test との対比でも一貫し、失敗時に違反行そのものが原因として残るので
  デバッグしやすい。
- **mart 3 本を 1 ファイルに集約**: `assert_marts_total_sales_non_negative.sql` は
  3 つのマートを `UNION ALL` で 1 テストに集約した。理由は (1) 違反条件が同じ
  (`total_sales_amount < 0`) で命名・粒度が一致する、(2) ファイル数が増えても
  情報量が増えず維持コストだけ上がる、(3) 失敗時にどのマートで違反したかを
  `mart` 列、どの行で違反したかを `key_value` 列（order_date / customer_id /
  product_id を text にキャストして統一）で識別できるので診断性も保てる。
- **`assert_daily_sales_not_empty` を CTE で実装した理由**: dbt singular test の
  セマンティクスは「行が返ったら失敗」。`select * from mart where false` 的に
  「件数 0 を fail にする」素直な書き方は無いため、`count(*)` を CTE で計算し
  `where n = 0` で空のときだけ 1 行（`'mart_daily_sales is empty'`）を返す形にした。
  これにより「マートが満たしていれば 0 行 → PASS、空っぽなら 1 行 → FAIL」と
  dbt の合否判定に綺麗に整合する。
- **`quantity > 0` ではなく `quantity <= 0` を違反条件にした理由**: 仕様（spec §9.2）
  は不変条件として「quantity > 0」を求めているが、singular test SQL に書くべきは
  その否定（違反条件 `quantity <= 0`）。`> 0` をそのまま書くと「合格行を SELECT」
  になり PASS / FAIL の意味が逆転する。同じ理由で `sales_amount >= 0` の不変条件は
  `sales_amount < 0` を SELECT、`total_sales_amount >= 0` の不変条件は
  `total_sales_amount < 0` を SELECT、という対応関係。
- **意図的失敗ドリル（口頭報告のみ・コミットなし）**: 4 本それぞれ条件を反転
  （`< 0` → `>= 0`、`<= 0` → `> 0`、`n = 0` → `n > 0`）すれば違反行が大量に
  返り fail することはコードレビュー上明らかなので、実 DB 反転実行はスキップ。
  式の論理（不変条件の否定）が上の表どおりであることを根拠とする。
