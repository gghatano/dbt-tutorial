# 5-4: わざと型を変えて contract 違反を起こし、build が落ちることを体験する

## シナリオ

5-3 で `mart_daily_sales_100knock` に `contract: enforced` を立てた。これが
**机上の宣言ではなく、実際に build を止める強さを持つ** ことを身体で
学ぶ回。

学習者は `mart_daily_sales_100knock.sql` の 1 列を **わざと別の型に変える** PR
を作り、`dbt run` が `Contract Error` で落ちることを目撃する。その後、
schema.yml の `data_type:` を更新するか SQL を元に戻すかして直し、再度
build が通ることを確認する。「壊して → 落ちて → 直す」の 1 サイクルを
回すこと自体が成果物。

> **採点の注意**: この問は「壊した状態で commit するか」「直した状態で
> commit するか」が学習者によって分かれる。grading.yaml は **最終的に
> contract 宣言が schema.yml に書かれていること** (= 5-3 の続きが守られて
> いること) と、`docs/exercises/100-knock/topic-5-mart/5-4-violation-log.md`
> に「壊して落ちた」記録があることだけを採点する。実際に build を
> red にする部分は学習体験として残す。

## 学べること

- contract 違反時の `Contract Error` のメッセージ形式
- どの型変更が contract を壊し、どれが alias_types で許容されるか
- 「壊して → 落ちて → 直す」サイクルの実践
- contract 違反は test fail ではなく **run fail** であること
- 壊した記録を `violation-log.md` に残す習慣

## 前提

- 5-3 完了 (`mart_daily_sales_100knock` に contract: enforced と data_type が
  宣言済み)
- dbt 1.5+

## 入力データ

なし。SQL の 1 行を書き換えるだけ。

## 課題

### Step 1: わざと型を変える

`dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql` の
`total_sales_amount` の cast を `numeric(18, 2)` から `integer` に変える:

```sql
-- 変更前 (5-3):
sum(sales_amount)::numeric(18, 2)        as total_sales_amount

-- 変更後 (本問 Step 1):
sum(sales_amount)::integer               as total_sales_amount
```

schema.yml は **触らない** (元のまま `data_type: numeric(18,2)`)。

### Step 2: build して落ちることを確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock 2>&1 | tee /tmp/5-4-violation.log
```

期待される出力 (抜粋):

```text
Contract Error in model mart_daily_sales_100knock
  This model has an enforced contract that failed.
  Please ensure the name, data_type, and number of columns in your contract match the columns in your model's definition.

  | column_name        | definition_type | contract_type | mismatch_reason   |
  | ------------------ | --------------- | ------------- | ----------------- |
  | total_sales_amount | INT4            | NUMERIC       | data type mismatch|
```

`Done. PASS=0 ... ERROR=1` となれば成功 (= 契約が effective に動いている)。

### Step 3: violation-log.md に証拠を残す

`docs/exercises/100-knock/topic-5-mart/5-4-violation-log.md` を新規作成。最低限:

- 何の型を何に変えたか (1〜2 行)
- `Contract Error` の出力を引用 (5〜10 行)
- 直し方の選択肢 (SQL を戻す / schema.yml の data_type を変える) と、
  どちらを選んだか + その理由
- 直した後 `dbt run` が再度 PASS したログ

200 bytes 以上。

### Step 4: 直す

選択肢:

A) SQL を元に戻す (`::numeric(18, 2)`) → 推奨。BI が壊れない方向。
B) schema.yml の `data_type:` を `integer` に変える → 「これからはこの mart の
   `total_sales_amount` は integer です」と契約を変更宣言する方向。BI 担当との
   合意が必要。

学習者は **A を選び**、再度 `dbt run` が PASS することを確認する。

```bash
../.venv/bin/dbt run --profiles-dir . --select mart_daily_sales_100knock
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

## 完了条件

- [ ] `5-4-violation-log.md` が存在 (200 bytes 以上)
- [ ] violation-log.md に `Contract Error` または `contract` の文字列が含まれる
- [ ] 5-3 で立てた contract 宣言 (`config.contract.enforced=true`) が schema.yml
      で維持されている (= 直した後も契約は外していない)
- [ ] 直した後の `dbt run --select mart_daily_sales_100knock` が PASS

## ヒント (詰まったら)

- **`Contract Error` が出ない**: 5-3 の contract 宣言が抜けている可能性。
  `manifest.json` で `config.contract.enforced=true` を再確認。`true` でないと
  build は通ってしまう。
- **`alias_types` で許容される変更**: dbt 1.6+ では `bigint` ↔ `int8`,
  `varchar` ↔ `text` などの Postgres alias は同一視される。`numeric(18,2)` ↔
  `integer` は alias ではないので必ず Contract Error になる。
- **契約を変える方が正解の場合もある**: ビジネス側から「今後は四捨五入で
  整数管理にします」と要求が来たら、SQL と schema.yml の両方を `integer` に
  揃えれば再び build が通る = **意図した契約変更**。Contract Error は
  「想定外の変更」を拾うための機構。
- **CI で「壊した状態」を採点するのは難しい**: build が落ちる状態を CI で
  そのまま fail ではなく PASS と判定するのは grading の仕組みが入り組むため、
  本問は **学習体験 (壊して落ちて直す) を log で証明** + **5-3 の宣言が
  維持されている** の二点を採点ポイントにしている。
- **A vs B の判断**: 9 割のケースで A (SQL を戻す) が正解。型を勝手に変えると
  BI 側が壊れる。B を選ぶのは「業務要件として整数化を決めた」という明示的な
  判断があるとき。

## 解答例

詳細は [`5-4-mart-contract-violation.solution.md`](5-4-mart-contract-violation.solution.md) を参照。
