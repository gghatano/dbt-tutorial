# 8-4: jp_holidays_2026.csv を seed として登録、mart_calendar_sales_100knock に is_holiday 列を追加

## シナリオ

「ある日が **祝日かどうか**」 は売上分析で頻出のフィルタ条件 (祝日と平日で売上
パターンが違う / 祝日だけ抽出してキャンペーン効果を見たい)。これを SQL に
ハードコード (`order_date in ('2026-01-01', '2026-01-12', ...)`) で書くと、
**翌年の祝日が変わった瞬間に全 model を grep して書き換える** 羽目になる。

正解は祝日リストを **CSV ファイルとしてリポジトリに置き** (= コード管理)、
`dbt seed` で物理テーブルにロードして `LEFT JOIN` で `is_holiday` を判定する。
CSV はコードと一緒に PR / レビューが回るので、「祝日マスタの更新」 が
**Git の歴史として追跡可能** になる。

8-4 では、2026 年の日本の祝日 16 日分の CSV を seed として登録し、`mart_calendar_sales_100knock`
(日次売上カレンダーマート) に `is_holiday` 列を追加する。CSV には `not_null` /
`unique` / `accepted_values` テストを宣言して、データの整合性を契約として宣言する。

## 学べること

- `dbt seed` の基本 (CSV ファイル → 物理テーブル化)
- seed の `schema.yml` でテスト宣言 (`not_null` / `unique` / `accepted_values`)
- `dbt seed --select <name>` での個別ロード
- mart 側で `LEFT JOIN seed ON date` の作法
- なぜ「マスタデータをコードで管理する」 のが業務的に正しいのか (PR レビュー / git 履歴 / 環境間整合性)

## 前提

- Topic ② 〜 ⑦ 完了 (`int_order_details_100knock` が物理化済み)
- 学習者の seed は `dbt/seeds/100-knock/topic-8/jp_holidays_2026.csv`
- 学習者の mart は `dbt/models/100-knock/topic-8/mart_calendar_sales_100knock.sql`
- (任意) 8-2 完了で `dbt-utils` が入っていれば、日付スパインの自動生成にも応用可能 (本演習では不要)

## 入力データ

学習者が手書きする CSV (16 行 + ヘッダ)。2026 年の日本の祝日全 16 日分:

```csv
holiday_date,holiday_name,holiday_type
2026-01-01,元日,national
2026-01-12,成人の日,national
2026-02-11,建国記念の日,national
2026-02-23,天皇誕生日,national
2026-03-20,春分の日,national
...
```

(全 16 行は解答例参照)

## 課題

### Step 1: seed CSV を作成

`dbt/seeds/100-knock/topic-8/jp_holidays_2026.csv` を新規作成。2026 年祝日 16 行 + ヘッダ。

要件:

- ヘッダ: `holiday_date,holiday_name,holiday_type` の 3 列
- `holiday_date` は ISO 8601 日付文字列 (`YYYY-MM-DD`)
- `holiday_type` は `national` (国民の祝日) / `substitute` (振替休日) のいずれか
  (本演習は便宜上 16 日全てを `national` で統一でも OK)
- 改行コードは LF、文字コードは UTF-8

### Step 2: seed の schema.yml でテスト宣言

`dbt/seeds/100-knock/topic-8/schema.yml`:

```yaml
version: 2

seeds:
  - name: jp_holidays_2026
    description: "2026 年の日本の祝日マスタ (16 日)。BI / 売上分析の祝日フラグ判定に使う。"
    config:
      schema: staging   # 本リポジトリの get_custom_schema.sql override で staging.jp_holidays_2026 に物理化
      column_types:
        holiday_date: date
        holiday_name: text
        holiday_type: text
    columns:
      - name: holiday_date
        description: "祝日日付 (date)。"
        tests:
          - not_null
          - unique
      - name: holiday_name
        description: "祝日名 (例: 元日)。"
        tests:
          - not_null
      - name: holiday_type
        description: "祝日種別 (national / substitute)。"
        tests:
          - not_null
          - accepted_values:
              values: [national, substitute]
```

### Step 3: seed をロード

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt seed --profiles-dir . --select jp_holidays_2026
```

完了の見え方:

- `staging.jp_holidays_2026` テーブルに 16 行
- `dbt test --select jp_holidays_2026` で `not_null` / `unique` / `accepted_values` が PASS

### Step 4: mart_calendar_sales_100knock を作る

`dbt/models/100-knock/topic-8/mart_calendar_sales_100knock.sql`:

```sql
{{ config(materialized='table', schema='marts') }}

-- ============================================================================
-- mart_calendar_sales_100knock  (Topic ⑧ 8-4)
-- ----------------------------------------------------------------------------
-- grain     : 1 row = order_date (日次集計)
-- 用途      : 売上カレンダー + 祝日フラグ。BI 側で「平日 vs 祝日」 の比較を可能に。
-- ============================================================================
with daily as (
    select
        order_date,
        sum(sales_amount) as total_sales_amount,
        count(distinct order_id) as order_count
    from {{ ref('int_order_details_100knock') }}
    group by 1
)

select
    d.order_date,
    d.total_sales_amount,
    d.order_count,
    case when h.holiday_date is not null then true else false end as is_holiday,
    h.holiday_name
from daily d
left join {{ ref('jp_holidays_2026') }} h
    on d.order_date = h.holiday_date
order by d.order_date
```

### Step 5: 実行

```bash
../.venv/bin/dbt run  --profiles-dir . --select mart_calendar_sales_100knock
../.venv/bin/dbt test --profiles-dir . --select jp_holidays_2026 mart_calendar_sales_100knock
```

確認:

```sql
SELECT count(*) FILTER (WHERE is_holiday) FROM marts.mart_calendar_sales_100knock;
-- 売上があった祝日数 (≦ 16)
```

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-8-reuse/8-4-seed-jp-holidays.grading.yaml
```

## 完了条件

- [ ] `dbt/seeds/100-knock/topic-8/jp_holidays_2026.csv` が存在 (ヘッダ + 16 行)
- [ ] `dbt/seeds/100-knock/topic-8/schema.yml` で seed のテストが宣言されている
- [ ] `dbt seed --select jp_holidays_2026` が成功 (16 行 LOAD)
- [ ] `dbt test --select jp_holidays_2026` が PASS (not_null + unique + accepted_values)
- [ ] `mart_calendar_sales_100knock` が物理化され、`is_holiday` 列を持つ
- [ ] `staging.jp_holidays_2026` の行数が 16

## ヒント (詰まったら)

- **CSV のヘッダと `column_types`**: `column_types` は seed YAML で型を明示する手段。
  指定しないと dbt が自動推論するが、`holiday_date` を text のまま物理化されると JOIN で
  問題が起きるので明示的に `date` を指定。
- **schema 配置**: `config.schema: staging` は本リポジトリの `get_custom_schema.sql`
  override により素直に `staging.jp_holidays_2026` に物理化される。標準 dbt なら
  `<target>_staging` になっていた。ADR-0005 参照。
- **seed の更新サイクル**: 「2027 年の祝日が出たら CSV に 16 行追加して PR」 の
  運用フローになる。`dbt seed --full-refresh` で全件入れ直しが基本 (incremental は seed には無い)。
- **`accepted_values` の構文 (1.7+)**: `tests: [accepted_values: {values: [...]}]` の
  list 形式と、`tests: [accepted_values: {arguments: {values: [...]}}]` の `arguments`
  ネスト形式の両方が許容されている (dbt 1.7+)。本演習は前者の short form を採用。
- **mart_calendar_sales_100knock の grain**: 「order_date 1 行ずつ」 が grain。`is_holiday`
  は LEFT JOIN の存在判定なので NULL → false の `case when` が必要。
- **MVP との関係**: MVP に `mart_calendar_sales` (Ex.07) があるが、こちらは `_100knock`
  suffix で名前空間を分けているので衝突しない。Ex.07 は dbt-utils.date_spine で日付
  スパインを生成する別アプローチ。本問は `int_order_details_100knock` 起点で
  「売上があった日」 のみのカレンダーになる (発展課題: date_spine と組み合わせて欠損日も埋める)。

## 解答例

詳細は [`8-4-seed-jp-holidays.solution.md`](8-4-seed-jp-holidays.solution.md) を参照。
