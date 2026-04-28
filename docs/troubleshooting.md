# トラブルシュート

## エラー文字列 → 対処の逆引き

| エラー文字列 (抜粋) | 起きる場面 | 一次切り分け | 詳細 |
|---|---|---|---|
| `password authentication failed for user "dbt_user"` | `dbt run` / `smoke_test.py` | `set -a; source .env; set +a` を忘れている可能性 | [setup.md §8](setup.md) |
| `could not connect to server: Connection refused` | `dbt debug` / psycopg | Postgres コンテナが落ちている / ポート競合 | 後述「Postgres に接続できない」 |
| `relation "raw.orders" does not exist` | `dbt run` | `load_raw_data.py` 未実行 | [setup.md §7](setup.md) |
| `permission denied for schema marts` | Metabase 接続 | readonly_user に grant が走っていない / `terraform apply` 不足 | [dashboard.md](dashboard.md) |
| `permission denied for table mart_*` | Metabase ダッシュボード描画 | `dbt run` を `dbt_user` 以外（例: `analytics_user`）で実行したため Default Privileges が発火せず、`readonly_user` に SELECT が自動付与されなかった | 後述「Metabase で `permission denied for table mart_*`」 |
| `パスワードが間違っているようです` (Metabase 設定画面 / bootstrap) | Metabase の DB 接続作成 | shell に export 済みの `METABASE_DB_RO_PASSWORD` 等が `.env` を上書きし、実 DB のパスワードと一致しない | 後述「shell の export が `.env` を上書きする」 |
| `Couldn't connect to the database` (Metabase 設定画面) | Metabase setup | host を `localhost` にしている。`postgres` を使う | [dashboard.md](dashboard.md) |
| `Compilation Error: ... generate_schema_name` | `dbt run` | `macros/get_custom_schema.sql` を消した | [ADR-0005](decisions/0005-dbt-config.md) |

## `docker pull` が無言ハングする / `exit 144`

`~/.docker/config.json` に `"credsStore": "desktop"` が残っているのに Docker Desktop が無いと、credential helper が応答せずハングする。

確認:

```bash
grep credsStore ~/.docker/config.json || echo "OK"
```

対策: 該当行を削除（バックアップ推奨）。詳細は [ADR-0002](decisions/0002-tooling-baseline.md)。

## `dbt run` で `<target>_marts` のような prefix schema が作られる

dbt-postgres のデフォルトでは `+schema: marts` は `<target_schema>_marts` に解決される。  
本プロジェクトは `dbt/macros/get_custom_schema.sql` で `generate_schema_name` を override し、`marts` schema をそのまま使う。詳細は [ADR-0005](decisions/0005-dbt-config.md)。

## Apple Silicon で特定イメージが遅い

`postgres:17-alpine` は arm64 ネイティブで問題なし。Metabase は amd64 のみ提供のため Rosetta / qemu エミュレーションで動く（起動に 60〜120 秒、メモリは 1GB+）。x86 依存サービスを追加する場合は `platform: linux/amd64` を指定可能。

## Postgres に接続できない

```bash
colima status                                  # running 確認
docker compose ps                              # postgres healthy 確認
lsof -i :5432                                  # ポート競合確認
docker exec local-data-postgres pg_isready -U analytics_user -d analytics
```

## `dbt test` が落ちたら

1. ログ末尾に出る `Failure in test ...` のテスト名をコピー
2. `target/run/local_analytics/<schema>/<test_name>.sql` を `cat`（dbt が DB に投げた compiled SQL）
3. `psql` でその SQL を直接流す → 違反行が見える
4. 永続化したい場合: `dbt test --store-failures` で `<schema>_dbt_test__audit` 配下に失敗行 table が残る（[Exercise 10](exercises/10-store-failures-and-expectations.md) で詳しく扱う）
5. 修正方針:
   - generic test (`schema.yml`): データ側を直す or テストを緩める
   - singular test (`tests/*.sql`): WHERE 条件を見直す

## Metabase で `permission denied for table mart_*`

Metabase のダッシュボードを開いた際にカードがこのエラーで落ちるとき、`marts.mart_*` テーブルの **オーナーが `dbt_user` ではない** ことが原因。Terraform は「`dbt_user` が `marts` に作るテーブルは `readonly_user` に SELECT を自動付与」する Default Privileges を仕込んでいる ([infra/terraform/main.tf](../infra/terraform/main.tf) の `postgresql_default_privileges`)。`analytics_user` (superuser) で `dbt run` してしまうとこのトリガが発火せず、`readonly_user` に何の権限も付かない。

確認:

```bash
# cwd: ~/repo
docker exec local-data-postgres psql -U analytics_user -d analytics -c \
  "select tablename, tableowner from pg_tables where schemaname='marts';"
```

`tableowner` が `analytics_user` になっていたらこれ。修復手順:

```bash
# 1) .env が dbt_user/dbt_password になっているか確認
grep -E '^DB_USER|^DB_PASSWORD' .env

# 2) shell の上書き env をクリア（後述参照）
unset DB_USER DB_PASSWORD

# 3) 既存スキーマを破棄して再作成
docker exec local-data-postgres psql -U analytics_user -d analytics -c \
  "DROP SCHEMA IF EXISTS staging CASCADE; DROP SCHEMA IF EXISTS intermediate CASCADE; DROP SCHEMA IF EXISTS marts CASCADE;"
cd infra/terraform && terraform apply -auto-approve && cd ../..

# 4) dbt_user で再ビルド
set -a; source .env; set +a
.venv/bin/dbt run --project-dir dbt --profiles-dir dbt
```

## shell の export が `.env` を上書きする

`set -a; source .env; set +a` でも、**既に `export` 済みの変数は上書きされない** わけではない (実際は上書きされる) のに対し、`scripts/*.py` が使う `python-dotenv` の `load_dotenv()` は **デフォルトで既存の os.environ を上書きしない**。このため、shell に `DB_USER=analytics_user` や `METABASE_DB_RO_PASSWORD=Local-data-1` 等が残っていると、`.env` の値が無視されて

- `dbt run` が想定外のユーザでテーブルを作成 → 上記 `permission denied for table mart_*`
- `metabase_bootstrap.py` の DB 接続作成が `パスワードが間違っているようです` で 400

になる。

確認 / 対策:

```bash
# 残存している export を確認
env | grep -E '^(DB_|POSTGRES_|METABASE_)' | sort

# クリアしてから流し込み直す
unset DB_USER DB_PASSWORD METABASE_DB_RO_PASSWORD METABASE_ADMIN_PASSWORD
set -a; source .env; set +a
```

新しい shell を開けば確実にクリーン。`scripts/metabase_bootstrap.py` は `load_dotenv(..., override=True)` で `.env` 優先にしているため、bootstrap 単体ならこの問題は起きないが、`dbt` 等他のツールでは引き続き shell が優先される点に注意。

## Metabase が `unhealthy` のまま

Metabase は amd64 エミュレーションのため初回起動が遅い（健全でも 90 秒前後）。

```bash
# 進捗を眺める
docker logs -f local-data-metabase
```

`Metabase Initialization COMPLETE` が出れば healthy になる直前。それ以降待っても healthy にならない場合は Colima のメモリ不足の可能性が高い（`colima start --memory 8` 以上推奨）。
