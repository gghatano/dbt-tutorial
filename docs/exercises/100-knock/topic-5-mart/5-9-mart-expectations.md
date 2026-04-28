# 5-9: mart に `dbt-expectations.expect_column_values_to_be_between` で業務範囲テストを宣言

## シナリオ

5-3 で `contract: enforced` を付けたことで `mart_daily_sales_100knock` の **列名 + 型** は守られている。だが「`avg_rating` は 1〜5 の範囲」「`total_sales_amount` は 0 以上」のような **値の業務範囲** は contract では表現できない。

dbt 組み込みの `accepted_values` (= 離散集合) では `[1,2,3,4,5]` までは書けるが、numeric の連続区間 (`avg_rating between 1.0 and 5.0`) は書けない。手で singular test (`tests/assert_*.sql`) を書く手もあるが、似たテストを毎 mart で再発明することになる。

外部パッケージ **`dbt-expectations`** (Calogica 製、Great Expectations 由来) は `expect_column_values_to_be_between` / `expect_column_values_to_match_regex` / `expect_table_row_count_to_be_between` など 50+ の宣言的テストを提供する。`packages.yml` に 1 行足し `dbt deps` で導入完了。

このエクササイズでは:

1. `dbt/packages.yml` に `dbt-expectations` を追加
2. `mart_top_rated_products_100knock.avg_rating` に `expect_column_values_to_be_between(min=1, max=5)` を貼る
3. `dbt build` でこのテストが PASS することを確認

## 学べること

- `packages.yml` の管理 (`dbt-utils` / `dbt-expectations` を並べる典型構成)
- `dbt deps` で hub からインストール
- `dbt_expectations.expect_column_values_to_be_between` の基本 args (`min_value` / `max_value` / `row_condition` / `strictly`)
- 「contract = 型の契約」「expectations = 値の契約」の分離
- 業務ルールを CI で機械的に止める (= データ品質ガード)

## 前提

- Topic ② ③ ④ + Topic ⑤ 5-1 完了 (`mart_top_rated_products_100knock` が `avg_rating` 列を持つ)
- インターネット越しに `hub.getdbt.com` から package を取得できる (CI / ローカルとも)
- `dbt deps` が成功する (空 packages の状態でも問題なし)

## 入力データ

不要。既存 mart に対してテストを足すだけ。

## 課題

### Step 1: `packages.yml` に `dbt-expectations` を追加

`dbt/packages.yml`:

```yaml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

(既に `dbt-utils` を入れている場合はその下に並べる)

### Step 2: `dbt deps` で取得

```bash
cd dbt
dbt deps --profiles-dir .
# Installing calogica/dbt_expectations
#   Installed from version 0.10.x
```

`dbt_packages/dbt_expectations/` ディレクトリが作られる (gitignore 推奨)。

### Step 3: `schema.yml` にテストを追加

`dbt/models/100-knock/topic-5/schema.yml` の `mart_top_rated_products_100knock.avg_rating` 列にテストを足す:

```yaml
columns:
  - name: avg_rating
    description: "平均レビュー評点。1〜5 の範囲 (5-9 で expect_column_values_to_be_between で保証)"
    tests:
      - not_null
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: 1
          max_value: 5
          row_condition: "avg_rating is not null"
          strictly: false
```

### Step 4: `dbt build` でテスト実行

```bash
dbt build --select mart_top_rated_products_100knock --profiles-dir .
```

ログに以下のような行が出るはず:

```
... PASS dbt_expectations_expect_column_values_to_be_between_mart_top_rated_products_100knock_avg_rating__... [PASS in 0.30s]
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-9-mart-expectations.grading.yaml
```

## 完了条件

- [ ] `dbt/packages.yml` に `calogica/dbt_expectations` 行がある
- [ ] `dbt deps` で `dbt_packages/dbt_expectations/` が展開されている
- [ ] `schema.yml` の `mart_top_rated_products_100knock.avg_rating` に `dbt_expectations.expect_column_values_to_be_between` テストがある
- [ ] `dbt test --select mart_top_rated_products_100knock` で expectations テストが PASS する

## ヒント (詰まったら)

- **`dbt deps` 失敗**: hub.getdbt.com への接続不可、または version 制約衝突。`packages.yml` の version 範囲を緩めて再試行。本リポジトリで `dbt-utils` も入れているなら `dbt-expectations` の依存 (= dbt-utils) は自動解決される。
- **テスト名が長い**: `dbt_expectations_expect_column_values_to_be_between_mart_..._avg_rating__1__5__avg_rating_is_not_null` のように長くなる。`schema.yml` で `name: rating_in_1_to_5_100knock` と明示するのがおすすめ。
- **`row_condition`**: `avg_rating is not null` を入れないと NULL が違反扱いになる。`not_null` 別途検査するなら NULL を弾く前提で `expect_*` を書く方がデバッグしやすい。
- **`strictly: false`**: `false` で境界値を含む (=`1 <= x <= 5`)。`true` だと `1 < x < 5`。
- **`accepted_values` との使い分け**: 離散集合 = `accepted_values`、連続区間 = `expect_column_values_to_be_between`。`avg_rating` は連続値なので後者。`payment_method` のような enum は前者。
- **CI で数秒遅くなる**: `dbt deps` のフェーズが追加される。GitHub Actions ではキャッシュ (`actions/cache@v3` で `dbt_packages/`) で対策できる。
- **`dbt-expectations` の他テスト**: `expect_table_row_count_to_be_between` (mart 全体の行数範囲)、`expect_column_distinct_count_to_be_in_set` (distinct 数)、`expect_column_pair_values_A_to_be_greater_than_B` (列間関係) などがある。本問は最も基本的な `_be_between` 1 つ。
- **gitignore に `dbt_packages/`**: 普通は管理しない (毎 CI で `dbt deps` で再取得)。リポジトリの `.gitignore` に既に入っている想定。

## 解答例

詳細は [`5-9-mart-expectations.solution.md`](5-9-mart-expectations.solution.md) を参照。
