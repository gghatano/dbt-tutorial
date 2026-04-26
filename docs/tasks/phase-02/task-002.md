# task-002: Terraform main.tf（schema / role / grant）

- Phase: 02
- Status: Done
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

### スキーマと役割の関係
- `dbt_user` を schema owner にした。dbt が schema 内に table/view を CREATE できる必要があるため、所有権を持たせた方が事故が少ない。
- 結果として `dbt_user` の grant（USAGE/CREATE/ALL on tables）は実質再宣言だが、ownerが将来変更されても明示権限は残る + ドキュメント効果のため `postgresql_grant` で明記した。
- 依存関係: `postgresql_role.dbt_user` を先に作成 → `postgresql_schema.layers` で `owner = postgresql_role.dbt_user.name` 参照、Terraform が依存DAGを自動解決。`depends_on` 明示は不要。

### grant 戦略
- `dbt_user`:
  - schema: USAGE + CREATE
  - tables (existing): ALL
  - default privileges (owner=dbt_user): tables ALL → 自分が作るテーブルに対して再付与不要。
- `readonly_user`:
  - marts schema のみ USAGE
  - marts tables (existing): SELECT
  - default privileges (owner=dbt_user): marts schema 内で dbt_user が後から CREATE するテーブルに自動 SELECT 付与
- raw / staging / intermediate には readonly_user の grant を入れない（spec の readonly = mart閲覧者の想定）。

### provider `superuser` フラグ
- spec の指示文では `superuser = false` を例示していたが、`docker exec ... \du analytics_user` の結果は `Superuser, Create role, Create DB, Replication, Bypass RLS` で実際に PostgreSQL の SUPERUSER ロール。
- そのため cyrilgdn/postgresql の `superuser = true`（デフォルト）でそのまま使った。`true` のときに provider が必要に応じて `SET ROLE` 発行することで grant の整合が取れるため、こちらが安全。
- もし将来 superuser を持たない bootstrap role に切り替える場合は `superuser = false` + `CREATEROLE / CREATEDB` 権限の付与が必要、と本ファイルに記載しておく。

### その他
- `postgresql_schema` は `drop_cascade = true` を指定（明示しなくても provider のデフォルトで `if_not_exists = true` が付くが、destroy 時に schema 内の object ごと消せるよう cascade を有効化）。
- ロールパスワードは `encrypted_password = true`。pg_authid に SCRAM/MD5 ハッシュで保存される。
- tfvars 運用は今回は不採用（学習用途のため variables.tf default で済ませた）。`.gitignore` の `*.tfvars` ルールは将来に備えて残す。

## 実行ログ

### terraform plan summary

```text
Plan: 21 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + db_endpoint = "localhost:5432"
  + roles       = ["dbt_user", "readonly_user"]
  + schemas     = ["intermediate", "marts", "raw", "staging"]
```

内訳: schemas 4 + roles 2 + grants 4(schema) + grants 4(tables) + default_privileges 4(dbt_user) + grants 1(readonly schema) + grants 1(readonly tables) + default_privileges 1(readonly) = 21。

### terraform apply

```text
Apply complete! Resources: 21 added, 0 changed, 0 destroyed.

Outputs:
db_endpoint = "localhost:5432"
roles       = ["dbt_user", "readonly_user"]
schemas     = ["intermediate", "marts", "raw", "staging"]
```

### psql 確認

```text
$ docker exec local-data-postgres psql -U analytics_user -d analytics -c "\dn"
     Name     |       Owner
--------------+-------------------
 intermediate | dbt_user
 marts        | dbt_user
 public       | pg_database_owner
 raw          | dbt_user
 staging      | dbt_user

$ docker exec local-data-postgres psql -U analytics_user -d analytics -c "\du"
   Role name    |                         Attributes
----------------+------------------------------------------------------------
 analytics_user | Superuser, Create role, Create DB, Replication, Bypass RLS
 dbt_user       | Password valid until infinity
 readonly_user  | Password valid until infinity
```

期待通り 4 schema が dbt_user 所有で作成され、dbt_user / readonly_user の login role が作成されている。
