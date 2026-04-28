# 4-6 解答例

## dbt/macros/100-knock/topic-4/calc_tax.sql

```jinja
{#-
    Calculate tax-inclusive amount.

    Arguments:
        amount  -- a SQL expression or column name representing 税抜金額
        rate    -- 税率 (decimal, e.g. 0.10 for 10%)

    Returns a numeric(14, 2) expression suitable for SELECT lists or aggregates.

    Centralising the tax formula here means a tax-rate change (10% → 12%, or
    軽減税率対応) is a single-file edit instead of grep across all marts.
-#}
{% macro calc_tax(amount, rate) %}
    ({{ amount }} * (1 + {{ rate }}))::numeric(14, 2)
{% endmacro %}
```

**ポイント**:

- **`{#- ... -#}`**: jinja コメントブロック。`-` を付けると前後の空白も食う。最終 SQL に余計な空行が残らない。
- **引数は SQL 式 / 列名**: `amount` を `'sales_amount'` (文字列リテラル) ではなく `sales_amount` (列名) として展開する。呼び出し側で `{{ calc_tax('sales_amount', 0.10) }}` と書いた時、`amount` には文字列 `"sales_amount"` が入り、`{{ amount }}` 展開で SQL 上の **識別子** として埋め込まれる仕組み。
- **`numeric(14, 2)` cast**: Postgres の `numeric(precision, scale)` で固定小数点数を確保。SUM / AVG で浮動小数点誤差が混入しないため、金額計算では原則 `numeric` 型を維持する。
- **macro の置き場所**: `dbt/macros/100-knock/topic-4/` のサブディレクトリでも dbt は再帰的に走査するので、トピック単位でフォルダを切ると後で見直しやすい (Topic ⑧ で macro が爆発的に増える)。

## dbt/models/100-knock/topic-4/int_order_with_tax_100knock.sql

```sql
{{ config(materialized='view', schema='intermediate') }}

-- Grain: 1 row = 1 order_id (int_order_details_100knock を継承)。
-- 税込金額 sales_amount_with_tax を calc_tax macro 経由で算出。
-- 税率は 10% を前提。将来軽減税率対応するなら calc_tax macro 側を拡張する。
select
    order_id,
    order_date,
    customer_id,
    product_id,
    quantity,
    unit_price,
    sales_amount,
    {{ calc_tax('sales_amount', 0.10) }} as sales_amount_with_tax
from {{ ref('int_order_details_100knock') }}
```

**ポイント**:

- **grain 継承**: `int_order_details_100knock` 自体が「1 order_id 1 行」 grain なので、その派生である本 model も同じ grain。冒頭コメントで「(int_order_details_100knock を継承)」と書いて grain 引継ぎを明示。
- **`{{ ref('int_order_details_100knock') }}`**: 上流が intermediate 同士の参照になる。DAG 上は `int_order_details_100knock → int_order_with_tax_100knock` という直列依存が生まれる。
- **macro 呼び出しの構文**: `{{ calc_tax('sales_amount', 0.10) }}` で 1 列追加。`as sales_amount_with_tax` で別名を付ける (macro の戻り値には別名が付かないので、SELECT 側で `as` 必須)。
- **`view` materialization**: 本問は税計算という軽い演算しか追加していないので、storage を消費せず常に上流最新を反映する view が適切。

## dbt/models/100-knock/topic-4/schema.yml (4-6 で追記する分)

既存の `schema.yml` (4-1 で作ったもの) に下記を追記:

```yaml
  - name: int_order_with_tax_100knock
    description: |
      Grain: 1 row = 1 order_id。int_order_details_100knock の派生。
      sales_amount_with_tax = calc_tax(sales_amount, 0.10) を追加した tax-inclusive 中継。
    columns:
      - name: order_id
        description: "Primary key (= grain key)。"
        tests:
          - not_null
          - unique
      - name: sales_amount
        description: "税抜金額 (numeric(14,2))。int_order_details_100knock から継承。"
        tests:
          - not_null
      - name: sales_amount_with_tax
        description: "税込金額 (numeric(14,2)) = sales_amount * 1.10。calc_tax macro で算出。"
        tests:
          - not_null
```

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
$ ../.venv/bin/dbt run --profiles-dir . --select int_order_with_tax_100knock
04:31:00  1 of 1 START sql view model intermediate.int_order_with_tax_100knock [RUN]
04:31:00  1 of 1 OK   created sql view model intermediate.int_order_with_tax_100knock [CREATE VIEW in 0.10s]
04:31:00  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

compiled SQL を見て macro 展開を確認:

```bash
$ cat target/compiled/local_analytics/models/100-knock/topic-4/int_order_with_tax_100knock.sql
select
    order_id,
    order_date,
    customer_id,
    product_id,
    quantity,
    unit_price,
    sales_amount,
    (sales_amount * (1 + 0.10))::numeric(14, 2) as sales_amount_with_tax
from "analytics"."intermediate"."int_order_details_100knock"
```

`{{ calc_tax('sales_amount', 0.10) }}` が `(sales_amount * (1 + 0.10))::numeric(14, 2)` に**1:1 展開**されているのが見える。これが「macro = SQL のテキスト置換」の本質。

DB で実値確認:

```sql
analytics=> SELECT order_id, sales_amount, sales_amount_with_tax,
                   round(sales_amount * 1.10, 2) AS expected
            FROM intermediate.int_order_with_tax_100knock LIMIT 3;
 order_id | sales_amount | sales_amount_with_tax | expected
----------+--------------+-----------------------+---------
        1 |       1500.00|                1650.00|   1650.00
        2 |       8000.00|                8800.00|   8800.00
        3 |        450.00|                 495.00|    495.00
```

全行 `sales_amount_with_tax = round(sales_amount * 1.10, 2)` が成立。grader の sql_assert がこの不変条件をチェックする。

## 解説まとめ

- **なぜ macro 化?**: 計算ロジックが「複数の model に同じ式で散らばる」 状況は、変更コストが
  **箇所数 × ファイル数** で爆発する。macro に集約すれば 1 箇所修正で全展開先が更新され、
  かつ「税計算の責務はここ」と読み手に明示される。**DRY (Don't Repeat Yourself) の dbt 流儀**。
- **macro と CTE の違い**: 「同じ計算を複数 model が共有」は CTE では解決できない (CTE は
  単一 model 内のスコープ)。複数 model 横断で式を共有するなら macro / 中間 model のどちらか。
  「**式単位で共有 → macro**」「**結果テーブル単位で共有 → 中間 model**」が原則。
- **macro と中間 model の使い分け**:
  - **macro が向く**: 軽い式 (cast, NULL ガード, surrogate key 生成, 税計算など)
  - **中間 model が向く**: JOIN を伴う、結果を物質化したい、下流 N 本から再利用される
  - 本問の `calc_tax` は前者の典型。`sales_amount_with_tax` 列を持つ中間 model を作るのは
    後者で、この 2 つを組み合わせて「macro が中間 model の中で使われる」という二層構造を作っている。
- **税率変更時のシナリオ**:
  - **macro 化なし**: `grep -r '* 1.10' dbt/models/` で全箇所探して書き換え → ミスが出る
  - **macro 化あり**: `dbt/macros/100-knock/topic-4/calc_tax.sql` の 1 行 (`0.10` → `0.12`) を
    変更 → `dbt run --select +int_order_with_tax_100knock+` で全下流が新税率で再計算
  - これが「**コード上の依存と変更影響範囲が一致する**」 という dbt の本質的な強み。
- **将来拡張**: 軽減税率 (食料品 8%, それ以外 10%) に対応するなら、macro を
  `calc_tax(amount, category)` に拡張し、内部で `case when category = 'food' then 0.08 else 0.10 end`
  と書くか、`dbt_project.yml` の `vars` に税率テーブルを定義する。いずれにせよ
  **変更箇所は macro 1 ファイルに閉じる**。
