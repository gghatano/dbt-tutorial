# 3-1: stg_customers を view materialization で書く

## シナリオ

Topic ② で `raw_100knock.customers` という source を宣言した。これで dbt 上の
論理 source は揃ったが、まだ raw 層のままなので、列の型は CSV ロード時の
DDL に依存している。アナリストや BI が下流で安心して使えるよう、ここで初めて
**staging contract** — 「列名は snake_case、型は明示 cast、materialization は view」 —
を model として宣言する。

これが「dbt の staging とは何か」のもっとも基本形であり、Topic ③ 全 10 問の
土台になる回。

## 学べること

- `source('raw_100knock', 'customers')` から SELECT する staging 1 本目
- 全列に **明示型 cast** を書く意味 (raw の型変更に対する盾になる)
- materialization を **view** にする理由 (storage 0 / refresh 不要 / 常に最新)
- MVP の `stg_customers` と衝突回避のための命名規約 (`stg_<table>_100knock`)
- `dbt parse` で構文を最初に通す → `dbt run` で物理化 → `dbt test` で契約検証

## 前提

- Topic ② 2-1〜2-5 完了: `dbt/models/100-knock/topic-2/sources.yml` で
  `name: raw_100knock` の source が宣言済み。`source('raw_100knock', 'customers')`
  が解決できる状態
- `raw.customers` テーブルに 1,000 行が COPY 済み (Topic ② 2-1 で投入)
- main HEAD の MVP が動く (`dbt run` / `dbt test` 緑)

## 入力データ

`raw.customers` (Topic ② で投入済み):

| 列              | 型      | 備考                |
|-----------------|---------|---------------------|
| `customer_id`   | bigint  | PK 1..1000          |
| `customer_name` | text    | 日本語名            |
| `email`         | text    | unique              |
| `created_at`    | text    | ISO 8601 (`YYYY-MM-DD`) |

## 課題

### Step 1: staging model を作る

`dbt/models/100-knock/topic-3/stg_customers.sql` を新規作成。

要件:

- 上部に `{{ config(materialized='view', schema='staging') }}` を明示
- `source('raw_100knock', 'customers')` から SELECT
- **全列に明示型 cast** を書く (`::bigint` / `::text` / `::date` など)
- 列名は raw と同じ snake_case のまま (この問では rename 不要)
- model 名は学習者ファイルとしては `stg_customers.sql` だが、dbt の node 名は
  ディレクトリで衝突しないよう **`stg_customers_100knock`** という名前にする
  (理由: MVP `dbt/models/staging/stg_customers.sql` と衝突回避)

> **命名の入れ方**: SQL ファイル先頭に `{{ config(alias='stg_customers_100knock') }}`
> と書くか、ファイル名そのものを `stg_customers_100knock.sql` にする。
> 後者の方が dbt の node 名 (`model.local_analytics.stg_customers_100knock`) が
> 自然に揃うのでおすすめ。

### Step 2: schema.yml に最低限のテストを書く

`dbt/models/100-knock/topic-3/schema.yml` (新規) に `stg_customers_100knock` の
column-level test を 1〜2 件書く (詳細は 3-4 で本格化するので最小限でよい):

```yaml
version: 2

models:
  - name: stg_customers_100knock
    description: "Type-cast view of raw.customers (100-knock topic-3)."
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select stg_customers_100knock
../.venv/bin/dbt test --profiles-dir . --select stg_customers_100knock
```

`PASS=1` (run) と `PASS=2` (test: not_null + unique) になれば成功。

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/stg_customers_100knock.sql` が存在する
- [ ] `dbt parse` が成功する
- [ ] manifest に `model.local_analytics.stg_customers_100knock` が登録される
- [ ] `dbt run --select stg_customers_100knock` が PASS
- [ ] `dbt test --select stg_customers_100knock` が PASS

## ヒント (詰まったら)

- **source が解決できない**: Topic ② 2-2 で宣言した source 名を確認。
  `name: raw_100knock` 配下の `tables: - name: customers` を `dbt ls --select source:raw_100knock.customers` で見つけられるはず。
- **node 名が `stg_customers` のまま**: ファイル名と alias の両方を見直す。
  `dbt ls --select stg_customers*` で MVP 側と新規側の 2 ノードが見えるか確認。
- **`::date` cast でエラー**: `raw.customers.created_at` は text 列 (CSV から COPY)。
  `'2025-04-13'::date` は OK だが、空文字列 `''::date` は失敗するので raw に NULL を許す列がないか確認。
- **schema 配置**: `dbt_project.yml` で `models.local_analytics.staging.+schema: staging` が
  staging 配下にしか効かない。`models/100-knock/topic-3/` は別パスなので、
  config で `schema='staging'` を明示しないと target schema (e.g. `dbt_user`) に
  作られてしまう。

## 解答例

詳細は [`3-1-stg-customers.solution.md`](3-1-stg-customers.solution.md) を参照。
