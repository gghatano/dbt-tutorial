# Exercise 05: 都道府県マスタを seed 化、共通 macro 作成

## シナリオ

業務部門から「店舗を地方区分（関東・関西・中部…）でも見たい」と要望が来た。既存の `stg_stores.prefecture` には都道府県名（"東京都" 等）しか無い。Excel で渡された 47 都道府県 → 地方区分の対応表を、dbt seed として管理して、SQL で安全に JOIN できるようにする。

ついでに、staging で頻発する `column::numeric(14,2)` のような型キャストを **共通 macro** にして、書き直しやすくする練習も行う。

## 学べること

- `dbt seed` の基本（CSV ファイルを dbt 管理下のテーブルに昇格）
- `seeds:` 設定（schema, column_types など）
- `dbt/macros/` で jinja macro を定義
- `ref()` で seed を参照（source を介さない）

## 前提

- main HEAD 完了状態
- Exercise 01〜04 とは独立

## 入力データ

CSV は学習者が自分で書く（または解答例の CSV をコピペ）。47 都道府県 × 2 列（`prefecture`, `region`）の小さい表。

```
prefecture,region
北海道,北海道
青森県,東北
岩手県,東北
...
東京都,関東
神奈川県,関東
...
沖縄県,九州
```

## 課題

### Step 1: seed CSV を作成

`dbt/seeds/exercises/prefectures.csv` を新規作成。47 行 + ヘッダ。区分の例:

| region | prefectures |
|---|---|
| 北海道 | 北海道 |
| 東北 | 青森・岩手・宮城・秋田・山形・福島 |
| 関東 | 茨城・栃木・群馬・埼玉・千葉・東京・神奈川 |
| 中部 | 新潟・富山・石川・福井・山梨・長野・岐阜・静岡・愛知 |
| 関西 | 三重・滋賀・京都・大阪・兵庫・奈良・和歌山 |
| 中国 | 鳥取・島根・岡山・広島・山口 |
| 四国 | 徳島・香川・愛媛・高知 |
| 九州 | 福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄 |

（学習者の解釈は自由。沖縄を「沖縄」として独立させる流派もある。解答例は「沖縄→九州」で統一。）

### Step 2: `seeds:` 設定

`dbt/dbt_project.yml` に直接追記したいところだが、既存ファイルは触らない方針なので、seed の `+schema:` は **CSV ファイル自身に対して seed のローカルコンフィグ** として書く方法もある。簡単に済ませるなら `dbt seed` のデフォルト挙動（target schema = `staging`）に任せ、`schema='staging'` または `'seeds'` を明示。

ヒント: `dbt/seeds/exercises/_seeds.yml` を作って:

```yaml
version: 2

seeds:
  - name: prefectures
    description: "47 都道府県 → 地方区分マスタ。"
    config:
      schema: staging
      column_types:
        prefecture: text
        region: text
    columns:
      - name: prefecture
        tests:
          - not_null
          - unique
      - name: region
        tests:
          - not_null
          - accepted_values:
              arguments:
                values: [北海道, 東北, 関東, 中部, 関西, 中国, 四国, 九州]
```

### Step 3: seed をロード

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt seed --profiles-dir . --select prefectures
```

完了の見え方:

- `staging.prefectures` が 47 行
- `dbt test --select prefectures` で `not_null` / `unique` / `accepted_values` が PASS

### Step 4: macro `cast_jpy` を書く

`dbt/macros/exercises/cast_jpy.sql`:

```jinja
{% macro cast_jpy(column) %}
    {{ column }}::numeric(14, 2)
{% endmacro %}
```

これを使うと、staging 等で `cast_jpy('unit_price')` と書くだけで `unit_price::numeric(14, 2)` に展開される。

### Step 5: マートで seed と macro を使う

`dbt/models/exercises/05/mart_regional_sales.sql`:

```sql
{{ config(materialized='table', schema='marts') }}

select
    pref.region,
    count(distinct iod.store_id)        as store_count,
    sum(iod.quantity)                   as total_quantity,
    {{ cast_jpy('sum(iod.sales_amount)') }} as total_sales_amount
from {{ ref('int_order_details') }} iod
inner join {{ ref('stg_stores') }}    s    on iod.store_id   = s.store_id
inner join {{ ref('prefectures') }}   pref on s.prefecture   = pref.prefecture
group by pref.region
order by total_sales_amount desc
```

…のような書き方を **自分で考える**。要件:

- `int_order_details` を起点に、`stg_stores.prefecture` を `prefectures` seed で region に変換
- region 単位で `count`, `sum(quantity)`, `sum(sales_amount)` を集計
- macro `cast_jpy` を 1 箇所以上で使う
- materialization は table

### Step 6: 実行

```bash
../.venv/bin/dbt run --profiles-dir . --select mart_regional_sales
../.venv/bin/dbt test --profiles-dir . --select mart_regional_sales
```

## 完了条件

- [ ] `dbt seed --select prefectures` が成功し、`staging.prefectures` が 47 行
- [ ] `dbt run --select mart_regional_sales` が成功
- [ ] `marts.mart_regional_sales` が 1〜8 行（生成データに登場する地方の数だけ。MVP のダミーデータは 20 都道府県のうちサンプリングなので、登場する region は 8 種類より少ない）
- [ ] `cast_jpy` macro を 1 箇所以上で使い、SQL が `compiled/` 配下で正しく `numeric(14, 2)` に展開されている

## ヒント（詰まったら）

- **47 都道府県全部書くのが面倒**: 解答例にコピペ用 CSV 全文あり。
- **seed の schema が変な所に作られる**: MVP の `get_custom_schema.sql` macro があるおかげで、`schema: staging` を指定すれば素直に `staging.prefectures` になる。指定しないと profile の target schema (`staging`) にフォールバックして同じ結果にはなるが、明示推奨。
- **dbt が macro を見つけてくれない**: `dbt/macros/` 配下なら自動で読み込まれる。サブディレクトリ (`exercises/`) でも OK。dbt は `macro-paths: ["macros"]` を再帰的に走査する。
- **macro の引数で `column` という名前を使うと予約語っぽい**: jinja の予約語ではないが、可読性のため `col` などにしてもよい。
- **コンパイル後 SQL の確認**: `dbt run --select mart_regional_sales` の後、`dbt/target/compiled/local_analytics/models/exercises/05/mart_regional_sales.sql` を `cat` すると展開後 SQL が見える。`{{ cast_jpy(...) }}` が `::numeric(14, 2)` に置換されているはず。

## 解答例

詳細は [`solutions/05-seeds-and-macros.solution.md`](solutions/05-seeds-and-macros.solution.md) を参照。
