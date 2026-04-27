# 3-9 解答例

## docs/exercises/100-knock/topic-3-staging/dag-traversal.md

```markdown
# DAG 演算子で stg_orders_100knock の影響範囲を確認

実行日: 2026-04-26
実行者: 学習者
ベース: 3-1〜3-8 完了状態 (Topic ④ 未着手のため下流は存在しない)

## 1. 単独セレクト: `stg_orders_100knock`

```bash
$ dbt ls --select stg_orders_100knock --profiles-dir .
local_analytics.staging_100knock.stg_orders_100knock
```

- 結果: 1 ノード (model 自身のみ)
- 意図: 演算子なしで単一 model を指定する基本形

## 2. 上流含む: `+stg_orders_100knock`

```bash
$ dbt ls --select +stg_orders_100knock --profiles-dir .
source:local_analytics.raw_100knock.orders
local_analytics.staging_100knock.stg_orders_100knock
```

- 結果: 2 ノード (source 1 + model 1)
- 意図: 「stg_orders を変更した影響を上流側で確認」する用途
- `source:raw_100knock.orders` が出てくるのは Topic ② 2-2 の `sources.yml` 宣言が DAG に乗った証拠

## 3. 下流含む: `stg_orders_100knock+`

```bash
$ dbt ls --select stg_orders_100knock+ --profiles-dir .
local_analytics.staging_100knock.stg_orders_100knock
```

- 結果: 1 ノード (model 自身のみ)
- 意図: 「stg_orders の変更で何が壊れる可能性があるか」を下流方向に確認
- Topic ④ (intermediate) 未着手なので下流は存在しない。Topic ④ 着手後はここに `int_*` / `mart_*` が連なる

## 4. 両方向: `+stg_orders_100knock+`

```bash
$ dbt ls --select +stg_orders_100knock+ --profiles-dir .
source:local_analytics.raw_100knock.orders
local_analytics.staging_100knock.stg_orders_100knock
```

- 結果: 2 ノード (source 1 + model 1)
- 意図: PR で stg_orders を触ったときの「影響範囲を全部 build」する定番セレクタ

## 5. 影響範囲 build

```bash
$ dbt build --select +stg_orders_100knock+ --profiles-dir .
12:00:00  Found 8 models, 4 sources, 21 tests, ...
12:00:01  Concurrency: 4 threads (target='dev')
12:00:02  1 of 7 START sql view model staging_100knock.stg_orders_100knock ... [RUN]
12:00:03  1 of 7 OK created sql view model staging_100knock.stg_orders_100knock ... [CREATE VIEW in 0.5s]
12:00:04  2 of 7 START test not_null_stg_orders_100knock_order_id ... [RUN]
12:00:04  2 of 7 PASS not_null_stg_orders_100knock_order_id ... [PASS in 0.2s]
... (省略)
12:00:10  Completed successfully

Done. PASS=7 WARN=0 ERROR=0 SKIP=0 TOTAL=7
```

- run: 1 model (stg_orders_100knock 自身)
- test: 6 個 (order_id not_null/unique + customer_id/product_id/store_id の relationships + order_date not_null)
- source freshness は build には含まれない (`dbt source freshness` で別途)

## 学び

- `+model+` 構文を **PR レビュー時の影響範囲確認** で常用すれば、毎回プロジェクト全部 build する必要はない
- source は DAG に出てくるが run/test 対象にはならない (= 上流の責務)
- Topic ④ 着手後はこのコマンドの下流が増え、自動的に build 対象が広がる
- 「影響範囲が見える化されている」状態は dbt の DAG モデルの根本的な強み
```

**ポイント**:

- **dag-traversal.md は「実行ログのキャプチャ」**: 出題が緩い分、何を残すかは学習者の判断。最低限「4 つの `dbt ls` 出力 + 1 つの `dbt build` 結果」が乗っていれば OK。
- **Topic ④ 未着手前提**: `stg_orders_100knock+` の下流が空なのは正常。学習者が混乱しないよう、「Topic ④ 着手後はここが増える」とフォワードルッキングなコメントを残す。
- **source は run 対象にならない**: 重要な仕様。`dbt run --select +stg_orders_100knock` だと source は SKIP される (実行対象外として扱われる)。
- **`--output json`** で構造化出力可能: `dbt ls --select +stg_orders_100knock+ --output json` で各ノードの `unique_id` / `resource_type` が JSON で出る。pre-commit hook で機械処理する場合に必須。
- **`dbt build --select` の挙動**: `dbt build` は `dbt run + dbt test` を 1 ノードずつ atomic に走らせる。`--select` で対象を絞ると、そのサブグラフだけが build される。

## 実行例 (採点 shell_command 視点)

```
$ cd dbt && dbt ls --select +stg_orders_100knock+ --profiles-dir .
source:local_analytics.raw_100knock.orders
local_analytics.staging_100knock.stg_orders_100knock

$ cd dbt && dbt ls --select +stg_orders_100knock+ --profiles-dir . | wc -l
2

# source が含まれていることを確認
$ cd dbt && dbt ls --select +stg_orders_100knock+ --profiles-dir . | grep -c '^source:'
1

# model 自身が含まれていることを確認
$ cd dbt && dbt ls --select +stg_orders_100knock+ --profiles-dir . | grep -c 'stg_orders_100knock$'
1
```

## 解説まとめ

- **なぜ DAG 演算子?**: dbt の本質は「モデル間依存を `ref()` で宣言した DAG」。その DAG を実行時にスライスする道具が `--select` 演算子群。これを覚えていないと「常にプロジェクト全部 run」しかできず、フィードバックループが致命的に遅くなる。
- **`+` の方向は左→右の慣習**: 英語圏のテキストの読み方 (左→右) と一致。`+model` は「左側 = 上流」、`model+` は「右側 = 下流」。Postgres の `EXPLAIN` の出力順や Airflow の DAG 描画とも整合。
- **数字付き `+N`**: 大規模プロジェクトで `+model+` だと数百ノードになる場合、`1+model+1` (1 hop だけ) で範囲を絞る。「直接の上流・下流だけ確認」が PR レビュー時の現実解。
- **source は run できない理由**: source は dbt が **外部から投入される前提のテーブル** を抽象化したもの。dbt が run する権限を持たない領域。`dbt source freshness` で鮮度確認だけは可能。
- **PR レビューでの典型ワークフロー**:
  1. `git diff --name-only main..HEAD | grep '\.sql$'` で変更ファイルを抽出
  2. 各ファイルに対応する model 名を `+model+` で `dbt build`
  3. PASS なら「影響範囲のテストが通った」と PR コメント
  - これを GitHub Actions で自動化したいなら `--defer` + `--state` を組み合わせる (上級トピック)
- **dag-traversal.md は将来の自分への手紙**: コマンドの結果を貼っておくことで、半年後に「あれ、`+model+` って下流も入ってたっけ?」と迷ったときの参照になる。文書化はキャッシュ。
