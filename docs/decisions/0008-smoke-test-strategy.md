# ADR 0008: smoke_test.py の検査範囲とエラー方針

- 日付: 2026-04-26
- ステータス: Accepted
- コンテキスト: phase-06/task-002 `scripts/smoke_test.py`
- 関連: spec §11.3, §13, ADR-0004

## 背景

spec §11.3 は smoke test の必須チェックを 3 項目に明示している。

1. PostgreSQL に接続できる
2. `raw.orders` 件数 >= 1
3. `marts.mart_daily_sales` 件数 >= 1

一方 spec §13（完了条件）は `dbt run` の成功も求めており、staging / intermediate
が空のまま mart だけ別経路で作られているケースを smoke が見落とす余地があった。
ここで「strict 範囲をどう決めるか」「補助情報をどう出すか」を整理する。

## 決定

### 1. strict（exit 1 判定）は spec §11.3 の 3 項目に厳密に限定

`raw.orders` と `marts.mart_daily_sales` の件数 >= 1、および `SELECT 1` 接続のみ
を exit 1 判定対象にする。spec の "smoke" 契約は §11.3 で明示されており、
これを越えて exit 1 を増やすと「仕様外の理由でビルドが落ちる」CI が出来上がる。

### 2. staging / intermediate は warn-level チェックとして実装

`staging.stg_orders` と `intermediate.int_order_details` の件数を `[WARN]` で
出力する。件数 0 でも exit 0 のまま。これにより:

- mart は作られたが intermediate が壊れている、というレアケースが目視で分かる。
- spec §13 の「`dbt run` が成功する」を **間接的に** ヒューマンチェックできる。
- exit code は spec §11.3 の strict 契約のままなので、CI 動作は不変。

### 3. 接続タイムアウト = 5 秒

ローカル Postgres の健全な往復時間は数 ms 〜 数十 ms。5 秒は健全ケースを十分
許容しつつ、ハング状態の Postgres / 起動途中状態に対しては fail-fast に寄せる
妥当な閾値。CI ステップのデフォルトタイムアウトより十分小さい。

### 4. 失敗メッセージは 1 行・固定プレフィックス

`[OK] / [WARN] / [FAIL] / [PASS]` の 4 種を行頭に付ける。失敗時は
`[FAIL] <what>: <how>` の形（例: `[FAIL] raw.orders: count is 0 (expected >= 1)`、
`[FAIL] connection: OperationalError: ...`）。改行を含む psycopg のメッセージは
`replace("\n", " ")` で 1 行化し、`grep "[FAIL] "` で全失敗を 1 行ずつ抽出可能に
する（CI ログ・人間スキャン双方に有利）。

### 5. 必須 env 変数の検証戦略

`load_raw_data.py` と同じく `python-dotenv` で `REPO_ROOT/.env` を `override=False`
で読み込み、`DB_HOST/PORT/NAME/USER/PASSWORD` を一括検証。欠けていれば
`[FAIL] config: Missing required environment variables: ...` で 1 行化して
exit 1。`.env` が無くても shell で env が export されていれば動く（ADR-0004 と
同じ約束）。

## 検討した案

### strict / warn の境界

| 案 | 説明 | 採否 |
|---|---|---|
| A. spec §11.3 の 3 項目のみ strict、staging/intermediate は warn | 上記 | **採用** |
| B. 4 mart 全部を strict | spec §11.3 を超える | 不採用（spec 契約逸脱） |
| C. staging / intermediate も strict | 同上 | 不採用 |
| D. 補助チェック無し | spec 最小実装 | 不採用（運用観点で diagnostics 不足） |

### 接続タイムアウト

| 値 | 評価 | 採否 |
|---|---|---|
| 5 秒 | 健全往復 << 閾値 << CI step | **採用** |
| 30 秒 | 起動直後の Postgres も拾うが fail が遅い | 不採用 |
| 無指定 (libpq 既定) | 環境依存・予測しづらい | 不採用 |

### 例外捕捉の粒度

| 案 | 説明 | 採否 |
|---|---|---|
| A. `psycopg.Error` のみ catch、その他は伝播 | プログラミングエラーは traceback で出る | **採用** |
| B. bare `Exception` で全部 catch | 隠蔽リスクあり | 不採用 |

## 採用理由

1. **spec 契約を厳密に守る**: smoke の "成功" 定義を勝手に強化しない。仕様外の
   失敗ノイズで CI が赤くなるのは smoke の趣旨に反する。
2. **運用 diagnostics は warn で出す**: exit code を変えずに「mart はあるが
   intermediate が空」のような異常を視認できるようにする。
3. **fail-fast な 5 秒**: ローカル DWH のレイテンシ実測（数 ms）から見ると
   桁違いに保守的で、誤検知の余地はほぼ無い。
4. **1 行 [FAIL] プレフィックス**: ログを行単位で grep する運用と相性が良い。
   `psycopg` のマルチライン例外メッセージも単行化することで一貫させる。
5. **`psycopg.Error` 限定 catch**: バグによる `NameError` 等まで握りつぶすと
   smoke の信頼性が下がる。DB エラーだけ catch して他は traceback を出す。

## 不採用案の理由

- **strict 範囲拡張**: spec §11.3 を超える「失敗」を smoke が宣言すると、
  仕様変更なしに後から判定が強くなり、依存スクリプト（CI 等）の挙動を破る。
- **長いタイムアウト**: smoke の目的は「速く健全性を出す」ことで、長時間待って
  詳細診断するのは smoke の役割ではない（その役割は `dbt test` 等が担う）。
- **bare except**: 例外隠蔽は smoke の信頼性を下げる方向にしか効かない。

## 異常系の確認結果（task-002 検証時）

`DB_PASSWORD=wrong` で実行すると `[FAIL] connection: OperationalError: ...
password authentication failed for user "dbt_user"` が 1 行で表示され、
exit code は 1。期待どおりの動作を確認した。

## 関連する決定

- ADR-0004 (raw load strategy): `python-dotenv` の `override=False` ロード方針と
  接続ロール `dbt_user` の使用を継承。
- spec §11.3 / §13: smoke の必須チェックと完了条件の出典。
