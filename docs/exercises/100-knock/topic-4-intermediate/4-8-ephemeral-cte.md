# 4-8: int_order_details_100knock を `ephemeral` 化し、compiled SQL で CTE 展開を確認

## シナリオ

dbt の materialization には `view` / `table` / `incremental` の他に **`ephemeral`** がある。
ephemeral は **物理オブジェクトを一切作らず、下流 model の compiled SQL に CTE として展開** される
特殊な物質化戦略。
DB 上に table も view も残さないので storage 0、`pg_class` にも出てこない。
DAG 上は依存として認識されるが、物理的には「下流 SQL の中に直接コピペされる」 イメージ。

「物理を持たない依存」というのは初見では混乱するが、**「中間ロジックを再利用したいが、
物質化するほど重要ではない」 ケース** で威力を発揮する。本問では
`int_order_details_100knock` を `ephemeral` に切り替え、下流 mart
(`mart_daily_sales` または学習者が作った任意の下流) の compiled SQL を
`target/compiled/` 配下から開いて、`with int_order_details_100knock__dbt_tmp as ( ... )`
形式の CTE が現れることを確認する。

> ⚠️ **本問は「最終 state を ephemeral にする」 ため、4-1〜4-7 で view / table 想定だった
> 下流 mart も再 build が必要**。本問終了後、4-9 / 4-10 のために `view` に戻すか、ephemeral
> のまま維持するかは学習者の判断 (採点は本問終了時点を見る)。

## 学べること

- `materialized='ephemeral'` の意味と使いどころ
- compiled SQL (`target/compiled/.../mart_*.sql`) を読む習慣
- ephemeral が下流の SQL に **CTE として展開** される様子
- ephemeral と CTE の関係 (= dbt がコード生成で CTE を自動挿入)
- 「物理を持たない依存」 が DAG 上は依存として正しく認識されること

## 前提

- Topic ② ③ 完了 + Topic ④ 4-1 完了 (`int_order_details_100knock` が存在)
- 本 model を ref している下流 mart (例: 4-5 で作った `mart_daily_sales_100knock` など)
  が **少なくとも 1 本** 存在する
- `dbt parse` が通る

> **下流が無い場合**: 4-5 を未着手なら、本問のために最小限の下流 mart を 1 本作る。
> 例: `dbt/models/100-knock/topic-4/mart_dummy_for_ephemeral.sql`:
> ```sql
> {{ config(materialized='table', schema='marts') }}
> select count(*) as n_orders, sum(sales_amount) as total
> from {{ ref('int_order_details_100knock') }}
> ```
> 詳細は solution.md 参照。

## 入力データ

不要。学習者が `int_order_details_100knock` の config を変更するだけ。

## 課題

### Step 1: int_order_details_100knock を ephemeral に変更

`dbt/models/100-knock/topic-4/int_order_details_100knock.sql` の冒頭 config を変更:

```sql
{{ config(materialized='ephemeral') }}
```

`schema=` は ephemeral では物理化されないので **書いても効果なし** (省略推奨)。

### Step 2: dbt compile を走らせる

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt compile --profiles-dir . --select int_order_details_100knock+
```

`+` で下流まで含めて compile。`int_order_details_100knock` 自身の compiled は **作られない** (物理化されないから) が、下流 mart の compiled SQL の中に CTE として展開される。

### Step 3: 下流 mart の compiled SQL を開いて CTE 展開を確認

例えば下流が `mart_daily_sales_100knock` なら:

```bash
cat target/compiled/local_analytics/models/100-knock/topic-4/mart_daily_sales_100knock.sql
```

冒頭付近に下記のような CTE が現れているはず:

```sql
with int_order_details_100knock as (

    -- (元の int_order_details_100knock.sql の中身がここに展開される)
    select ...
    from "analytics"."staging"."stg_orders_100knock" o
    inner join ...

)

select ...
from int_order_details_100knock
group by ...
```

これが「ephemeral = compile 時に下流 SQL に CTE として埋め込まれる」 の実物。

### Step 4: DB 上で物理オブジェクトが無いことを確認

```bash
psql -h "$DBT_HOST" -U "$DBT_USER" -d analytics -c "
SELECT relname, relkind FROM pg_class
WHERE relname = 'int_order_details_100knock';
"
# → 0 行 (table も view も存在しない)
```

### Step 5: 下流 mart を再 build して動作確認

```bash
../.venv/bin/dbt build --select int_order_details_100knock+ --profiles-dir .
```

`int_order_details_100knock` 自体は SKIP されないが「物理化しない」というログが出る。
下流 mart は CTE 展開込みで RUN され、結果が変わらないことを確認 (4-1 時点と同じ集計値)。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-4-intermediate/4-8-ephemeral-cte.grading.yaml
```

## 完了条件

- [ ] `int_order_details_100knock` の `materialized` が **ephemeral** で宣言されている
- [ ] `dbt parse` が成功する
- [ ] manifest 上 `int_order_details_100knock` の `config.materialized = 'ephemeral'`
- [ ] `dbt compile --select int_order_details_100knock+` が成功する
- [ ] 下流 mart の compiled SQL 内に `int_order_details_100knock` を含む CTE 展開が見える
- [ ] DB 上に `intermediate.int_order_details_100knock` の table / view が **存在しない**

## ヒント (詰まったら)

- **下流が無いと ephemeral にしても compile で何も起きない**: ephemeral は「下流に展開されて初めて意味がある」 model。下流 0 だと dbt は warning を出して何も build しない。本問の前提として最低 1 本の下流が必要。Topic ④ 4-5 を済ませているか、未着手ならダミー下流を作る。
- **`schema=` が ephemeral で効かない**: ephemeral は DB に物理化されないので schema 配置は無意味。指定しても無視されるだけだが、視覚ノイズになるので config から削除推奨。
- **compiled SQL の場所**: `dbt/target/compiled/<project>/models/<path>/<model>.sql`。`dbt compile` を打たないと作られない / 古いまま。`dbt clean` で `target/` を消した後に再 compile すると確実。
- **ephemeral にすると test が走らない場合がある**: model 自体の `not_null` / `unique` test は **ephemeral では skip される** (物理化されてないので test SQL を当てられない)。grain 契約を test で守りたいなら ephemeral にしないのが原則。
- **元に戻したくなったら**: config を `materialized='view'` に戻して `dbt run --select int_order_details_100knock` で view が再作成される。本問終了後、4-9 / 4-10 で int_order_details_100knock を改めて使うので、その時点で view に戻すか ephemeral のまま続けるかは学習者の判断。

## 解答例

詳細は [`4-8-ephemeral-cte.solution.md`](4-8-ephemeral-cte.solution.md) を参照。
