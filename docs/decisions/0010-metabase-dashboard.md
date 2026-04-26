# ADR 0010: BI レイヤとして Metabase を採用

- 日付: 2026-04-26
- ステータス: Accepted

## コンテキスト

spec §14 では BI を「次フェーズ」と整理していたが、MVP 完成後にユーザーから「ダッシュボードを見たい」と要望。学習用途で、dbt の marts を可視化できる BI を最小コストで導入する。

## 検討した選択肢

| ツール | 判断 | 備考 |
|---|---|---|
| **Metabase** | ✅ 採用 | Postgres native、Docker で完結、UI が直感的、SQL クエリも書ける、無料 |
| Superset | ❌ | 設定が重い（celery/redis 等の依存）、学習用には過剰 |
| Grafana | ❌ | 時系列向き、表形式の DWH ダッシュボードには不向き |
| Streamlit | ❌ | コードを書く必要あり、「ダッシュボード」UI 体験が薄い |
| Lightdash / Evidence | ❌ | dbt-native は魅力的だが学習段階では設定オーバーヘッド大 |

## 決定

1. **Metabase v0.55 系（OSS 版）** を docker-compose に追加。
2. **接続ユーザは `readonly_user`**。dbt_user ではなく BI 専用の最小権限ロールを使う。
   - 既に Terraform で `readonly_user` に `marts` schema の SELECT 権限を付与済み
   - BI 経由の誤操作（DELETE / UPDATE）に対する保険
   - Metabase の「データブラウザ」に raw/staging/intermediate が出てこないため、BI 利用者の認知負荷も下がる
3. **Apple Silicon では `platform: linux/amd64`**。spec §15.4 の方針に従う。
   - パフォーマンスは出ないが学習用なら十分
   - arm64 ネイティブ image は本記事執筆時点で OSS 版 Metabase には未提供
4. **Metabase メタストアは内蔵 H2** を使用（`MB_DB_FILE`）。
   - 本番では Postgres 別 schema や別 DB に置くのが推奨だが、学習用にはオーバーキル
   - メタストア破棄＝ダッシュボード全消去だが、命名・接続情報は手順書（`docs/dashboard.md`）から再現可能

## 影響

- `docker-compose.yml` に `metabase` サービスを追加（ports 3000、`platform: linux/amd64`、healthcheck）
- `docker compose up -d` で Postgres と Metabase が一緒に立ち上がる（`depends_on: postgres healthy`）
- 起動時間が初回 60-120 秒伸びる（Apple Silicon の amd64 エミュレーション + Java 起動）
- メモリ使用量が +1GB 程度（`JAVA_OPTS: -Xmx1g`）

## 結果

- `docs/dashboard.md` に初回セットアップ・推奨クエリ・トラブルシュートを集約
- spec §13 の完了条件には影響なし（BI は spec 外）
- 次フェーズ（CI/CD、Airflow）に進む際もこの BI 設定はそのまま維持

## 副作用: docker compose プロジェクト名の固定

### 背景

phase-01 で worktree から `docker compose up` を実行していた都合で、Postgres コンテナが付属していた docker network / volume は worktree ディレクトリ名から自動生成された名前空間（`feature-phase-01-task-001-docker-compose_*`）にいた。

このまま別 worktree から `docker compose up` を実行すると、`local-data-postgres` という固定 container_name の衝突 + 別 network での起動 → Metabase が `postgres` というホスト名で接続できない、というハマりが起きる。

### 対応

- `docker-compose.yml` 先頭に `name: dbt-tutorial` を追加し、cwd に依存せず project 名を `dbt-tutorial` に固定。
- 既存の `feature-phase-01-task-001-docker-compose_postgres_data` ボリュームを `dbt-tutorial_postgres_data` に **データそのままコピー** した:
  ```bash
  docker stop local-data-postgres && docker rm local-data-postgres
  docker volume create dbt-tutorial_postgres_data
  docker run --rm \
    -v feature-phase-01-task-001-docker-compose_postgres_data:/from \
    -v dbt-tutorial_postgres_data:/to \
    alpine sh -c 'cd /from && cp -a . /to/'
  docker compose up -d  # 新しい project 名で再起動、既存データを引き継ぎ
  ```
- 旧 volume `feature-phase-01-task-001-docker-compose_postgres_data` は削除せず残置。誰も参照しないので必要になったら `docker volume rm` で消してよい。

### 結果

- 任意のディレクトリから `docker compose up -d` がプロジェクト名 `dbt-tutorial` で動くようになった
- Postgres + Metabase が同じ network `dbt-tutorial_default` 上に存在し、Metabase からは hostname `postgres` で名前解決できる
- 既存の dbt mart / raw データはすべて保持（学習継続に影響なし）

## 残課題

- Metabase の dashboard / question を YAML 等でコード化する仕組み（serdes）は本 ADR では未対応。手動で作ったダッシュボードは H2 にしか残らない。
- 必要になったら `metabase-serialize` or [BridgeOpsHQ/metabase-resource](https://github.com/) 等の Terraform プロバイダを検討。
- 旧ボリューム `feature-phase-01-task-001-docker-compose_postgres_data` は手動削除可能。
