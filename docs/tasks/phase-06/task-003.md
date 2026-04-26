# task-003: README + 完了条件確認

- Phase: 06
- Status: Todo
- Owner: -
- Depends on: phase-06/task-001, phase-06/task-002
- Parallelizable with: -

## 目的
spec §13 の完了条件をすべて満たすことを確認し、README に環境構築・実行・トラブルシュートをまとめる。

## 成果物
- `README.md`
  - 概要
  - 前提（macOS + Colima）
  - セットアップ手順
  - 実行手順（spec §10 のコマンド）
  - 各層の説明
  - トラブルシュート（spec §15.7 ベース）
- `docs/decisions/` への完了報告（必要に応じて）

## 受入条件
- spec §13 の全項目に対し ✅ がつく
- README の手順を別ターミナルで写経して end-to-end が再現する（手動確認）
- `docker compose down -v && colima stop` 後、再度手順通り立ち上げて動作する（再現性確認）

## 実装メモ / 判断ログ
- 完了条件チェックリストは README 末尾 or `docs/decisions/0099-completion.md` に記録
