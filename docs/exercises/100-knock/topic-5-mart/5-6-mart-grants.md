# 5-6: mart に `+grants:` config を付け、`readonly_user` に SELECT を自動付与 (hook を使わない宣言的解)

## シナリオ

Topic ⑤ ここまでで `mart_*_100knock` を複数作ってきた。これらは `marts` schema に `dbt_user` として書き込まれるが、BI / アプリ用の `readonly_user` には **SELECT 権限が付いていない**。Terraform は MVP の固定 mart にしか grant していないし、`dbt run` で新しい mart が増えても自動では追従しない。

Ex.09 では `on-run-end` フックで `grant select on all tables in schema marts to readonly_user` を毎 run 末尾に発行する解を学んだ。これはこれで動くが、**「どの mart に誰が SELECT できるか」が macro の実装中に隠れる** という弱点がある。lineage を読んでも grant 関係は出てこない。

dbt 1.2+ の `+grants:` config はこれを **モデル側の宣言** に置き換える。`models:` 配下に `+grants: { select: ['readonly_user'] }` と書けば、dbt が自動で「この model を build した直後にこの role に SELECT を grant する」 SQL を発行する。hook は不要。`schema.yml` を見れば誰がアクセスできるかが分かる。

このエクササイズでは Topic ⑤ の `100-knock-marts` 全モデルに `+grants:` を効かせ、`readonly_user` が新しい mart にも自動で SELECT できる状態を **宣言だけで** 実現する。

## 学べること

- `+grants:` config (dbt 1.2+ / dbt-postgres 1.10) の宣言的 grant 機構
- `dbt_project.yml` の `models:` 階層継承で「このディレクトリ配下全部に同じ grant」を 1 行表現
- hook 解 (Ex.09) と宣言的解 (`+grants:`) の比較
- `pg_class` / `has_table_privilege()` で grant が効いているかの確認方法
- 「誰が SELECT できるか」も DAG / マニフェストの一部になる感覚

## 前提

- Topic ② ③ ④ + Topic ⑤ 5-1〜5-5 完了
- `dbt/models/100-knock/topic-5/` 配下に `mart_*_100knock` が複数存在 (5-1, 5-2, 5-3 等)
- `marts` schema が存在し、`readonly_user` role が bootstrap 済み (`scripts/ci/bootstrap_schemas.sql` が用意)
- dbt-postgres 1.10+ (本リポジトリの `requirements.txt` 想定通り)

## 入力データ

不要。既存の Topic ⑤ mart に対して `+grants:` を効かせるだけ。

## 課題

### Step 1: 現状確認 (grant 不足を再現)

`readonly_user` で接続して 5-1 などの mart を SELECT してみる:

```bash
docker exec -it local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_top_rated_products_100knock;"
# ERROR: permission denied for table mart_top_rated_products_100knock
```

`has_table_privilege()` でも確認できる:

```sql
SELECT has_table_privilege('readonly_user',
                           'marts.mart_top_rated_products_100knock', 'SELECT');
-- f
```

### Step 2: `dbt_project.yml` に `+grants:` を追加

`dbt/dbt_project.yml` の `models.local_analytics:` 配下に **`100-knock-marts:` セクション** を新設し、対象パスへ `+grants:` を継承させる。具体的な書き方は解答例を参照。ポイント:

- `100-knock-marts:` ブロックは `dbt/models/100-knock/topic-5/` を物理ディレクトリ階層で指す (path-based config)
- `+grants:` は `select: ['readonly_user']` の dict
- `+materialized: table` / `+schema: marts` も同セクションで宣言してよい

### Step 3: `dbt build` で grant が効くことを確認

```bash
cd dbt
dbt build --select 100-knock-marts --profiles-dir .
```

`dbt run` のログ末尾に **`apply grants`** の行が出ることを確認:

```
... 1 of 5 OK created sql table model marts.mart_top_rated_products_100knock ... [SELECT 1 in 0.20s]
... 1 of 5 OK applied grants ...
```

### Step 4: readonly_user で再 SELECT

```bash
docker exec -it local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_top_rated_products_100knock;"
# count: <数値> (ERROR にならない)
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-6-mart-grants.grading.yaml
```

## 完了条件

- [ ] `dbt/dbt_project.yml` の `models:` 配下に `100-knock-marts:` (相当) セクションがあり、`+grants:` が宣言されている
- [ ] `dbt build --select 100-knock-marts` が PASS し、ログに `applied grants` が出る
- [ ] `readonly_user` が `marts.mart_*_100knock` を SELECT できる (`has_table_privilege` = true)
- [ ] hook (`on-run-end:`) を **使っていない** (新規追加していない)

## ヒント (詰まったら)

- **`+grants:` は dict**: `+grants: {select: ['readonly_user']}` または yaml block 形式 (`select:` の下に `- readonly_user`) どちらでも可。
- **継承される**: `dbt_project.yml` の階層に書くと配下全 model に効く。個別 model の `config()` で上書きもできる (`config(grants={'select': ['some_user']})`)。
- **`apply grants` が出ない**: dbt-postgres のバージョンが古いと `+grants:` を解釈できない。`pip show dbt-postgres` で 1.10+ を確認。
- **新 mart が増えても追従**: `+grants:` は build のたびに対象 model に対して `GRANT SELECT` を発行する。新規 mart 追加時に追加作業不要。これが hook 解との違い。
- **schema 単位の `grant usage`**: `+grants:` は table 単位の `GRANT SELECT` のみ発行する。`grant usage on schema marts to readonly_user` は別途必要 (Terraform / bootstrap で 1 度実行されていればよい)。
- **target 切替**: `+grants:` には `if target.name == 'dev'` のような分岐は書けない (静的宣言のため)。本番別 grant が必要なら `vars:` + Jinja で分岐するか、target 別に `dbt_project.yml` を分ける運用になる。
- **既存 hook (Ex.09) と共存可能**: 同じ grant を hook と `+grants:` の両方で発行しても idempotent (権限は冪等)。本問は宣言的解単体で十分なので hook は追加しない。

## 解答例

詳細は [`5-6-mart-grants.solution.md`](5-6-mart-grants.solution.md) を参照。
