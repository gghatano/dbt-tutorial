# Exercise 10 解答例

## Step 1: --store-failures を体験

### `dbt/models/exercises/10/schema.yml` (初版)

```yaml
version: 2

models:
  - name: stg_reviews
    columns:
      - name: rating
        tests:
          - accepted_values:
              values: [1, 2, 3, 4, 5]
              quote: false
              config:
                store_failures: true
```

### 違反データを混ぜる

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.reviews SET rating = 7 WHERE review_id IN (1, 2, 3);
UPDATE raw.reviews SET rating = 0 WHERE review_id IN (4, 5);
SQL
```

### test 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 04:58:01  Running with dbt=1.11.8
# 04:58:02  Found 9 models, 4 sources, ... 1 data test
# 04:58:03  1 of 1 START test accepted_values_stg_reviews_rating__1__2__3__4__5 . [RUN]
# 04:58:03  1 of 1 FAIL 5 accepted_values_stg_reviews_rating__1__2__3__4__5 ... [FAIL 5 in 0.10s]
# 04:58:03
# 04:58:03  Failure in test accepted_values_stg_reviews_rating__1__2__3__4__5 (models/exercises/10/schema.yml)
# 04:58:03    Got 5 results, configured to fail if != 0
# 04:58:03    See test failures: select * from "analytics"."dbt_test__audit"."accepted_values_stg_reviews_rating__1__2__3__4__5"
```

dbt 自身が「失敗行の SELECT 文」を出してくれるのが `--store-failures` の最大の利点。

### 失敗テーブルを SELECT

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics
```

```sql
analytics=> \dn dbt_test__audit
       List of schemas
       Name       |  Owner
------------------+----------
 dbt_test__audit  | dbt_user

analytics=> \dt dbt_test__audit.*
                            List of relations
      Schema      |                          Name                           | Type  |  Owner
------------------+---------------------------------------------------------+-------+----------
 dbt_test__audit  | accepted_values_stg_reviews_rating__1__2__3__4__5       | table | dbt_user

analytics=> SELECT * FROM dbt_test__audit.accepted_values_stg_reviews_rating__1__2__3__4__5;
 value_field | n_records
-------------+-----------
           7 |         3
           0 |         2
(2 rows)
```

`accepted_values` test は集計形（値ごとの違反件数）で保存される。test の種類によっては「違反した行そのもの」が保存される（例: `unique` test なら重複した PK 行）。

### 修正と再 test

```sql
UPDATE raw.reviews SET rating = 5 WHERE review_id IN (1, 2, 3);
UPDATE raw.reviews SET rating = 1 WHERE review_id IN (4, 5);
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 1 of 1 PASS accepted_values_stg_reviews_rating__1__2__3__4__5 ... [PASS in 0.05s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1
```

PASS に戻ったあとは `dbt_test__audit` テーブルもクリアされる（dbt が `delete from` で空にする）。手動で drop するなら:

```sql
DROP TABLE dbt_test__audit.accepted_values_stg_reviews_rating__1__2__3__4__5;
```

## Step 2: dbt-expectations 導入

### `dbt/packages.yml`

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

```bash
../.venv/bin/dbt deps --profiles-dir .
# Installing dbt-labs/dbt_utils
#   Up to date!
# Installing calogica/dbt_expectations
#   Installed from version 0.10.x
```

`dbt_packages/dbt_expectations/macros/` 配下に大量の test macro が入る。

## Step 3: expect_column_values_to_be_between

### `dbt/models/exercises/10/schema.yml` (拡張版)

```yaml
version: 2

models:
  - name: stg_reviews
    columns:
      - name: rating
        tests:
          - accepted_values:
              values: [1, 2, 3, 4, 5]
              quote: false
              config:
                store_failures: true
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 1
              max_value: 5
              row_condition: "rating is not null"
              strictly: false
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 1 of 2 PASS accepted_values_stg_reviews_rating__1__2__3__4__5 ........ [PASS in 0.05s]
# 2 of 2 PASS dbt_expectations_expect_column_values_to_be_between_stg_reviews_rating__5__1 [PASS in 0.06s]
# Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2
```

## Step 4: severity: warn

```yaml
- accepted_values:
    values: [1, 2, 3, 4, 5]
    quote: false
    config:
      store_failures: true
      severity: warn
```

violation:

```sql
UPDATE raw.reviews SET rating = 99 WHERE review_id = 1;
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 1 of 2 WARN  1 accepted_values_stg_reviews_rating__1__2__3__4__5 ... [WARN 1 in 0.05s]
# 2 of 2 FAIL 1 dbt_expectations_expect_column_values_to_be_between_stg_reviews_rating__5__1 ... [FAIL 1 in 0.06s]
# Done. PASS=0 WARN=1 ERROR=1 SKIP=0 NO-OP=0 TOTAL=2
```

`accepted_values` は WARN で許容、`expect_column_values_to_be_between` は default の ERROR で落ちる。両方 WARN にするなら同じく `config: severity: warn` を追加。

`severity: warn` を付けた test が複数あり、しきい値で WARN→ERROR を切り替えたい場合:

```yaml
- accepted_values:
    values: [1, 2, 3, 4, 5]
    quote: false
    config:
      severity: warn
      warn_if: '>0'
      error_if: '>10'
```

「1 件以上で WARN、10 件超えたら ERROR」 のような段階制御。

戻す:

```sql
UPDATE raw.reviews SET rating = 5 WHERE review_id = 1;
```

## Step 5: ロールバック

```bash
# packages.yml から dbt_expectations 行を削除
# (Edit で行削除)
../.venv/bin/dbt deps --profiles-dir .   # dbt_packages/dbt_expectations が消える

# exercises 10 を片付け
rm -rf dbt/models/exercises/10/

# 失敗行 schema を drop
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "DROP SCHEMA IF EXISTS dbt_test__audit CASCADE;"

# Step 4 で混入させた WARN 用の rating=99 を念のため戻す
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.reviews SET rating = 5 WHERE review_id = 1;"
```

## 解説まとめ

- **`--store-failures` の本質**: テスト失敗時に「何件失敗したか」だけでは何もできない。「どの行か」を即座に SELECT できる状態を作るのが本フラグの価値。CI 環境では `--store-failures` を常時 ON にして失敗行 schema を Slack に投げる、などの運用が可能。
- **schema 名 `dbt_test__audit`**: dbt-postgres のデフォルト。本リポジトリは `get_custom_schema.sql` で prefix を打ち消しているのでそのまま `dbt_test__audit` になる。custom macro が無い環境では `<target_schema>_dbt_test__audit` のように prefix が付く。
- **`dbt-expectations` の長所**: Great Expectations のメンタルモデルで「期待する振る舞い」を宣言的に書ける。`accepted_values` だけでは表現できない範囲 / 分布 / 文字列パターン / 行数チェックなどが揃っている。
- **`severity: warn` の使い所**: 「データ品質の劣化を検知したいが、ビルドは止めたくない」シナリオ。例: 「商品評価平均が 3.0 を切ったら WARN（ビジネスシグナル）」「raw 行数が前日比 50% 減ったら WARN（取り込み異常の可能性）」など。

## 拡張アイデア

- `dbt-expectations` の `expect_column_distinct_count_to_be_between` で「カテゴリ数が想定範囲内か」をチェック（カテゴリマスタが膨張 / 縮小していないか）
- `expect_table_row_count_to_be_between` で「raw テーブル行数の急変」を検知
- `expect_column_pair_values_a_to_be_greater_than_b` で「order_date >= created_at」のようなクロス列条件を検証
- 失敗行 table を Metabase に取り込み、データ品質ダッシュボードを作る
