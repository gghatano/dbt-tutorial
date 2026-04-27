# 4-2 解答例

## dbt/tests/100-knock/topic-4/assert_int_order_details_grain.sql

```sql
-- Singular test: int_order_details_100knock の grain (1 row = 1 order_id) を担保。
-- SELECT が 1 行でも返ったら grain 違反 = test FAIL。
-- 4-1 で schema.yml に書いた `unique` test と二重に見えるが、こちらは
--   「複合 grain にも素直に拡張できる singular 形式」を学ぶための練習問題。
--   4-3 で複合 grain (customer_id, activity_date) を扱うときに同じ書き方を流用する。
select
    order_id,
    count(*) as row_count
from {{ ref('int_order_details_100knock') }}
group by order_id
having count(*) > 1
```

**ポイント**:

- **`ref()` 経由で書く**: ハードコード (`from intermediate.int_order_details_100knock`)
  だと dbt が依存を認識しない。`ref()` で書くと
  - manifest 上 `test.local_analytics.assert_int_order_details_grain` の
    `depends_on.nodes` に `model.local_analytics.int_order_details_100knock` が入る
  - `dbt test --select int_order_details_100knock+` でこの test が拾われる
  - 環境 (dev / prod) で schema が違っても自動解決される
- **`having count(*) > 1` の意味**: 「grain key (= order_id) が同じ行が 2 行以上
  ある」を SELECT する SQL。grain が守られていれば必ず 0 行になる。
  この「0 行 = OK、1 行 = NG」が dbt test の評価モデル。
- **コメントに 4-3 への伏線**: 単一列 grain なら schema.yml の `unique` で
  済むが、複合キー grain (4-3 の `customer_id × activity_date`) になると
  generic test では書けない。singular test の形は **そのまま `group by 列1, 列2`
  に拡張できる**。「今は冗長だが、構文を体に染み込ませるための練習」と
  コメントで明示しておく。

## 動作確認

### PASS ケース (期待動作)

```bash
$ cd dbt
$ ../.venv/bin/dbt test --profiles-dir . --select assert_int_order_details_grain
06:11:00  Running with dbt=1.11.x
06:11:00  Found 13 models, 5 sources, 71 data tests, ...
06:11:01  1 of 1 START test assert_int_order_details_grain ............ [RUN]
06:11:01  1 of 1 PASS  assert_int_order_details_grain .................. [PASS in 0.05s]
06:11:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### FAIL ケース (わざと壊す)

`int_order_details_100knock.sql` の末尾に下記を一時的に追記:

```sql
union all
select * from {{ ref('int_order_details_100knock') }} limit 1
```

`dbt run` で物理化し直してから test を再実行:

```bash
$ ../.venv/bin/dbt run  --profiles-dir . --select int_order_details_100knock
$ ../.venv/bin/dbt test --profiles-dir . --select assert_int_order_details_grain
06:12:00  1 of 1 START test assert_int_order_details_grain ............ [RUN]
06:12:00  1 of 1 FAIL 1 assert_int_order_details_grain ................ [FAIL 1 in 0.07s]
06:12:00  Failure in test assert_int_order_details_grain
06:12:00    Got 1 result, configured to fail if != 0
06:12:00  Done. PASS=0 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

「`Got 1 result, configured to fail if != 0`」が test FAIL の本体。
**「1 行 = grain 違反 = 失敗」を 1 SQL で表現できている** ことの証明になる。

確認できたら、追加した `union all ...` は **必ず削除して `dbt run` を再実行**
し、test PASS の状態に戻すこと。

### `psql` で同じ check を手で叩く

```sql
analytics=> SELECT order_id, count(*)
            FROM intermediate.int_order_details_100knock
            GROUP BY order_id
            HAVING count(*) > 1;
 order_id | count
----------+-------
(0 rows)
```

0 行 = grain 違反 0 件。singular test が見ている world と完全に一致。

## DAG 上の見え方

```bash
$ ../.venv/bin/dbt ls --select int_order_details_100knock+ --profiles-dir .
model.local_analytics.int_order_details_100knock
test.local_analytics.assert_int_order_details_grain
test.local_analytics.unique_int_order_details_100knock_order_id
test.local_analytics.not_null_int_order_details_100knock_order_id
... (略)
```

`+` (= 自分とすべての下流) で `int_order_details_100knock` を選ぶと、
`assert_int_order_details_grain` が下流として一緒に出てくる。これが
「`ref()` 経由で書く」効能 — singular test も DAG の市民権を持つ。

## 解説まとめ

- **dbt の test 哲学**: 「assert_X」のような関数を書くのではなく、
  **「test = FAIL 行を SELECT する SQL」**。0 行 = PASS、> 0 行 = FAIL。
  この単純なモデルが、generic test も singular test も同じ評価ルールで
  扱える理由。
- **singular test が必要になる場面**:
  1. **複合キー unique** (e.g. 顧客 × 日 grain) — generic `unique` は単一列のみ
  2. **複雑なビジネスルール** (e.g. 「sales_amount > 1000 円なら必ず VIP」)
  3. **複数 model にまたがる整合性** (e.g. 「mart の合計 = staging の合計」)
- **generic test と singular test の使い分けの目安**:
  - 単一列 + 標準制約 (unique / not_null / accepted_values / relationships) → generic
  - それ以外 → singular。または「将来複数 model で再利用したい」と分かったら
    macro 化して generic test 自作 (Topic ⑦ で扱う dbt-utils の `unique_combination_of_columns`
    のように、複合 grain unique を generic 化したものもある)
- **`ref()` 経由で書くこと**: singular test も `ref()` を使うと DAG 上の
  「test ノード」になり、`dbt test --select <model>+` で自動で拾われる。
  ハードコードすると DAG 切れの孤立 test になる (実行はされるが、依存追跡
  できないので CI で見落としが起きやすい)。
- **「intermediate の grain 契約」を test で守る = 下流が安心して `ref()` できる**:
  4-2 の本質はここ。intermediate を切る理由のひとつが「下流に契約を提供
  する」だが、契約は **test で担保されないとただの口約束**。grain test を
  必ずセットで書く癖をつけることで、intermediate が「下流から信頼される
  契約点」になる。
- **次の問 (4-3)**: 複合 grain `customer_id × activity_date` の int を作り、
  この問で身に着けた singular test 形式を拡張する。`dbt_utils.generate_surrogate_key`
  で複合 grain を 1 列にまとめる手筋も導入する。
