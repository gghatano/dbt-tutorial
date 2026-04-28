# 9-4: merge_exclude_columns で「源泉システムの updated_at」を merge から除外する

## シナリオ

9-2 で作った `mart_orders_incremental_100knock` (incremental + merge) は、PK 一致なら
**全列を上書き** する仕様。だがこの設計には罠がある:

- mart に **`updated_at = current_timestamp`** を入れている
- 既存 row が merge で UPDATE されるたび、`updated_at` が **dbt run の現在時刻** で
  上書きされる
- BI 側で「この order が **最後に源泉システムで** 変更されたのはいつ?」を見たくても、
  「dbt が **最後に build した時刻**」しか見えなくなる

dbt 1.6+ で導入された **`merge_exclude_columns`** は、「PK が一致した UPDATE 時に
**この列だけは更新しない**」を宣言できる仕組み。源泉システムから来た時刻列を保護
するのに使う。

本問では `mart_orders_incremental_100knock` (or 9-2 の model をベース) に
`merge_exclude_columns=['updated_at']` を追加し、再 run しても既存 row の `updated_at`
が **新規 build 時刻で上書きされない** ことを確認する。

## 学べること

- `merge_exclude_columns=['col1', 'col2']` の意味と効果 (列単位の merge 制御)
- なぜ「源泉システムの時刻列」を merge から除外するのか (BI 表示の意味論)
- `target/run/<model>.sql` の merge 文を読んで、UPDATE 列が除外されているか確認
- dbt 1.6+ 以降の機能であることに注意 (古い dbt では config 自体が無効)

## 前提

- 9-2 完了 (`mart_orders_incremental_100knock` が存在)
- dbt 1.6 以上 (`dbt --version` で確認)
- main HEAD の MVP `dbt run` が緑

## 入力データ

9-2 の状態 (raw.orders 11000 行 + mart 11000 行) からスタート。差分 1000 行を
さらに追加して、**既存 row の `updated_at` が保護される** ことを確認する。

## 課題

### Step 1: mart_orders_incremental_100knock に merge_exclude_columns を追加

`dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql` の `config()` に
`merge_exclude_columns` を追加:

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    merge_exclude_columns=['updated_at'],
    on_schema_change='fail',
    schema='marts'
) }}

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
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
-- ↑ わざと過去 500 行を含めて、merge による UPDATE が発生する状況を作る
{% endif %}
```

`max - 500` で **既存 500 行 + 新規 500 行** を引き込み、merge で 500 row が
UPDATE される状態にする。

### Step 2: 既存 row の更新前 timestamp を控える

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT order_id, updated_at
FROM marts.mart_orders_incremental_100knock
WHERE order_id IN (10999, 11000)
ORDER BY order_id;
"
```

例:

```
 order_id |          updated_at
----------+-------------------------------
    10999 | 2026-04-26 10:30:00.000000
    11000 | 2026-04-26 10:30:00.000000
```

→ この 2 行の `updated_at` が **次回 run 後も変わらない** ことを期待する。

### Step 3: 差分追加 → 再 run

```bash
cd ..
.venv/bin/python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000

cd dbt
../.venv/bin/dbt run --select +mart_orders_incremental_100knock --profiles-dir .
```

### Step 4: updated_at が変わっていないことを確認

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT order_id, updated_at
FROM marts.mart_orders_incremental_100knock
WHERE order_id IN (10999, 11000)
ORDER BY order_id;
"
```

期待される結果: **Step 2 と同じ timestamp** (= 既存 row の `updated_at` は merge で
**保護されている**)。

新規 row (11001 〜 12000) は **新しい timestamp** を持つ:

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT min(updated_at), max(updated_at), count(*)
FROM marts.mart_orders_incremental_100knock
WHERE order_id BETWEEN 11500 AND 12000;
"
```

### Step 5: target/run/ の merge 文を読む

```bash
cat dbt/target/run/local_analytics/models/100-knock/topic-9/mart_orders_incremental_100knock.sql
```

merge / update 句に `updated_at` が **含まれていない** ことを確認 (= dbt が
`merge_exclude_columns` 宣言を読んで、UPDATE 列リストから除外している)。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-9-performance/9-4-merge-exclude-columns.grading.yaml
```

## 完了条件

- [ ] `mart_orders_incremental_100knock.sql` の config に `merge_exclude_columns=['updated_at']`
- [ ] dbt 1.6+ で `dbt parse` が成功
- [ ] `dbt run --select mart_orders_incremental_100knock` が成功
- [ ] target/run/ の生成 SQL に merge_exclude_columns の効果 (updated_at が UPDATE
      列に無い) が出ている
- [ ] 既存 row の `updated_at` が再 run 後も変わらない (sql_assert で検証)

## ヒント (詰まったら)

- **dbt のバージョンが古い**: `dbt --version` で 1.6 未満なら、`merge_exclude_columns`
  config は **無視される** (warning も出ない)。`pip install --upgrade dbt-core dbt-postgres`
  で 1.6 以上に上げる。
- **`merge_exclude_columns` が効いていないように見える**: 上流 SQL で `updated_at` を
  毎回 `current_timestamp` で生成しているので、**新規 row は新しい timestamp を持つ** のは
  正しい挙動。「**既存 row が UPDATE される際、その既存 row の `updated_at` が新しく
  なっていないか**」を確認する。
- **既存 row が一度も UPDATE されていない可能性**: `where` 句が `> max(order_id)` の
  ままだと merge による UPDATE が発生しない (純粋に INSERT のみ)。本問では `max - 500`
  で過去を含めることで「**500 行が UPDATE 対象になる**」状況を作る。
- **使い所 (real-world)**:
  - **`source_updated_at`**: 源泉システムが「いつ変更したか」を入れている列。dbt の
    build 時刻で上書きしては意味が壊れる
  - **`first_seen_at`**: 「この row を最初に観測した時刻」。merge で更新されて欲しくない
  - **`created_by_user_id`**: 元々誰が作成したか。merge で上書きしてはいけない
  - 一般則: 「**履歴を残したい列 / 過去状態に意味がある列**」は merge 除外
- **`merge_exclude_columns` vs `merge_update_columns`**: 1.6+ では両方使える:
  - `merge_exclude_columns=['updated_at']`: 「これだけ除外、残り全部 UPDATE」
  - `merge_update_columns=['quantity', 'sales_amount']`: 「これだけ UPDATE、残り保護」
  どちらも **指定列以外** の取り扱いが対称。本問は exclude を使う (除外列が少ない側)。

## 解答例

詳細は [`9-4-merge-exclude-columns.solution.md`](9-4-merge-exclude-columns.solution.md) を参照。
