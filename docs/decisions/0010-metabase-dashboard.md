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

## 自動セットアップ

### 経緯

最初は「ブラウザで管理者作成 → DB 接続 → 3 枚の Card 作成 → Dashboard に並べる」をマニュアル手順として `docs/dashboard.md` に書いていた。学習用には十分だったが:

- worktree / volume を作り直すたびに 5〜10 分の繰り返し作業が発生する
- 新規参加者が再現するときに「どの SQL でどの可視化タイプか」を読み合わせる必要がある
- ADR-0010 当初の「残課題: serdes 未対応」がそのまま塩漬けになる

そこで `scripts/metabase_bootstrap.py` を追加し、`.env` の値だけで一発再現できるようにした。

### 採用した API

Metabase OSS 版（v0.55）の **REST API** で完結する。Enterprise 専用の `serialize` は **使わない**。

| ステップ | API | 備考 |
|---|---|---|
| ヘルス待ち | `GET /api/health` | 2 秒間隔ポーリング、最大 120 秒 |
| 初回判定 | `GET /api/session/properties` | **`has-user-setup`** で判定（`setup-token` は完了後も値が残るため単独では使えない、Metabase API のクセ） |
| 管理者 + DB 一括作成 | `POST /api/setup` | `setup-token` を渡し、user / database / prefs を 1 回で投入。完了後は token 失効 |
| 既存環境 fallback | `POST /api/session` → `GET /api/database` | admin login → DB 一覧から名前検索、無ければ `POST /api/database` |
| Schema sync | `POST /api/database/{id}/sync_schema` + `GET /api/database/{id}/metadata` | marts スキーマが見えるまで polling |
| Collection / Card / Dashboard | `GET → POST/PUT` の upsert パターン | name で検索、既存なら `PUT` で内容を最新化、無ければ `POST` で作成 |
| Dashcard 配置 | `PUT /api/dashboard/{id}` の `dashcards` 配列 | 12 列グリッドで size 6×6 を 2 列、上段に Daily Sales を 12×6 で配置 |

### 冪等戦略

- **name で upsert**: collection / card / dashboard とも、表示名で `GET` 一覧から検索 → 既存ならスキップまたは更新、無ければ作成。
- Card の SQL / 可視化設定はスクリプトを source-of-truth として毎回 `PUT` で再投入する（手で編集していても上書き戻る、というのが期待動作）。
- Dashcard は「既に同じ card_id が dashboard 上に居れば skip」、つまり再配置はしない。
- 結果: 同じ `.env` で何度実行しても、`/api/card` の総件数も dashcards 配置も変化しない。

### Decision

1. **Setup API を使う**（手動ウィザードを完全代替）。Enterprise 限定機能には依存しない。
2. **接続情報は環境変数経由**（`.env`）。スクリプト本体には平文の認証情報を含めない。
3. **冪等は name-based**。UUID 等の安定 ID 管理はせず、命名で識別する（学習リポジトリで十分なシンプルさ）。
4. **manual 手順は残す**。`docs/dashboard.md` の「マニュアル操作（リファレンス）」として、API が使えない / API を学びたい場合に手動で再現できるようにしておく。

## 残課題

- 本格的なバージョン管理が必要になったら、Metabase Enterprise の `serialize`（YAML エクスポート）または OSS 互換のサードパーティ tool を検討する。
- `metabase_data` volume を消すと管理者・データソースもろとも消えるが、bootstrap スクリプトを再実行すれば数秒で復元できる（H2 のスナップショット保存は不要）。
- 旧ボリューム `feature-phase-01-task-001-docker-compose_postgres_data` は手動削除可能。
