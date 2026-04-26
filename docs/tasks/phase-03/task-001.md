# task-001: uv 環境 + requirements.txt

- Phase: 03
- Status: Todo
- Owner: -
- Depends on: -
- Parallelizable with: phase-03/task-002（生成スクリプトは仮想環境完成前に実装可能）

## 目的
Python 3.12 + uv で依存関係を固定し、仮想環境を再現可能にする。

## 入力 / 前提
- spec §2 / §12

## 成果物
- `requirements.txt`（spec §12 準拠）
- `.python-version`（任意、3.12）

## 受入条件
- `uv venv` で `.venv` 作成
- `uv pip install -r requirements.txt` が成功
- `python -c "import dbt, psycopg, pandas, faker, dotenv"` が成功

## 実装メモ / 判断ログ
- `dbt-core==1.11.8`, `dbt-postgres==1.10.0`（spec固定）
- `psycopg[binary]==3.2.3`
- `Faker==33.3.1`, `pandas==2.2.3`, `python-dotenv==1.0.1`
