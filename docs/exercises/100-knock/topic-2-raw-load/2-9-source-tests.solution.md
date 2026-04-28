# 2-9 解答例

## dbt/models/100-knock/topic-2/sources.yml (関連部分)

```yaml
version: 2

sources:
  - name: raw
    schema: raw
    description: "ELT raw layer (CSV inserted by load_2_1_raw.py)."
    tables:
      - name: customers
        description: "Customer master (1,000 rows)."
        columns:
          - name: customer_id
            description: "Customer primary key. Unique + not null at the raw layer."
            tests:
              - unique
              - not_null
          - name: customer_name
            description: "Display name."
            tests:
              - not_null
          - name: email
            description: "Contact email. Globally unique."
            tests:
              - unique
              - not_null
          - name: created_at
            description: "Customer registration date (DATE)."
      # ... (products / stores / orders は元のまま)
```

**ポイント**:

- **`customer_id` に `unique` + `not_null` の 2 つを書く**: これで dbt は実質的な PK 制約を 1 セットの test として走らせる。SQL の `PRIMARY KEY` 制約とは別物 (warehouse 側で物理 PK を強制するわけではない) だが、**契約として宣言・検証**できる。
- **`email` にも `not_null` + `unique` を追加 (推奨)**: Topic ① 1-1 で `Faker.unique.email()` で生成したことを test で再確認する形。ここで書いておくと、後で `Faker.email()` (重複あり) に書き換えた瞬間に CI が落ちて、設計の劣化が止まる。
- **short form vs long form**: `- not_null` は最短形。`- not_null: severity: warn` のように config を足したいなら long form (`- not_null:`) を使う。本問では short form で十分。

## 実行コマンド

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# Found N sources, ...

../.venv/bin/dbt test --profiles-dir . --select source:raw.customers
# 11:34:56  Running with dbt=1.8.x
# 11:34:56  Found 0 models, 4 tests, ...
# 11:34:56  
# 11:34:56  Concurrency: 4 threads (target='dev')
# 11:34:56  
# 11:34:56  1 of 4 START test source_not_null_raw_customers_customer_id   ... [RUN]
# 11:34:56  2 of 4 START test source_not_null_raw_customers_customer_name ... [RUN]
# 11:34:56  3 of 4 START test source_not_null_raw_customers_email         ... [RUN]
# 11:34:56  4 of 4 START test source_unique_raw_customers_customer_id     ... [RUN]
# 11:34:56  1 of 4 PASS  source_not_null_raw_customers_customer_id  ... [PASS in 0.05s]
# 11:34:56  ... (略)
# 11:34:56  Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

すべて PASS であれば、raw が「PK ユニーク + 必須列 NULL なし」の契約を満たしていることが宣言＆検証で確認できた。

## 想定アンチパターン

### ❌ tests を staging 側にだけ書く

```yaml
# stg_customers のみで unique/not_null を張る
models:
  - name: stg_customers
    columns:
      - name: customer_id
        tests: [unique, not_null]
```

これだと「staging を作る最中に test できる」が、「raw が壊れている → staging build に時間を使う → やっと test で気付く」という遅い検知になる。本問のように source 側にも張ることで、`dbt test --select source:*` だけで早期検知できる。

### ❌ `tests:` ブロックを `columns:` の外に書く

```yaml
- name: customers
  tests:               # ← table-level に書いている
    - not_null         # ← どの列に？という曖昧さ
  columns:
    - name: customer_id
```

table-level の `tests:` は `dbt_utils.equal_rowcount` のような **複数列にまたがる test** を書く場所。column-level test (unique / not_null) は `columns: - name: ... tests: [...]` の中に書くのが正解。

### ❌ short form を間違える

```yaml
columns:
  - name: customer_id
    tests:
      unique          # ← `-` がない (list ではなく string になる)
      not_null
```

YAML パーサが list として解釈できず、`dbt parse` が `Compilation Error` で落ちる。`-` を必ず付ける。

## 解説まとめ

- **source test の意義 (= contract on source)**: 「dbt が触れる最も上流」に test を張ることで、staging を作る前に raw の不整合を検知できる。これは "fail fast" の典型例。staging build は時間とコストがかかるので、その前に「raw が約束を守っているか」を 1 秒で確認できると CI 時間が短縮する。
- **dbt の test = "宣言された assertion"**: SQL で `assert count(distinct customer_id) = count(*)` を毎回書く代わりに、`tests: [unique]` 1 行で同じ assertion を **manifest 上に契約として登録**する。lineage 上で test ノードとして可視化されるので、「この raw に test が張られているか」を docs サイトで確認できる。
- **PK 制約との違い**: PostgreSQL の `PRIMARY KEY` は **物理的に強制** される (違反すれば INSERT が失敗)。dbt の `unique` + `not_null` test は **事後検証** (バッチ後に SQL で確認)。raw が外部から入ってくるパスでは「物理 PK 制約を貼れない・貼りたくない」ケースが多く (= 重複が来ても受け入れて検知だけする)、dbt test で受け止めるのが現実的。
- **後続トピックでの活かし方**: Topic ③ で staging を作るとき、`stg_customers` 側にも同じ `unique` / `not_null` を貼ることが多い。**source と staging の両方に張る** ことは冗長ではなく、「source が壊れているのか / staging の transformation で壊れたのか」を test の発火位置で切り分けられる利点がある (test の局所性)。
- **CI への組み込み**:
  ```bash
  dbt test --select source:* --profiles-dir .   # 1 秒〜数秒
  dbt build --profiles-dir .                    # 数分
  ```
  最初に source test だけ走らせる前段を仕込めば、raw が壊れている PR は数秒で fail させられる。これが production-grade dbt CI の作法。
