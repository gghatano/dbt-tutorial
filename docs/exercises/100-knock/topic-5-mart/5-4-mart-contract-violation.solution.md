# 5-4 解答例

## Step 1: わざと型を変える

`dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql` の最終 SELECT
末尾を以下のように 1 行だけ書き換える:

```sql
-- 変更前 (5-3 の最終形):
sum(sales_amount)::numeric(18, 2)        as total_sales_amount

-- 変更後 (本問 Step 1, わざと壊す):
sum(sales_amount)::integer               as total_sales_amount
```

schema.yml は **触らない**:

```yaml
- name: total_sales_amount
  data_type: numeric(18,2)   # <- このまま
```

## Step 2: build して落ちることを確認

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock 2>&1 | tee /tmp/5-4-violation.log
04:31:00  Running with dbt=1.11.x
04:31:01  Found 12 models, ...
04:31:02  Concurrency: 1 threads (target='dev')
04:31:02  1 of 1 START sql table model marts.mart_daily_sales_100knock ............ [RUN]
04:31:02  1 of 1 ERROR creating sql table model marts.mart_daily_sales_100knock ... [ERROR in 0.10s]
04:31:02  Finished running 1 table model in 0 hours 0 minutes and 0.20 seconds (0.20s).

Completed with 1 error and 0 warnings:

  Compilation Error in model mart_daily_sales_100knock (models/100-knock/topic-5/mart_daily_sales_100knock.sql)
    This model has an enforced contract that failed.
    Please ensure the name, data_type, and number of columns in your contract match the columns in your model's definition.

    | column_name        | definition_type | contract_type | mismatch_reason   |
    | ------------------ | --------------- | ------------- | ----------------- |
    | total_sales_amount | INT4            | NUMERIC       | data type mismatch|

04:31:02  Done. PASS=0 WARN=0 ERROR=1 SKIP=0 TOTAL=1
```

`ERROR=1` で停止。**dbt は壊れた mart を物理化していない** (table が
作られない) のがポイント。BI 側にダメージが出る前に止まった = 契約の効果。

## Step 3: violation-log.md を書く

`docs/exercises/100-knock/topic-5-mart/5-4-violation-log.md`:

```markdown
# 5-4 Contract Violation Log

## 何を変えたか

`dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql` の
`total_sales_amount` の cast を `numeric(18, 2)` から `integer` に変更。
`schema.yml` の `data_type: numeric(18,2)` はそのまま。

## 起きたこと

`dbt run --select mart_daily_sales_100knock` が以下のエラーで失敗:

\`\`\`
Compilation Error in model mart_daily_sales_100knock
  This model has an enforced contract that failed.
  | column_name        | definition_type | contract_type | mismatch_reason   |
  | total_sales_amount | INT4            | NUMERIC       | data type mismatch|

Done. PASS=0 WARN=0 ERROR=1 SKIP=0 TOTAL=1
\`\`\`

dbt が table を物理化する前に止まったため、`marts.mart_daily_sales_100knock`
の中身は前回 build 時の状態のまま (= BI 側にダメージなし)。

## どう直したか

選択肢 A (SQL を戻す) を選んだ。

理由: BI 側 (`Daily Sales` ダッシュボード) は `total_sales_amount` が
小数 2 桁の金額として表示されることを前提に組まれている。整数化すると
1 円未満の精度が消えて棒グラフの軸が ¥ 単位で表示できなくなる。
**「想定外の型変更だったので元に戻す」が今回の正解**。

業務側から「整数管理にする」という決定があったときは選択肢 B
(schema.yml の data_type も integer に変える) を選び、ダッシュボード側にも
変更を周知する必要がある。

## 直した後の build 結果

\`\`\`
$ ../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock
04:35:00  1 of 1 OK created sql table model marts.mart_daily_sales_100knock [in 0.30s]
04:35:00  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
\`\`\`

無事 PASS。契約宣言 (`contract: enforced`) と data_type 宣言は schema.yml に
維持したまま。
```

## Step 4: 直す

`mart_daily_sales_100knock.sql` の cast を元に戻す:

```sql
sum(sales_amount)::numeric(18, 2)        as total_sales_amount
```

```bash
$ ../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock
04:35:00  1 of 1 OK created sql table model marts.mart_daily_sales_100knock [in 0.30s]
04:35:00  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

## 解説まとめ

- **Contract Error は run 時に発生する**: dbt 1.5+ の contract は SQL コンパイル
  後 / 物理化前のタイミングで `information_schema` 相当を比較する。落ちたとき
  table はまだ書き換わっていない = **BI 側に副作用が出ない**まま停止する、
  これが「build red で守る」の意味。
- **「壊して→直す」を一度通すことの教育的価値**: contract: enforced を立てた
  だけだと「動く宣言」ではなく「動かない飾り」になりがち。一度わざと壊して
  Contract Error を見ることで、mental model が「型契約は実在する」に切り替わる。
- **violation-log.md を残す理由**: 壊したまま commit する PR ではなく、
  「壊して落とした → 何が起きた → どう判断して直した」のジャーナルが学習成果。
  実務でも post-mortem (ポストモーテム) を書く文化と地続き。
- **A vs B の判断軸**:
  - **A (SQL を戻す)**: 「契約は守る、SQL の変更が間違いだった」 → 9 割こちら
  - **B (data_type を変える)**: 「契約自体を変える業務判断がある」
    → 業務 PR + BI 側の事前周知 + ダッシュボード手直しがセット
  - 自動でどちらかに振るのは危険。**人間が判断する関門** として contract が
    機能する
- **採点が「壊した状態」を直接見ない理由**: build が red の状態を CI で PASS と
  判定するには、grading 側に逆向きの ロジック (= "expect failure") が必要で、
  YAML の表現力を超える。代わりに「壊した記録 (log)」と「修正後の build PASS」
  と「契約宣言が schema.yml に残っている」 の三点で代替している。学習体験は
  log の中身に閉じ込める。
- **alias 許容範囲のメモ**: dbt 1.6+ では `bigint`/`int8` のような Postgres
  alias を `alias_types: true` (デフォルト) で同一視する。`numeric(18,2)` →
  `numeric(20,2)` のような precision 違いも data type mismatch になる
  (alias ではないため)。
