# task-002: Colima起動確認 + Postgres疎通smoke

- Phase: 01
- Status: Todo
- Owner: -
- Depends on: phase-01/task-001
- Parallelizable with: -

## 目的
Colima起動 → docker compose 起動 → ホストからの psql 疎通までを確認する。

## 入力 / 前提
- task-001 完了
- `colima` インストール済み（spec §15.2）

## 成果物
- 確認ログ（task内に追記）
- 必要なら `scripts/smoke_db.sh`（任意）

## 受入条件
- `colima status` が running
- `docker compose up -d` 後、postgres コンテナが healthy
- ホストから `psql -h localhost -U analytics_user -d analytics -c '\\l'` が成功（または `docker compose exec postgres psql ...`）

## 実装メモ / 判断ログ
- ホスト疎通は `psql` がローカルにない可能性も考慮し、`docker compose exec postgres psql` を一次手段とする。
