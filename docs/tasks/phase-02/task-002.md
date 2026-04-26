# task-002: Terraform main.tf（schema / role / grant）

- Phase: 02
- Status: Todo
- Owner: -
- Depends on: phase-02/task-001
- Parallelizable with: -

## 目的
DB内に schema 4種・role 2種・必要な grant を Terraform で構築する。

## 入力 / 前提
- spec §7

## 成果物
- `infra/terraform/main.tf`

## 受入条件
- `terraform apply -auto-approve` が成功
- schemas: `raw`, `staging`, `intermediate`, `marts` が作成される
- roles: `dbt_user`, `readonly_user` が作成される
- grants:
  - `dbt_user` は全schemaに対して USAGE + CREATE + テーブルへの ALL（default privileges 含む）
  - `readonly_user` は marts schema に対して USAGE + SELECT（既存 + default privileges）
- `terraform destroy` でクリーンに削除できる（idempotent）

## 実装メモ / 判断ログ
- ロールパスワードは variables から渡し、tfvarsはgit無視（`.gitignore` 追加）
- dbt接続用に `dbt_user` を使う想定（profiles.yml と整合）
- default privileges は Terraform で明示
