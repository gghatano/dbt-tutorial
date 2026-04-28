# 7-5: snapshot 自身に schema test を貼る

## シナリオ

7-1〜7-4 で snapshot を 3 種 (`snap_products_100knock`、`snap_products_ts_100knock`、
`snap_products_hd_100knock`) 作って動かしてきた。これらの行はすべて dbt が
**自動生成** した SCD Type-2 構造を持つので、「機械生成だから安心」と思いがち。

しかし実際には:

- `dbt_scd_id` の hash 衝突 (天文学的だが原理的に 0 ではない)
- snapshot 実行が **同じ秒に複数回** 走ったときの race
- 手動で snapshot 行を `INSERT` / `UPDATE` してしまう運用事故
- 上流 source の `unique_key` 列 (product_id) に NULL が混ざる

といった原因で「メタ列が壊れる」ことは起きうる。Topic ⑥ で staging に契約を
貼ったのと同じ感覚で、**snapshot 自身にも schema 契約 (test) を貼って機械的に
保証する** のが本問のテーマ。

## 学べること

- snapshot 用 `schema.yml` の書き方 (snapshots: ブロック)
- メタ列 (`dbt_scd_id` / `dbt_valid_from` / `dbt_valid_to`) への generic test
- 「snapshot は machine-generated だから契約不要」の **誤解** を覆す
- `dbt test --select snap_products_100knock` で snapshot test を回す手順

## 前提

- 7-1 完了: `snap_products_100knock` が動き、`snapshots.snap_products_100knock` が
  120 行 (7-2 まで実行済みの想定。100 行でも test 自体は通る)
- snapshot 用の `schema.yml` をこれから新規作成

## 課題

### Step 1: snapshot 用 schema.yml を作る

`dbt/snapshots/100-knock/topic-7/schema.yml` を新規作成。

要件:

- `version: 2`
- `snapshots:` ブロック (`models:` ではない)
- `name: snap_products_100knock` を宣言
- `columns:` で:
  - `dbt_scd_id` に `not_null` + `unique` test
  - `product_id` に `not_null` test (任意で `unique` は不可 = 履歴で重複する)
  - `dbt_valid_from` に `not_null` test
- description を各 column に付ける (docs 用)

### Step 2: dbt test を実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt test --profiles-dir . --select snap_products_100knock
```

完了の見え方:

- 4 件の test (`not_null_dbt_scd_id` / `unique_dbt_scd_id` / `not_null_product_id` /
  `not_null_dbt_valid_from`) がすべて PASS
- `Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4`

### Step 3 (任意): わざと壊して NG を見る

```sql
-- 検証: dbt_scd_id の unique を壊す
INSERT INTO snapshots.snap_products_100knock
SELECT * FROM snapshots.snap_products_100knock LIMIT 1;
```

その状態で `dbt test --select snap_products_100knock` を再実行すると
`unique_snap_products_100knock_dbt_scd_id` が FAIL になる。確認後は
`DELETE FROM snapshots.snap_products_100knock WHERE ...` で復元する。

## 完了条件

- [ ] `dbt/snapshots/100-knock/topic-7/schema.yml` が存在する
- [ ] schema.yml に `snapshots:` トップレベルキーがある
- [ ] `snap_products_100knock` の `dbt_scd_id` に `not_null` + `unique` test 宣言がある
- [ ] `dbt test --select snap_products_100knock` が **PASS=4 以上** で完了

## ヒント (詰まったら)

- **`models:` で書いてしまう**: snapshot は `snapshots:` トップレベルキーで
  宣言する (dbt 1.x 以降の仕様)。`models:` で書くと `Compilation Error: ...
  was not found` になる。
- **`unique` test を `product_id` に貼ってしまう**: snapshot は同じ product_id で
  履歴複数行を持つので **`product_id` に `unique` を貼ると常に FAIL** する。
  unique は `dbt_scd_id` (snapshot 自動生成の物理 PK) に貼る。
- **`dbt_valid_to` に `not_null` を貼ってしまう**: 最新行は `dbt_valid_to is null`
  なので、これも常に FAIL する。`dbt_valid_to` には test を貼らない、または
  独自に「同一 unique_key で `dbt_valid_to is null` の行は 1 行ちょうど」を
  検証する singular test (`tests/100-knock/topic-7/snap_one_active_per_key.sql`) を
  書くのが本格派 (本問では宿題)。
- **PASS 数が 4 にならない**: schema.yml で test を宣言した数 (例: not_null + unique +
  product_id not_null + valid_from not_null = 4) と一致するはず。`dbt ls --select
  snap_products_100knock,test_type:not_null` で test 一覧を確認。

## 解答例

詳細は [`7-5-snap-schema-test.solution.md`](7-5-snap-schema-test.solution.md) を参照。
