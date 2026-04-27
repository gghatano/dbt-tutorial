# トラブルシュート

## エラー文字列 → 対処の逆引き

| エラー文字列 (抜粋) | 起きる場面 | 一次切り分け | 詳細 |
|---|---|---|---|
| `password authentication failed for user "dbt_user"` | `dbt run` / `smoke_test.py` | `set -a; source .env; set +a` を忘れている可能性 | [setup.md §8](setup.md) |
| `could not connect to server: Connection refused` | `dbt debug` / psycopg | Postgres コンテナが落ちている / ポート競合 | 後述「Postgres に接続できない」 |
| `relation "raw.orders" does not exist` | `dbt run` | `load_raw_data.py` 未実行 | [setup.md §7](setup.md) |
| `permission denied for schema marts` | Metabase 接続 | readonly_user に grant が走っていない / `terraform apply` 不足 | [dashboard.md](dashboard.md) |
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

## Metabase が `unhealthy` のまま

Metabase は amd64 エミュレーションのため初回起動が遅い（健全でも 90 秒前後）。

```bash
# 進捗を眺める
docker logs -f local-data-metabase
```

`Metabase Initialization COMPLETE` が出れば healthy になる直前。それ以降待っても healthy にならない場合は Colima のメモリ不足の可能性が高い（`colima start --memory 8` 以上推奨）。
