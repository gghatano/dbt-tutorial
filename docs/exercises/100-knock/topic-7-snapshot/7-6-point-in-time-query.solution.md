# 7-6 解答例

## ゴール再掲

`snapshots.snap_products_100knock` (v1 100 行 + v2 20 行 = 計 120 行) から、
`as_of = '2026-04-15'` 時点で **有効だった行のみ** を 1 product 1 行で取り出す。
結果は `docs/exercises/100-knock/topic-7-snapshot/point-in-time-result.md` に記録。

## SQL

```sql
SELECT
    product_id,
    product_name,
    category,
    unit_price,
    dbt_valid_from,
    dbt_valid_to
FROM snapshots.snap_products_100knock
WHERE dbt_valid_from <= '2026-04-15'
  AND ('2026-04-15' < dbt_valid_to OR dbt_valid_to IS NULL)
ORDER BY product_id;
```

**ポイント (なぜこの形なのか)**:

- **半開区間 `[from, to)`**: SCD Type-2 の業界標準。`from` は **その値も含む**
  (= 履歴開始の瞬間)、`to` は **その値を含まない** (= 次の世代の `from` と一致)。
  これによって任意の時刻 `t` は **必ず 1 つの履歴行** に対応 (境界の重複が無い)。
- **`dbt_valid_to IS NULL` は「+∞」**: 「現役 = まだ次の世代が来ていない」状態。
  `coalesce(dbt_valid_to, '9999-12-31')` と書いても等価。本問は `OR` 形を採用。
- **`<=` と `<` の使い分け**: 両方 `<=` にすると境界 (= 改定の瞬間) で
  2 行マッチする。両方 `<` にすると境界の瞬間がどちらにも入らない (穴ができる)。
  半開区間規約はこの「重複も穴も無い」性質を保証する。

## 実行例

```bash
$ docker exec -i local-data-postgres psql -U analytics_user -d analytics <<'SQL'
SELECT
    product_id,
    product_name,
    category,
    unit_price,
    dbt_valid_from,
    dbt_valid_to
FROM snapshots.snap_products_100knock
WHERE dbt_valid_from <= '2026-04-15'
  AND ('2026-04-15' < dbt_valid_to OR dbt_valid_to IS NULL)
ORDER BY product_id;
SQL

 product_id |   product_name   |  category   | unit_price |   dbt_valid_from    |     dbt_valid_to
------------+------------------+-------------+------------+---------------------+---------------------
          1 | Product-001      | Electronics |    1200.00 | 2026-04-10 09:00:00 |
          2 | Product-002      | Books       |     500.00 | 2026-04-10 09:00:00 |
          3 | Product-003      | Apparel     |    1240.00 | 2026-04-10 09:00:00 | 2026-04-26 10:05:00
          ...
        100 | Product-100      | Stationery  |     180.00 | 2026-04-10 09:00:00 |
(100 rows)
```

100 行が返る。内訳:

- 80 行: 一度も改定されていない product (= `dbt_valid_to IS NULL` で
  `dbt_valid_from <= '2026-04-15'` を満たす)
- 20 行: v2 で改定された product の **v1 行** (= `dbt_valid_to` が
  今日 4/26 の timestamp で、`'2026-04-15' < 4/26` を満たす)

## point-in-time-result.md (例)

`docs/exercises/100-knock/topic-7-snapshot/point-in-time-result.md`:

```markdown
# 7-6 実行結果

## 実行 SQL

\`\`\`sql
SELECT
    product_id,
    product_name,
    category,
    unit_price,
    dbt_valid_from,
    dbt_valid_to
FROM snapshots.snap_products_100knock
WHERE dbt_valid_from <= '2026-04-15'
  AND ('2026-04-15' < dbt_valid_to OR dbt_valid_to IS NULL)
ORDER BY product_id;
\`\`\`

## 結果

行数: **100 行**

抜粋 (先頭 3 + 末尾 1):

| product_id | product_name | category    | unit_price | dbt_valid_from      | dbt_valid_to        |
|-----------:|--------------|-------------|-----------:|---------------------|---------------------|
| 1          | Product-001  | Electronics |    1200.00 | 2026-04-10 09:00:00 | (NULL)              |
| 2          | Product-002  | Books       |     500.00 | 2026-04-10 09:00:00 | (NULL)              |
| 3          | Product-003  | Apparel     |    1240.00 | 2026-04-10 09:00:00 | 2026-04-26 10:05:00 |
| ...        | ...          | ...         |        ... | ...                 | ...                 |
| 100        | Product-100  | Stationery  |     180.00 | 2026-04-10 09:00:00 | (NULL)              |

## 解説

product_id=3 は 2026-04-26 に改定された (v2 投入)。だが `as_of='2026-04-15'`
時点では v2 はまだ存在せず、v1 (`unit_price=1240.00`) が **その時点で有効**
だった。半開区間 `dbt_valid_from <= as_of < dbt_valid_to` がこれを 1 行に絞る。

全 100 product 各 1 行 = 100 行が返るのが、point-in-time クエリの正しい挙動。
```

## 解説まとめ

1. **「履歴を持つ」と「履歴を引ける」は別**: snapshot は SCD Type-2 で履歴を
   持たせるが、それを **`as_of` で 1 行に絞る SQL** を書けて初めて使い物になる。
   この SQL は `WHERE` 句 2 行ですべて表現できる定型。
2. **半開区間が境界の重複/穴を排除する**: `[from, to)` 規約は SCD Type-2 だけ
   でなく、bitemporal データ全般で常套手段。OLAP / OLTP どちらでもこの形を
   そのまま使える。
3. **`as_of` を変数化すれば監査クエリ**: 本問は固定値だが、本番では
   `WHERE dbt_valid_from <= :as_of AND (:as_of < dbt_valid_to OR ...)` のように
   パラメータ化する。BI ツールの date filter から渡せば「3 ヶ月前の価格表
   を再生成」が UI 操作で出来る。
4. **次の問 (7-7)**: 同じ半開区間 JOIN を **range JOIN** として書き、
   注文 1 件 ずつに「**注文時点の単価**」を引き当てる intermediate を作る。
   point-in-time の概念を「点」から「列 (各行ごとに違う as_of)」に拡張する流れ。
