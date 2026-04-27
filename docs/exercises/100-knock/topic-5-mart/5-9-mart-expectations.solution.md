# 5-9 解答例

## ゴール再掲

`packages.yml` に `dbt-expectations` を追加 → `dbt deps` で導入 → `mart_top_rated_products_100knock.avg_rating` に `dbt_expectations.expect_column_values_to_be_between(min=1, max=5)` を貼り、`dbt build` で PASS させる。

## Step 1: `packages.yml`

`dbt/packages.yml`:

```yaml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

> 既に `dbt-utils` を `packages.yml` に入れている (Topic ⑤ 5-2 で複合 PK 用に `dbt_utils.generate_surrogate_key` を使った場合) なら以下のように 2 つ並べる:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

## Step 2: `dbt deps`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
# 22:50:01  Installing calogica/dbt_expectations
# 22:50:03    Installed from version 0.10.4
# 22:50:03    Up to date!
# 22:50:03  Installing dbt-labs/dbt_utils
# 22:50:04    Installed from version 1.3.0
# 22:50:04    Up to date!
```

`dbt_packages/` に展開される:

```bash
ls dbt_packages/
# dbt_expectations
# dbt_utils
```

## Step 3: `schema.yml` 編集

`dbt/models/100-knock/topic-5/schema.yml` の `mart_top_rated_products_100knock.avg_rating` 列にテストを足す:

```yaml
version: 2

models:
  - name: mart_top_rated_products_100knock
    description: |
      高評価商品マート (avg_rating >= 4 AND review_count >= 10)。
      grain = 1 product 1 row。
    meta:                                            # 5-8 で書いた meta はそのまま
      owner: marketing-analytics@example.com
      slack_channel: "#mart-marketing"
      sla_hours: 4
    columns:
      - name: product_id
        description: "Primary key. FK to stg_products_100knock.product_id"
        tests:
          - not_null
          - unique
      - name: product_name
        tests:
          - not_null
      - name: avg_rating
        description: "平均レビュー評点 (1〜5 の連続値、numeric(3,2))"
        tests:
          - not_null
          # ----- 5-9: 業務範囲テスト (dbt-expectations) -----
          # contract (5-3) は型を守る、これは値を守る。
          # row_condition で NULL は除外 (not_null 側で別途検査)
          - dbt_expectations.expect_column_values_to_be_between:
              name: avg_rating_in_1_to_5_100knock
              min_value: 1
              max_value: 5
              row_condition: "avg_rating is not null"
              strictly: false
      - name: review_count
        description: "対象商品のレビュー件数 (>=10 が条件)"
        tests:
          - not_null
      # ... 他列 ...
```

> `name:` を明示することで自動生成のテスト名が短くなり、CI ログが読みやすくなる。

## Step 4: `dbt build` 実行

```bash
../.venv/bin/dbt build --select mart_top_rated_products_100knock --profiles-dir .
# 22:55:01  1 of 4 START sql table model marts.mart_top_rated_products_100knock ... [RUN]
# 22:55:02  1 of 4 OK created sql table model marts.mart_top_rated_products_100knock ... [SELECT 142 in 0.30s]
# 22:55:02  2 of 4 START test not_null_mart_top_rated_products_100knock_avg_rating ... [RUN]
# 22:55:02  3 of 4 START test avg_rating_in_1_to_5_100knock ... [RUN]
# 22:55:02  4 of 4 START test unique_mart_top_rated_products_100knock_product_id ... [RUN]
# 22:55:03  2 of 4 PASS not_null_mart_top_rated_products_100knock_avg_rating ... [PASS in 0.10s]
# 22:55:03  3 of 4 PASS avg_rating_in_1_to_5_100knock ... [PASS in 0.10s]
# 22:55:03  4 of 4 PASS unique_mart_top_rated_products_100knock_product_id ... [PASS in 0.10s]
# Done. PASS=4 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=4
```

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-9-mart-expectations.grading.yaml
```

期待:

```
## Grading Result: OK (100%)
| OK | packages-yml-exists                | 10/10 |
| OK | packages-yml-has-expectations      | 15/15 |
| OK | dbt-expectations-installed         | 20/20 |
| OK | schema-yml-has-expect-be-between   | 20/20 |
| OK | dbt-test-mart-passes               | 35/35 |
```

## ポイント

- **`packages.yml` の役割**: dbt の依存パッケージ定義。`requirements.txt` の dbt 版。`dbt deps` で hub.getdbt.com (または git URL) から取得し `dbt_packages/` に展開。CI でも毎回 `dbt deps` を回す。
- **dbt-expectations の哲学**: Great Expectations (pandas / spark 系の data quality framework) を dbt で動くように移植したもの。「テストは宣言、実行は dbt のテストランナーに任せる」というスタイルに統一できる。
- **`expect_column_values_to_be_between` のシグネチャ**:
  - `min_value`: 下限。包含 (`<=`) は `strictly: false`、排他 (`<`) は `strictly: true`
  - `max_value`: 上限。同様
  - `row_condition`: WHERE 句相当。NULL を除外したい場合は `"<col> is not null"` を渡す
  - `strictly`: bool。`false` で `min <= x <= max`、`true` で `min < x < max`
  - 他にも `mostly: 0.95` (95% が範囲内なら PASS) のような確率的判定もある
- **「型契約 (contract) と値契約 (expectations) の分業」**:
  - **`contract: enforced`** (5-3): 列名 + 型の一致。BI のスキーマ依存を守る
  - **`dbt-expectations`** (本問): 列の値の業務範囲。BI の意味依存を守る
  - 両方を組み合わせて初めて「mart は BI に対して正しいデータを正しい構造で出している」が成立。
- **builtin で書ける場合は builtin で書く**: `not_null` / `unique` / `accepted_values` / `relationships` の 4 つは builtin で十分。`dbt-expectations` を入れる動機は「**builtin にないテスト**」 (連続範囲、正規表現、行数、distinct 数など)。**自作の generic test** (Ex.08) との使い分けも同じ思想。
- **CI の `dbt deps` キャッシュ**: GitHub Actions では `actions/cache@v3` で `dbt_packages/` を `packages.yml` のハッシュキーでキャッシュすると数秒節約できる。

## 実行例 (採点 shell_command 視点)

```bash
$ test -f dbt/packages.yml && echo OK
OK
$ grep -E 'calogica/dbt_expectations' dbt/packages.yml
  - package: calogica/dbt_expectations

$ cd dbt && dbt deps --profiles-dir . 2>&1 | tail -3
22:50:04    Up to date!

$ test -d dbt/dbt_packages/dbt_expectations && echo OK
OK

$ grep -E 'dbt_expectations\.expect_column_values_to_be_between' dbt/models/100-knock/topic-5/schema.yml
          - dbt_expectations.expect_column_values_to_be_between:

$ cd dbt && dbt test --select mart_top_rated_products_100knock --profiles-dir . 2>&1 | grep -E 'PASS=|ERROR='
Done. PASS=3 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=3
```

## 解説まとめ

- **なぜ `dbt-expectations` を入れる？**: builtin テストでは表現しづらい業務範囲制約 (連続区間 / 確率的閾値 / 行数 / 統計的特性) を **再発明せずに宣言** で書けるから。同じ目的のシングルテストを毎 mart で SQL を書き直すのは DRY 違反。
- **builtin / 自作 generic / dbt-expectations の選択軸**:
  - **builtin** (`not_null` 等 4 つ): 何も入れずに使える。最頻出
  - **自作 generic** (Ex.08): `tests/generic/` に SQL macro を置き、複数列で再利用。組織独自のルール (例: `positive_value`)
  - **dbt-expectations**: 50+ の汎用テストが揃っている。「既にあるなら使う」発想で時間節約
  - **singular test** (`tests/assert_*.sql`): 単発で複雑な SQL が必要なときの最終手段
- **「mart の契約は技術 + 値 + 運用 + 公開範囲の 4 重宣言」**:
  - **技術契約** = `contract: enforced` + `data_type:` (5-3) - 列名 + 型
  - **値契約** = `tests:` + `dbt-expectations` (本問) - 値の範囲・関係
  - **運用契約** = `meta:` (5-8) - SLA・connection
  - **公開範囲契約** = `groups:` + `access:` + `+grants:` (5-6, 5-7) - 誰が何をできるか
  - これら 4 つを `schema.yml` + `dbt_project.yml` だけで宣言完結できる。SQL 側は集計ロジックだけ書けばよい (= 関心の分離)。
- **CI で値契約が落ちると BI が止まらない**: `dbt build` で test FAIL → 下流 mart の build が SKIP → BI が古いデータを見続ける。これは「悪いデータを BI に流すよりはマシ」という設計。test を緩めたいなら `severity: warn` (Ex.10) で警告だけにする選択肢もある。
- **`dbt-expectations` のバージョン依存**: dbt 1.5 系には `dbt-expectations 0.9 / 0.10`、dbt 1.6+ なら 0.10+。本リポジトリの dbt 1.10 + `0.10.x` は安定組合せ。

## 拡張アイデア

- **`expect_table_row_count_to_be_between`**: mart 全体の行数を検査。「`mart_daily_sales_100knock` は 30〜400 行」など季節性を加味した範囲を宣言
- **`expect_column_pair_values_A_to_be_greater_than_B`**: 列間関係 (例: `last_order_date >= first_order_date`)
- **`expect_column_values_to_match_regex`**: `customer_email` のような文字列パターン検査
- **`severity: warn` と組合せ**: 範囲を超えても CI を止めずに警告だけにする運用 (= Ex.10 の延長)
- **複数 mart に横展開**: 5-1 / 5-2 / 5-3 全 mart の数値列に `expect_column_values_to_be_between` を貼り、業務範囲制約をまとめて schema.yml に集約
