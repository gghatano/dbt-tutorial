# 5-10 解答例

## ゴール再掲

- `dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql` を新規作成
- `{{ ref('int_order_details_100knock', v=2) }}` で v2 (税込列付き) を参照
- 旧 `mart_daily_sales_100knock` (v1 系統) は削除せず並走
- `dbt build` で table 作成 → 税込列が税抜より大きいことを SQL で確認

## Step 1: `mart_daily_sales_with_tax_100knock.sql`

`dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql`:

```sql
{{ config(
    materialized='table',
    schema='marts'
) }}

-- mart_daily_sales_with_tax_100knock
-- ----------------------------------------------------------------------
-- Grain: 1 row per order_date.
-- Source: int_order_details_100knock v2 (Topic ④ 4-10 で版数分岐済み)。
-- v1 系統の mart_daily_sales_100knock (税抜) と並走させる。
--
-- 列契約 (informal):
--   order_date                   date           PK
--   order_count                  bigint
--   customer_count               bigint
--   total_quantity               bigint
--   total_sales_amount           numeric(18,2)  税抜売上 (v1 と同等の値)
--   total_sales_amount_with_tax  numeric(18,2)  税込売上 (v2 で追加された列を集計)
--   tax_amount                   numeric(18,2)  total_with_tax - total_amount
--
-- なぜ v2 を別 mart で消費するか:
--   - mart_daily_sales_100knock の contract: enforced (5-3) を壊さない
--   - exposure (5-5) を経由する既存 BI ダッシュボードを止めない
--   - 「税込が必要なチーム」だけが新 mart を ref()/select すればよい
-- ----------------------------------------------------------------------

select
    order_date,
    count(*)                               as order_count,
    count(distinct customer_id)            as customer_count,
    sum(quantity)                          as total_quantity,
    sum(sales_amount)::numeric(18, 2)      as total_sales_amount,
    sum(sales_amount_with_tax)::numeric(18, 2) as total_sales_amount_with_tax,
    (sum(sales_amount_with_tax) - sum(sales_amount))::numeric(18, 2) as tax_amount
from {{ ref('int_order_details_100knock', v=2) }}
group by order_date
order by order_date
```

> Topic ④ 4-10 で `int_order_details_100knock` v2 が `unit_price_with_tax` / `sales_amount_with_tax` の 2 列を追加して持つ前提。列名が違う場合は v2 の実装に合わせて修正。

### `schema.yml` への登録 (任意)

`dbt/models/100-knock/topic-5/schema.yml` に追記:

```yaml
  - name: mart_daily_sales_with_tax_100knock
    description: |
      日次売上マート (税込含む)。grain = 1 order_date 1 row。
      int_order_details_100knock v2 (Topic ④ 4-10) を参照。
      旧 mart_daily_sales_100knock と並走する v2 系統 mart。
    columns:
      - name: order_date
        tests: [not_null, unique]
      - name: total_sales_amount
        tests: [not_null]
      - name: total_sales_amount_with_tax
        description: "税込売上 (税率は int v2 側で計算)"
        tests: [not_null]
      - name: tax_amount
        description: "total_sales_amount_with_tax - total_sales_amount"
        tests: [not_null]
```

## Step 2: parse / build

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# 23:10:01  Found 13 models, 4 sources, ...

../.venv/bin/dbt build --select mart_daily_sales_with_tax_100knock --profiles-dir .
# 23:10:11  1 of 1 START sql table model marts.mart_daily_sales_with_tax_100knock ... [RUN]
# 23:10:12  1 of 1 OK created sql table model marts.mart_daily_sales_with_tax_100knock ... [SELECT 31 in 0.30s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1
```

## Step 3: 旧 / 新 mart 共存確認

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -c \
  "\dt marts.mart_daily_sales*"
#                List of relations
#  Schema |              Name              | Type  |  Owner
# --------+--------------------------------+-------+----------
#  marts  | mart_daily_sales_100knock      | table | dbt_user
#  marts  | mart_daily_sales_with_tax_100knock | table | dbt_user
```

両方ある = 並走成功。

## Step 4: 税込 > 税抜 を SQL で確認

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
SELECT
  order_date,
  total_sales_amount,
  total_sales_amount_with_tax,
  tax_amount
FROM marts.mart_daily_sales_with_tax_100knock
ORDER BY order_date
LIMIT 5;
SQL
#  order_date | total_sales_amount | total_sales_amount_with_tax | tax_amount
# ------------+--------------------+-----------------------------+------------
#  2026-04-01 |          120000.00 |                   132000.00 |   12000.00
#  2026-04-02 |          135000.00 |                   148500.00 |   13500.00
#  ...
```

`tax_amount > 0` が全行成立。

## Step 5: DAG 可視化 (任意)

```bash
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve --port 8080 --profiles-dir .
# Lineage タブで mart_daily_sales_with_tax_100knock を選択:
# stg_orders_100knock --+-> int_order_details_100knock (v1) -> mart_daily_sales_100knock
# stg_customers_100knock |
# stg_products_100knock  +-> int_order_details_100knock_v2  -> mart_daily_sales_with_tax_100knock  ← 本問で追加
# stg_stores_100knock    |
```

二系統 DAG が見える。

## Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-10-mart-version-parallel.grading.yaml
```

期待:

```
## Grading Result: OK (100%)
| OK | mart-sql-exists                    | 15/15 |
| OK | sql-uses-v2-ref                    | 20/20 |
| OK | dbt-parse-success                  | 10/10 |
| OK | manifest-node-exists               | 15/15 |
| OK | dbt-build-mart-success             | 20/20 |
| OK | tax-column-greater-than-amount     | 15/15 |
| OK | old-mart-still-exists              | 5/5   |
```

## ポイント

- **`ref('xxx', v=2)` の意味**: dbt は `int_order_details_100knock_v2` という別物理 model を作っている (4-10 で `versions:` ブロックを書いたため)。`v=2` を付けると `_v2` 物理 model に解決される。`v=` 省略すると `latest_version:` (4-10 で宣言) または最初の `versions:` エントリに解決。
- **`v=` を付け忘れると旧 mart と同じになる**: もし本問の SQL で `{{ ref('int_order_details_100knock') }}` (v 指定なし) と書いてしまうと、`sales_amount_with_tax` 列が見つからずビルドエラー (= v1 デフォルトには無い列)。明示の `v=2` で v2 を引く。
- **「税抜 → 税込」の業務変更を扱うパターン**:
  1. **同 model 内で計算追加** (NG): `mart_daily_sales_100knock` に `total_sales_amount_with_tax` 列を足す → contract: enforced (5-3) が違反 → BI dashboard が壊れる
  2. **新列を contract に足す** (副作用大): `data_type:` を schema.yml で追加 → BI 側が `SELECT *` で取得しているなら影響なしだが、列順を期待しているクエリがあると壊れる
  3. **新 mart を作る** (本問): 旧 mart はそのまま、新 mart を別名で並走 → 旧 BI は止まらず、新 BI が新 mart を ref できる
  - **3 が dbt 1.5+ における正解**。version + 並走 mart で「壊さない進化」を実現。
- **「version は型 (schema)、新 mart は使い方」**:
  - `int_order_details_100knock` v2 = **schema の version** (列が増えた)
  - `mart_daily_sales_with_tax_100knock` = **使い方の version** (税込で集計するという業務ルール)
  - 「schema が変わった = 必ず新 mart が要る」ではない (v1 も v2 も両方使う mart があってもよい)。だが本問のように「新列を意味的に活かす mart」があると、二系統 DAG が綺麗に見える。
- **旧 mart 削除のタイミング**: BI 側 (5-5 の exposure) が新 mart を `depends_on:` に切り替えた **後**。`dbt ls --select +exposure:foo_dashboard` で「ダッシュボードが現在依存している mart 一覧」を確認し、新 mart に切り替わっていれば旧 mart の `materialized: ephemeral` 化 → 削除、と段階を踏む。

## 実行例 (採点 shell_command 視点)

```bash
$ test -f dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql && echo OK
OK

$ grep -E "ref\('int_order_details_100knock',\s*v\s*=\s*2\)" \
    dbt/models/100-knock/topic-5/mart_daily_sales_with_tax_100knock.sql
from {{ ref('int_order_details_100knock', v=2) }}

$ cd dbt && dbt build --select mart_daily_sales_with_tax_100knock --profiles-dir . 2>&1 | tail -3
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA -c \
    "SELECT count(*)::int FROM marts.mart_daily_sales_with_tax_100knock
       WHERE total_sales_amount_with_tax > total_sales_amount;"
31    # 全行で税込 > 税抜 (期待通り)
```

## 解説まとめ

- **なぜ「v2 を作る」と「v2 を消費する」を別問題に？**: schema 進化の責務は **上流 model** (int v2 を作る人 = 4-10 の課題) と、その新 schema を活かす **下流 mart** (本問) に分かれる。両者を 1 PR に詰め込むと巨大な diff になり、レビューしにくい。実運用でも「上流チームが v2 を切る → 下流チームが新 mart で消費」という時系列で進む。
- **二系統 DAG の意味**: lineage が「単一の正解 DAG」ではなく「**移行期の二系統**」になる。これは過渡的状態だが、健全。両方を `dbt build` で test まで通せば、移行期間中も品質は守られる。
- **`{{ ref('xxx', v=2) }}` の表記力**: `ref()` 1 つで「どの version を使っているか」が SQL に明示される。grep で「v=2 を ref している model 一覧」を出せるので、移行追跡 (= どの mart が v2 に乗り換え済みか) が機械的にできる。
- **contract: enforced との連携**: 5-3 で `mart_daily_sales_100knock` に contract を付けたから、本問で「旧 mart は変えない」が必須になる。contract を付けていなければ「旧 mart に税込列を足す」誘惑に負けてしまうかもしれない。**contract → 新 mart 強制 → 段階移行設計** の流れが Topic ⑤ の設計の核。
- **Topic ⑤ 総仕上げとしての位置づけ**: 5-1 (grain) / 5-2 (複合 PK) / 5-3 (contract) / 5-5 (exposure) / 5-6 (grants) / 5-7 (groups) / 5-8 (meta) / 5-9 (expectations) で揃えてきた「mart の宣言 6 点セット」を、本問の新 mart (`mart_daily_sales_with_tax_100knock`) でも同様に整備すれば、Topic ⑤ 完了後の到達点 (= 「新 mart を反射的に揃えられる」) を実証できる。
- **Topic ⑥ 以降への接続**: snapshot (Topic ⑦) で「過去のある時点の税率を再現」したくなる動機は、本問の二系統 DAG から自然に出てくる。「税率が `1.10` から `1.12` に変わったら、過去の注文の税込再計算はどうする？」 → snapshot で時間軸を持つ、という流れ。

## 拡張アイデア

- **5-7 の `groups:` を本 mart にも付ける**: `mart_daily_sales_with_tax_100knock` を `marts_finance` group に所属させ、`access: protected` で「marketing は見ない、finance だけ」を表現
- **5-5 の exposure を新 mart 用に追加**: `mart_daily_sales_with_tax_dashboard` を `exposures.yml` に新規宣言し、`depends_on: [ref('mart_daily_sales_with_tax_100knock')]` で BI 依存を明示
- **旧 mart 廃止 PR を書いてみる**: 全 exposure が新 mart に切り替わったと仮定し、`mart_daily_sales_100knock.sql` を delete して `dbt parse` する。下流参照が残っていれば error になる。エラー数 = 移行残作業
- **v2 → v3 への進化**: `int_order_details_100knock` v3 を「軽減税率対応」で作る場合、本問と同じ要領で `mart_daily_sales_reduced_tax_100knock` を新規追加。三系統 DAG になる
- **contract: enforced を新 mart にも付ける**: `mart_daily_sales_with_tax_100knock` の `schema.yml` に `contract: enforced` + `data_type:` を宣言し、税込列の型まで対外契約化
