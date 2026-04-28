# 5-3 解答例

## dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql

```sql
{{ config(
    materialized='table',
    schema='marts',
    contract={'enforced': true}
) }}

-- ============================================================================
-- mart_daily_sales_100knock
-- ----------------------------------------------------------------------------
-- grain          : 1 order_date 1 row.
-- contract       : enforced (dbt 1.5+).
--                  全 5 列の data_type を schema.yml で宣言済み。
--                  SQL の cast と schema.yml の data_type が一致しない場合は
--                  dbt run が "Contract Error" で fail する。
-- consumers      : Metabase "Daily Sales" dashboard (declared in 5-5 exposure).
-- upstream       : int_order_details_100knock
-- ============================================================================

select
    order_date::date                         as order_date,
    count(*)::bigint                         as order_count,
    count(distinct customer_id)::bigint      as customer_count,
    sum(quantity)::bigint                    as total_quantity,
    sum(sales_amount)::numeric(18, 2)        as total_sales_amount
from {{ ref('int_order_details_100knock') }}
group by order_date
order by order_date
```

**ポイント**:

- **`config(contract={'enforced': true})`**: これだけで「この model は schema.yml
  の `columns:` 宣言と SQL の出力列構成が完全一致しないと build fail」と
  なる。`true` 以外に `false` (= 未宣言と同じ) も書ける。
- **全列に明示 cast**: `count(*)::bigint`, `sum(...)::numeric(18,2)` のように
  右辺で cast する。これを書かないと、Postgres の集計関数が返す自然型
  (`bigint`, `numeric` precision なし) と schema.yml の `data_type:` が
  不一致になって `unverified contract` 警告が出る。
- **冒頭コメントで `contract: enforced` を宣言**: 「この mart は build 時に
  型が検証される」ことを SQL の冒頭で人間にも伝える。schema.yml を見ない
  人 (= ほぼ全員) のための保険。
- **`order by order_date` を最後に**: table 物理化なので意味はないが、
  catalog 確認時に見やすい。

## dbt/models/100-knock/topic-5/schema.yml (mart_daily_sales_100knock 部分)

```yaml
version: 2

models:
  # ... (5-1 / 5-2 の mart も同居)

  - name: mart_daily_sales_100knock
    config:
      contract:
        enforced: true
    description: |
      Daily sales mart with enforced column contract.
      One row per order_date. All columns have data_type declared, so
      `dbt run` fails with Contract Error if SQL output schema diverges.
    columns:
      - name: order_date
        data_type: date
        description: "Calendar date of orders. Primary key."
        tests:
          - not_null
          - unique
      - name: order_count
        data_type: bigint
        description: "Number of orders on this date."
        tests:
          - not_null
      - name: customer_count
        data_type: bigint
        description: "Distinct customers placing an order on this date."
        tests:
          - not_null
      - name: total_quantity
        data_type: bigint
        description: "Sum of quantity on this date."
        tests:
          - not_null
      - name: total_sales_amount
        data_type: numeric(18,2)
        description: "Sum of sales_amount on this date. numeric(18,2) for downstream BI safety."
        tests:
          - not_null
```

**ポイント**:

- **`config: contract: enforced: true` は schema.yml 側にも書ける**:
  SQL 側の `config()` と schema.yml 側の `config:` のどちらか、もしくは両方に
  書く。両方書くなら値は揃える。本問は SQL 側にも書いてある (二重宣言で
  読み手が分かりやすいよう)。
- **全列に `data_type:` を必須**: 1 列でも `data_type:` がないと、その列は
  contract から除外されてしまう。「全部書く or 何も書かない」 の二択。
- **Postgres 型の表記揺れに注意**:
  - `bigint` ≡ `int8`
  - `integer` ≡ `int4` (`bigint` とは別物！)
  - `numeric(18, 2)` ≡ `numeric(18,2)` (空白は無視される)
  - `text` ≡ `varchar` (Postgres は alias 同一視するが、dbt 1.5 では厳密マッチが
    必要なケースあり。1.6+ で `alias_types: true` がデフォルト化されて緩和)
- **MVP の `mart_daily_sales` には contract を付けていない**: MVP は教材の
  ベースラインを最小に保つため、contract は本問で初めて学ぶ。
  `mart_daily_sales_100knock` は MVP と並走する別 node なので影響なし。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
$ ../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock
04:31:10  Concurrency: 1 threads (target='dev')
04:31:10  1 of 1 START sql table model marts.mart_daily_sales_100knock ... [RUN]
04:31:10  1 of 1 OK   created sql table model marts.mart_daily_sales_100knock [in 0.20s]
04:31:10  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select mart_daily_sales_100knock
04:31:20  PASS not_null_mart_daily_sales_100knock_order_date ...
04:31:20  PASS unique_mart_daily_sales_100knock_order_date   ...
04:31:20  Done. PASS=6 WARN=0 ERROR=0 SKIP=0 TOTAL=6
```

`unverified contract` 警告が出ていないことを確認。

manifest 側の確認:

```bash
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.mart_daily_sales_100knock']
print('contract:', node['config'].get('contract'))
print('columns data_types:')
for col, meta in node['columns'].items():
    print(f'  {col}: {meta.get(\"data_type\")}')
"
contract: {'enforced': True, 'alias_types': True, 'checksum': '...'}
columns data_types:
  order_date: date
  order_count: bigint
  customer_count: bigint
  total_quantity: bigint
  total_sales_amount: numeric(18,2)
```

`contract.enforced=True` と全 5 列に data_type が並んでいれば成功。

## 解説まとめ

- **なぜ contract: enforced か**: mart は **dbt の世界が外と接続する境界面**。
  内部 (intermediate / staging) なら列名や型が変わっても dbt 内部の調整で済むが、
  mart の列を消したり型を変えたりすると、Metabase ダッシュボード / CSV
  エクスポートを使うアナリスト / ML 特徴量パイプラインが順番に壊れる。
  contract は「壊す変更を build 時に止める」最後の砦。
- **なぜ `dbt test` ではなく `dbt run` で fail するのか**:
  `dbt test` は「物理化されたデータが契約に合っているか」を見る。contract は
  「これから物理化しようとしている SQL のスキーマが宣言と合っているか」を見る。
  build 前に止めるからこそ、壊れたデータが BI 側に出る前に防御できる。
- **data_type を書くコストとリターン**: 全列に `data_type:` を書くのは確かに
  手間。しかしそのコストは「mart 1 個あたり 5 行の YAML」程度で、リターンは
  「6 ヶ月後に誰かが SQL の cast を消した瞬間に CI red」 という巨大な安全網。
  **mart は技術的契約を持つべきレイヤー**であることが学べる回。
- **alias_types とは**: dbt 1.6+ で `bigint` と `int8` のような Postgres alias を
  同一視する自動マッチング機能。デフォルト on。1.5 では厳密マッチなので、
  alias を使い分けると `unverified contract` 警告で気付ける。
- **次の 5-4 への接続**: 本問で contract を立てた後、5-4 では「わざと型を
  壊す PR」を作って Contract Error が出ることを実体験する。型契約が机上の
  空論ではなく **実際に build を止める強さ**を持つことを身体で学ぶ流れ。
