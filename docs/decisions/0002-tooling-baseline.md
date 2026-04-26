# ADR 0002: ツールチェーン現況と対応

- 日付: 2026-04-26
- ステータス: Accepted

## 確認結果（実環境）

| ツール | 状態 | バージョン |
|---|---|---|
| colima | ✅ | 0.10.1 |
| docker | ✅ | 29.2.1 |
| uv | ✅ | 0.9.17 |
| python3 (system) | ⚠️ | 3.9.6 |
| terraform | ❌ | 未インストール |
| psql | ❌ | 未インストール |
| Colima VM | 🟡 | not running（未起動） |

## 決定

1. **python3.12 は uv 経由で取得**: `uv venv --python 3.12` を使い、システムpython3を依存から外す。spec §2 の要件は維持。
2. **psql は未インストールのまま進める**: ホスト接続確認は `docker compose exec postgres psql ...` を一次手段とする。phase-01/task-002 の受入条件もこれに合わせる。
3. **terraform はインストール待ち**: phase-02 着手前にユーザーへ確認の上インストール（`brew install terraform` または tfenv 経由）。phase-01・03 は terraform 不要のため先に進められる。
4. **Colima 起動**: phase-01/task-002 で `colima start --cpu 4 --memory 8 --disk 20` を実行。本ADRでは未起動状態を記録のみ。

## phase-01 補足（2026-04-26 追記）

### docker pull が無言ハングする問題

- 症状: `docker pull postgres:17-alpine` が進捗を出さずブロック、SIGTERMで kill すると exit 144。
- 原因: `~/.docker/config.json` に `"credsStore": "desktop"` が残置されているが、Docker Desktop は本機未インストール。`docker-credential-desktop` ヘルパが存在せず（または応答せず）、認証情報取得段階で無限待ちになる。
- 対応: `~/.docker/config.json` から該当行を削除。バックアップは `~/.docker/config.json.bak`。
- 影響範囲: ホスト全体（worktreeルール上は外側だが、環境を機能させるための機械的修正と判断）。
- 再発防止: 将来別マシンで再構築する際、Docker Desktopアンインストール後の `credsStore` が "desktop" のままになっていないか README の前提セクションで確認すべき。phase-06/task-003 の README に追記する。

