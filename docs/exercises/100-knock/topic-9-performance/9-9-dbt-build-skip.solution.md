# 9-9 解答例

## ゴール再掲

- 意図的に 1 つの test を `severity: error` で失敗させる
- `dbt build --select +mart_customer_sales_100knock` を実行
- 上流 test 失敗 → 下流 model + その test が SKIP される様子をログに残す
- `build-skip.md` に観察を記録
- **後始末**: test 設定を元に戻す

## 壊し方 (Step 2 の選択肢 2 通り)

### 選択肢 A: schema.yml に dbt_utils.expression_is_true を追加

`dbt/models/100-knock/topic-3/schema.yml`:

```yaml
version: 2

models:
  - name: stg_orders_100knock
    columns:
      - name: quantity
        tests:
          - dbt_utils.expression_is_true:
              expression: "quantity > 9999"   # 全行が必ず false → test 失敗
              config:
                severity: error
```

dbt-utils を packages.yml に入れている場合 (Topic ⑦ 7-X で導入済み前提)。

### 選択肢 B: singular test SQL を新設 (dbt-utils 不要)

`dbt/tests/100-knock/topic-9/assert_quantity_too_large.sql`:

```sql
{{ config(severity='error') }}
-- 「失敗行」 = quantity <= 9999 の行 (= 全行)
-- このクエリが 1 行でも返したら FAIL
select
    order_id,
    quantity
from {{ ref('stg_orders_100knock') }}
where quantity <= 9999
```

「**この SELECT が返した行の数 = 失敗行数**」という singular test の規約に従っている。本問の壊しテストとして 1 行 SQL で済むこちらが推奨。

## dbt build 実行 (Step 3)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select +mart_customer_sales_100knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-9-skip.log
cd ..
```

期待ログ:

```text
06:00:00  Running with dbt=1.11.0
06:00:00  Found 12 models, 4 sources, 22 tests, ...
06:00:00  Concurrency: 4 threads (target='dev')
06:00:00
06:00:00  1 of 8 START sql view model staging_100knock.stg_customers_100knock ...... [RUN]
06:00:00  2 of 8 START sql view model staging_100knock.stg_orders_100knock ......... [RUN]
06:00:00  3 of 8 START sql view model staging_100knock.stg_products_100knock ....... [RUN]
06:00:00  1 of 8 OK   created sql view model staging_100knock.stg_customers_100knock [CREATE VIEW in 0.10s]
06:00:00  2 of 8 OK   created sql view model staging_100knock.stg_orders_100knock ... [CREATE VIEW in 0.11s]
06:00:00  3 of 8 OK   created sql view model staging_100knock.stg_products_100knock . [CREATE VIEW in 0.10s]
06:00:01  4 of 8 START test assert_quantity_too_large .............................. [RUN]
06:00:01  4 of 8 FAIL  assert_quantity_too_large ................................... [FAIL 10000 in 0.05s]
06:00:01  5 of 8 SKIP relation marts_100knock.mart_customer_sales_100knock ......... [SKIP]
06:00:01  6 of 8 SKIP relation intermediate_100knock.int_order_details_100knock .... [SKIP]
06:00:01  7 of 8 SKIP test not_null_mart_customer_sales_100knock_customer_id ....... [SKIP]
06:00:01  8 of 8 SKIP test unique_mart_customer_sales_100knock_customer_id ......... [SKIP]

06:00:01  Done. PASS=3 WARN=0 ERROR=1 SKIP=4 TOTAL=8
```

## 観察ポイント

- **stg_orders_100knock の物理化 (run) は成功** = run は失敗していない
- **assert_quantity_too_large が FAIL** (severity=error)
- **その下流 (`int_order_details_100knock`, `mart_customer_sales_100knock`) の run + test が SKIP**
  - SKIP は「自分は悪くないが上流が壊れたので走らない」
  - `severity: warn` だったらここは走っていた (警告のみで突き進む)
- **PASS=3 (上流 staging) WARN=0 ERROR=1 (壊した test) SKIP=4 (下流すべて)**

## docs/exercises/100-knock/topic-9-performance/build-skip.md (例)

```markdown
# 9-9 dbt build の SKIP 依存ガード

実行日: 2026-04-26

## 1. ベースライン (test を壊す前)

\`\`\`bash
dbt build --select +mart_customer_sales_100knock --profiles-dir .
# Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8
\`\`\`

## 2. 壊した test

`dbt/tests/100-knock/topic-9/assert_quantity_too_large.sql` を新設:

\`\`\`sql
{{ config(severity='error') }}
select * from {{ ref('stg_orders_100knock') }}
where quantity <= 9999
\`\`\`

= 全行が「失敗条件」に該当するので必ず ERROR

## 3. dbt build 実行 (壊した状態)

\`\`\`text
1 of 8 OK   created sql view model staging_100knock.stg_customers_100knock
2 of 8 OK   created sql view model staging_100knock.stg_orders_100knock
3 of 8 OK   created sql view model staging_100knock.stg_products_100knock
4 of 8 FAIL assert_quantity_too_large [FAIL 10000 in 0.05s]
5 of 8 SKIP relation intermediate_100knock.int_order_details_100knock
6 of 8 SKIP relation marts_100knock.mart_customer_sales_100knock
7 of 8 SKIP test not_null_mart_customer_sales_100knock_customer_id
8 of 8 SKIP test unique_mart_customer_sales_100knock_customer_id

Done. PASS=3 WARN=0 ERROR=1 SKIP=4 TOTAL=8
\`\`\`

## 4. 観察

- `stg_orders_100knock` の run は成功 (model 自体は物理化された)
- `assert_quantity_too_large` が FAIL
- → **下流 model + 下流 test が SKIP** (= 上流壊れたら下流を止める依存ガード)
- もし `severity: warn` だったらここは PASS (警告) で突き進む = ガードなし

## 5. 後始末

\`\`\`bash
rm dbt/tests/100-knock/topic-9/assert_quantity_too_large.sql
dbt build --select +mart_customer_sales_100knock --profiles-dir .
# → Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8 で復活
\`\`\`
```

## 解説まとめ

### なぜ `dbt build` で test 失敗 → 下流 SKIP なのか

- dbt の前提: **「test = データ品質 contract」**。test が失敗 = contract 違反 = 下流に流すべきでないデータ
- `dbt run` だけだと「壊れたデータでも下流まで突き進む」 → 数百 model が壊れたデータで再 build され計算リソースを浪費
- `dbt build` の依存ガードは「**壊れたら止まる**」 = いわば「ヒューズ」。1 model 壊れたら下流 N model のリソース消費を即座にゼロに

### `severity: error` vs `severity: warn`

| | error | warn |
|---|---|---|
| test 失敗時の build | **停止** (下流 SKIP) | **続行** (下流まで run) |
| ログ | ERROR | WARN |
| exit code | 非 0 | 0 |
| 用途 | 「絶対に守る contract」 | 「気にしているが緊急 build したい」 |

実務では:

- **`severity: error`**: PK の not_null / unique、外部キー relationships、業務 KPI の閾値違反
- **`severity: warn`**: 「source data が枯れてきたら教えて」のような soft alert

### なぜ `dbt run` ではなく `dbt build` を本番運用で使うか

- `dbt run` には test ガードがない → 壊れたデータが本番 schema に流れ込む
- `dbt build` は run + test を直列で動かし、test 失敗で下流停止 → 本番 schema に壊れたデータが入らない
- CI / cron / Airflow の dbt 呼び出しは **必ず `dbt build`** を使うのが原則
- `dbt run` / `dbt test` の個別呼び出しは「test だけ走らせたい」「run だけ高速に試したい」開発時のみ

### SKIP のログを読むときの注意

- SKIP は「壊れていない」ステップ。`SKIP` と `ERROR` を混同しないこと
- ジョブの exit code は `ERROR` の有無で決まる (SKIP だけなら exit 1 にはならない、と思いきや dbt は **ERROR が 1 つでもあれば exit 1**)
- CI 上では `Done. PASS=N WARN=M ERROR=K SKIP=L` の `K > 0` をジョブ失敗の条件にする

### 採点で何を見ているか

- `file_exists` で `build-skip.md` 存在
- `shell_command` で md に「SKIP」「ERROR」両キーワードを grep
- `shell_command` で md に `mart_customer_sales_100knock` の言及を grep (= 下流 SKIP の証拠)
- 採点 CI は **学習者が壊した test を残しているとは限らない** ので、grader 側で意図的に壊す singular test を一時的に作って `dbt build` を回す → SKIP/ERROR を観察する設計にできる (grading.yaml の shell_command で実装)

### 注意 — 後始末を忘れると以降の演習が壊れる

- 9-9 で意図的に壊した test を残したまま 9-10 に進むと「`dbt build` が常に ERROR」状態になる
- 後始末 (Step 5) を必ず実行。`git status` で「unexpected new files / changes」が無いことを確認

### 次の問 (9-10) との接続

- 9-9 で「**build の依存ガード**」を学んだ後、9-10 では「**incremental の ROI を時間で計測**」に進む
- Topic ⑨ 全体: 「**materialization 階層** + **並列度** + **差分 build** + **依存ガード** + **incremental ROI**」 = 「**物理コストを宣言で抑える** 5 つの武器」
