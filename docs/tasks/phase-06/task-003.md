# task-003: README + 完了条件確認

- Phase: 06
- Status: Done
- Owner: -
- Depends on: phase-06/task-001, phase-06/task-002
- Parallelizable with: -

## 目的
spec §13 の完了条件をすべて満たすことを確認し、README に環境構築・実行・トラブルシュートをまとめる。

## 成果物
- `README.md`（更新済み）
  - 概要 / 前提（macOS + Colima）/ クイックスタート / 各層の説明 / トラブルシュート
  - 末尾に "完了状況 / Project Status" セクションを新設（phase 表 + §13 チェックリスト）
- `docs/decisions/0009-project-completion-summary.md`（新規作成）
- `docs/tasks/phase-06/task-003.md`（本ファイル、Status=Done）

## 受入条件
- [x] spec §13 の全項目に ✅
- [x] README にクイックスタート / トラブルシュート / 完了状況が網羅
- [~] `docker compose down -v && colima stop` 後の再現性ドリル → 本ターンではスキップ。
      ADR-0009 §5 に「ユーザーが実施する場合の手順」として残置。理由は判断ログ参照。

## 実行ログ（2026-04-26、本ブランチで実行）

`set -a; source ../.env; set +a` を `dbt` 配下で実行する前に必ず行った前提:

| 検証 | コマンド要約 | 出力サマリ |
|---|---|---|
| a. Postgres healthy | `docker ps --filter name=local-data-postgres --format '{{.Status}}'` | `Up 3 hours (healthy)` |
| b. Terraform schema/role | `\dn` / `SELECT rolname FROM pg_roles ...` | 4 schema (`raw/staging/intermediate/marts`, owner=dbt_user) + 2 role (`dbt_user`, `readonly_user`)。tfstate は worktree 外（main 経由）で管理されるため `terraform output/state list` は本 worktree では空、ただし実 schema/role は Postgres で確認済み |
| c. ダミーデータ生成 | `.venv/bin/python scripts/generate_dummy_data.py` + `wc -l data/raw/*.csv` | `customers 1001 / orders 10001 / products 101 / stores 21`（header 込み行数）。スクリプト出力も `1000 / 100 / 20 / 10000 rows` |
| d. raw 投入 | `.venv/bin/python scripts/load_raw_data.py` | `raw.customers 1,000 / products 100 / stores 20 / orders 10,000` |
| e. dbt run | `cd dbt && ../.venv/bin/dbt run --profiles-dir .` | `Done. PASS=8 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=8`（staging 4 view + intermediate 1 view + marts 3 table） |
| f. dbt test | `../.venv/bin/dbt test --profiles-dir .` | `Done. PASS=61 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=61` |
| g. mart 確認 | `docker exec -i local-data-postgres psql -U dbt_user -d analytics -c '\dt marts.*'` | 3 table: `mart_customer_sales / mart_daily_sales / mart_product_sales`（owner=dbt_user） |
| h. dbt docs generate | `../.venv/bin/dbt docs generate --profiles-dir .` | `target/manifest.json` (683KB) + `target/catalog.json` (10KB) 生成 |
| i. smoke_test | `.venv/bin/python scripts/smoke_test.py` | `[PASS] all smoke checks passed (raw.orders=10000, marts.mart_daily_sales=365)`、exit 0 |
| j. README 確認 | `README.md` 内容レビュー | クイックスタート / 構成図 / トラブルシュート / 完了状況の各セクションあり。差分追加で「完了状況」セクション、ADR-0006/0008/0009 リンク、`dbt/tests/` のディレクトリ追記を実施 |

## 実装メモ / 判断ログ

### README 仕上げ範囲

- 既存 README は良くまとまっており、全面書き直しはしなかった（タスク指示通り）。差分のみ:
  1. ディレクトリ構成図に `dbt/tests/` (custom singular test 4 本) を追記
  2. ドキュメントセクションに ADR-0006 / 0008 / 0009 へのリンクを追加
  3. 末尾に "完了状況 / Project Status" セクションを新設（phase 到達点表 + §13 チェックリスト + 次フェーズ候補）
- クイックスタート内のコマンドは `set -a; source .env; set +a` を含めて既に整合済み。
  追加修正なし。

### Terraform state の扱い

本 worktree (`feature-phase-06-task-003-completion`) では `infra/terraform/` 配下に
ローカル state が無い (`terraform state list` は state-not-found)。これは tfstate が
gitignored で main / 別 worktree のローカルに存在するため。
spec §13 の判定上は「実 Postgres に schema と role が存在する」ことが本質なので、
`\dn` と `pg_roles` の SQL クエリで verification を満たすと判断した。

### 再現性ドリルをスキップした根拠

- destructive な `docker compose down -v` / `terraform destroy` / `colima delete` は
  前 phase の実行済み状態（Postgres ボリューム + tfstate）を消すため、本ターン内で
  実施すると即時のロールバック手段が無い（タスク指示にも「禁止」と明記）。
- spec §13 の完了条件 9 項目に「再構築から動く」は含まれない（受入条件の外）。
- idempotency は (1) `load_raw_data.py` の DROP→CREATE→COPY と (2) dbt の
  view/table 再生成で実測（本タスク内で 2 度目の `dbt run` を実行して PASS=8 確認）。
- 将来ユーザーが再現性ドリルを実施する場合の手順は ADR-0009 §5 にチェックリスト形式で記載。

### 検証中に気づいた点

- `scripts/generate_dummy_data.py` のメッセージは「row 数」を 1000/100/20/10000 で
  返すが、`wc -l` 結果はヘッダ込みで +1（1001/101/21/10001）。両方を verification log
  に併記して齟齬を避けた。
- `dbt docs serve` は本タスクでは実行しなかった（バックグラウンド常駐になり worktree の
  動作確認には不要）。`docs generate` の artifact 生成のみで spec §13 を満たす。
- smoke_test の出力は warn-level チェック (staging/intermediate) も全て `[OK]` だった
  ため、「mart はあるが intermediate が空」のレアケースは発生していないことを確認。

### 次タスク

なし。MVP 完了。次フェーズ候補は ADR-0009 §4 を参照。
