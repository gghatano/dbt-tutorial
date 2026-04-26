# task-002: smoke_test.py

- Phase: 06
- Status: Todo
- Owner: -
- Depends on: phase-05/task-002
- Parallelizable with: phase-06/task-001

## 目的
DB接続・raw投入・mart生成を end-to-end で確認するsmoke。

## 入力 / 前提
- spec §11.3

## 成果物
- `scripts/smoke_test.py`

## 受入条件
- `python scripts/smoke_test.py` が exit 0
- DB接続失敗時 / 件数0時に明確なエラーメッセージで exit 1
- 確認内容:
  - PostgreSQL接続できる
  - raw.orders 件数 >= 1
  - marts.mart_daily_sales 件数 >= 1

## 実装メモ / 判断ログ
- 接続は psycopg3、env_var 使用
