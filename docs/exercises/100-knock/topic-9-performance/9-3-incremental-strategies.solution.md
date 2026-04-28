# 9-3 解答例

## 3 つの mart SQL (戦略別)

### dbt/models/100-knock/topic-9/mart_orders_incremental_append_100knock.sql

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='append',
    schema='marts'
) }}

-- strategy=append: 重複 PK チェックなしで INSERT。最速、冪等性なし。
-- where 句で意図的に過去 500 行 + 新規 500 行 = 重複 PK 500 行を引き込む。
select
    order_id, order_date, customer_id, customer_name,
    product_id, product_name, category, store_id,
    quantity, unit_price, sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
{% endif %}
```

### dbt/models/100-knock/topic-9/mart_orders_incremental_delete_insert_100knock.sql

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='delete+insert',
    schema='marts'
) }}

-- strategy=delete+insert: 差分の PK を既存から DELETE してから INSERT。
-- 重複 PK は INSERT 前の DELETE で吸収されるので冪等。
select
    order_id, order_date, customer_id, customer_name,
    product_id, product_name, category, store_id,
    quantity, unit_price, sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
{% endif %}
```

### dbt/models/100-knock/topic-9/mart_orders_incremental_merge_100knock.sql

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    schema='marts'
) }}

-- strategy=merge: PK 一致なら UPDATE、無ければ INSERT (= upsert)。
-- Postgres adapter は内部で delete+insert に展開するが概念は upsert。冪等。
select
    order_id, order_date, customer_id, customer_name,
    product_id, product_name, category, store_id,
    quantity, unit_price, sales_amount,
    current_timestamp as updated_at
from {{ ref('int_order_details_100knock') }}

{% if is_incremental() %}
where order_id > (select coalesce(max(order_id) - 500, 0) from {{ this }})
{% endif %}
```

**ポイント**:

- **3 本の SQL 本体は同一**。違うのは `incremental_strategy` 1 行だけ。これが
  「**戦略を宣言で切り替えられる**」 dbt 設計の妙
- **`max - 500`**: わざと過去 500 行を含めて引き込み、PK 重複を発生させるのが本問の仕掛け

## 実行例

```bash
# 3 本同時に build (初回 = 全件)
$ cd dbt && dbt run --select mart_orders_incremental_append_100knock \
    mart_orders_incremental_delete_insert_100knock \
    mart_orders_incremental_merge_100knock --profiles-dir .
3 of 3 OK created sql incremental model ...

# 行数確認 (3 本とも 12000 行)
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT 'append' AS s, count(*) FROM marts.mart_orders_incremental_append_100knock
    UNION ALL SELECT 'd+i', count(*) FROM marts.mart_orders_incremental_delete_insert_100knock
    UNION ALL SELECT 'merge', count(*) FROM marts.mart_orders_incremental_merge_100knock"
   s    | count
--------+-------
 append | 12000
 d+i    | 12000
 merge  | 12000

# 差分 1000 行 append (raw.orders が 13000 行に)
$ cd .. && python3 scripts/100-knock/topic-9/generate_orders_diff.py --rows 1000

# 上流から rebuild
$ cd dbt && dbt run --select +mart_orders_incremental_append_100knock \
    +mart_orders_incremental_delete_insert_100knock \
    +mart_orders_incremental_merge_100knock --profiles-dir .

# 行数比較
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
    SELECT 'append' AS s, count(*) FROM marts.mart_orders_incremental_append_100knock
    UNION ALL SELECT 'd+i', count(*) FROM marts.mart_orders_incremental_delete_insert_100knock
    UNION ALL SELECT 'merge', count(*) FROM marts.mart_orders_incremental_merge_100knock"
   s    | count
--------+-------
 append | 13500   ← 重複 500 行が二重に積まれた!
 d+i    | 13000   ← 重複 PK は DELETE で吸収
 merge  | 13000   ← 重複 PK は UPDATE で吸収
```

## docs/exercises/100-knock/topic-9-performance/strategy-comparison.md

```markdown
# incremental_strategy 3 種比較: append / delete+insert / merge

実行日: 2026-04-26
重複 PK 500 行を含む差分を投入した結果。

## 1. 行数結果

| strategy        | 初回 | 2 回目 (差分) | 増分    | 重複 PK の扱い            |
|-----------------|------|---------------|---------|---------------------------|
| `append`        | 12000 | **13500**    | +1500   | 重複 500 行が **二重化**  |
| `delete+insert` | 12000 | 13000        | +1000   | DELETE で吸収             |
| `merge`         | 12000 | 13000        | +1000   | UPDATE で吸収             |

## 2. 冪等性の評価

**冪等性 (idempotency)** = 「同じ入力で何回 run しても同じ結果になる」性質。

- **append: 冪等性なし** — 同じ差分を 2 回流せば 2 回二重化する。リトライ不可。
  ログ追記系 (event log, audit) のように「同じ row が 2 回入っても文脈上意味がある」
  ユースケース専用。
- **delete+insert: 冪等** — 差分の PK を既存から DELETE → INSERT。同じ差分を 2 回
  流しても DELETE で重複が吸収される。
- **merge: 冪等** — PK 一致なら UPDATE、無ければ INSERT (= upsert)。同じ差分を
  何回流しても結果は同じ。

**結論**: master / mart は **必ず merge か delete+insert** を選ぶ。append は
ログ系限定。

## 3. 三軸トレードオフ

| 観点         | append          | delete+insert     | merge             |
|--------------|-----------------|-------------------|-------------------|
| 速度         | 最速 (INSERT のみ) | 中 (DELETE+INSERT) | 中 (Postgres は d+i 同等、Snowflake はネイティブ MERGE で速い) |
| 冪等性       | **なし**        | あり              | あり              |
| ロック範囲   | INSERT のみ     | DELETE + INSERT (大) | DELETE + INSERT (大) |
| 重複 PK 検出 | しない          | DELETE で吸収     | UPDATE で吸収     |
| 必要 config  | unique_key 任意 | unique_key 必須   | unique_key 必須   |

## 4. 判断指針 (チームでの選択)

- **append**: event log / audit trail / 不可逆ログ。冪等性が要らない / 求めない場合
- **merge**: customer / product / order などの master / mart。**デフォルトはこれ**
- **delete+insert**: 「日次集計の上書き」のように既存 row を **大量に置き換える**
  ケース。merge より DELETE が一括で速いことがある (Postgres での経験則)
```

## 解説まとめ

- **冪等性は分散システム / バッチ運用の基本要件**: 「同じ入力で何回 run しても同じ結果」
  が保証されないと、失敗時のリトライが安全にできない。「再実行したら売上が 2 倍に
  なる」mart は本番では使えない。**append を選ぶときは冪等性を捨てる覚悟が必要**。
- **3 strategy の選択は config 1 行**: SQL 本体は同じで `incremental_strategy` だけ
  変える。「正しさ」を保ったまま「物理戦略」を切り替えられるのが dbt 設計の本質。
  コードレビューで「これ append のままでいいの?」と聞ける構造。
- **adapter 依存性**: `merge` は **adapter ごとに実装が異なる**:
  - Postgres / Redshift: 内部で `delete + insert` に展開 (MERGE 文を持たない)
  - Snowflake / BigQuery: ネイティブ `MERGE INTO` 文を発行、最速
  - Databricks: Delta Lake の `MERGE INTO` (high-throughput)
  → 「Postgres ローカルで merge と delete+insert が同等速度に見える」のは
  Postgres adapter の実装事情。Snowflake では merge の方が大幅に速い。
- **append の使い所 (real-world)**:
  - **GA / Mixpanel イベントログ**: 「同じイベントが 2 回送られたら 2 行入る」
    が仕様に組み込まれているケース (デデュープは下流で `qualify row_number() = 1`)
  - **CDC (Change Data Capture) ログ**: 変更履歴を全部残したい
  - **Airflow / dbt のジョブログ自体**
- **merge の罠**: PK が **本当に PK か** を疑う必要がある。`unique_key='order_id'`
  で merge を回しているのに `order_id` が実は重複していた場合、結果が **dbt 自身も
  予測不能** になる (どの row で UPDATE するかは adapter 依存)。`unique` test で
  PK の純度を担保する習慣を併用する。
- **delete+insert と merge は Postgres では実質同じ**: ローカル環境での見え方は
  ほぼ同じだが、SQL 生成の内部構造は微妙に違う:
  - `delete+insert`: dbt 側で「DELETE FROM target WHERE pk IN (SELECT pk FROM tmp)」
    を素直に生成
  - `merge`: dbt のマクロが「MERGE 風に」展開する (Postgres では結局 delete+insert)
  本問では「**adapter ごとの抽象**」を体感することに意義がある (Snowflake に移行する
  日のため)。
- **strategy-comparison.md を残す習慣**: 「なぜこの mart は merge を選んだのか?」を
  半年後に質問されたとき、「append 試したけど冪等性が壊れた、merge にした」と
  根拠付きで答えられる。**設計判断のキャッシュ**。
