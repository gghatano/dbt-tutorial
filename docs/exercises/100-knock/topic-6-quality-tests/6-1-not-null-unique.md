# 6-1: stg_orders_100knock.order_id に not_null + unique を schema.yml で宣言

## シナリオ

Topic ③ で `stg_orders_100knock` を物理化するときに、3-4 の段階で
`order_id` に **`not_null` + `unique`** を貼っているはず。
本問はその **「主キー契約 (identity 制約) を YAML に書く」** 行為を
Topic ⑥ の入口として明示的に再確認する。

「PK は重複しない」「PK は NULL でない」は SQL 上の `PRIMARY KEY` 制約に
相当する不変条件だが、dbt staging は view (DDL に PK 制約を書けない)
で物理化されることが多く、**RDB の DDL に頼らず YAML に契約を残す** のが
dbt 流。`schema.yml` の `tests:` 配下に `not_null` と `unique` を 1 行ずつ
書いた瞬間、その列は manifest 上で「PK である」と宣言された扱いになる。

## 学べること

- なぜ `not_null` だけ / `unique` だけでは PK 契約として不十分なのか (二段構えの理由)
- `schema.yml` の column-level test の書き方 (`tests:` 配下にリスト)
- `dbt test --select stg_orders_100knock` の使い方 (model 単位での実行)
- `manifest.json` 上での test node の命名規則
  (`test.local_analytics.not_null_<model>_<col>`)
- なぜ test を model と同じ schema.yml に **コロケート** (近接配置) するのか

## 前提

- Topic ② ③ ④ ⑤ 完了 — `dbt/models/100-knock/topic-3/schema.yml` が存在し、
  `stg_orders_100knock` が物理化済み
- 3-4 を解いていれば、本問はほぼ「既に書いてある宣言を確認する」だけになる

## 入力データ

`staging.stg_orders_100knock` (10,000 行) — Topic ③ 3-3 で物理化済み。
`order_id` は 1..10000 の bigint で、Topic ① 1-4 の生成スクリプトにより
PK 性が保証されている。

## 課題

### Step 1: schema.yml に `not_null` + `unique` を宣言

`dbt/models/100-knock/topic-3/schema.yml` を開き、`stg_orders_100knock` の
`order_id` 列に **2 件の test** が並んでいることを確認 (or 追記):

```yaml
  - name: stg_orders_100knock
    columns:
      - name: order_id
        description: "Primary key (bigint)。主キー契約: not_null + unique。"
        tests:
          - not_null
          - unique
```

3-4 で既に書いている場合は **新規追記不要**。本問の採点は「書かれていること」
を確認する。

### Step 2: parse + test 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_orders_100knock
```

期待出力:

- `not_null_stg_orders_100knock_order_id` が PASS
- `unique_stg_orders_100knock_order_id` が PASS
- `Done. PASS>=2 ...`

### Step 3: manifest 上で test node を確認

```bash
../.venv/bin/dbt parse --profiles-dir .
python3 -c "
import json
m = json.load(open('target/manifest.json'))
tests = [k for k in m['nodes'] if 'order_id' in k and 'stg_orders_100knock' in k]
print('\n'.join(tests))
"
```

`test.local_analytics.not_null_stg_orders_100knock_order_id` と
`test.local_analytics.unique_stg_orders_100knock_order_id` の **2 行**
が出れば成功。

## 完了条件

- [ ] `schema.yml` に `stg_orders_100knock.order_id.tests: [not_null, unique]` がある
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select stg_orders_100knock` で `not_null` / `unique` が PASS
- [ ] manifest に `test.local_analytics.not_null_stg_orders_100knock_order_id` 登録
- [ ] manifest に `test.local_analytics.unique_stg_orders_100knock_order_id` 登録

## ヒント (詰まったら)

- **`not_null` だけだと NULL は弾けるが重複は素通し**。`(1, 1, 2, 3)` のような
  PK 列は `not_null` を PASS してしまう。
- **`unique` だけだと NULL が複数行入る**。Postgres の `UNIQUE` 制約は
  NULL 複数許容なので、`(NULL, NULL, 1, 2)` を素通しする。**両方セット** が
  staging の作法。
- **`tests:` vs `data_tests:`**: dbt 1.8+ で `data_tests:` が推奨だが、
  本リポジトリの dbt-core 1.11 では `tests:` も後方互換で動く。どちらでも採点 OK。
- **コロケート (近接配置) の意味**: 同じ schema.yml に model 定義と test 宣言が
  並ぶことで、レビューアは 1 ファイルで「列の意味と契約」を読める。
  test を別ファイルに置くと「この列の不変条件は何だったか」 を 2 箇所追う羽目に。
- **manifest node 命名規則**: `test.<project>.<test_type>_<model>_<column>`
  の自動命名。`name:` で明示すれば上書き可能 (本問では使わない)。

## 解答例

詳細は [`6-1-not-null-unique.solution.md`](6-1-not-null-unique.solution.md) を参照。
