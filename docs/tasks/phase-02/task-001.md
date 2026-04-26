# task-001: Terraform 雛形（versions / variables / outputs）

- Phase: 02
- Status: Todo
- Owner: -
- Depends on: phase-01/task-001
- Parallelizable with: phase-02/task-002 は不可（main.tfに依存）

## 目的
Terraform プロバイダ固定と変数・出力雛形を整備する。

## 入力 / 前提
- spec §7
- provider: `cyrilgdn/postgresql`
- Terraform 1.14.9

## 成果物
- `infra/terraform/versions.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`

## 受入条件
- `terraform init` がエラーなく通る
- `terraform validate` が通る
- 変数: host, port, database, superuser, superuser_password, dbt_user_password, readonly_user_password
- 接続情報のデフォルトは spec 準拠（host=localhost, port=5432, database=analytics, superuser=analytics_user）
- outputsで作成schema/role名を出力

## 実装メモ / 判断ログ
- providerバージョン: 採用時点最新の安定版を `~> 1.x` で固定（実装時にバージョン確定）
- パスワード系は機微情報のため `sensitive = true`
- 開発用途のため tfstate はlocal backend
