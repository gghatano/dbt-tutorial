# 7-4 解答例

## dbt/snapshots/100-knock/topic-7/snap_products_hd_100knock.sql

```sql
{% snapshot snap_products_hd_100knock %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='check',
        check_cols=['unit_price'],
        hard_deletes='new_record',
    )
}}

-- 100-knock Topic ⑦ Q4: hard_deletes='new_record' (dbt 1.9+) で
-- raw からの物理削除も「削除イベント行」として履歴に残す。
-- 7-1 の snap_products_100knock とは別 snapshot として並走させ、
-- 削除挙動の比較もできるようにしている。
select
    product_id,
    product_name,
    category,
    unit_price
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

**ポイント**:

- **`hard_deletes='new_record'`**: dbt 1.9+ の新オプション。値は 3 種:
  - `'ignore'` (default, 1.8 以前の挙動): raw から消えても snapshot 側放置
  - `'invalidate'`: raw から消えた瞬間に **既存行の `dbt_valid_to`** を埋めるだけ
  - `'new_record'`: 既存行の `dbt_valid_to` を埋めた上で、**削除イベント行を新規 INSERT**
    する。`dbt_is_deleted=true` メタ列が立つ。本問はこれを使う
- **`new_record` の利点**: 「いつ消えたか」が `dbt_valid_from`、「消える前は何
  だったか」が直前行に保存され、`as_of` 時点クエリで「その時点で raw から消えていたか」
  まで再現できる。
- **既存 7-1 snapshot と並走**: 7-1 のファイルを上書き編集すると `hard_deletes` が
  既に作られた snapshot に効かないリスクがある。**新規 snapshot として独立させる**
  のが安全な手順。

## Step 2: 1 回目の snapshot 実行ログ

```text
$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_hd_100knock
14:58:01  1 of 1 START snapshot snapshots.snap_products_hd_100knock ..... [RUN]
14:58:01  1 of 1 OK snapshotted snapshots.snap_products_hd_100knock ..... [SELECT 100 in 0.13s]
14:58:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

```sql
analytics=> SELECT count(*) AS total,
                  count(*) FILTER (WHERE dbt_is_deleted = true) AS deleted_events
            FROM snapshots.snap_products_hd_100knock;
 total | deleted_events
-------+----------------
   100 |              0
```

## Step 3: 5 行物理削除

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
DELETE FROM raw.products WHERE product_id IN (1, 2, 3, 4, 5);
SQL
DELETE 5

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "SELECT count(*) FROM raw.products"
 count
-------
    95
```

## Step 4: 2 回目の snapshot

```text
$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_hd_100knock
14:59:10  1 of 1 START snapshot snapshots.snap_products_hd_100knock ..... [RUN]
14:59:10  1 of 1 OK snapshotted snapshots.snap_products_hd_100knock ..... [SELECT 5 in 0.15s]
14:59:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`SELECT 5` は「5 個の削除イベント行を新規 INSERT した」意味。

## Step 5: 履歴確認

```sql
analytics=> SELECT count(*) AS total,
                  count(*) FILTER (WHERE dbt_is_deleted = true)  AS deleted_events,
                  count(*) FILTER (WHERE dbt_valid_to IS NULL)   AS active
            FROM snapshots.snap_products_hd_100knock;
 total | deleted_events | active
-------+----------------+--------
   105 |              5 |    100

analytics=> SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to, dbt_is_deleted
            FROM snapshots.snap_products_hd_100knock
            WHERE product_id IN (1, 2, 3, 4, 5)
            ORDER BY product_id, dbt_valid_from;
 product_id | unit_price |   dbt_valid_from    |    dbt_valid_to     | dbt_is_deleted
------------+------------+---------------------+---------------------+----------------
          1 |    1240.00 | 2026-04-26 14:58:01 | 2026-04-26 14:59:10 | f
          1 |    1240.00 | 2026-04-26 14:59:10 |                     | t
          2 |    8520.00 | 2026-04-26 14:58:01 | 2026-04-26 14:59:10 | f
          2 |    8520.00 | 2026-04-26 14:59:10 |                     | t
          3 |     230.00 | 2026-04-26 14:58:01 | 2026-04-26 14:59:10 | f
          3 |     230.00 | 2026-04-26 14:59:10 |                     | t
```

各 product_id (1〜5) に対して 2 行:

- 1 行目: 元の状態 (`dbt_is_deleted=false`、`dbt_valid_to` 埋まり)
- 2 行目: 削除イベント行 (`dbt_is_deleted=true`、`dbt_valid_to is null` = 「最新は削除状態」)

## ヒント代替案: `hard_deletes` が動かない時

dbt-core が 1.9 未満で `hard_deletes` が `Compilation Error` になる場合:

```sql
{% snapshot snap_products_hd_100knock %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='check',
        check_cols=['unit_price', 'is_deleted'],   -- is_deleted も追跡列に
    )
}}

select
    product_id,
    product_name,
    category,
    unit_price,
    false as is_deleted          -- raw に存在する行は常に false
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

この方式では削除イベント行は自動生成されないので、削除を「歴史」にしたい
場合は raw 側に `is_deleted` 列を持たせて論理削除する設計に切り替える。
`hard_deletes` の本質的価値はまさに「raw 側を変えずに削除を歴史化できる」点。

## 解説まとめ

- **削除も時間軸の事実**: SKU 廃番、退会、店舗閉店は単なる「データの消失」では
  なく、ビジネス上の **イベント** (廃番した、退会した) として記録すべき情報。
  `hard_deletes='new_record'` はこれを宣言的に表現する dbt 1.9+ の機能。
- **3 段階の意味付け**: `ignore` < `invalidate` < `new_record` の順で歴史化が
  強くなる。デフォルトの `ignore` は「raw から消えたら snapshot にも痕跡を残さない」
  という設計判断 (歴史を持たない方を選ぶケース、軽量化)。`new_record` は
  「source からの完全消失を許さない」最も保守的な設計。
- **`dbt_is_deleted` のクエリ作法**: `WHERE dbt_is_deleted = false` で「過去の
  実存データ」、`WHERE dbt_is_deleted = true` で「削除イベントログ」、`WHERE
  dbt_valid_to IS NULL` で「現在の最新状態 (削除済み含む)」とフィルタを使い分ける。
  point-in-time クエリ (7-6) では `WHERE dbt_is_deleted = false AND dbt_valid_from
  <= as_of < ...` で「その時点で生きていた行」を取り出す。
- **dbt 1.9 機能の運用注意**: 既存 snapshot に後から `hard_deletes` を足すと、
  既存行に `dbt_is_deleted` 列が NULL で追加されるだけ。**過去の削除は遡及できない**
  (snapshot を作る前に消された行はどうにも復元できない)。新規プロジェクトで
  最初から有効にしておくか、既存プロジェクトでは「ここから先は削除も歴史にする」
  と運用上で線引きする。
- **設計判断の問い**: 「source からの削除が起きたとき、業務上どこまで遡って
  履歴が必要か」を最初に決める。マスタ系 (顧客・商品) は `new_record` 推奨、
  巨大ログ系は `ignore` で行数爆発を回避、など。
