# 7-1 解答例

## Step 0: snapshots schema を作成

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -c "CREATE SCHEMA IF NOT EXISTS snapshots AUTHORIZATION dbt_user;"
# CREATE SCHEMA
```

`AUTHORIZATION dbt_user` で owner を dbt_user にしておくと、その後 dbt が
自由に CREATE TABLE / INSERT できる。これを忘れると `permission denied for
schema snapshots` で 1 回目の `dbt snapshot` が落ちる。

## dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql

```sql
{% snapshot snap_products_100knock %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='check',
        check_cols=['unit_price'],
    )
}}

-- 100-knock Topic ⑦ Q1: products の価格履歴を SCD Type-2 で残す。
-- raw_100knock.products は raw 物理テーブルを直接 source 宣言したもの。
-- 物理上は同じ raw.products テーブルだが、dbt 上の論理 source 名は raw_100knock。
select
    product_id,
    product_name,
    category,
    unit_price
from {{ source('raw_100knock', 'products') }}

{% endsnapshot %}
```

**ポイント**:

- **ファイル名 = snapshot 名 = `snap_products_100knock`**: dbt の慣習として
  ファイル名と `{% snapshot <name> %}` の名前を揃える。manifest 上は
  `snapshot.local_analytics.snap_products_100knock` という node id で参照される。
- **`target_schema='snapshots'`**: 本リポジトリの `dbt/macros/get_custom_schema.sql`
  が `generate_schema_name` を override して `custom_schema_name` をそのまま返すので、
  結果的に `snapshots` schema に物理化される。標準 dbt 挙動だと `<target>_snapshots`
  (例: `dev_snapshots`) になっていた。
- **`unique_key='product_id'`**: 「行同一性」の宣言。snapshot は次回実行時に
  「同じ product_id の行が source 側にあるか?」を見て履歴を判断する。
- **`strategy='check'` + `check_cols=['unit_price']`**: source 側の `unit_price`
  が変わったら「歴史を切る」(旧行に `dbt_valid_to` を入れて新行を INSERT)。
  category や product_name が変わっても無視される。**追跡したい列を最小限に
  絞る** のが運用上の鉄則 (無駄な履歴爆発を防ぐ)。
- **SELECT の列限定**: `select *` でなく明示列を書くと、source 側に列追加が
  あった時に snapshot が **意図せず変化検知してしまう事故** を防げる。
- **MVP との衝突回避**: `_100knock` suffix で名前空間を切ることで、Ex.04 の
  `snap_products` (もし存在していても) と並走できる。

## Step 2: 実行ログ例

```text
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
14:30:01  Running with dbt=1.11.x
14:30:01  Registered adapter: postgres=1.x.x
14:30:01  Found 1 snapshot, ...
14:30:02  Concurrency: 4 threads (target='dev')
14:30:02
14:30:02  1 of 1 START snapshot snapshots.snap_products_100knock ........ [RUN]
14:30:02  1 of 1 OK snapshotted snapshots.snap_products_100knock ........ [SELECT 100 in 0.12s]
14:30:02
14:30:02  Finished running 1 snapshot in 0 hours 0 minutes and 0.45 seconds.
14:30:02  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

`SELECT 100` が「100 行を新規 INSERT した」意味。1 回目なので全行が新規。

## Step 3: 物理確認

```sql
analytics=> SELECT count(*) AS total,
                  count(*) FILTER (WHERE dbt_valid_to IS NULL) AS active
            FROM snapshots.snap_products_100knock;
 total | active
-------+--------
   100 |    100

analytics=> SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to, dbt_scd_id
            FROM snapshots.snap_products_100knock LIMIT 3;
 product_id | unit_price |   dbt_valid_from    | dbt_valid_to |            dbt_scd_id
------------+------------+---------------------+--------------+----------------------------------
          1 |    1240.00 | 2026-04-26 14:30:02 |              | 8e1f7c...32f
          2 |    8520.00 | 2026-04-26 14:30:02 |              | 47b29a...c01
          3 |     230.00 | 2026-04-26 14:30:02 |              | a3e5d8...b6f
```

- `dbt_valid_to` は全 100 行で NULL = 「最新行」を意味する規約
- `dbt_valid_from` は snapshot 実行時刻
- `dbt_scd_id` は (`unique_key` + `dbt_valid_from`) からの hash で snapshot が
  自動生成。Type-2 行の物理 PK として使える

## 解説まとめ

- **snapshot は時間軸の同一性宣言**: 「unique_key で同一性が決まる行が、いつから
  いつまで `check_cols` の値だったか」を SCD Type-2 で記録する。これは「raw が
  上書きで歴史を失う問題」への dbt 流の処方箋。
- **check vs timestamp の選択軸**: `check` は source の素性を問わない汎用解
  (任意列の値変化を検知)。`timestamp` は source に `updated_at` などの
  「更新時刻列」があれば 1 列の比較で済むので高速。本問は raw に時刻列が
  無いので `check` 一択 (7-3 で `timestamp` 版を別途作って比較する)。
- **schema 事前作成の必然性**: snapshot は `CREATE TABLE snapshots.<name>` を
  実行するので、対象 schema が **存在し、かつ dbt_user が CREATE 権限を持つ**
  必要がある。Terraform が作っていない schema は手動 CREATE が要る。Production
  では Terraform に追加するか、`on-run-start` hook で `CREATE SCHEMA IF NOT EXISTS`
  を流す設計に進化させる (運用近接の発展課題)。
- **macro override との相性**: 本リポジトリの `get_custom_schema.sql` が
  `custom_schema_name` を透過するので、`target_schema='snapshots'` が **本当に
  `snapshots` schema** になる。標準 dbt なら `<target>_snapshots` (target が
  `dev` なら `dev_snapshots`) になっていたはず。ADR-0005 の override がここで
  きれいに効いている。
- **dbt 上の管理対象が増える**: snapshot は model でも seed でも test でもない
  独立 node 種別 (`snapshot.<project>.<name>`)。`dbt run` には含まれず
  `dbt snapshot` で別コマンドとして実行する (`dbt build` には含まれる)。
  運用上は「raw 投入 → snapshot → run → test」の順で回すのが定石。
