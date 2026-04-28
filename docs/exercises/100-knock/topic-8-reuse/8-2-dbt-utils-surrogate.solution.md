# 8-2 解答例

## dbt/packages.yml

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
```

**ポイント**:

- **version range の `>=1.3.0, <2.0.0`**: メジャーバージョンを固定して
  「破壊的変更を勝手に取り込まない」 防御。dbt-utils 1.x 系の API が安定している
  前提でレンジ pin。
- **`hub.getdbt.com` 経由**: `dbt-labs/dbt_utils` は dbt Hub に登録されている公式
  パッケージ。`git: https://github.com/dbt-labs/dbt-utils` 直指定もできるが、
  hub 経由のほうが version 解決が速い。

## Step 2: dbt deps の実行

```text
$ ../.venv/bin/dbt deps --profiles-dir .
14:30:01  Running with dbt=1.11.x
14:30:02  Installing dbt-labs/dbt_utils
14:30:02    Installed from version 1.3.0
14:30:02    Up to date!
```

`dbt/dbt_packages/dbt_utils/` ができている。中身を覗くと:

```text
dbt/dbt_packages/dbt_utils/
  dbt_project.yml
  macros/
    cross_db_utils/
      generate_surrogate_key.sql       # ← これが今回呼ぶ macro の本体
      ...
  ...
```

`dbt/package-lock.yml` も生成され、依存解決の結果が固定される (チームで共有する
場合 commit しておくと再現性が上がる)。

## dbt/models/100-knock/topic-4/int_customer_daily_100knock.sql (書き換え後)

```sql
{{ config(materialized='view', schema='intermediate') }}

-- ============================================================================
-- int_customer_daily_100knock  (Topic ④ 4-3 + Topic ⑧ 8-2 改訂)
-- ----------------------------------------------------------------------------
-- grain     : 1 row = (order_date, customer_id) ペア。
-- surrogate : customer_day_key = md5(order_date || '|' || customer_id)
--             dbt_utils.generate_surrogate_key で adapter 非依存に生成。
-- 用途     : 下流 mart で「日次 × 顧客」JOIN 時に 1 列で済ませる。
-- ============================================================================
select
    {{ dbt_utils.generate_surrogate_key(['order_date', 'customer_id']) }} as customer_day_key,
    order_date,
    customer_id,
    sum(quantity)                                  as total_quantity,
    {{ cast_money('sum(sales_amount)') }}          as total_sales_amount,
    count(distinct order_id)                       as order_count
from {{ ref('int_order_details_100knock') }}
group by 1, 2, 3
```

**ポイント**:

- **`dbt_utils.generate_surrogate_key([...])` が SELECT 先頭**: 主キーが先頭列、
  という業務 SQL の慣習に従う。「この model の grain は何か」 が一目で分かる。
- **入力 list の順序**: `['order_date', 'customer_id']` の順序を変えると
  ハッシュ値が変わるので、**1 度決めたら変えない** ルール。team で順序規約を
  決めておく (例: 「時系列キーが先、エンティティキーが後」)。
- **`group by 1, 2, 3`**: PostgreSQL なら式ベースの group by が効くので
  `customer_day_key` も group キーに入れて問題ない。`order_date, customer_id` から
  決定論的に決まるので冗長だが、明示する方が安全。
- **8-1 の `cast_money` も併用**: `sum(sales_amount)` を 8-1 で作った macro 経由で
  cast。Topic ⑧ 内の macro 同士が組み合わさる例。

## dbt/models/100-knock/topic-4/schema.yml (該当部分)

```yaml
version: 2

models:
  - name: int_customer_daily_100knock
    description: "日次 × 顧客の集計 (Topic ④ 4-3)。Topic ⑧ Q2 で代理キー customer_day_key を追加。"
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
      - name: total_quantity
        tests: [not_null]
      - name: total_sales_amount
        tests: [not_null]
```

**ポイント**:

- **`unique` 1 行で複合 PK 一意性**: built-in `unique` test は単一列のみ対応。
  代理キー化することで 1 列に圧縮 → built-in test が使える。複合キーをそのまま
  `unique` で見たい場合は `dbt_utils.unique_combination_of_columns` を使う手もあるが、
  代理キー化のほうが下流の JOIN も簡潔になる。
- **元の (order_date, customer_id) も not_null は維持**: 代理キーが unique でも、
  元の構成列が NULL では業務的に意味がないので保険として残す。

## 実行例

```text
$ ../.venv/bin/dbt run --profiles-dir . --select int_customer_daily_100knock
1 of 1 OK created sql view model intermediate.int_customer_daily_100knock ... [CREATE VIEW in 0.15s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

$ ../.venv/bin/dbt test --profiles-dir . --select int_customer_daily_100knock
... PASS not_null_int_customer_daily_100knock_customer_day_key
... PASS unique_int_customer_daily_100knock_customer_day_key
... 全 5 件 PASS
Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

物理確認:

```sql
analytics=> SELECT customer_day_key, order_date, customer_id
            FROM intermediate.int_customer_daily_100knock LIMIT 3;
       customer_day_key            | order_date | customer_id
-----------------------------------+------------+-------------
 e8a4f2c1d9b7a3e5f6c8d1b2a4e9f7c3 | 2025-08-13 |          42
 a1b2c3d4e5f6789012345678abcdef01 | 2025-08-13 |         108
 9f8e7d6c5b4a3210fedcba9876543210 | 2025-08-13 |         215

analytics=> SELECT length(customer_day_key) FROM intermediate.int_customer_daily_100knock LIMIT 1;
 length
--------
     32       -- md5 hex digest = 32 chars
```

## 解説まとめ

- **代理キー = 複合 PK の圧縮**: 業務的には `(order_date, customer_id)` が PK だが、
  この 2 列を JOIN 条件 / GROUP BY に毎回書くのは冗長。md5 1 列に圧縮すれば
  下流が「`customer_day_key = ?`」 で済む。代理キー = **物理的な利便性のための
  追加列**、業務キー (order_date, customer_id) は別途 not_null で保護する。
- **md5 と業務的整合性の関係**: md5 は **決定論的** (同じ入力 → 同じ出力)。
  なので 2 回 build しても同じ代理キーが得られる (snapshot との整合も取れる)。
  暗号学的に弱い hash だが、衝突は天文学的確率で発生しないので業務 PK としては十分。
- **adapter 非依存**: Postgres は `md5(text)` を持つが、BigQuery は `MD5(STRING)` →
  hex 出力には別途変換が必要。dbt-utils の macro は adapter 差を吸収してくれる。
  「BigQuery に移植したくなった瞬間に SQL を 1 行も変えずに済む」 のはパッケージの
  ROI を実感する瞬間。
- **`packages.yml` の version pin**: `>=1.3.0, <2.0.0` は **「マイナーアップデートは
  許す、メジャーアップデートは手動で対応する」** という保守的な指定。dbt パッケージは
  semver に従う前提なので、メジャーアップデートで API が変わる可能性に備える。
- **`dbt_packages/` を git 管理しない理由**: パッケージは hub 経由で取得できる
  ので、毎回 `dbt deps` で取り直せる。`.gitignore` に `dbt/dbt_packages/` を入れる
  ことで repo size を抑える。`package-lock.yml` だけ commit すれば再現性は取れる。
- **8-3 への伏線**: 本問で `dbt-utils` を 1 個入れた。8-3 で `dbt-expectations` を
  追加して **2 個共存** にし、内部依存解決 (`dbt_expectations` も `dbt_utils` に
  依存) と `package-lock.yml` の役割を体験する。
