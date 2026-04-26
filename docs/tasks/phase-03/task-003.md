# task-003: load_raw_data.py

- Phase: 03
- Status: Todo
- Owner: -
- Depends on: phase-02/task-002 (raw schema が必要), phase-03/task-001, phase-03/task-002
- Parallelizable with: -

## 目的
生成CSVを raw schema に冪等にロードする。

## 入力 / 前提
- spec §11.2

## 成果物
- `scripts/load_raw_data.py`

## 受入条件
- 1回目実行で raw.customers/products/stores/orders が件数通り存在
- 2回目以降の再実行でも件数が変わらない（truncate or drop+create でidempotent）
- 環境変数（.env）から接続情報を取得

## 実装メモ / 判断ログ
- 接続: psycopg3 (`psycopg.connect`)
- ロード方式: `COPY ... FROM STDIN`（pandas読み出し → io.StringIO 経由）
- 型: テーブル定義は最小限（idはBIGINT、文字列はTEXT、日付はDATE、金額はNUMERIC(12,2)）
- raw層は型変換しない方針だが、CSVの素直な型は付与する（dbt staging で再変換）
- ロード前 `TRUNCATE` で冪等化
