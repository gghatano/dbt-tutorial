# 9-2: mart_orders_incremental_100knock を incremental + merge で実装

## シナリオ

`int_order_details_100knock` (10,000 行) を毎回フル rebuild する mart は MVP では問題ない
が、本番環境では「**毎晩 1,000 行新規追加 → 翌朝 BI で見る**」のループで、フル rebuild
が現実的でない規模 (100 万行 / 1 億行) に育つ。

そこで **incremental materialization** を使う。`is_incremental()` で「初回 or `--full-refresh`
のときは全件、それ以外は **直前 build 以降の差分だけ** をマージ」を 1 つの SQL で
両対応する。`unique_key='order_id'` + `incremental_strategy='merge'` で「同じ PK が来たら
更新、無ければ insert」の **upsert** が宣言で済む。

本問では `mart_orders_incremental_100knock` (1 row = 1 order_id の incremental mart) を
実装し、新規 1,000 行を追加してから 2 回目の `dbt run` で **差分マージ** が走ることを
確認する。`target/run/...sql` を読んで「dbt が自動生成した merge 文」を目で見ることが
本問の要点。

## 学べること

- `materialized='incremental'` + `unique_key` + `incremental_strategy='merge'` の 3 点セット
- `is_incremental()` jinja 関数で初回 vs 差分実行を分岐する書き方
- 「**高水位線 (high-watermark)**」 = `select max(updated_at) from {{ this }}` の意味
- `target/run/<model>.sql` で **dbt が生成した実 DDL** を読む
- 2 回 run しても結果が同じになる「**冪等性**」の確認方法

## 前提

- Topic ④ 4-1 完了 (`int_order_details_100knock` が存在、9-1 で table 化済み)
- 9-1 完了 (推奨だが必須ではない)
- main HEAD の MVP `dbt run` が緑
- `psql` が `analytics` DB に接続できる

## 入力データ

新規 1,000 行を生成する script を別途用意する (Step 2)。

## 課題

### Step 1: incremental mart を作る

`dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql` を新規作成:

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    on_schema_change='fail',
    schema='marts'
) }}

-- Grain: 1 row = 1 order_id (incremental mart)。
-- 初回 / --full-refresh: int_order_details_100knock の全件を読む
-- 差分 run: int_order_details_100knock のうち this より大きい order_id のみ追加
select
    order_id,
    order_date,
    customer_id,
    customer_name,
    product_id,
    product_name,
    category,
    store_id,
    quantity,
    unit_price,
    sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id), 0) from {{ this }})
{% endif %}
```

### Step 2: 差分データ生成スクリプトを作る

`scripts/100-knock/topic-9/generate_orders_diff.py` を新規作成。1,000 行の新規 orders
を `raw.orders` に **append** する script。

要件:

- `--rows N` で行数指定 (default 1000)
- 既存 `raw.orders` の最大 `order_id` を取得し、その次から連番で新規 PK
- `order_date` は当日 + N 日のランダム (FK は既存範囲から)
- 既存 raw に **APPEND** (TRUNCATE しない)

簡略実装でよい (擬似コードは解答例参照)。

### Step 3: 初回 dbt run (全件)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --select mart_orders_incremental_100knock --profiles-dir .
```

完了の見え方:

- `marts.mart_orders_incremental_100knock` が作られて `count(*) = 10000` (既存 orders 全件)
- ログに `OK created sql incremental model marts.mart_orders_incremental_100knock` が出る

物理化確認:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT count(*) FROM marts.mart_orders_incremental_100knock;
"
# 10000
```

### Step 4: 差分 1,000 行を追加 → 2 回目の dbt run

```bash
cd ..
.venv/bin/python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000
# raw.orders が 11000 行になる

# upstream を再 build (int_order_details_100knock を rebuild してから mart に流す)
cd dbt
../.venv/bin/dbt run --select +mart_orders_incremental_100knock --profiles-dir .
```

完了の見え方:

- `marts.mart_orders_incremental_100knock` が **11000 行** になる
- ログ: 2 回目は **incremental model として実行** され、フル rebuild ではない
- `target/run/local_analytics/models/100-knock/topic-9/mart_orders_incremental_100knock.sql`
  に **`merge into ... using ... on order_id = order_id when matched then update ... when not matched then insert ...`** が生成されている (Postgres adapter は内部で
  delete + insert に展開するので実装は若干違うが、概念は同じ)

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-9-performance/9-2-incremental-merge.grading.yaml
```

> **採点時の最終 state**: `mart_orders_incremental_100knock` が **11000 行** であること。
> Step 4 の状態でコミット / push する。

## 完了条件

- [ ] `dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql` が存在
- [ ] manifest 上 `materialized=incremental` + `unique_key=order_id` + `incremental_strategy=merge`
- [ ] `dbt run` が 2 回 (初回 + 差分) とも成功
- [ ] `marts.mart_orders_incremental_100knock` が 11,000 行
- [ ] `scripts/100-knock/topic-9/generate_orders_diff.py` が存在

## ヒント (詰まったら)

- **`is_incremental()` が初回で True を返してしまう**: dbt 1.x では「table が存在し、
  `--full-refresh` でない時」に True。初回は table が無いので False が返る、これが
  期待挙動。`--full-refresh` で table DROP → 次回また初回扱いに戻る。
- **`unique_key` 無しだと merge できない**: `incremental_strategy='merge'` には
  `unique_key` が必須。指定しないと dbt が ERROR で落ちる。
- **postgres adapter での merge**: dbt-postgres は MERGE 文をネイティブにサポートして
  おらず、内部で **`delete + insert` に展開** する。`unique_key='order_id'` の重複は
  ここで効く。`append` strategy にすると重複が発生しうるので注意 (9-3 で扱う)。
- **`on_schema_change='fail'` の意味**: 上流 schema が変わった (列追加など) のに
  incremental table の schema と一致しないとき、dbt run を fail させる安全装置。
  代替値は `'ignore'` (新列を無視) / `'append_new_columns'` (追加列を本 table にも追加) /
  `'sync_all_columns'` (列追加 + 型変更も追従)。MVP は `'fail'` 推奨。
- **差分判定が高水位線で済む?**: 本問は `order_id > max(order_id)` で十分 (新規 PK
  は連番で増える前提)。実務では `loaded_at > max(loaded_at)` のほうが汎用的。
  `order_id` が連番でない / 過去 PK が後から来る場合は破綻する。
- **2 回目の run で 0 行になってしまう**: upstream `int_order_details_100knock` を
  rebuild していない可能性。`+mart_orders_incremental_100knock` で **上流から build**
  し直すか、`--full-refresh` で全件作り直し。

## 解答例

詳細は [`9-2-incremental-merge.solution.md`](9-2-incremental-merge.solution.md) を参照。
