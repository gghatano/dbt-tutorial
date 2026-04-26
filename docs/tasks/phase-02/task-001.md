# task-001: Terraform 雛形（versions / variables / outputs）

- Phase: 02
- Status: Done
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
- providerバージョン: `cyrilgdn/postgresql ~> 1.25` と指定し、`terraform init` で v1.26.0 を取得した。
  - 採用理由: 1.25/1.26 が最新の安定マイナーで、`postgresql_default_privileges` が安定して扱えるため。`~> 1.25` は 1.25.x / 1.26.x 系を許容しつつ 2.x の breaking change から守る。
- パスワード系（superuser_password / dbt_user_password / readonly_user_password）はすべて `sensitive = true`。
- ローカル学習用途のため、各 password のデフォルト値を spec 互換の固定値（`analytics_password` / `dbt_password` / `readonly_password`）として `default` に置いた。実運用ではenvや tfvars で上書きする前提。
- tfstate は local backend（明示宣言なし=デフォルト）。`.gitignore` にて `*.tfstate*` および `.terraform/` `.terraform.lock.hcl` `*.tfvars` 除外済みを確認。
- outputs は schemas / roles のリストと `db_endpoint`（host:port）。`postgresql_schema.layers` は `for_each` のため `for s in ... : s.name` で取り出し。

## 実行ログ

```text
$ terraform init
- Installing cyrilgdn/postgresql v1.26.0...
Terraform has been successfully initialized!

$ terraform validate
Success! The configuration is valid.

$ terraform fmt -check -recursive ../..
(差分なし)
```
