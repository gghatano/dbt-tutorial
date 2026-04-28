# 4-2: grain 違反を検知する singular test を書く

## シナリオ

4-1 で `int_order_details_100knock` の grain を「1 `order_id` = 1 行」と
コメント / description / `unique` test の 3 点で宣言した。が、
**`schema.yml` の `unique` test は generic test で「列単位」しか見られない**。
これだけだと、例えば「複数列の組み合わせ grain」(顧客 × 日 など) を持つ
intermediate を後から作ったとき、grain 違反を捕まえる test が書けない。

そこで Topic ④ の早い段階で **singular test** (= 個別 SQL ファイルとして書く
カスタム test) の書き方をマスターしておく。今回は「`int_order_details_100knock`
の grain (= order_id) が `having count(*) > 1` で 1 行も返らないこと」を
1 つの `.sql` で表現する。

singular test は **「test = "FAIL を返すべき行を SELECT する SQL"」** という
dbt の test 哲学そのままを書く形式で、generic test に収まらない複雑な
ビジネスルールを表現する最後の手段。grain 担保はその代表例。

## 学べること

- singular test (`dbt/tests/...` 配下の `.sql`) と generic test (`schema.yml`) の違い
- 「test SQL が 1 行でも返したら FAIL」という dbt test の評価モデル
- `having count(*) > 1` で grain 違反 (重複 PK) を 1 SQL で表現する
- `dbt test --select test_name` で singular test を狙い撃ち実行する
- なぜ複合 grain では singular test が必須なのか (4-3 への前振り)

## 前提

- 4-1 完了: `int_order_details_100knock` が物理化済み、`unique` test も PASS する状態
- main HEAD が動く

## 入力データ

不要。`int_order_details_100knock` (4-1 で物理化) を test の対象にするだけ。

## 課題

### Step 1: tests ディレクトリを作る

`dbt/tests/100-knock/topic-4/` を新規作成 (MVP の `dbt/tests/` 直下と
混ぜないようサブディレクトリで分離)。

```bash
mkdir -p dbt/tests/100-knock/topic-4
```

### Step 2: singular test を書く

`dbt/tests/100-knock/topic-4/assert_int_order_details_grain.sql` を新規作成。

要件:

- 中身は **「grain 違反の行を SELECT する SQL」** 1 本のみ (Jinja config は不要)
- `int_order_details_100knock` を `ref()` で参照する (= DAG に test → model 依存が出る)
- `group by order_id having count(*) > 1` で重複 order_id を返す
- 重複が 0 件なら SELECT 結果が 0 行 = test PASS。1 行でも返ったら test FAIL

例 (この通り書いて OK):

```sql
-- Singular test: int_order_details_100knock の grain (1 row = 1 order_id) を担保。
-- SELECT が 1 行でも返ったら grain 違反 = test FAIL。
select
    order_id,
    count(*) as row_count
from {{ ref('int_order_details_100knock') }}
group by order_id
having count(*) > 1
```

### Step 3: 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select assert_int_order_details_grain
```

期待出力:

```
1 of 1 START test assert_int_order_details_grain ............ [RUN]
1 of 1 PASS  assert_int_order_details_grain .................. [PASS in 0.05s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### Step 4 (任意): わざと FAIL させてみる

`int_order_details_100knock.sql` の最後に `union all select * from {{ ref('int_order_details_100knock') }} limit 1`
のような行を一時的に足すと、同じ order_id が 2 行になる → singular test が FAIL する
ことを確認できる。確認後、変更は **必ず巻き戻す** こと。

## 完了条件

- [ ] `dbt/tests/100-knock/topic-4/assert_int_order_details_grain.sql` が存在する
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select assert_int_order_details_grain` が PASS (grain 違反 0 件)
- [ ] `psql` で同等の `having count(*) > 1` が 0 行を返す

## ヒント (詰まったら)

- **singular test の置き場**: `dbt_project.yml` の `test-paths: ["tests"]` で
  `dbt/tests/` 配下が test パスとして登録される。サブディレクトリも自動で
  recursive に拾う。`dbt/tests/100-knock/topic-4/` でも問題なく test として
  認識される。
- **singular test の名前付け**: ファイル名 = test 名。`assert_int_order_details_grain.sql`
  なら test 名は `assert_int_order_details_grain`。`dbt test --select <test_name>` で
  個別実行できる。
- **`ref()` を書かないと test の依存が消える**: ハードコードで
  `from intermediate.int_order_details_100knock` と書くと dbt は依存を
  認識しない。`ref()` 経由で書くと「int_order_details_100knock の test である」と
  manifest に登録される。これにより `dbt test --select int_order_details_100knock+`
  (下流) でこの test も実行されるようになる。
- **「test = FAIL 行を返す SQL」が腹落ちしない**: 通常のアプリ test は
  `assert x == y` のように「合格条件」を書く。dbt の test は逆で、「失敗条件
  (= 違反行) を SELECT する SQL」を書く。`select` 結果の行数が 0 なら PASS、
  > 0 なら FAIL。慣れると「不変条件 = `not (...)` の SELECT」と機械的に
  書ける。
- **generic test (`unique`) と singular test の使い分け**: 単一列の `unique` /
  `not_null` などお決まりは generic test (= `schema.yml` 1 行)。複合キー
  unique や、ビジネス固有の複雑ルール (e.g. 「sales_amount は 1000 円超なら
  customer_segment が VIP のみ」など) は singular test。

## 解答例

詳細は [`4-2-grain-singular-test.solution.md`](4-2-grain-singular-test.solution.md) を参照。
