# task-001: dbt project 雛形（dbt_project / profiles / packages）

- Phase: 04
- Status: Done
- Owner: -
- Depends on: phase-02/task-002, phase-03/task-001
- Parallelizable with: -

## 目的
dbt プロジェクト `local_analytics` を初期化し、staging/intermediate/marts 各層の出力先 schema を設定する。

## 入力 / 前提
- spec §8 / §3

## 成果物
- `dbt/dbt_project.yml`
- `dbt/profiles.yml`
- `dbt/packages.yml`（必要なら `dbt-utils` など。最小構成では空でも可）
- `dbt/macros/get_custom_schema.sql`（追加成果物。`generate_schema_name` を override）

## 受入条件
- `dbt debug --profiles-dir .` が成功
- `dbt parse --profiles-dir .` が成功
- 各層の materialization と schema が設定されている
  - staging: view, schema=staging
  - intermediate: view, schema=intermediate
  - marts: table, schema=marts
- profiles.yml は環境変数で接続情報を読む（`{{ env_var('DB_USER') }}` など）

## 実装メモ / 判断ログ
- profile名: `local_analytics`
- target: `dev`
- threads: 4
- 接続user: `dbt_user`（Terraformで作成）
- search_path は不使用（schema設定で明示）
- packages: 初期はdbt_utilsを入れない（最小構成）。必要になったら追加。
- **`generate_schema_name` macro を override**: dbt-postgres のデフォルト挙動では `+schema: marts` が `<target_schema>_marts` のように prefix されてしまう。spec §4 / Terraform で作成済みの schema (`raw`, `staging`, `intermediate`, `marts`) に 1:1 で対応させたいので、`dbt/macros/get_custom_schema.sql` で `custom_schema_name` をそのまま返す override を実装した。詳細は `docs/decisions/0005-dbt-config.md` を参照。
- **`target.schema = staging`**: custom macro と組み合わせて、`+schema:` 未指定モデルは staging に fallback する。

## 実行ログ

### `dbt debug --profiles-dir .`

```
Configuration:
  profiles.yml file [OK found and valid]
  dbt_project.yml file [OK found and valid]
Required dependencies:
 - git [OK found]

Connection:
  host: localhost
  port: 5432
  user: dbt_user
  database: analytics
  schema: staging
  ...
Registered adapter: postgres=1.10.0
  Connection test: [OK connection ok]

All checks passed!
```

### `dbt parse --profiles-dir .`

エラーなし完了。`models.local_analytics.{staging,intermediate,marts}` が「未使用 configuration path」として WARNING されるが、これは models 未配置のフォルダがあるためで、phase-04/task-002 (staging) 作成後は staging が消え、intermediate/marts も後続 phase でモデルを置くと自然に解消される。

## generate_schema_name override 採用理由（要約）

1. spec §4 / Terraform schema 名と 1:1 に揃えたい (`marts.mart_daily_sales` のような表記が実 schema 名と一致)
2. `<target>_<schema>` の prefix を避けるための dbt 公式推奨の拡張ポイント
3. profile を増やさずに各層 schema 分離を実現できる

詳細は `docs/decisions/0005-dbt-config.md`。
