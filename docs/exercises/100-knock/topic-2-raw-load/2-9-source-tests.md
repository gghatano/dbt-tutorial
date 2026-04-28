# 2-9: `raw.customers` に `tests:` ブロック (`unique` / `not_null`) を source 側に直接書く

## シナリオ

dbt の `tests:` は staging 以下に書くものと思われがちだが、source 側にも書ける。「**raw のうち、絶対に守られているべき制約**」(PK の一意性、必須列の非 NULL) は staging より前に張っておくと、staging を作るより前に上流の不整合を検知できる。これが "contract on source" のミニマル形。

具体的には `dbt test --select source:raw.customers` を CI で `dbt build` の前に挟むことで、「raw が壊れていれば staging を作るまでもなく落ちる」運用にできる。本問では 2-2 で書いた `sources.yml` の `customer_id` 列に `tests: [unique, not_null]` を追加し、`dbt test` で PASS することを確認する。

(2-2 の sample yaml にも例として書かれているが、本問はそれを **明示的に学習者が書き直す** 演習として位置づける。すでに書いてあれば書かれていることを採点で確認する形になる。)

## 学べること

- source 側 column に `tests:` を直接書ける構文
- `unique` / `not_null` という generic test の意味と組み合わせ方 (= PK 制約)
- `dbt test --select source:raw.customers` で source の test だけ走らせる selector
- "contract on source" の発想: 「staging を作る前に raw の不整合を検知する」二段構えの test 戦略

## 前提

- 2-1 で raw に customers が COPY 済み (`raw.customers` テーブルに 1,000 行)
- 2-2 で `dbt/models/100-knock/topic-2/sources.yml` が `name: raw` で 4 テーブル宣言済み
- 2-1 の入力 CSV (`data/100-knock/topic-2/customers.csv`) で `customer_id` がユニーク + NULL なし (= test が PASS する前提のデータ)
- ローカル Postgres + raw schema が起動している

## 入力データ

不要 (本問は yaml の編集だけ)。

## 課題

### Step 1: sources.yml に test を追加

`dbt/models/100-knock/topic-2/sources.yml` の `customers` ブロックを編集。`customer_id` 列に `tests:` を **明示的に書く**:

```yaml
sources:
  - name: raw
    schema: raw
    tables:
      - name: customers
        columns:
          - name: customer_id
            description: "Customer primary key. Unique + not null at the raw layer."
            tests:
              - unique
              - not_null
          # ... (他の列)
```

要件:

- `customers` ブロックの `customer_id` に `tests:` ブロックがある
- `tests:` の中に `unique` と `not_null` の **両方** が書かれている
- 構文は YAML の正しい list of strings (または `- unique:` のような short form)

### Step 2: dbt test を走らせる

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test --profiles-dir . --select source:raw.customers
# 11:34:56  Running with dbt=1.8.x
# 11:34:56  2 of 2 START test source_unique_raw_customers_customer_id   ... [RUN]
# 11:34:56  2 of 2 PASS  source_unique_raw_customers_customer_id      ... [PASS in 0.05s]
# 11:34:56  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
```

`PASS=2` (unique + not_null) になることが期待値。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-9-source-tests.grading.yaml
```

## 完了条件

- [ ] `sources.yml` の `customers.customer_id` 列に `tests:` ブロックが存在する
- [ ] `tests:` の中に `unique` が含まれる
- [ ] `tests:` の中に `not_null` が含まれる
- [ ] `dbt test --select source:raw.customers` が `PASS >= 2` で終わる (ERROR=0)

## ヒント (詰まったら)

- **書き方の自由度**: `tests:` の中身は `- not_null` (short) でも `- not_null:` (long, config 付き可) でもどちらでも有効。本問では short form で十分。
- **CI で source test を先に走らせる流儀**:
  ```bash
  dbt test --select source:* --profiles-dir .   # まず raw 制約だけ確認
  dbt build --profiles-dir .                    # OK なら staging 以下を build
  ```
  この 2 段にすると「raw が壊れている時、staging を作る前に止まる」フェイルファスト構成になる。
- **test 名の規則**: dbt が自動で `source_unique_<source_name>_<table>_<column>` のような名前を付ける。`dbt test --select test_name:source_unique_raw_customers_customer_id` のようにピンポイント指定もできる (デバッグ時に便利)。
- **PASS しない場合のチェック**: `customer_id` に重複や NULL が混ざっていないか SQL で直接確認:
  ```sql
  SELECT customer_id, count(*) FROM raw.customers GROUP BY 1 HAVING count(*) > 1;
  SELECT count(*) FROM raw.customers WHERE customer_id IS NULL;
  ```
  上が 0 件、下が 0 になるはず。落ちる場合は 2-1 の loader を見直す。
- **column を増やしたい場合**: `email` にも `not_null` / `unique` を貼ると、Topic ① 1-1 で書いた「`Faker.unique.email()` で全行ユニーク」という設計と一致する。本問の採点対象は `customer_id` のみだが、追加で書いても減点はされない。

## 解答例

詳細は [`2-9-source-tests.solution.md`](2-9-source-tests.solution.md) を参照。
