# task-001: docker-compose / .env.example / .gitignore 整備

- Phase: 01
- Status: Done
- Owner: -
- Depends on: -
- Parallelizable with: -

## 目的
PostgreSQL 17-alpine をローカルで起動できる docker-compose 構成と、接続情報の雛形・git無視設定を整える。

## 入力 / 前提
- spec.md §6 / §15（Colima利用）
- macOS + Colima前提

## 成果物
- `docker-compose.yml`
- `.env.example`（DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD）
- `.gitignore`（.env, **/.terraform, dbt/target, dbt/dbt_packages, .venv, __pycache__, data/raw/*.csv など）

## 受入条件
- `docker compose config` がエラーなく通る
- `docker compose up -d` で postgres コンテナが healthy
- `docker compose exec postgres pg_isready -U analytics_user -d analytics` が成功
- `.env.example` に必要な変数が揃っている
- `.gitignore` で生成物が無視される

## 実装メモ / 判断ログ
- DB接続情報: spec準拠（analytics / analytics_user / analytics_password / 5432）
- volume: `postgres_data`
- healthcheck: `pg_isready` を採用
- `data/raw/*.csv` は生成物として無視（generate_dummy_data.py で再生成可能なため）
- `.gitignore` は task-001 着手前から既に整備済みだったため変更なし（要件は満たしている）。
- compose 内の env は `${VAR:-default}` 構文を採用し、`.env` 未配置でもデフォルトで起動する一方、`.env` を置けば上書き可能とした。
- `container_name: local-data-postgres` を固定し、`docker exec` を使う後続スクリプトの可搬性を高めた。

## 実行ログ

```bash
$ docker compose config
# (要約) services.postgres / image=postgres:17-alpine / container_name=local-data-postgres
#         healthcheck CMD-SHELL pg_isready -U analytics_user -d analytics
#         interval=5s timeout=3s retries=10
#         volumes.postgres_data / ports 5432:5432
# warning なし、exit 0

$ docker compose up -d
 Container local-data-postgres Created
 Container local-data-postgres Started

$ docker inspect --format '{{.State.Health.Status}}' local-data-postgres
healthy   # 1 回目のポーリング（起動から ~10 秒）でhealthyに到達

$ docker compose exec -T postgres pg_isready -U analytics_user -d analytics
/var/run/postgresql:5432 - accepting connections   # exit 0
```

受入条件はすべて満たした。コンテナは phase-02 以降で利用するため、停止せずそのまま稼働中のまま残している。
