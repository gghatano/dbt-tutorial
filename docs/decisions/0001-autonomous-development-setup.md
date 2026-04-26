# ADR 0001: 自律開発の進め方

- 日付: 2026-04-26
- ステータス: Accepted

## コンテキスト

`docs/spec.md` に基づき、ローカルELT/ELT学習環境（Postgres + Terraform + Python + dbt）を構築する。
ユーザーから「自律的にエージェントを呼び出しながら開発を進めて」「判断が必要な箇所は記録して進めてOK」「並列は最大2」との指示。

## 決定

1. **タスク分解**: `docs/tasks/phase-NN/task-MMM.md` 形式。phaseは依存関係順に並べ、phase内のtaskで独立可能なものを並列化。
2. **並列度**: 最大2エージェント。phase間の依存（環境→IaC→データ→dbt）は逐次、phase内独立タスクのみ並列。
3. **worktree運用**: CLAUDE.mdに従い `gitworktree/feature-<phase-NN-task-MMM>-<keyword>` で切る。mainには直接コミットしない。
4. **判断ログ**: 自律進行中の判断は本ディレクトリ `docs/decisions/NNNN-<topic>.md` に追記。
5. **完了基準**: spec.md の「13. 完了条件」をプロジェクト完了の単一基準とする。
6. **spec取扱い**: `docs/spec2.md` は `docs/spec.md` に統合済み。spec2.mdは履歴として残す（削除しない）。

## phase一覧（暫定）

- phase-01: 環境構築（docker-compose, Colima前提, smoke）
- phase-02: Terraform IaC（schema/role/grant）
- phase-03: Python基盤（uv, requirements, dummy生成, raw投入）
- phase-04: dbt基盤・staging（project/profiles/sources/staging4本）
- phase-05: intermediate/marts（int_order_details + mart 3本）
- phase-06: テスト・ドキュメント・統合（custom test, smoke_test.py, README, 完了条件確認）

## 結果

- 各phase完了時にmainへmerge、完了条件進捗を `docs/tasks/phase-NN/task-MMM.md` で `Status: Done` 化。
- 重要な技術的判断（バージョン固定、命名、デフォルト値など）は本フォルダに追記。
