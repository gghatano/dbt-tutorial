# task-002: Colima起動確認 + Postgres疎通smoke

- Phase: 01
- Status: Done
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
- 実行時、`~/.docker/config.json` の `credsStore: desktop` 設定により `docker pull` が `docker-credential-desktop` を起動して無限待機する事象に遭遇。Docker Desktop は本環境に存在せず Colima 専用のため、`credsStore` 行を削除して回避（旧設定は `~/.docker/config.json.bak` に退避）。リポジトリ外の作業マシン固有の補正につき、worktree 内へのコミットは行わない。

## 実行ログ

```bash
$ colima status
colima is running using macOS Virtualization.Framework
arch: aarch64
runtime: docker
mountType: virtiofs
docker socket: unix:///Users/<user>/.colima/default/docker.sock

# 初回起動が必要だった場合の手順:
# $ colima start --cpu 4 --memory 8 --disk 20

$ docker compose up -d
 Container local-data-postgres Started

$ docker compose ps
NAME                  IMAGE                COMMAND                   SERVICE    CREATED          STATUS                    PORTS
local-data-postgres   postgres:17-alpine   "docker-entrypoint.s…"   postgres   12 seconds ago   Up 11 seconds (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp

$ docker compose exec -T postgres pg_isready -U analytics_user -d analytics
/var/run/postgresql:5432 - accepting connections   # exit 0

$ docker compose exec -T postgres psql -U analytics_user -d analytics -c '\l'
   Name    |     Owner      | Encoding | ...
-----------+----------------+----------+----
 analytics | analytics_user | UTF8     | ...
 postgres  | analytics_user | UTF8     | ...
 template0 | analytics_user | UTF8     | ...
 template1 | analytics_user | UTF8     | ...
(4 rows)
```

ホスト localhost:5432 ポートも `0.0.0.0:5432->5432/tcp` で公開済み。`psql` がローカルに無いため一次確認は `docker compose exec` 経由で実施した（spec §15.8 の手順と等価）。

受入条件はすべて満たした。コンテナは停止せずそのまま稼働中。
