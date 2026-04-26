# セットアップ詳細

README のクイックスタートを補足する詳細手順。`docker compose up` から `dbt run` / `dbt test` 通過までを 1 ファイルで完結させる。

## 採用技術

| 区分 | 技術 | バージョン | 役割 |
|---|---|---|---|
| Linux VM (macOS) | Colima | 0.10+ | Docker を動かす軽量 VM。Docker Desktop の代替 |
| コンテナ実行 | Docker Compose | v2 系 | PostgreSQL / Metabase の起動 |
| IaC | Terraform | 1.14.9 | schema / role / grant の宣言的構築 |
| DWH 代替 | PostgreSQL | 17-alpine | analytics DB |
| Python | Python | 3.12 | uv が自動取得するので別途インストール不要 |
| パッケージ管理 | uv | 0.6+ | Python 依存解決 |
| dbt Core | dbt-core | 1.11.8 | SQL transform の DAG 管理 |
| dbt Adapter | dbt-postgres | 1.10.0 | PostgreSQL アダプタ |

## 前提

- macOS（Apple Silicon / Intel 両対応）。Linux でも動くが手順未検証。
- Homebrew インストール済み。
- Docker Desktop は **使用しない**。Colima を使う。
- Docker Desktop からの移行者: `~/.docker/config.json` の `"credsStore": "desktop"` を削除しておく（残っていると `docker pull` が無言ハングする。詳細は [troubleshooting.md](troubleshooting.md) と [ADR-0002](decisions/0002-tooling-baseline.md)）。

## cwd 規約

このドキュメントのすべてのコードブロックは、リポジトリルートを `~/repo` として、ブロック直前に `# cwd: ...` で実行ディレクトリを明示する。

## ステップ別手順

### 1. ツールインストール

```bash
# cwd: ~/repo
brew install colima docker docker-compose uv
brew install hashicorp/tap/terraform
```

uv は Python 自体も管理する。`uv venv --python 3.12` が必要バージョンを自動 DL するため、システム python3 / pyenv は不要。

### 2. Colima 起動

```bash
# cwd: ~/repo
# 既存 VM があれば先に停止（リソース変更のため）
colima status >/dev/null 2>&1 && colima stop
colima start --cpu 4 --memory 8 --disk 20
colima status   # arch / runtime / cpu / memory が表示されること
```

Metabase まで動かす場合は memory 8 GB 必須（Metabase は amd64 エミュレーションで動く）。

### 3. PostgreSQL 起動

```bash
# cwd: ~/repo
docker compose up -d postgres
docker exec local-data-postgres pg_isready -U analytics_user -d analytics
```

### 4. Terraform で schema / role 構築

```bash
# cwd: ~/repo/infra/terraform
terraform init
terraform apply -auto-approve
```

`variables.tf` のデフォルトで `analytics_user / analytics_password` 接続するため、`.env` の値を変えた場合は `-var` か `terraform.tfvars` で同じ値を渡す。

### 5. Python 環境

```bash
# cwd: ~/repo
uv venv --python 3.12
uv pip install -r requirements.txt
```

Apple Silicon では `psycopg` 単体だと libpq の build 失敗が起こりやすい。`requirements.txt` は `psycopg[binary]` を使っている。

### 6. `.env` の用意

```bash
# cwd: ~/repo
cp .env.example .env
# 必要なら METABASE_ADMIN_PASSWORD / METABASE_DB_RO_PASSWORD を埋める
```

`.env.example` には `analytics_user / analytics_password`（Terraform / 初期化用）が入っている。dbt から接続する `dbt_user / dbt_password` は Terraform が作ったあと、必要に応じて `.env` を書き換える。

### 7. ダミーデータ生成 + raw 投入

```bash
# cwd: ~/repo
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py
```

### 8. dbt 実行

dbt は `profiles.yml` 内で `{{ env_var('DB_HOST', ...) }}` という形でシェル環境変数を読む。`.env` ファイル自体は dbt には見えないので、シェルに流し込んでから dbt を呼ぶ。

```bash
# cwd: ~/repo
set -a; source .env; set +a
```

```bash
# cwd: ~/repo/dbt
../.venv/bin/dbt debug --profiles-dir .
../.venv/bin/dbt run --profiles-dir .
../.venv/bin/dbt test --profiles-dir .
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve --profiles-dir .
```

成功すると `marts.mart_daily_sales` / `marts.mart_customer_sales` / `marts.mart_product_sales` が `analytics` DB に生成される。

### `.env` を dbt に渡す仕組み

| 呼び出し元 | `.env` の読み方 | 補足 |
|---|---|---|
| dbt CLI | シェル環境変数 経由 (`{{ env_var(...) }}`) | `set -a; source .env; set +a` で流し込んでから呼ぶ |
| Python スクリプト (`scripts/*.py`) | `python-dotenv` が `.env` を直接読む | 流し込み不要 |
| docker compose | `${VAR:-default}` 形式で `.env` を直接読む | 流し込み不要 |
| Terraform | `variables.tf` のデフォルト値 | `.env` は読まない |

## 動作確認 (smoke test)

```bash
# cwd: ~/repo
set -a; source .env; set +a
.venv/bin/python scripts/smoke_test.py
```

`[PASS] all smoke checks passed (raw.orders=10000, marts.mart_daily_sales=365)` が出れば OK。
内部で何を見ているかは [ADR-0008](decisions/0008-smoke-test-strategy.md)。

## ゼロから再構築する

新しいマシンで同じ環境を作るための一括手順は [ADR-0009 §5](decisions/0009-project-completion-summary.md) を参照。
