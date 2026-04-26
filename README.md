# local-data-platform (dbt-tutorial)

ローカル環境で **IaC・DWH・dbt・データマート・ELT・テスト・ドキュメント生成** を一通り練習できる最小構成のデータ基盤チュートリアル。

## 目的

「データの ELT / ETL を実際に動かして理解する」ことを目的に、以下の流れを 1 リポジトリで再現できるようにする。

1. **IaC** で DB（schema / role / grant）を定義する
2. **raw 層**にダミーデータを投入する
3. **dbt** で staging → intermediate → marts へ変換処理を管理する
4. **データマート**を作成する（日次売上 / 顧客別売上 / 商品別売上）
5. **テスト** と **ドキュメント生成** で品質と可観測性を担保する

スケジューラ・BI・クラウド DWH・CI/CD は意図的に含めない（次フェーズの対象）。

## アーキテクチャ

```text
   CSV (Faker)
        │
        ▼  COPY (psycopg3)
 ┌────────────┐
 │  raw       │   ← Terraform で schema / role 構築
 └────────────┘
        │
        ▼  dbt (view)
 ┌────────────┐
 │  staging   │   ← 型変換・列名統一・PK/FK テスト
 └────────────┘
        │
        ▼  dbt (view)
 ┌────────────┐
 │ intermediate│  ← 注文 × 顧客 × 商品 × 店舗 結合 + sales_amount
 └────────────┘
        │
        ▼  dbt (table)
 ┌────────────┐
 │  marts     │   ← daily / customer / product sales
 └────────────┘
```

## 採用技術

| 区分 | 技術 | バージョン |
|---|---|---|
| コンテナ実行 | Docker Compose | v2 系 |
| Linux VM (macOS) | Colima | 0.10+ |
| IaC | Terraform | 1.14.9 |
| DWH 代替 | PostgreSQL | 17-alpine |
| Python | Python | 3.12 |
| パッケージ管理 | uv | 0.6+ |
| dbt Core | dbt-core | 1.11.8 |
| dbt Adapter | dbt-postgres | 1.10.0 |

## 前提

- macOS（Apple Silicon / Intel 両対応）。Linux でも動くが手順未検証。
- Homebrew インストール済み
- Docker Desktop は **使用しない**。Colima を使う

## クイックスタート

```bash
# 1. ツール
brew install colima docker docker-compose
brew install hashicorp/tap/terraform
# uv は https://docs.astral.sh/uv/getting-started/installation/ 参照

# 2. Colima 起動
colima start --cpu 4 --memory 8 --disk 20

# 3. PostgreSQL 起動
docker compose up -d
docker exec local-data-postgres pg_isready -U analytics_user -d analytics

# 4. Terraform で schema / role 構築
cd infra/terraform
terraform init
terraform apply -auto-approve
cd ../../

# 5. Python 環境
uv venv --python 3.12
uv pip install -r requirements.txt

# 6. .env を用意（dbt_user 接続）
cat <<EOF > .env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=analytics
DB_USER=dbt_user
DB_PASSWORD=dbt_password
EOF

# 7. ダミーデータ生成 + raw 投入
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py

# 8. dbt（環境変数を流し込んでから）
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt debug --profiles-dir .
../.venv/bin/dbt run --profiles-dir .
../.venv/bin/dbt test --profiles-dir .
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve --profiles-dir .
```

すべて成功すると、`marts.mart_daily_sales` / `marts.mart_customer_sales` / `marts.mart_product_sales` が `analytics` DB に生成される。

## ディレクトリ構成

```text
.
├── README.md
├── docker-compose.yml         # PostgreSQL 17-alpine
├── .env.example               # 接続情報の雛形（実体は .env で gitignored）
├── requirements.txt           # Python 依存（dbt-core, psycopg, Faker, ...）
├── infra/terraform/           # schema / role / grant の IaC
├── scripts/                   # ダミーデータ生成・raw ロード・smoke
├── data/raw/                  # 生成 CSV（gitignored・再生成可）
├── dbt/                       # dbt project (local_analytics)
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── sources.yml        # raw を source 宣言
│   │   ├── staging/           # stg_* (view)
│   │   ├── intermediate/      # int_* (view)
│   │   └── marts/             # mart_* (table)
│   └── macros/
│       └── get_custom_schema.sql  # generate_schema_name override
└── docs/
    ├── spec.md                # プロジェクト仕様（本ドキュメントの権威）
    ├── tasks/                 # phase-NN/task-MMM.md でタスク管理
    └── decisions/             # ADR（重要決定の記録）
```

## ドキュメント

- **[docs/spec.md](docs/spec.md)** — プロジェクト仕様。完了条件はここの §13 が単一基準。
- **[docs/tasks/](docs/tasks/)** — phase / task 単位の進捗とログ。
  - phase-01: 環境構築
  - phase-02: Terraform IaC
  - phase-03: Python 基盤・raw 投入
  - phase-04: dbt project 初期化・staging
  - phase-05: intermediate / marts
  - phase-06: テスト・ドキュメント・統合
- **[docs/decisions/](docs/decisions/)** — Architecture Decision Records。
  - [0001 自律開発の進め方](docs/decisions/0001-autonomous-development-setup.md)
  - [0002 ツールチェーン現況と Docker credsStore 問題](docs/decisions/0002-tooling-baseline.md)
  - [0004 raw ロード戦略](docs/decisions/0004-raw-load-strategy.md)
  - [0005 dbt 設定（schema 解決 macro）](docs/decisions/0005-dbt-config.md)

## トラブルシュート

### `docker pull` が無言ハングする / `exit 144`

`~/.docker/config.json` に `"credsStore": "desktop"` が残っているのに Docker Desktop が無いと、credential helper が応答せずハングする。  
**対策**: 該当行を削除（バックアップ推奨）。詳細は [ADR-0002](docs/decisions/0002-tooling-baseline.md) を参照。

### `dbt run` で `&lt;target&gt;_marts` のような prefix schema が作られる

dbt-postgres のデフォルトでは `+schema: marts` は `&lt;target_schema&gt;_marts` に解決される。  
本プロジェクトは `dbt/macros/get_custom_schema.sql` で `generate_schema_name` を override し、`marts` schema をそのまま使う。詳細は [ADR-0005](docs/decisions/0005-dbt-config.md)。

### Apple Silicon で特定イメージが遅い

postgres:17-alpine は arm64 ネイティブで問題なし。x86 依存サービスを追加する場合は `platform: linux/amd64` を指定可能。

### Postgres に接続できない

```bash
colima status                                  # running 確認
docker compose ps                              # postgres healthy 確認
lsof -i :5432                                  # ポート競合確認
docker exec local-data-postgres pg_isready -U analytics_user -d analytics
```

## ライセンス

学習用の個人プロジェクト。明示ライセンスなし。
