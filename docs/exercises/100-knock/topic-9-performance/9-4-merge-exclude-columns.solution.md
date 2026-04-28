# 9-4 解答例

## dbt/models/100-knock/topic-9/mart_orders_incremental_100knock.sql (最終 state)

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    merge_exclude_columns=['updated_at'],
    on_schema_change='fail',
    schema='marts'
) }}

-- Grain: 1 row = 1 order_id (incremental + merge mart)。
-- merge_exclude_columns=['updated_at']: PK 一致時の UPDATE で updated_at を上書きしない。
--   理由: updated_at は「dbt が build した時刻」を入れているが、source 側で
--   最後に変更された時刻を残したいケース (BI 表示の意味論) を模した設計。
--   実務では source_updated_at / first_seen_at などを exclude する。
-- where 句で max(order_id)-500 から SELECT し、merge による UPDATE が発生する状況を作る。
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
{% endif %}
```

**ポイント**:

- **`merge_exclude_columns=['updated_at']` の 1 行追加** が本問の核心。SQL 本体は
  9-2 とほぼ同じ
- **`max - 500` の where 句**: merge による UPDATE を発生させるための仕掛け。
  `> max(order_id)` のままだと INSERT しか起きず、merge_exclude_columns の効果が見えない

## 実行例

```bash
# Step 2: 更新前 timestamp を記録
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT order_id, updated_at FROM marts.mart_orders_incremental_100knock
    WHERE order_id IN (10999, 11000) ORDER BY order_id"
 order_id |          updated_at
----------+-------------------------------
    10999 | 2026-04-26 10:30:00.123456
    11000 | 2026-04-26 10:30:00.123456

# Step 3: 差分追加 + 再 run
$ python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000
Appended 1000 rows to raw.orders (PK 11001..12000)

$ cd dbt && dbt run --select +mart_orders_incremental_100knock --profiles-dir .
... 4 of 4 OK created sql incremental model marts.mart_orders_incremental_100knock ...

# Step 4: updated_at が変わっていないことを確認
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT order_id, updated_at FROM marts.mart_orders_incremental_100knock
    WHERE order_id IN (10999, 11000) ORDER BY order_id"
 order_id |          updated_at
----------+-------------------------------
    10999 | 2026-04-26 10:30:00.123456   ← 変わっていない (= 保護されている)
    11000 | 2026-04-26 10:30:00.123456   ← 変わっていない

# 新規 row は新しい timestamp を持つ
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT min(updated_at), max(updated_at), count(*)
    FROM marts.mart_orders_incremental_100knock
    WHERE order_id BETWEEN 11500 AND 12000"
        min                |        max                | count
---------------------------+---------------------------+-------
 2026-04-26 11:42:30.78... | 2026-04-26 11:42:30.78... |  501
```

## target/run/ の生成 SQL (抜粋)

```sql
-- Postgres adapter での incremental + merge + merge_exclude_columns 実装
begin;
    delete from "analytics"."marts"."mart_orders_incremental_100knock"
    where (order_id) in (
        select (order_id) from "mart_orders_incremental_100knock__dbt_tmp"
    );

    insert into "analytics"."marts"."mart_orders_incremental_100knock"
        ("order_id", "order_date", ..., "sales_amount", "updated_at")
    select "order_id", "order_date", ..., "sales_amount",
           -- ↓ updated_at は tmp 側の値 (= 新規 build 時刻) を使う
           "updated_at"
    from "mart_orders_incremental_100knock__dbt_tmp";
commit;
```

> **注意**: Postgres adapter では merge を delete+insert に展開するため、
> `merge_exclude_columns` の **見え方が独特**。「DELETE → INSERT」の流れだと
> 既存 row の値は **失われる** ように思えるが、実は dbt は `__dbt_tmp` を作るとき
> に「**既存 row の `updated_at` を引き継ぐ JOIN**」を組んでいる (重複 PK のみ)。
> Snowflake / BigQuery ではネイティブ `MERGE INTO` 文の `WHEN MATCHED THEN UPDATE
> SET col1 = ..., col2 = ...` で `updated_at` を SET 句から除外する形になる。

実装詳細は dbt-postgres の `incremental_merge` macro を参照
(`dbt/include/postgres/macros/materializations/incremental_merge.sql`)。

## 解説まとめ

- **なぜ merge_exclude_columns が必要?**: incremental + merge の **デフォルト挙動**
  は「PK 一致なら **全列 UPDATE**」だが、これだと「上書きされたくない列」を保護
  できない。dbt 1.6+ で導入された **列単位の merge 制御** が解決策。
- **典型的な exclude 候補**:
  - **`source_updated_at`** / **`source_modified_at`**: 源泉システムが管理する時刻列。
    dbt build 時刻で上書きしてはいけない (BI 表示で「最後に営業担当が更新した日」が
    見えなくなる)
  - **`first_seen_at`**: 「この PK を初めて観測した時刻」。merge UPDATE で上書きする
    のは意味論違反 (= 観測初回時刻が「最後に更新された時刻」になってしまう)
  - **`created_by_user_id`** / **`created_at`**: 作成者・作成時刻は上書きしない
  - **`is_active`**: 論理削除フラグを源泉が管理している場合、merge で復活させない
- **`merge_exclude_columns` vs `merge_update_columns`**: 1.6+ では両方使える:
  - `merge_exclude_columns=['updated_at', 'created_at']`: 「これだけ除外、残り全部 UPDATE」
  - `merge_update_columns=['quantity', 'sales_amount']`: 「これだけ UPDATE、残り保護」
  → **除外列が少ないなら exclude、UPDATE 列が少ないなら update_columns**。本問のように
  「1 列だけ除外したい」場合は exclude のほうが冗長性が低い。
- **adapter 依存性 (重要)**:
  - **Snowflake / BigQuery**: ネイティブ `MERGE INTO ... WHEN MATCHED THEN UPDATE
    SET col1=src.col1, col2=src.col2` の SET 句から exclude 列を抜く形
  - **Postgres / Redshift**: `delete + insert` 展開時に「既存値を引き継ぐ JOIN」を
    内部で組む。コード生成が複雑、target/run/ の SQL は読みづらい
  - **Databricks (Delta Lake)**: ネイティブ MERGE INTO、Snowflake と同等
  → ローカル Postgres での挙動を見るだけでは不十分。**adapter ごとに実機検証する習慣**
  が必要。
- **dbt 1.5 以前との互換性**: 古い dbt では `merge_exclude_columns` config は **黙って
  無視** される (警告も出ない)。これは罠 — 「設定したのに効かない」状態に気づかない。
  運用前に **`dbt --version`** で 1.6+ を確認。
- **設計のヒント**: 「**履歴に意味がある列**」と「**現在値だけが意味のある列**」を
  schema.yml の `description:` に書き分ける習慣を付ける。merge_exclude を後から追加する
  ときに「どの列が履歴系か」を読み取れる。
- **代替設計**: SCD Type 2 (snapshot) で履歴を別 table に持つ手もあるが、要件が
  「**最新値 + 一部の履歴系列保護**」程度なら incremental + merge_exclude で済む。
  「全履歴を残す」が要件なら snapshot を使う (Topic ⑦)。
