# Exercise 10: 失敗行を追跡する (--store-failures + dbt-expectations)

## シナリオ

`dbt test` が FAIL した時、ログには「`Got 17 results, configured to fail if != 0`」のような件数しか出ない。**どの 17 行が違反しているか** を知るには `target/run/<schema>/<test>.sql` を `cat` して psql で流し直す、という二度手間が必要。

dbt の `--store-failures` フラグを付けると、テストが返した違反行を **Postgres のテーブルに残す** ことができる。デバッグ時に「失敗行を SELECT して見る」 → 「データを修正」 → 「再 test」 のループが速くなる。

加えて、より高度な test ライブラリ **`dbt-expectations`** を入れると、Great Expectations 風の宣言的アサーション（`expect_column_values_to_be_between` など 50+）が使える。Exercise 08 の自作 generic test を全部捨てて、dbt-expectations の builtin を使う、という選択もとれる。

## 学べること

- `dbt test --store-failures` の挙動と保存先 schema
- 失敗行テーブルを psql で SELECT してデバッグ
- `dbt-expectations` パッケージの導入と主要 test
- `severity: warn` で「FAIL させずに警告だけ」運用
- テスト失敗 → データ修正 → 再 test のループ

## 前提

- main HEAD 完了状態
- Exercise 01 完了（`raw.reviews` がある — `rating` 1〜5 の検査対象として使う）
- Exercise 07 完了（`packages.yml` 編集に慣れている）

> Exercise 01 が未完了の場合、検査対象を `raw.orders` の `quantity` などに置き換えても本演習の主旨は変わらない。

## 入力データ

不要。既存の `raw.reviews`（または `raw.orders`）に対して人為的に違反データを混ぜて検証する。

## 課題

### Step 1: `--store-failures` を体験

#### 1-1. わざと壊れる test を仕込む

`dbt/models/exercises/10/schema.yml`:

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

> `store_failures: true` を test ごとに有効化することで、CLI から `--store-failures` を渡さなくても保存される。CLI フラグでも可。

#### 1-2. 違反データを混ぜる

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.reviews SET rating = 7 WHERE review_id IN (1, 2, 3);
UPDATE raw.reviews SET rating = 0 WHERE review_id IN (4, 5);
SQL
```

`stg_reviews` を再 build（view なら何もしなくても次の test で最新値を見る）。

#### 1-3. test を実行 → 失敗テーブル確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# ... FAIL 5 accepted_values_stg_reviews_rating__1__2__3__4__5 ... [FAIL 5 in 0.10s]
```

失敗行は `dbt_test__audit` schema 配下の table に保存される（dbt-postgres デフォルト）:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics
```

```sql
\dn dbt_test__audit
\dt dbt_test__audit.*
SELECT * FROM dbt_test__audit.accepted_values_stg_reviews_rating__1__2__3__4__5;
-- 5 行（rating=7 が 3 件、rating=0 が 2 件）が見える
```

#### 1-4. 修正して再 test

```sql
UPDATE raw.reviews SET rating = 5 WHERE review_id IN (1, 2, 3);
UPDATE raw.reviews SET rating = 1 WHERE review_id IN (4, 5);
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# Done. PASS=N WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=N
```

PASS に戻る。失敗行 table はそのまま残る（次回 FAIL すると上書きされる）。手で `DROP TABLE dbt_test__audit.*` してもよい。

### Step 2: `dbt-expectations` を導入

`dbt/packages.yml` に追記（Exercise 07 で `dbt-utils` を入れている前提）:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

```bash
../.venv/bin/dbt deps --profiles-dir .
# Installing calogica/dbt_expectations
#   Installed from version 0.10.x
```

### Step 3: `dbt_expectations.expect_column_values_to_be_between` を試す

`dbt/models/exercises/10/schema.yml` に追記:

```yaml
  - name: stg_reviews
    columns:
      - name: rating
        tests:
          - accepted_values:    # Step 1 の test を残す
              values: [1, 2, 3, 4, 5]
              quote: false
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 1
              max_value: 5
              row_condition: "rating is not null"
              strictly: false
```

両方の test が同じ条件を異なる方法で表現している（`accepted_values` は離散集合、`expect_column_values_to_be_between` は連続範囲）。

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# 2 つの test が PASS することを確認
```

### Step 4: `severity: warn` で警告に格下げ

`accepted_values` test 部分を:

```yaml
- accepted_values:
    values: [1, 2, 3, 4, 5]
    quote: false
    config:
      severity: warn
```

violation を発生させる:

```sql
UPDATE raw.reviews SET rating = 99 WHERE review_id = 1;
```

```bash
../.venv/bin/dbt test --profiles-dir . --select stg_reviews
# WARN  1 accepted_values_stg_reviews_rating__1__2__3__4__5 ... [WARN 1 in ...]
# Done. PASS=N WARN=1 ERROR=0 SKIP=0 NO-OP=0 TOTAL=N+1
```

exit code は 0（CI 上で fail にはならない）。`warn_if` / `error_if` で「N 件以上で WARN、M 件以上で ERROR」のような閾値も設定可能（dbt 公式: [Configuring tests](https://docs.getdbt.com/reference/resource-properties/data-tests)）。

戻す:

```sql
UPDATE raw.reviews SET rating = 5 WHERE review_id = 1;
```

### Step 5: ロールバック

```bash
# packages.yml から dbt_expectations 行を削除（dbt-utils は Exercise 07 のため残す）
# Edit で削除 → dbt deps で reinstall
../.venv/bin/dbt deps --profiles-dir .

# exercises 10 ディレクトリ片付け
rm -rf dbt/models/exercises/10/

# 失敗行テーブルを drop
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "DROP SCHEMA IF EXISTS dbt_test__audit CASCADE;"
```

## 完了条件

- [ ] `dbt test --store-failures` で `dbt_test__audit.<test_name>` テーブルが作られる
- [ ] 失敗行を SELECT して内容（`rating=7` など）が見える
- [ ] データ修正後 `dbt test` で全 PASS に戻る
- [ ] `dbt-expectations` がインストールされ、`expect_column_values_to_be_between` test が PASS
- [ ] `severity: warn` を付けた test が WARN を出すが exit 0

## ヒント（詰まったら）

- **`dbt_test__audit` schema が作られない**: dbt-postgres は `--store-failures` を `<target.schema>_dbt_test__audit` schema に作る場合がある。本リポジトリは `get_custom_schema.sql` で prefix を打ち消しているので `dbt_test__audit` が直接できる。`\dn` で schema 一覧を確認。
- **失敗テーブルの命名**: `<test_name>` がそのまま table 名になる。長い test 名（`accepted_values_stg_reviews_rating__1__2__3__4__5`）を避けたい場合は schema.yml で `name:` を明示:
  ```yaml
  - accepted_values:
      name: rating_in_1_to_5
      values: [1, 2, 3, 4, 5]
  ```
- **store_failures をデフォルト ON にしたい**: `dbt_project.yml` の `tests:` または `data_tests:` セクションで一括指定:
  ```yaml
  data_tests:
    +store_failures: true
  ```
  ただし全 test の失敗行を残すとストレージを食うので、本番では選択的に有効化する。
- **`dbt-expectations` の探し方**: hub.getdbt.com → calogica/dbt_expectations → README に主要 test 一覧。`expect_column_values_to_match_regex` / `expect_table_row_count_to_be_between` / `expect_column_distinct_count_to_equal` あたりが使い所多い。
- **`row_condition`**: `expect_column_values_to_be_between` は NULL を「違反扱い」にする。NULL を除外したいなら `row_condition: "rating is not null"` を渡す。
- **`severity: warn` と `error_if`**: WARN は `severity: warn` で常時警告。「N 件超えたら ERROR」が欲しい場合は `error_if: '>10'` のように書く。dbt がテスト結果の行数を元に判定。

## 解答例

詳細は [`solutions/10-store-failures-and-expectations.solution.md`](solutions/10-store-failures-and-expectations.solution.md) を参照。
