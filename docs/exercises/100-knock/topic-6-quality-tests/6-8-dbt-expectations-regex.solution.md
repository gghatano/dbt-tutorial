# 6-8 解答例

## dbt/packages.yml

```yaml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

**ポイント**:

- **`version: [">=0.10.0", "<0.11.0"]`**: Semantic Versioning の **0.10.x の最新**
  を許す範囲指定。0.11.x が出た時に破壊的変更が混じる可能性があるので
  境界を明示。pin (`version: 0.10.5`) より柔軟、`*` より安全 — の中庸。
- **`dbt_utils` を明示しない選択**: dbt_expectations は `dbt_utils >= 1.1.1` に
  依存しているが、`dbt deps` が依存解決して自動で入れてくれる。本問では
  `dbt_utils` を直接呼ばないので、`packages.yml` には書かない (依存の **間接性**
  を活かす)。直接呼ぶ exercise (Topic ⑧ 8-2 など) では明示宣言する設計。
- **MVP の `packages: []` を上書き**: MVP は外部依存ゼロで動く前提なので
  `[]`。本問で初めて外部 package を入れる体験になる。

## dbt deps の実行ログ

```bash
$ ../.venv/bin/dbt deps --profiles-dir .
04:00:00  Running with dbt=1.11.x
04:00:01  Installing calogica/dbt_expectations
04:00:02    Installed from version 0.10.5
04:00:02    Up to date!
04:00:02  Installing dbt-labs/dbt_utils
04:00:03    Installed from version 1.3.0
04:00:03    Up to date!
04:00:03  Updates available for packages: ['dbt-labs/dbt_utils', 'calogica/dbt_expectations']
04:00:03  Update your versions in packages.yml, then run dbt deps
```

`dbt_packages/` 配下:

```text
dbt/
  dbt_packages/
    dbt_expectations/   # 本問で追加
    dbt_utils/          # 自動依存解決
  package-lock.yml      # 解決後の正確なバージョンを lock
```

## dbt/models/100-knock/topic-3/schema.yml (stg_customers_100knock 部分)

```yaml
version: 2

models:
  # ... (他 model はそのまま)

  - name: stg_customers_100knock
    description: "Type-cast staging view of raw.customers (100-knock topic-3)。"
    columns:
      - name: customer_id
        description: "Primary key (bigint)。"
        tests:
          - not_null
          - unique
      - name: customer_name
        description: "顧客名 (Faker ja_JP)。"
      - name: email
        description: |
          顧客メール (raw 1-1 で unique 保証)。
          dbt_expectations.expect_column_values_to_match_regex で
          "<local>@<domain>.<tld>" の最小構成を満たすことも宣言。
        tests:
          - not_null
          - unique
          - dbt_expectations.expect_column_values_to_match_regex:
              arguments:
                regex: "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
      - name: created_at
        description: "登録日 (date)。"
        tests:
          - not_null
```

**ポイント**:

- **`dbt_expectations.expect_column_values_to_match_regex`**: パッケージ名 + 関数名
  の **dotted 命名**。built-in test (`not_null`) は package prefix なしで呼べるが、
  外部 package の test は **必ず prefix 付き**。
- **`arguments: regex: ...`**: dbt 1.8+ の推奨構文。旧 flat 記法
  (`expect_column_values_to_match_regex: {regex: ...}`) も動くが、新規プロジェクトは
  `arguments:` 統一。
- **regex の内訳**:
  - `^[A-Za-z0-9._%+-]+` — local part: 英数字 + `._%+-` を 1 文字以上
  - `@` — 区切り文字
  - `[A-Za-z0-9.-]+` — domain: 英数字 + `.-` を 1 文字以上
  - `\\.` — ドット (YAML エスケープで `\.` に → SQL 内で正規表現の `.` を
    リテラルマッチ)
  - `[A-Za-z]{2,}$` — TLD: 英字 2 文字以上
- **「ゆるい regex」 で十分な理由**: RFC 5322 完全対応の regex は数百文字に
  なり、可読性ゼロ。実用では `<x>@<y>.<z>` の最小構成チェックで十分。
  完全対応が必要なら `email-validator` 系のライブラリを使うべきで、
  正規表現 1 行では本来書けない (= **YAGNI**)。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found N models, 5 sources, M data tests, K macros ...

$ ../.venv/bin/dbt test --profiles-dir . --select stg_customers_100knock
04:00:00  ... 
04:00:01  N of M PASS not_null_stg_customers_100knock_email .................. [PASS]
04:00:01  N of M PASS unique_stg_customers_100knock_email ................... [PASS]
04:00:02  N of M PASS dbt_expectations_expect_column_values_to_match_regex_stg_customers_100knock_email__... [PASS in 0.20s]
04:00:02  Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

3 つの test (built-in 2 + dbt_expectations 1) がすべて PASS する。

## わざと FAIL させて regex の効き目を確認

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.customers SET email = 'not_an_email_format' WHERE customer_id = 1;"
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_customers_100knock
... 
N of M FAIL 1 dbt_expectations_expect_column_values_to_match_regex_stg_customers_100knock_email__... [FAIL 1]
... 
Done. PASS=N WARN=0 ERROR=1 SKIP=0 TOTAL=N+1
```

戻す:

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.customers SET email = 'restored@example.com' WHERE customer_id = 1;"
```

## 解説まとめ

- **なぜ外部 package か (= 車輪の再発明回避)**:
  - regex / 範囲 / 統計 / 分布 系の test は、業務に依存しない **汎用パターン**。
    dbt-expectations の 50+ test を 1 行で借りられるなら、自作する理由がない。
  - 業務固有の不変条件 (例: 「自社オーダー ID は B で始まる」) こそ自作 generic で
    書く。**汎用 = パッケージ、固有 = 自作** の境界を意識する。
- **dbt-expectations の主要 test**:
  - `expect_column_values_to_match_regex` — 正規表現マッチ (本問で使用)
  - `expect_column_values_to_be_between` — 数値範囲
  - `expect_column_distinct_count_to_equal` — distinct 件数固定
  - `expect_table_row_count_to_be_between` — 行数範囲 (= 件数監視)
  - `expect_column_values_to_be_in_set` — 集合チェック (built-in `accepted_values` の上位互換)
  - `expect_column_pair_values_A_to_be_greater_than_B` — 列間関係 (例: end_date > start_date)
- **`packages.yml` と `package-lock.yml` の関係**:
  - `packages.yml` = 「依存範囲」 の宣言 (`>=0.10.0, <0.11.0`)
  - `package-lock.yml` = `dbt deps` 時に解決した **正確なバージョン** (例: 0.10.5)
  - lock を git commit すると、CI で再現性が保証される (`dbt deps` が同じ
    バージョンを取得)。Topic ⑧ 8-10 で深堀り予定。
- **`dbt_test__audit` schema との関係 (6-9 への布石)**:
  6-9 で `store_failures: true` を追加すると、この regex test の違反行も
  `dbt_test__audit.<test_name>` に保存できる。「regex に通らなかった email
  のリストを SQL で見る」 デバッグループが回せる。
- **Topic ⑧ との並行性**: 8-3 (dbt-expectations 多重依存) と本問は同じ package を
  扱うが、軸が違う:
  - **6-8 (本問)**: 「外部 test ライブラリで契約宣言を増やす」 = データ品質視点
  - **8-3**: 「複数 package 共存の依存解決」 = 開発依存視点
  - 同じ機能を **2 つの軸** から学ぶことで、メンタルモデルが立体化する。
- **regex に頼りすぎない設計**:
  - regex は「形式」 を見る test。「実在するメールか」 「到達可能か」 までは
    test できない (それは別系統の検証 = 外部 API 呼び出し / verification 系)。
  - test は **そのレイヤで言える契約** に集中する。staging で言えるのは
    「形式が崩れていない」 まで、 「実在性」 は別レイヤ (= 単一責任原則)。
