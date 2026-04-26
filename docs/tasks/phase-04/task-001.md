# task-001: dbt project 雛形（dbt_project / profiles / packages）

- Phase: 04
- Status: Todo
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
