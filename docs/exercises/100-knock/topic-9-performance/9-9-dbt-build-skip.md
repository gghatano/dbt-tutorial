# 9-9: `dbt build --select +mart_customer_sales_100knock` で test 失敗 → 下流 SKIP の依存ガードを確認

## シナリオ

`dbt build` は `dbt run` (model 物理化) と `dbt test` (品質テスト) を **トポロジカル順に直列で** 実行する総合コマンド。`dbt run` だけだと「上流 model が壊れていても下流まで突き進んで build」してしまうが、`dbt build` は **upstream test が失敗したら downstream を SKIP する** 安全装置がある。

例えば `stg_orders_100knock` の `not_null` test が失敗すると、その下流の `int_order_details_100knock` / `mart_customer_sales_100knock` は build されず SKIP 扱いになる。これにより「**壊れたデータをわざわざ下流に流して計算リソースを消費する**」無駄が防げる。

本問では意図的に 1 つの test を失敗させ (`severity: error` の test を新設、または既存 test の `where` 条件を逆転)、`dbt build --select +mart_customer_sales_100knock` で **下流が SKIP される** ことを確認、ログを `build-skip.md` に残す。

> **後始末**: 意図的に失敗させた test 設定は本問完了後に必ず元に戻す。Step 5 にロールバック手順あり。

## 学べること

- `dbt build` が `run` + `test` を直列で実行する総合コマンドであること
- test の `severity: error` (= 失敗で build 停止) と `severity: warn` (= 警告のみで継続) の差
- upstream test 失敗 → downstream SKIP の依存ガード
- ログ上の `SKIP` / `ERROR` の見方
- なぜ `dbt run` ではなく `dbt build` を本番運用で使うべきか

## 前提

- Topic ② 〜 ⑦ + ⑧ + 9-1〜9-8 完了
- `dbt/models/100-knock/topic-3/stg_orders_100knock.sql` + 下流に `int_order_details_100knock` + `mart_customer_sales_100knock` がある
- `mart_customer_sales_100knock` は 5-X (sibling) または 9-1〜9-5 で実装済みと仮定
- `dbt build --select +mart_customer_sales_100knock` がベースラインで PASS する状態
- `git status` がクリーン

## 入力データ

不要。既存 model + schema.yml を編集するのみ。

## 課題

### Step 1: ベースライン確認 (まず PASS する)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select +mart_customer_sales_100knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-9-baseline.log
# Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N が出ること
cd ..
```

### Step 2: 意図的に test を失敗させる (singular test を新設)

`dbt/tests/100-knock/topic-9/assert_quantity_too_large.sql` を新規作成:

```sql
{{ config(severity='error') }}
-- 「失敗行」 = quantity <= 9999 の行 (= 全行)
-- このクエリが 1 行でも返したら FAIL → severity=error なので下流が SKIP
select * from {{ ref('stg_orders_100knock') }}
where quantity <= 9999
```

singular test の規約: 「**この SELECT が返した行の数 = 失敗行数**」。`severity='error'` で build を停止させる。

(代替案として schema.yml に `dbt_utils.expression_is_true` を追加する手もあるが、本問では singular test の方が手早い)

### Step 3: dbt build を実行 → 下流 SKIP 確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select +mart_customer_sales_100knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-9-skip.log
cd ..
```

期待ログ:

```text
... 1 of N OK created sql view model staging_100knock.stg_orders_100knock ...
... 2 of N FAIL  assert_quantity_too_large ........................ [FAIL N in 0.05s]
... 3 of N SKIP relation marts_100knock.mart_customer_sales_100knock ... [SKIP]
... 4 of N SKIP test not_null_mart_customer_sales_100knock_xxx ......... [SKIP]

Done. PASS=K WARN=0 ERROR=1 SKIP=M TOTAL=K+1+M
```

ポイント: stg_orders 自身の物理化 (run) は成功するが、test が ERROR で **下流の mart_customer_sales_100knock の run と test が SKIP** される。

### Step 4: build-skip.md に記録

`docs/exercises/100-knock/topic-9-performance/build-skip.md` を新規作成。最低限以下を含める:

- ベースライン (test を壊す前) の `Done. PASS=N WARN=0 ERROR=0 SKIP=0` ログ
- 壊した test の中身 (singular test の SQL or schema.yml の宣言)
- 壊した状態の build ログ抜粋 (`SKIP` 行と `FAIL`/`ERROR` 行を含む)
- `mart_customer_sales_100knock` 系の SKIP 行があることへの言及
- `severity: warn` だったら下流まで run されていた、という対比の一文

詳細は解答例参照。

### Step 5: 後始末 (test 設定を元に戻す)

```bash
# 追加した singular test を削除
rm dbt/tests/100-knock/topic-9/assert_quantity_too_large.sql

# あるいは git checkout で全部戻す
git checkout HEAD -- dbt/tests/ dbt/models/100-knock/topic-3/schema.yml

# 動作確認: ベースラインに戻ったか
cd dbt
../.venv/bin/dbt build --select +mart_customer_sales_100knock --profiles-dir . --no-colors
# → Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N が再び出れば OK
```

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-9-performance/9-9-dbt-build-skip.grading.yaml
```

**注意**: 採点 CI は **意図的に失敗する test を一時的に作り直す**スクリプトを内部で実行し、SKIP/ERROR ログを観察する。学習者は `build-skip.md` (= 観察記録) を残しておけば良い。

## 完了条件

- [ ] `docs/exercises/100-knock/topic-9-performance/build-skip.md` が存在
- [ ] md に「SKIP」「ERROR」両キーワードがある
- [ ] md に `mart_customer_sales_100knock` の言及がある (= 下流が SKIP された証拠)
- [ ] Step 5 後にベースラインの `dbt build` が PASS で戻る (test 設定を元に戻している)

## ヒント (詰まったら)

- **`severity: warn` だと下流が走る**: `severity: warn` は test 失敗を「警告」として扱い、下流の build を **続行**する。実務では「壊れているのは知っているが今は緊急で上流データを使いたい」局面で使う。本問の主旨は `severity: error` の方
- **singular test の場所**: `dbt/tests/` 配下に SQL ファイルを置くと自動的に singular test として認識される。ファイル名 = test 名。中身は **「失敗とみなす行を返す SELECT」**
- **`dbt-utils.expression_is_true` の意味**: `expression` で書いた条件が **全行 true** なら PASS。1 行でも false なら FAIL
- **SKIP と ERROR の違い**:
  - `SKIP`: 上流 test が失敗したので skip された (= 自分は何も悪くない)
  - `ERROR`: 自分が失敗した (test 失敗 / 物理化失敗)
- **ログに SKIP が出ない**: `dbt run` を使っている可能性 (run には test ガードがない)。`dbt build` を使うこと
- **後始末を忘れない**: 意図的に壊した test を残すと **以降のすべての build で失敗**する。本問完了後 Step 5 を必ず実行

## 解答例

詳細は [`9-9-dbt-build-skip.solution.md`](9-9-dbt-build-skip.solution.md) を参照。
