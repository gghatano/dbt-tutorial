# 6-8: dbt-expectations を導入、expect_column_values_to_match_regex で email 形式チェック

## シナリオ

`stg_customers_100knock.email` は 6-1 / 3-4 で `not_null` + `unique` を貼って
「NULL でない一意な文字列」 までは契約済み。だが **「文字列の形式が email っぽいか」**
までは built-in test では宣言できない (built-in は集合 / 集計 / 参照系のみ)。

正規表現マッチを書きたいなら自作 generic test (Topic ⑥ 6-5 / 6-6 で学んだ) でも
できるが、**「メールっぽい / 電話番号っぽい / 郵便番号っぽい」** といった汎用
パターンは **車輪の再発明をせず外部 test ライブラリ** から借りるのが筋。

dbt 界の Great Expectations 移植版が `dbt-expectations`。`expect_column_values_to_match_regex`
だけでなく、`expect_column_values_to_be_between` / `expect_table_row_count_to_be_between` /
`expect_column_distinct_count_to_be_between` 等 50+ の宣言的 test が手に入る。
本問は **packages.yml に追加 → dbt deps → schema.yml で email に regex test** の
3 ステップで「外部 test ライブラリを契約宣言に取り込む」 体験をする。

## 学べること

- `packages.yml` で外部 dbt パッケージ (`calogica/dbt_expectations`) を宣言
- `dbt deps` でパッケージインストール (`dbt_packages/` 配下に展開)
- `dbt_expectations.expect_column_values_to_match_regex` の使い方
- なぜ「自作 generic vs パッケージ test」 を使い分けるのか
- `regex` 引数のメール形式パターン (簡易版で十分な理由)

## 前提

- Topic ② ③ ④ ⑤ + Topic ⑥ 6-1〜6-5 完了
- `dbt/packages.yml` が存在する (本リポジトリは `packages: []` で初期化済み)
- `stg_customers_100knock.email` が `text` 型で物理化済み (3-1 完了)

## 入力データ

`staging.stg_customers_100knock` (1,000 行)。`email` 列は Topic ① 1-1 で
`Faker.unique.email()` 生成 → `<word>.<word>@<domain>` 形式が保証されている。
本問の regex は **「@ を含む英数字 + 記号文字列」** 程度の **ゆるい** 正規表現で OK。

## 課題

### Step 1: packages.yml に dbt_expectations を追加

`dbt/packages.yml`:

```yaml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

> **注**: dbt_expectations は内部で `dbt_utils` に依存する。`dbt deps` が
> 自動で取得するため、`packages.yml` に `dbt_utils` を明示的に書く必要はない
> (ただし他 Exercise で `dbt_utils` を直接使っているなら明示宣言が安全)。

### Step 2: dbt deps でインストール

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

期待:

- `dbt_packages/dbt_expectations/` ができる
- (依存解決で) `dbt_packages/dbt_utils/` も同時にできる
- `package-lock.yml` が生成 / 更新される

### Step 3: schema.yml で regex test を宣言

`dbt/models/100-knock/topic-3/schema.yml` の `stg_customers_100knock.email` ブロック
に追加:

```yaml
  - name: stg_customers_100knock
    columns:
      # ... (既存の customer_id / customer_name 等)
      - name: email
        description: "Customer email (regex 検証付き)。"
        tests:
          - not_null
          - unique
          - dbt_expectations.expect_column_values_to_match_regex:
              arguments:
                regex: "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
```

> **regex の意味**: `<英数字記号>@<英数字>.<2 文字以上 TLD>` の最小構成。
> `\\.` は YAML 内で `\.` として解釈される (YAML エスケープ + regex エスケープ)。

### Step 4: 実行

```bash
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_customers_100knock
```

期待:

- `dbt_expectations_expect_column_values_to_match_regex_stg_customers_100knock_email_*` が PASS
- `Done. PASS=N WARN=0 ERROR=0` (Faker 生成のメールは regex を満たす)

### Step 5: わざと FAIL させる (任意)

```sql
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.customers SET email = 'not_an_email' WHERE customer_id = 1;"
```

`dbt test --select stg_customers_100knock` → regex test が **FAIL 1 件**。
戻す: `UPDATE raw.customers SET email = 'a@b.co' WHERE customer_id = 1;`
(または元の Faker 値に戻す)。

## 完了条件

- [ ] `dbt/packages.yml` に `calogica/dbt_expectations` が宣言されている
- [ ] `dbt deps` 後、`dbt/dbt_packages/dbt_expectations/` ディレクトリが存在
- [ ] schema.yml で `email` 列に
      `dbt_expectations.expect_column_values_to_match_regex` test が宣言されている
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select stg_customers_100knock` で regex test が PASS

## ヒント (詰まったら)

- **package 名は `<org>/<package>`**: hub.getdbt.com で公開されたパッケージは
  `calogica/dbt_expectations` のように `<owner>/<name>` 形式。GitHub URL 直指定
  (`git: https://github.com/...`) も可能だが、hub 経由がバージョン管理しやすい。
- **regex のエスケープ**: YAML 内で `"\\."` は SQL に渡る時 `\.` になる。
  ダブルクォート文字列内の `\\` が 1 つの `\` にデコードされるため。
  シングルクォート (`'^...$'`) なら `\.` をそのまま書ける (YAML 仕様)。
- **`row_condition` 引数**: NULL を「違反扱いしない」ようにしたい時は
  `row_condition: "email is not null"` を追加。今回は `not_null` で先に
  弾いているので NULL は来ない前提 → 不要。
- **自作 generic vs パッケージ test の判断軸**:
  - **車輪の再発明になりそう** → パッケージ (regex / 範囲 / 統計)
  - **業務固有のルール** (例: 「自社 product_id は 1〜99999」) → 自作 generic
  - **特定 mart 1 個限定の不変条件** → singular test
- **`dbt deps` を CI でも回すか**: 本リポジトリの grader CI は `dbt deps` を
  build ステップで回す前提。`dbt_packages/` は `.gitignore` 対象なので、
  CI で毎回ダウンロード → install される。ローカルで一度走らせれば確認可能。

## 解答例

詳細は [`6-8-dbt-expectations-regex.solution.md`](6-8-dbt-expectations-regex.solution.md) を参照。
