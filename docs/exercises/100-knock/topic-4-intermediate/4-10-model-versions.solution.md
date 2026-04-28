# 4-10 解答例

## dbt/models/100-knock/topic-4/int_order_details_100knock.sql (v1, 4-1 から変更なし)

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (orders を主軸に master 3 本を INNER JOIN で enrich)。
-- このファイルは int_order_details_100knock の v1 (税抜のみ)。
-- v2 は int_order_details_100knock_v2.sql で並走 (4-10 演習)。
select
    o.order_id,
    o.order_date,
    o.customer_id,
    c.customer_name,
    o.product_id,
    p.product_name,
    p.category,
    o.store_id,
    o.quantity,
    o.unit_price,
    (o.quantity * o.unit_price)::numeric(14, 2) as sales_amount
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

## dbt/models/100-knock/topic-4/int_order_details_100knock_v2.sql (v2, 新規作成)

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (v1 と同じ grain)。
-- v2 で追加した変更点: 税込金額列 sales_amount_with_tax (10% 固定) を追加。
-- v1 と並走: 既存 mart は v=1、新規 mart のみ v=2 を参照する段階移行設計。
-- 税率を可変にするなら calc_tax macro (4-6) を呼び出す形に置き換え可。
select
    o.order_id,
    o.order_date,
    o.customer_id,
    c.customer_name,
    o.product_id,
    p.product_name,
    p.category,
    o.store_id,
    o.quantity,
    o.unit_price,
    (o.quantity * o.unit_price)::numeric(14, 2)              as sales_amount,
    (o.quantity * o.unit_price * 1.10)::numeric(14, 2)       as sales_amount_with_tax
from {{ ref('stg_orders_100knock') }}    as o
inner join {{ ref('stg_customers_100knock') }} as c on o.customer_id = c.customer_id
inner join {{ ref('stg_products_100knock') }}  as p on o.product_id  = p.product_id
inner join {{ ref('stg_stores_100knock') }}    as s on o.store_id    = s.store_id
```

**ポイント**:

- **v1 と v2 は 90% 同じ SQL**: 違いは `sales_amount_with_tax` 列の有無のみ。これが
  「**最小差分での schema 進化**」 の見本。後で v3 を切るなら同じパターンで
  `_v3.sql` を追加するだけ。
- **冒頭コメントで「何が変わったか」を明記**: `v2 で追加した変更点: ...` の 1 行が
  半年後の自分への手紙。SQL 差分だけ見ても「何が意図されたか」 は読み取れない。
- **v1 を一切編集しない**: 既存 mart が v1 を ref しているので、v1 を変更すると
  既存 mart の挙動が変わる。schema 進化の鉄則は「**v1 は不変**」。

## dbt/models/100-knock/topic-4/schema.yml (`versions:` ブロックを追加)

```yaml
version: 2

models:
  - name: int_order_details_100knock
    description: |
      Grain: 1 row = 1 order_id。stg_orders_100knock を主軸に customers / products /
      stores の master 3 本を INNER JOIN し、sales_amount を算出した中間モデル。
      v2 で sales_amount_with_tax 列を追加 (税込金額)。既存 mart は v=1 のまま、
      新規 mart は v=2 を参照する段階移行設計。
    latest_version: 2
    columns:
      - name: order_id
        description: "Primary key (= grain key)。v1/v2 共通。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date)。v1/v2 共通。"
        tests:
          - not_null
      - name: customer_id
        description: "FK to stg_customers_100knock.customer_id。v1/v2 共通。"
        tests:
          - not_null
      - name: customer_name
        description: "顧客名。v1/v2 共通。"
      - name: product_id
        description: "FK to stg_products_100knock.product_id。v1/v2 共通。"
        tests:
          - not_null
      - name: product_name
        description: "商品名。v1/v2 共通。"
      - name: category
        description: "商品カテゴリ。v1/v2 共通。"
      - name: store_id
        description: "FK to stg_stores_100knock.store_id。v1/v2 共通。"
        tests:
          - not_null
      - name: quantity
        description: "注文数量 (integer)。v1/v2 共通。"
        tests:
          - not_null
      - name: unit_price
        description: "商品単価 (numeric(10,2))。v1/v2 共通。"
        tests:
          - not_null
      - name: sales_amount
        description: "売上金額 (税抜, numeric(14,2)) = quantity * unit_price。v1/v2 共通。"
        tests:
          - not_null
      - name: sales_amount_with_tax
        description: "売上金額 (税込, numeric(14,2)) = sales_amount * 1.10。**v2 で追加**。"
        # version 固有 column の test は version ブロック内で定義 (v1 にはこの列が無いので
        # ここで test を書くと parse が落ちる)。

    versions:
      - v: 1
        defined_in: int_order_details_100knock   # ファイル名と version のマッピングを明示
        columns:
          - name: order_id
          - name: order_date
          - name: customer_id
          - name: customer_name
          - name: product_id
          - name: product_name
          - name: category
          - name: store_id
          - name: quantity
          - name: unit_price
          - name: sales_amount
      - v: 2
        # defined_in 省略 → デフォルトで int_order_details_100knock_v2.sql が使われる
        columns:
          - name: order_id
          - name: order_date
          - name: customer_id
          - name: customer_name
          - name: product_id
          - name: product_name
          - name: category
          - name: store_id
          - name: quantity
          - name: unit_price
          - name: sales_amount
          - name: sales_amount_with_tax
            tests:
              - not_null
```

**ポイント**:

- **`latest_version: 2`**: 「version 指定なしの `{{ ref('int_order_details_100knock') }}` は v2 を返す」 を宣言。下流 mart が `v=` 引数なしで参照すると新版 (v2) に流れる。安全寄りなら `latest_version: 1` のままにして、新規 mart のみ明示的に `v=2` を指定する設計もある。
- **トップレベル `columns:`** = **両 version で共通の column メタ**。`order_id` の test (not_null + unique) は v1/v2 両方に適用される。共通 description のおかげで version ブロックでの重複記述を避けられる。
- **v1 / v2 ブロックの `columns:`**: その version に**含まれる列名のリスト** を宣言。トップレベルにある共通 column メタを継承しつつ、各 version で **どの列を持つか** を明示。
- **`defined_in: int_order_details_100knock`**: v1 のファイル名が `_v1` suffix 無しなので明示。これが無いと dbt は `int_order_details_100knock_v1.sql` を探して FileNotFound になる。
- **`sales_amount_with_tax` の test**: トップレベルではなく **v2 ブロック内** で `tests: [not_null]` を書く。v1 にはこの列が存在しないので、トップレベルに書くと「v1 で `sales_amount_with_tax` 列が無い」 エラーで落ちる。

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
04:31:00  Found 12 models, 5 sources, ...

$ ../.venv/bin/dbt ls --select int_order_details_100knock --profiles-dir .
local_analytics.intermediate.int_order_details_100knock.v1
local_analytics.intermediate.int_order_details_100knock.v2

$ ../.venv/bin/dbt build --select int_order_details_100knock --profiles-dir .
04:31:10  1 of 4 START sql view model intermediate.int_order_details_100knock_v1 [RUN]
04:31:10  1 of 4 OK created sql view model intermediate.int_order_details_100knock_v1 [CREATE VIEW in 0.10s]
04:31:11  2 of 4 START sql view model intermediate.int_order_details_100knock_v2 [RUN]
04:31:11  2 of 4 OK created sql view model intermediate.int_order_details_100knock_v2 [CREATE VIEW in 0.11s]
04:31:11  3 of 4 START test not_null_int_order_details_100knock_v1_order_id [RUN]
04:31:11  3 of 4 PASS  not_null_int_order_details_100knock_v1_order_id ... [PASS]
04:31:11  4 of 4 START test unique_int_order_details_100knock_v1_order_id [RUN]
04:31:11  4 of 4 PASS  unique_int_order_details_100knock_v1_order_id ..... [PASS]
04:31:12  Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

物理化された 2 つの view を確認:

```bash
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c "
\dt intermediate.int_order_details_100knock*
\dv intermediate.int_order_details_100knock*
"
                       List of relations
    Schema      |              Name              | Type | Owner
----------------+--------------------------------+------+-------
 intermediate   | int_order_details_100knock_v1  | view | dbt_user
 intermediate   | int_order_details_100knock_v2  | view | dbt_user
```

両 version が **別の物理 view** として並走している。下流 mart が v=1 と v=2 を選択して
ref できる状態。

## 採点 shell_command 視点

```bash
# v1 と v2 が manifest に存在することを確認
$ python3 -c "
import json
m = json.load(open('dbt/target/manifest.json'))
expected = ['model.local_analytics.int_order_details_100knock.v1',
            'model.local_analytics.int_order_details_100knock.v2']
for nid in expected:
    assert nid in m['nodes'], f'missing: {nid}'
    print('OK:', nid)
"

# dbt ls の出力に v1 / v2 両方が出ること
$ cd dbt && dbt ls --select int_order_details_100knock --profiles-dir . | grep -cE '\.v[12]$'
2
```

## 解説まとめ

- **なぜ model versions?**: schema 進化 (列追加 / 列削除 / 型変更) は実務で頻発するが、
  下流の挙動を壊さずに進めるのは難しい。**従来の解決策は「列を追加するだけ (削除しない)」
  + 「下流テストで壊れないことを確認」**。だがこれだと SQL がレガシー列で膨れ、
  「この列はもう使ってない」が分からなくなる。**model versions はこの問題を「v1 / v2 並走」
  で解決** する。v1 を deprecation period 中は維持、新規 mart は v2 を ref、頃合を見て
  v1 を削除、というライフサイクル管理が可能になる。
- **dbt 1.5+ の機能** (リリース時期): 2023 年春に追加された比較的新しい機能。
  Snowflake / Databricks の現場では既に標準ツールセット。Postgres ローカルでも
  dbt-core 1.5+ ならそのまま使える。
- **3 つの主要構文**:
  1. **`schema.yml` の `versions:`**: どの version が存在するか宣言
  2. **`<name>_v<N>.sql` ファイル命名**: version ごとに別ファイルで実装 (v1 だけ
     `defined_in:` で別命名も可能)
  3. **`{{ ref('name', v=N) }}`**: 下流が version 指定で参照
- **`latest_version` の戦略**: 2 通りの設計がある:
  - **新版を default にする (本演習)**: `latest_version: 2`。新規 mart は何も書かなくても v2 を
    使う。安全に進化させるなら、v1 を ref している既存 mart に明示的に `v=1` を
    書き加える migration が必要
  - **旧版を default に維持**: `latest_version: 1`。既存挙動は変わらない。新規 mart のみ
    `v=2` で明示参照。下位互換性を最重視
- **物理化されるテーブル名**: 各 version は **別の物理 view / table** として作られる
  (`<name>_v1`, `<name>_v2`)。同じ schema 内で名前衝突しない。`alias:` で物理名を
  カスタマイズも可能。
- **deprecation のライフサイクル例**:
  1. **Day 0**: v1 のみ存在
  2. **Day 30**: v2 を追加 (本演習の状態)。`latest_version: 1` のまま、新規 mart は v=2 を明示
  3. **Day 60**: 既存 mart を v=2 に移行、`latest_version: 2` に切替
  4. **Day 90**: 全 mart が v=2 を ref していることを `dbt ls --select +int_order_details_100knock.v1`
     で確認、ゼロなら v1 を削除 (schema.yml から v=1 ブロック削除 + `_v1.sql` ファイル削除)
- **テストの扱い**: トップレベル `columns:` の test は両 version に適用、version ブロック
  内の test はその version 固有。本演習では `sales_amount_with_tax` の test を v2 ブロック
  内に置いた (v1 にはこの列が無いので)。
- **下流からの参照方法**:
  - `{{ ref('int_order_details_100knock') }}` → `latest_version` (= 2) が解決される
  - `{{ ref('int_order_details_100knock', v=1) }}` → 明示的に v1
  - `{{ ref('int_order_details_100knock', v=2) }}` → 明示的に v2
  - 既存 mart の安定運用には `v=` 明示推奨 (latest 切り替え時に挙動が変わらない)
- **Topic ⑤ 5-10 との接続**: 5-10 で v=2 を参照する `mart_daily_sales_with_tax` を作る。
  「**上流 v1 → 旧 mart → 旧 exposure**」 と「**上流 v2 → 新 mart → 新 exposure**」 の
  二系統 DAG が並走する状態を体感する。これが本演習の真の到達点。
- **deprecation_date** (将来の自分への警告): version ブロックには
  `deprecation_date: 2026-12-31` を書くと dbt が「この version は X 日に deprecate されます」
  と warning を出してくれる。本演習では使わないが、実務での migration では必須機能。
- **schema 進化のベストプラクティス (dbt 流)**:
  1. **列追加** → v2 で追加、v1 は維持
  2. **列削除** → v2 で削除、v1 は維持して下流移行を促す
  3. **型変更** → v2 で型変更、v1 は維持 (型が変わると test 互換性が壊れるので version 必須)
  4. **意味変更** (例: 税抜 → 税込) → v2 で再定義、v1 は維持して旧定義を保護
  - **すべて「v1 は不変」** が共通の原則。schema migration をこの形式に統一すれば
    「壊さない進化」 が DAG レベルで管理できる。
