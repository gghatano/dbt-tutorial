# task-002: smoke_test.py

- Phase: 06
- Status: Done
- Owner: -
- Depends on: phase-05/task-002
- Parallelizable with: phase-06/task-001

## 目的
DB接続・raw投入・mart生成を end-to-end で確認するsmoke。

## 入力 / 前提
- spec §11.3

## 成果物
- `scripts/smoke_test.py`
- `docs/decisions/0008-smoke-test-strategy.md`

## 受入条件
- `python scripts/smoke_test.py` が exit 0
- DB接続失敗時 / 件数0時に明確なエラーメッセージで exit 1
- 確認内容:
  - PostgreSQL接続できる
  - raw.orders 件数 >= 1
  - marts.mart_daily_sales 件数 >= 1

## 実行ログ

### ハッピーパス

```
$ set -a; source .env; set +a
$ .venv/bin/python scripts/smoke_test.py
[OK] connection: SELECT 1 succeeded
[OK] raw.orders: count=10000
[OK] marts.mart_daily_sales: count=365
[OK] staging.stg_orders: count=10000 (warn-level)
[OK] intermediate.int_order_details: count=10000 (warn-level)
[PASS] all smoke checks passed (raw.orders=10000, marts.mart_daily_sales=365)
$ echo $?
0
```

### 異常系シミュレーション（コミットしていない口頭確認）

`DB_PASSWORD=wrong`（接続認証を意図的に失敗させる）で 1 回実行。

```
$ DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=analytics DB_USER=dbt_user DB_PASSWORD=wrong .venv/bin/python scripts/smoke_test.py
[FAIL] connection: OperationalError: connection failed: connection to server at "127.0.0.1", port 5432 failed: FATAL:  password authentication failed for user "dbt_user"
$ echo $?
1
```

確認結果:
- `[FAIL] connection:` プレフィックス付きで 1 行のエラーが stdout に出る。
- exit code は 1。
- 終了後、`.env` の `DB_PASSWORD` は `dbt_password` のまま（変更していないので戻し作業不要）。

## 実装メモ / 判断ログ

- **psycopg3 接続のタイムアウト指定**: `psycopg.connect(dsn, connect_timeout=5)`
  を採用。ローカル Postgres の往復は数 ms オーダーで 5 秒は十分なヘッドルーム
  があり、ハング / 起動途中状態に対しては fail-fast に倒せる。CI ステップの
  デフォルトより十分小さく、smoke の "速く落とす" 趣旨に合う。詳細は ADR-0008
  §3。

- **必須 env 変数の検証戦略**: `load_raw_data.py` と同じく `python-dotenv` で
  `REPO_ROOT/.env` を `override=False` 読み込みし、`DB_HOST/PORT/NAME/USER/PASSWORD`
  を一括検証。欠けていれば `[FAIL] config: Missing required environment variables: ...`
  で 1 行化して exit 1。`.env` が無くても shell で export 済みなら動く（CI/コンテナ
  互換）。

- **staging/intermediate を補助 (warn) チェックに含めた理由**: spec §13 の
  「`dbt run` が成功する」という完了条件を smoke が間接的に観測できるように、
  `staging.stg_orders` / `intermediate.int_order_details` の件数を `[WARN]` で
  出す。ただし spec §11.3 が strict として要求しているのは 3 項目のみなので、
  warn 件数 0 は exit 1 にしない（仕様契約を超えて smoke が落ちると、仕様変更
  なしに CI の判定が強くなってしまうため）。詳細は ADR-0008 §1, §2。

- **失敗メッセージのフォーマット意図**: 行頭プレフィックスを `[OK] / [WARN] /
  [FAIL] / [PASS]` の 4 種に固定し、`[FAIL] <what>: <how>` の 1 行で出す
  （例: `[FAIL] raw.orders: count is 0 (expected >= 1)`、
  `[FAIL] connection: OperationalError: ...`）。`psycopg` の改行入り例外
  メッセージは `replace("\n", " ")` で単行化してログ grep を容易にする。
  詳細は ADR-0008 §4。

- **例外捕捉の粒度**: `psycopg.Error` のみ catch し、`NameError` 等のプログラム
  バグは traceback で表面化させる。bare `except Exception` は smoke の信頼性を
  下げるだけなので採らない。詳細は ADR-0008 §5。

- **spec §11.3 への厳密対応**: strict 判定対象は spec §11.3 の 3 項目（接続・
  `raw.orders` >= 1・`marts.mart_daily_sales` >= 1）のみ。仕様外の失敗で
  CI を赤にしないため、追加の dbt 整合性検証等は意図的にスコープ外（それは
  `dbt test` の責務）。
