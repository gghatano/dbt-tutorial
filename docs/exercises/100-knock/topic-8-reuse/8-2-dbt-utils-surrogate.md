# 8-2: dbt-utils を packages.yml に追加、generate_surrogate_key で複合代理キーを 1 列化

## シナリオ

Topic ④ 4-3 で作った `int_customer_daily_100knock` のような **「日付 × 顧客」**
集計マートでは、複合 PK が `(order_date, customer_id)` の 2 列。下流マートで
`group by order_date, customer_id` を毎回書くか、JOIN で 2 列の ON 条件を
書き続けるのは面倒で、書き間違いの温床になる。

**1 列のハッシュ代理キー** にしてしまえば、`group by surrogate_key` /
`on a.surrogate_key = b.surrogate_key` の 1 条件で済む。さらに代理キーは
**unique 制約 test を 1 列に張るだけ** で複合 PK の一意性を担保できる
(複数列の `unique` は dbt built-in に無いので generic test を別途書く必要があった)。

ハッシュ代理キーを SQL で書くと `md5(coalesce(order_date::text, '') || '|' ||
coalesce(customer_id::text, ''))` のように Postgres 方言まみれの長文になる。
**dbt-utils の `generate_surrogate_key()` macro** は同等の処理を 1 行に集約し、
かつ adapter 非依存 (BigQuery / Snowflake へ移行しても同じ書き方) を保証する。

## 学べること

- `packages.yml` で `dbt-labs/dbt_utils` を宣言、`dbt deps` でインストール
- `dbt_utils.generate_surrogate_key(['col1', 'col2'])` の使い方 (引数は列名 list)
- 複合 PK を 1 列化 → `unique` test を 1 列に張るだけで一意性保証
- `dbt_packages/` は `.gitignore` 対象 (各環境で `dbt deps` が必要)
- adapter 非依存の macro が「dbt 移植性」 をどう支えるか

## 前提

- Topic ② 〜 ⑦ 完了 (`int_customer_daily_100knock` が存在)
- `dbt/packages.yml` が存在 (本リポジトリは `packages: []` で初期化済み)
- インターネット接続 (`dbt deps` で hub.getdbt.com から取得)

## 入力データ

不要。既存 `int_customer_daily_100knock` を **書き換え** + 代理キー列を追加するだけ。

## 課題

### Step 1: packages.yml に dbt-utils を追加

`dbt/packages.yml`:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
```

> **注**: 本ファイルは MVP 共通設定。学習者が直接書き換えると他 Exercise に
> 影響する可能性があるが、本演習では「自分用環境で `dbt/packages.yml` を直接
> 編集する」 前提で進める。共有環境では別 file
> (`dbt/packages.knock-8.yml`) を作って `dbt deps --packages-yaml-file` で
> 読み込む手もある。

### Step 2: パッケージインストール

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

期待:

- `dbt/dbt_packages/dbt_utils/dbt_project.yml` ができる
- `dbt/package-lock.yml` が生成される

### Step 3: int_customer_daily_100knock に代理キー列を追加

`dbt/models/100-knock/topic-4/int_customer_daily_100knock.sql` を書き換え。
冒頭の SELECT に `customer_day_key` 列を追加:

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = (order_date, customer_id) ペア。
-- Topic ⑧ Q2: dbt_utils.generate_surrogate_key で複合 PK を 1 列ハッシュ化。
select
    {{ dbt_utils.generate_surrogate_key(['order_date', 'customer_id']) }} as customer_day_key,
    order_date,
    customer_id,
    sum(quantity)                                  as total_quantity,
    {{ cast_money('sum(sales_amount)') }}          as total_sales_amount,
    count(distinct order_id)                       as order_count
from {{ ref('int_order_details_100knock') }}
group by 1, 2, 3   -- customer_day_key も決定論的に order_date+customer_id から決まるので 1 を入れて OK
```

> **注**: `generate_surrogate_key` の出力は **md5 ハッシュ文字列 (32 文字)** なので、
> `text` 型として作られる。group by 1, 2, 3 で問題ないのは
> `customer_day_key` が `(order_date, customer_id)` から決定論的に決まるため。
> (Postgres 上は実際には group by に式があれば計算してくれる。安全のため明示)

### Step 4: schema.yml に unique test を追加

`dbt/models/100-knock/topic-4/schema.yml` の該当ブロック:

```yaml
  - name: int_customer_daily_100knock
    columns:
      - name: customer_day_key
        description: "(order_date, customer_id) の md5 surrogate key (dbt_utils.generate_surrogate_key)。"
        tests:
          - not_null
          - unique
      - name: order_date
        tests: [not_null]
      - name: customer_id
        tests: [not_null]
```

### Step 5: 実行 + テスト

```bash
../.venv/bin/dbt run  --profiles-dir . --select int_customer_daily_100knock
../.venv/bin/dbt test --profiles-dir . --select int_customer_daily_100knock
```

期待:

- `customer_day_key` の `not_null` / `unique` が PASS
- DB 上で `length(customer_day_key) = 32` (md5 hash 長)

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-8-reuse/8-2-dbt-utils-surrogate.grading.yaml
```

## 完了条件

- [ ] `dbt/packages.yml` に `dbt-labs/dbt_utils` を宣言済み
- [ ] `dbt/dbt_packages/dbt_utils/` が展開されている (`dbt deps` 完了)
- [ ] `int_customer_daily_100knock.sql` で `dbt_utils.generate_surrogate_key([...])` を呼ぶ
- [ ] `customer_day_key` 列が `not_null` + `unique` test を持つ
- [ ] `dbt run --select int_customer_daily_100knock` が PASS
- [ ] `dbt test` で代理キー test が PASS

## ヒント (詰まったら)

- **第 1 引数は文字列 list**: `generate_surrogate_key(['order_date', 'customer_id'])` のように
  **列名の文字列を list で渡す**。dbt-utils が内部で `coalesce(<col>::text, '')` →
  `concat(...)` → `md5(...)` まで展開してくれる。
- **NULL 処理**: `coalesce(<col>::text, '')` で NULL は空文字に変換される (NULL と空文字の
  区別はつかない)。本演習の `int_customer_daily` では `(order_date, customer_id)` 両方が
  not_null なので NULL 衝突は起きない。
- **`{% set %}` で macro 出力を変数化したい場合**: `{% set sk = dbt_utils.generate_surrogate_key([...]) %}`
  → SELECT 内で `{{ sk }} as customer_day_key`。本演習では直書きで OK。
- **`dbt_packages/` がコミット対象になる**: `.gitignore` に `dbt/dbt_packages/` が入っている
  (はず)。CI 側は毎回 `dbt deps` を回す。
- **bigquery / snowflake への移行**: `generate_surrogate_key` は adapter 別実装が
  dispatch されているので、`dbt deps` 後は SQL を変えずに DB 移行できる。これが
  「外部パッケージ macro = 移植性レイヤー」 と言われる所以。
- **複合キーの代理キー化が嫌なら**: dbt-utils の `surrogate_key` (古い名前、deprecated) ではなく
  必ず `generate_surrogate_key` を使う。前者は NULL 処理が違う。

## 解答例

詳細は [`8-2-dbt-utils-surrogate.solution.md`](8-2-dbt-utils-surrogate.solution.md) を参照。
