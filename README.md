# local-data-platform (dbt-tutorial)

ローカル環境で **IaC・DWH・dbt・データマート・ELT・テスト** を一通り触れる、最小構成のデータ基盤チュートリアル。

## 何ができるようになるか

- **dbt** で SQL transform を DAG として宣言的に管理する
- **raw → staging → intermediate → marts** の 4 層構成でデータを整理する
- **Terraform** で schema / role / grant を IaC として持つ
- **テスト・ドキュメント** で品質を担保する
- **Metabase** で marts を可視化する（任意）

スケジューラ・クラウド DWH・CI/CD は意図的に含めない（卒業後の発展テーマ）。

## アーキテクチャ

```text
   CSV (Faker) ─COPY─▶ raw ─dbt(view)─▶ staging ─dbt(view)─▶ intermediate ─dbt(table)─▶ marts ─SELECT─▶ Metabase
```

詳細は [docs/architecture.md](docs/architecture.md)。

## クイックスタート

```bash
# 1. ツール
brew install colima docker docker-compose uv
brew install hashicorp/tap/terraform

# 2. Colima + Postgres
colima start --cpu 4 --memory 8 --disk 20
docker compose up -d postgres

# 3. schema / role を Terraform で構築
cd infra/terraform && terraform init && terraform apply -auto-approve && cd ../../

# 4. Python 環境 + .env
uv venv --python 3.12
uv pip install -r requirements.txt
cp .env.example .env

# 5. ダミーデータ生成 + raw 投入
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py

# 6. dbt 実行（環境変数を流し込んでから dbt/ で実行）
set -a; source .env; set +a
cd dbt && ../.venv/bin/dbt run --profiles-dir . && ../.venv/bin/dbt test --profiles-dir .
```

詰まったら [docs/setup.md](docs/setup.md)（cwd 注釈付きの詳細手順）と [docs/troubleshooting.md](docs/troubleshooting.md) を見る。

## 学習ロードマップ

1. **クイックスタート**で `dbt run` / `dbt test` を成功させる
2. **[docs/dashboard.md](docs/dashboard.md)** で Metabase を立ち上げ、marts を可視化する（SQL の結果が画面で見えると学習意欲が上がる）
3. **[docs/exercises/](docs/exercises/README.md)** の 10 問を解く
   - 01〜05: dbt の基本を一周（CSV 取り込み / マート / incremental / snapshot / seed+macro）
   - 06〜10: 運用に近い機能（exposures / packages / 自作 generic test / hooks / 失敗行のデバッグ）
4. **次フェーズ候補**: Airflow / dbt-bigquery / GitHub Actions / Great Expectations（[ADR-0009 §4](docs/decisions/0009-project-completion-summary.md)）

## ドキュメント

- [docs/setup.md](docs/setup.md) — セットアップ詳細手順（cwd 規約付き）
- [docs/architecture.md](docs/architecture.md) — レイヤー / ロール / ディレクトリ構成
- [docs/troubleshooting.md](docs/troubleshooting.md) — エラー逆引き
- [docs/spec.md](docs/spec.md) — プロジェクト仕様（権威）
- [docs/dashboard.md](docs/dashboard.md) — Metabase 起動手順
- [docs/exercises/](docs/exercises/README.md) — 練習問題セット（10 問）
- [docs/decisions/](docs/decisions/) — Architecture Decision Records
- [docs/tasks/](docs/tasks/) — phase / task の進捗とログ

プロジェクト完了状況・Phase 一覧は [ADR-0009](docs/decisions/0009-project-completion-summary.md) を参照。

## ライセンス

学習用の個人プロジェクト。明示ライセンスなし。
