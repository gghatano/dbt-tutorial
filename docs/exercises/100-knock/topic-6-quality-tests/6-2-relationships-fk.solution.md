# 6-2 解答例

## dbt/models/100-knock/topic-3/schema.yml (該当ブロック)

`stg_orders_100knock.customer_id` に `relationships` test が宣言されている状態
(3-4 完成形のまま):

```yaml
  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders。"
    columns:
      # ... order_id / order_date 省略 ...
      - name: customer_id
        description: "FK → stg_customers_100knock.customer_id (relationships で検査)。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers_100knock')
                field: customer_id
      # ... product_id / store_id / quantity / unit_price ...
```

**ポイント**:

- **`arguments:` ネスト形式**: dbt 1.11 で test の引数渡しが整理された
  最新構文。`to:` / `field:` を直接トップレベルに書く旧形式も動くが、
  新規プロジェクトでは新形式に揃える。
- **`to: ref('stg_customers_100knock')`**: `ref()` を使うことで manifest 上に
  「この test は親モデルにも依存する」 というエッジが生える。
  `dbt build --select +stg_orders_100knock` のような上流ビルドで自動的に
  順序が解決される。
- **`field: customer_id`**: 親モデル側の対応列名。FK と PK が同名でない場合
  (例: `orders.cust_id` → `customers.customer_id`) はここで明示する。
- **`not_null` とのセット**: `relationships` 単体は NULL 行を素通りさせる
  ので、注文に必ず顧客がいる EC ドメインでは `not_null` も併記する。

## わざと FK を壊して FAIL を体感

### 1. 違反行を 1 件混ぜる

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET customer_id = 99999 WHERE order_id = 1;
SQL
UPDATE 1
```

### 2. dbt test を実行 → FAIL を確認

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
1 of N PASS not_null_stg_orders_100knock_order_id ...........
2 of N PASS unique_stg_orders_100knock_order_id .............
... 
N of M FAIL 1 relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_ [FAIL 1 in 0.07s]
... 
Failure in test relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_ (models/100-knock/topic-3/schema.yml)
  Got 1 result, configured to fail if != 0

  compiled Code at target/compiled/local_analytics/models/100-knock/topic-3/schema.yml/relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_.sql

Done. PASS=N WARN=0 ERROR=1 SKIP=0 TOTAL=N+1
```

`exit code = 1`。CI では普通なら job が落ちるが、本問では「**FAIL する
ことが正解**」 なのでこの exit 1 を採点側で `shell_command` の
`expect_exit_code: 1` で受け取る。

### 3. dbt がコンパイルした SQL を読む

```bash
$ cat target/compiled/local_analytics/models/100-knock/topic-3/schema.yml/relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_.sql
```

```sql
with child as (
    select customer_id as from_field
    from "analytics"."staging"."stg_orders_100knock"
    where customer_id is not null
),
parent as (
    select customer_id as to_field
    from "analytics"."staging"."stg_customers_100knock"
)
select
    from_field
from child
left join parent
    on child.from_field = parent.to_field
where parent.to_field is null
```

`LEFT JOIN ... WHERE parent IS NULL` 構造で「親にいない FK 値」 を返している。
このクエリが 1 行 (`customer_id = 99999`) を返すので test は FAIL。

### 4. 失敗行を直接 SELECT (デバッグループ)

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
SELECT order_id, customer_id
FROM staging.stg_orders_100knock
WHERE customer_id NOT IN (
    SELECT customer_id FROM staging.stg_customers_100knock
);
SQL
 order_id | customer_id
----------+-------------
        1 |       99999
(1 row)
```

「どの注文行の FK が壊れているか」が即わかる = 修復対象が特定できる。
本番ならこの `order_id=1` を ETL チームに渡すか、staging で
`WHERE customer_id IN (SELECT ...)` でフィルタして除外する。

## 戻す (ロールバック)

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET customer_id = 1 WHERE order_id = 1;"
UPDATE 1

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
... 
Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

> **本問の最終提出時の注意**: 採点 CI は「FAIL する状態」 を期待するので、
> ロールバックせずに submit する。手元で確認 → 戻す → CI で再度壊す、
> のような往復は不要。`exercise-100-knock-6-2-...` ブランチで raw を
> 壊した状態のまま push すれば OK。

## 解説まとめ

- **`relationships` = 参照整合の不変条件契約**: SQL の DDL に `FOREIGN KEY`
  を書かなくても、dbt は test として同等の検査をしてくれる。staging が view で
  物理 FK を持てない設計でも安心。
- **DAG が「物理依存」 と「参照整合依存」 の二層を語る**: `ref()` だけだと
  「ビルド順」しか分からないが、`relationships` を貼ると DAG 上に
  「**子は親に存在せよ**」 という意味的なエッジが追加される。
  `dbt docs` で見える依存図はこの両方を表現する。
- **「FAIL を採点する」 設計**: 通常 test は PASS を期待するが、6-2 / 6-3 の
  ような **「壊れる体験」** を学ぶ問では、FAIL することが正解。採点は:
  1. `sql_assert` で「不正行 >= 1」 を確認 (= 壊れていることの検証)
  2. `shell_command` で `dbt test` の `exit code = 1` を確認
  3. `dbt_test_passes` は使わない (PASS しないので)
  4. `manifest_node_exists` で test 宣言は確認 (構造はあること)
- **NULL 素通り問題**: `relationships` 単体だと NULL 行は検査対象外。
  本リポジトリは `not_null` を併記して NULL も拒否する設計。「FK が
  あるなら親にいる」 + 「FK は必ずある」 で完全な参照整合契約。
- **修復は raw か staging か**: 本問では raw を直接 UPDATE しているが、
  本番では (a) ETL 上流で投入時に弾く、(b) staging で `WHERE` で除外、
  (c) 親テーブルに足すべきデータを補完投入、の選択肢から業務要件に
  合わせて選ぶ。test はあくまで「**気付く**」 ための装置。
- **FK 方向の設計判断**: `relationships` は子→親の単方向。逆向き (親に
  対する子のカバレッジ) は別の test (例: `dbt_utils.equal_rowcount` や
  自作 generic test) で表現する。1-6 で学んだ「休眠顧客 (= 注文を 1 件も
  持たない customer)」 はあえて relationships を貼らない (親→子は
  カバレッジ非 100% を許す) 設計判断とつながる。
