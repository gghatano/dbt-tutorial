# task-001: docker-compose / .env.example / .gitignore 整備

- Phase: 01
- Status: Todo
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
