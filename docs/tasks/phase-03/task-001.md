# task-001: uv 環境 + requirements.txt

- Phase: 03
- Status: Done
- Owner: -
- Depends on: -
- Parallelizable with: phase-03/task-002（生成スクリプトは仮想環境完成前に実装可能）

## 目的
Python 3.12 + uv で依存関係を固定し、仮想環境を再現可能にする。

## 入力 / 前提
- spec §2 / §12

## 成果物
- `requirements.txt`（spec §12 準拠、差分なし）
- `.python-version`（`3.12`）

## 受入条件
- `uv venv` で `.venv` 作成
- `uv pip install -r requirements.txt` が成功
- `python -c "import dbt, psycopg, pandas, faker, dotenv"` が成功

## 実装メモ / 判断ログ
- `dbt-core==1.11.8`, `dbt-postgres==1.10.0`（spec固定）
- `psycopg[binary]==3.2.3`
- `Faker==33.3.1`, `pandas==2.2.3`, `python-dotenv==1.0.1`
- `.python-version` ファイル方針: ルートに `3.12` を置き、`uv` / `pyenv` 等が自動で 3.12 を選択できるようにする。これによりチーム内の Python バージョン揺らぎを抑える。なお `.gitignore` で除外設定があるため、明示的に `git add -f` でステージする。
- system Python 3.9.6 を回避した理由: spec §2 で Python 3.12 を要求している。dbt-core 1.11 / pandas 2.2 系などは 3.9 でも動くものがあるが、spec準拠と再現性のため、`uv venv --python 3.12` で 3.12 を取得して使用する（uv は必要なら CPython 3.12 を自動 fetch する）。
- 生じた warnings の扱い: `uv pip install` 実行時に警告メッセージは観測されなかった（Resolved 60 / Prepared 38 / Installed 60 で完了）。今後 dbt 起動時の deprecation warning などが出た場合は別タスクで個別対応する。

## 実行ログ

### uv --version
```
uv 0.9.17 (2b5d65e61 2025-12-09)
```

### uv venv --python 3.12 サマリ
```
Using CPython 3.12.12
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate
```

### uv pip install -r requirements.txt 最終サマリ
```
Resolved 60 packages in 630ms
Prepared 38 packages in 498ms
Installed 60 packages in 341ms
```

### import smoke 出力
```
$ .venv/bin/python -c "import dbt; import psycopg; import pandas; import faker; import dotenv; print('OK')"
OK
```

### パッケージバージョン確認 (`uv pip list | grep -iE '^(dbt-core|dbt-postgres|psycopg|pandas|faker|python-dotenv) '`)
```
dbt-core                  1.11.8
dbt-postgres              1.10.0
faker                     33.3.1
pandas                    2.2.3
psycopg                   3.2.3
python-dotenv             1.0.1
```
（`psycopg[binary]==3.2.3` 指定により `psycopg-binary==3.2.3` も同時にインストール済み。`dbt-postgres` の依存で `psycopg2-binary==2.9.12` も追加されている）
