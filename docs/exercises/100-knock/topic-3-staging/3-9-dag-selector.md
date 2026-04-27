# 3-9: `dbt run --select +stg_orders_100knock+` で DAG 演算子を使い、上下流が両方走ることを確認

## シナリオ

`stg_orders_100knock` を変更したとき、影響範囲は **上流 (source) と下流 (intermediate / mart)** の両方。dbt の `+` 演算子は DAG 上の隣接ノードを選択する強力な構文で、`+stg_orders_100knock+` と書くと「stg_orders の上流 + stg_orders 自身 + stg_orders の下流」を全部選んでくれる。

実務では「PR で 1 model 触ったら影響範囲を全部 build して確認」というワークフローが基本。`--select` を覚えていないと、毎回 `dbt build` でプロジェクト全部を回すか、依存を手で列挙する羽目になる。今回は `+` / `+model+` / `model+` の使い分けを **実行ログを見ながら** 体感し、結果を `dag-traversal.md` に書き残す。

なお Topic ④ (intermediate) が未着手なら、`stg_orders_100knock` の **下流が存在しない** のは正常。本問は「source → stg → (将来の下流)」の DAG を `dbt ls` で可視化することに重点を置く。

## 学べること

- `dbt ls --select <selector>` で DAG ノードを列挙する習慣
- `+model` / `model+` / `+model+` 3 種の DAG 演算子の意味
- `dbt run --select +stg_orders_100knock+` で「変更影響範囲だけ」走らせる
- source ノードは `--select` で列挙はされるが `dbt run` の対象には**ならない** (run できない)
- 実行ログを残して「いつ何を走らせたか」を再現可能にする

## 前提

- 3-1〜3-8 完了 (`stg_*_100knock` 4 model + `dbt_project.yml` の `100-knock:` セクション)
- Topic ② 2-2 で `sources.yml` に `raw_100knock.orders` が宣言済み
- `dbt parse` が通る
- `dbt run --select 100-knock` が初回成功している (= ベースライン)

## 入力データ

不要。学習者が `dbt ls` / `dbt run` を実行してログを取るだけ。

## 課題

### Step 1: DAG 演算子 3 種を試す

```bash
cd dbt

# 1. stg_orders_100knock 単独
dbt ls --select stg_orders_100knock --profiles-dir .

# 2. 上流 (source 含む) + stg_orders 自身
dbt ls --select +stg_orders_100knock --profiles-dir .

# 3. stg_orders 自身 + 下流 (もしあれば)
dbt ls --select stg_orders_100knock+ --profiles-dir .

# 4. 上流 + 自身 + 下流 (両方向)
dbt ls --select +stg_orders_100knock+ --profiles-dir .
```

### Step 2: 影響範囲を実際に run

```bash
# +stg_orders_100knock+ を build (run + test)
dbt build --select +stg_orders_100knock+ --profiles-dir .
```

source は run 対象にならないが、stg_orders とその下流 (Topic ④ 着手後は intermediate / mart) が走る。

### Step 3: dag-traversal.md に記録

`docs/exercises/100-knock/topic-3-staging/dag-traversal.md` を作成。以下を含める:

- 4 つの `dbt ls` の出力をコピー
- それぞれの selector が **何を選んだか** の一言コメント
- `dbt build --select +stg_orders_100knock+` の出力サマリ (PASS/FAIL 件数)
- 「Topic ④ 未着手なので下流は無い」のような注記 (該当する場合)

形式は自由。30〜80 行を目安。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-3-staging/3-9-dag-selector.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-3-staging/dag-traversal.md` が存在する
- [ ] `dbt ls --select +stg_orders_100knock+` を実行した記録がある
- [ ] 上流 (source:raw_100knock.orders) が DAG に出てくることを確認した
- [ ] `dbt build --select +stg_orders_100knock+` が成功する (Topic ④ 未着手なら stg_orders 単独でも OK)

## ヒント (詰まったら)

- **`+` の方向**: `+model` の `+` は「上流 (左側) を含む」、`model+` の `+` は「下流 (右側) を含む」、`+model+` で両方向。DAG を左から右に流れるイメージ (source → staging → mart)。
- **数字付き `+N`**: `2+stg_orders_100knock+2` のように `+` の前後に数字を付けると「2 hop までの上流 / 下流」を指定できる。デフォルト (数字無し) は無制限。
- **source は run できない**: `dbt ls --select +stg_orders_100knock` で `source.local_analytics.raw_100knock.orders` が表示されるが、`dbt run` の対象にはならない (source は外部から投入される前提)。`dbt build` でも同じ。
- **下流が無いと selector の結果が空に近い**: Topic ④ 未着手なら `stg_orders_100knock+` は `stg_orders_100knock` 自身 1 つだけ。これは正常。本問の採点も「下流 0 でも source + 自身が見えれば OK」と緩い設定。
- **`dbt ls --output json`** で機械可読な出力を得られる。CI 連携や pre-commit hook で「変更ファイルの影響範囲を自動算出」するとき必須。

## 解答例

詳細は [`3-9-dag-selector.solution.md`](3-9-dag-selector.solution.md) を参照。
