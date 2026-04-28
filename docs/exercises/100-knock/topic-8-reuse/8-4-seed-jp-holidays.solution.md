# 8-4 解答例

## dbt/seeds/100-knock/topic-8/jp_holidays_2026.csv

2026 年の日本の祝日 16 日分。改行は LF、文字コードは UTF-8、ヘッダ + 16 行 = 17 行。

```csv
holiday_date,holiday_name,holiday_type
2026-01-01,元日,national
2026-01-12,成人の日,national
2026-02-11,建国記念の日,national
2026-02-23,天皇誕生日,national
2026-03-20,春分の日,national
2026-04-29,昭和の日,national
2026-05-03,憲法記念日,national
2026-05-04,みどりの日,national
2026-05-05,こどもの日,national
2026-05-06,振替休日,substitute
2026-07-20,海の日,national
2026-08-11,山の日,national
2026-09-21,敬老の日,national
2026-09-23,秋分の日,national
2026-11-03,文化の日,national
2026-11-23,勤労感謝の日,national
```

**ポイント**:

- **2026 年の祝日構成**: 国民の祝日 15 日 + 振替休日 1 日 = 計 16 日。
  内閣府発表の祝日法に基づく (5/3 憲法記念日が日曜なので 5/6 が振替休日)。
- **ヘッダ命名**: `date` ではなく `holiday_date` と書くことで「祝日日付」 という
  意味を明示。`order_date` と JOIN しても列名衝突しない。
- **`holiday_type` 列の存在意義**: `national` (法定祝日) と `substitute` (振替休日)
  を分けることで、後で「振替を除いた純粋な祝日売上」 を分析できる。
  単純な `boolean is_holiday` だと拡張性が無い。
- **改行コード LF**: 一部の OS / Excel で CRLF になりがち。`file dbt/seeds/.../jp_holidays_2026.csv`
  で「ASCII text」 と出れば LF (CRLF だと「ASCII text, with CRLF line terminators」)。

## dbt/seeds/100-knock/topic-8/schema.yml

```yaml
version: 2

seeds:
  - name: jp_holidays_2026
    description: |
      2026 年の日本の祝日マスタ (16 日)。BI / 売上分析の祝日フラグ判定に使う。
      内閣府発表の祝日法に基づく。2027 年版は別 seed (jp_holidays_2027.csv) として
      新規追加する運用 (年度単位で seed を切る)。
    config:
      schema: staging
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

**ポイント**:

- **`column_types`**: dbt の自動推論に任せると `holiday_date` が `text` になる
  ことがある (Postgres は CSV から date 推論できないため)。明示すれば `date` 型で
  物理化されて、JOIN で type 不整合が出ない。
- **`schema: staging`**: 本リポジトリの `get_custom_schema.sql` override により
  そのまま `staging.jp_holidays_2026` になる。標準 dbt なら `<target>_staging`。
- **`unique` を `holiday_date` に**: 「同じ日付の祝日が 2 行ある」 のは業務的に
  ありえない。CSV 編集ミスを test で検知する。
- **`accepted_values` で取りうる値を契約化**: `holiday_type` は 2 値のみ。
  CSV 編集者が `祝日` (日本語) や `holiday` (英語別表現) を書いた瞬間に test FAIL。

## dbt/models/100-knock/topic-8/mart_calendar_sales_100knock.sql

```sql
{{ config(materialized='table', schema='marts') }}

-- ============================================================================
-- mart_calendar_sales_100knock  (Topic ⑧ 8-4)
-- ----------------------------------------------------------------------------
-- grain     : 1 row = order_date (売上があった日のみ)。
-- 用途      : BI で「平日 vs 祝日」 の売上比較 / 祝日売上ランキング。
-- upstream  : int_order_details_100knock + jp_holidays_2026 (seed)
-- ============================================================================
with daily as (
    select
        order_date,
        sum(sales_amount)         as total_sales_amount,
        count(distinct order_id)  as order_count
    from {{ ref('int_order_details_100knock') }}
    group by 1
)

select
    d.order_date,
    d.total_sales_amount,
    d.order_count,
    case when h.holiday_date is not null then true else false end as is_holiday,
    h.holiday_name,
    h.holiday_type
from daily d
left join {{ ref('jp_holidays_2026') }} h
    on d.order_date = h.holiday_date
order by d.order_date
```

**ポイント**:

- **LEFT JOIN + `case when ... is not null` で boolean 化**: `INNER JOIN` だと
  「祝日のみの行」 になってしまう。LEFT JOIN で全 order_date を保持し、祝日
  該当時のみ holiday 列が埋まる。`is_holiday` を boolean 化して BI 側で
  フィルタしやすく。
- **`ref('jp_holidays_2026')`**: seed も `ref()` で参照できる (source は不要)。
  `dbt run --select +mart_calendar_sales_100knock` を叩いた時、依存解決で
  「seed → mart」 の順で実行される。
- **mart の grain 維持**: `daily` CTE で `group by order_date` で grain を
  確定させてから JOIN。逆に「order_date を group しない状態で JOIN」 すると
  fan-out (1 order に祝日 1 行が紐づくが、order_date 重複で行数が爆発) が起きる。
  本問は grain 確定済みなので 1:1 LEFT JOIN で安全。

## 実行例

```text
$ ../.venv/bin/dbt seed --profiles-dir . --select jp_holidays_2026
1 of 1 START seed file staging.jp_holidays_2026 ............ [RUN]
1 of 1 OK loaded seed file staging.jp_holidays_2026 ........ [INSERT 16 in 0.10s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select jp_holidays_2026
... PASS not_null_jp_holidays_2026_holiday_date
... PASS unique_jp_holidays_2026_holiday_date
... PASS not_null_jp_holidays_2026_holiday_name
... PASS not_null_jp_holidays_2026_holiday_type
... PASS accepted_values_jp_holidays_2026_holiday_type__national__substitute
Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5

$ ../.venv/bin/dbt run --profiles-dir . --select mart_calendar_sales_100knock
1 of 1 OK created sql table model marts.mart_calendar_sales_100knock ... [SELECT 365 in 0.20s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

物理確認:

```sql
analytics=> SELECT count(*) FROM staging.jp_holidays_2026;
 count
-------
    16

analytics=> SELECT count(*) FILTER (WHERE is_holiday) AS holiday_days,
                  count(*) FILTER (WHERE NOT is_holiday) AS weekday_days,
                  count(*) AS total_days
            FROM marts.mart_calendar_sales_100knock;
 holiday_days | weekday_days | total_days
--------------+--------------+------------
           N  |       (365-N)|         365   -- 売上があった祝日数 N (≤ 16)

analytics=> SELECT order_date, holiday_name, total_sales_amount
            FROM marts.mart_calendar_sales_100knock
            WHERE is_holiday
            ORDER BY total_sales_amount DESC LIMIT 3;
 order_date | holiday_name | total_sales_amount
------------+--------------+--------------------
 2026-05-05 | こどもの日   |          1234567.00
 2026-01-01 | 元日         |           987654.00
 ...
```

## 解説まとめ

- **「マスタデータをコード管理する」 の本質**: 祝日リスト / 都道府県マスタ /
  税率テーブルのような **頻度低・更新少・規模小** のデータは DB に手動 INSERT する
  のではなく **CSV を git に置いて PR で更新** する。git の歴史が「マスタの更新履歴」
  になる。本番 / 開発で同じ値になる (= 環境間 drift が起きない) のも大きい。
- **seed vs source の使い分け**: 業務 source データ (raw.orders, raw.customers) は
  サイズも大きく頻繁に更新されるので **DB に直接投入** + dbt source で参照。
  マスタデータは **CSV → seed** で投入。境界の判断は「(1) サイズ < 数千行 (2)
  更新頻度 < 月 1 (3) コード管理する価値があるか」 の 3 軸。
- **`accepted_values` の威力**: `holiday_type` を `[national, substitute]` に絞ることで
  「typo の即時検知」 + 「下流での switch 文の網羅性保証」 の 2 重の意味がある。
  enum 型相当の宣言を YAML で書ける = dbt の宣言性の真価。
- **dbt seed の物理化挙動**: `dbt seed` は「CSV → DROP + CREATE TABLE + INSERT」 の
  全件入れ直し (デフォルト)。10,000 行を超える seed は性能に注意 (基本マスタ用途で
  使う前提)。incremental load は seed には無いので、大きいデータは raw 側で扱う。
- **`column_types` の保険**: dbt は CSV → DB の型変換を自動で行うが、`date` /
  `numeric` / `boolean` などは推論を間違えがち。明示すれば「型を契約として宣言」
  できる。staging contract と同じ考え方を seed にも適用。
- **`mart_calendar_sales_100knock` の限界**: 本問の grain は「売上があった日」 だけ。
  「売上が 0 円の祝日」 は表に出ない (8-4 の素直版)。MVP の Ex.07 のように
  `dbt-utils.date_spine` で全日付スパインを作って LEFT JOIN すれば「欠損日 = 0 円」
  も表現できる。これは Topic ⑧ の発展課題 / Topic ⑨ パフォーマンス回での再登場可能。
- **MVP との関係**: Ex.07 の `mart_calendar_sales` は `dbt-utils.date_spine` 起点。
  本問の `mart_calendar_sales_100knock` は `int_order_details_100knock` 起点 +
  seed JOIN。**起点の違い** が grain と用途の違いを生む良い対比。
