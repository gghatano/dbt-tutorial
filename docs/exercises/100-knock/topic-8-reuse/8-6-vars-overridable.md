# 8-6: `vars` でビジネスパラメータをコードから分離し、`--vars` で CLI 上書きできる状態を作る

## シナリオ

Topic ④ で書いた `int_order_details_100knock` には「`sales_amount` がある程度大きい注文だけを下流 mart に流したい」という業務要件が後から発生した、という想定。素直に書けば `where sales_amount >= 100` を model SQL に直書きすれば動く。動くが、3 つの問題がある:

1. **マジックナンバー** — `100` という閾値の意味が SQL からは読めない (通貨? 件数? なぜ 100?)
2. **環境差**: dev では「全件流したい」、staging では「100 以上」、prod では「1000 以上」のようにしきい値が変わる場合に、3 通りの model を持つことになる
3. **テスト時の上書き不可**: CI で「閾値 0 で流したらどうなるか」を試したくても、SQL を編集して revert する流れを踏むことになる

dbt の `vars:` 宣言と `var('name', default)` 関数は、この種の **「コードに埋めると硬直化するが、設定として外に出すと柔軟になるパラメータ」** を扱うための機構。`dbt_project.yml` の `vars:` ブロックで「プロジェクト既定値」を宣言し、model 側は `var('min_order_amount')` で参照する。CLI 実行時は `dbt run --vars '{min_order_amount: 0}'` で上書きできる。コードは 1 つ、値は環境/実行ごとに切替可能 — Topic ⑧ の **「再利用」** 軸でいうと「同じ SQL を別パラメータで使い回す」依存設計の入口にあたる。

このエクササイズでは `dbt_project.yml` の `vars:` に `min_order_amount: 100` を追加し、`int_order_details_100knock` で `where sales_amount >= var('min_order_amount')` を効かせ、`dbt run --vars` で動的差し替えを目視確認する。

## 学べること

- `dbt_project.yml` の `vars:` ブロックでプロジェクト既定値を宣言する
- model 側で `var('name')` / `var('name', default)` を呼ぶ
- `dbt run --vars '{name: value}'` で CLI 上書きする
- 「コードは 1 つ、パラメータは外側で差し替え」 という再利用設計の感覚
- ビジネス値 (しきい値・税率・期間) を SQL に埋めない理由

## 前提

- Topic ② ③ ④ 完了 (`stg_*_100knock` / `int_order_details_100knock` が build 済み)
- Topic ⑧ 8-1〜8-5 完了 (macro / packages / seed の基本が動いている)
- `dbt/models/100-knock/topic-4/int_order_details_100knock.sql` が存在し、`sales_amount` 列を持っている

## 入力データ

不要。既存の `int_order_details_100knock` に `where` 句を 1 行追加するだけ。

## 課題

> **MVP への影響に注意**: 本問は `dbt/dbt_project.yml` を直接編集する。MVP の `dbt build` は通常通り通るが、`int_order_details_100knock` の行数が変わる。ロールバックは Step 5 を参照。

### Step 1: 現状確認 (フィルタなしの行数を覚えておく)

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT count(*), min(sales_amount), max(sales_amount)
FROM intermediate.int_order_details_100knock;
SQL
# 例: 10000|10.00|9800.00
```

「全件で N 行、最小 sales_amount は K 円」 という現状を控えておく。

### Step 2: `dbt_project.yml` に `vars:` を追加

`dbt/dbt_project.yml` のトップレベル (= `models:` と同階層) に **`vars:` ブロック** を追加し、`min_order_amount: 100` を宣言する。

具体的な書き方は解答例参照。ポイント:

- `vars:` は `models:` と同階層 (= ネストしない)
- 値は **数値リテラル** (文字列ではなく `100`、引用符不要)
- コメントで「何のしきい値か」「単位は何か」「なぜ 100 か」を 1 行残す

### Step 3: `int_order_details_100knock` に `var()` 呼び出しを足す

`dbt/models/100-knock/topic-4/int_order_details_100knock.sql` の末尾に `where sales_amount >= var('min_order_amount')` を追加する。

ポイント:

- `var('min_order_amount')` だけ書くと **未定義時に compile エラー**。`var('min_order_amount', 0)` のように **第 2 引数で default** を渡しておくと、`dbt_project.yml` を消した将来の自分にも優しい (ここは設計判断: 既定を宣言ファイルに集約したいなら default なし、防御的に書きたいなら default あり)
- `where` は最終 SELECT に対して効く必要がある。CTE 内に書くと外側で再フィルタが効かないので注意

### Step 4: `dbt run` 3 通りで行数が変わることを確認

```bash
set -a; source .env; set +a
cd dbt

# (a) デフォルト = 100 (dbt_project.yml の値)
../.venv/bin/dbt run --select int_order_details_100knock --profiles-dir .

# (b) CLI で 0 に上書き → 全件流れる
../.venv/bin/dbt run --select int_order_details_100knock \
  --vars '{min_order_amount: 0}' --profiles-dir .

# (c) CLI で 1000 に上書き → 大口注文だけ
../.venv/bin/dbt run --select int_order_details_100knock \
  --vars '{min_order_amount: 1000}' --profiles-dir .
```

各 run の後に Step 1 と同じ count クエリを叩き、**(a) < (b)** かつ **(c) < (a)** であることを目視確認する (= var が効いている証跡)。

### Step 5: 採点 / ロールバック

採点:

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-6-vars-overridable.grading.yaml
```

ロールバック (本演習を撤去するとき):

```bash
# 1. dbt_project.yml の vars: ブロックを削除
# 2. int_order_details_100knock.sql の where 行を削除
# 3. dbt run --select int_order_details_100knock で MVP 状態に戻す
```

## 完了条件

- [ ] `dbt/dbt_project.yml` のトップレベルに `vars:` ブロックがあり、`min_order_amount: 100` を宣言
- [ ] `int_order_details_100knock.sql` の最終 SELECT に `where sales_amount >= var('min_order_amount')` (相当) が入っている
- [ ] `dbt run --vars '{min_order_amount: 0}'` で行数が増えること、`--vars '{min_order_amount: 1000}'` で行数が減ることを目視確認
- [ ] 採点 yaml が PASS

## ヒント (詰まったら)

- **`var('foo')` で未定義エラー**: `dbt_project.yml` の `vars:` か CLI `--vars` のどちらかで値が必要。落とさず default を返したいなら `var('foo', 0)` のように **第 2 引数** を渡す。
- **`--vars` の引数形式**: YAML / JSON どちらでも可。`'{min_order_amount: 0}'` が最短。複数渡すなら `'{a: 1, b: 2}'`。
- **`vars:` を model 単位にスコープしたい**: `vars:` 配下に **package 名でネスト** することで「local_analytics プロジェクト内の var」「特定 package の var」と分離できる (`vars: {local_analytics: {min_order_amount: 100}}`)。本問はトップレベルで十分。
- **`var()` を `{{ config(...) }}` 内で使えるか**: 使える。例えば `{{ config(materialized=var('mat', 'view')) }}` のように物質化戦略の差し替えにも使える (ただし dbt parse 時に評価されるので注意)。
- **`where` を CTE 内に書いてしまった**: 最終 SELECT で再度効かせる必要がある。最終 SELECT 直前の CTE で絞るか、最終 SELECT に `where` を直書きするのが確実。
- **`dbt build` の場合**: `--vars` は `dbt build` でも同じく効く。CI で「閾値 0 でテスト」「閾値 1000 で本番想定」と切り替えるのが本来の使い方。
- **環境変数経由の var**: `--vars '{key: env_var("DBT_MIN_ORDER", "100")}'` のように Jinja で env_var を挟めば、CI の secret から値を流し込める (発展)。
- **`hardcoded` を見つけたら var 化**: 業務しきい値・期間 (90 日以内) ・税率 (0.1) ・通貨レート — これらは **var の有力候補**。「将来 SQL 編集で対応するか / vars で対応するか」 を区別する嗅覚を持つ。

## 解答例

詳細は [`8-6-vars-overridable.solution.md`](8-6-vars-overridable.solution.md) を参照。
