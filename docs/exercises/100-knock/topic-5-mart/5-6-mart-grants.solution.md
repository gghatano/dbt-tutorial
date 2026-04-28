# 5-6 解答例

## ゴール再掲

`dbt/dbt_project.yml` に **`100-knock-marts:` セクション + `+grants:` 宣言** を追加し、`dbt build --select 100-knock-marts` で `marts.mart_*_100knock` の SELECT 権限が `readonly_user` に自動付与される状態を作る。hook (`on-run-end:`) は使わない。

## Step 1: 現状確認

```bash
# readonly_user で SELECT → permission denied になることを再確認
docker exec -it local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_top_rated_products_100knock;"
# ERROR: permission denied for table mart_top_rated_products_100knock
```

dbt_user (= grader 接続ユーザ) でも `has_table_privilege` で確認:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
SELECT
  has_table_privilege('readonly_user',
                      'marts.mart_top_rated_products_100knock', 'SELECT') AS can_select;
SQL
-- can_select: f
```

## Step 2: `dbt/dbt_project.yml` を編集

既存 (Ex.09 / Topic ⑤ 5-1〜5-5 をやった後) は↓のような状態:

```yaml
models:
  local_analytics:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts
    100-knock:
      topic-3:
        +materialized: view
        +schema: staging
      topic-4:
        +materialized: view
        +schema: intermediate
      topic-5:
        +materialized: table
        +schema: marts
```

ここに `+grants:` を **`100-knock-marts` 用に独立したブロック** として追記する。本問はディレクトリ階層 `100-knock/topic-5/` がそのまま `100-knock-marts` の役割を担うため、既存 `topic-5:` セクションに `+grants:` を足すのが最短:

```yaml
models:
  local_analytics:
    # ... 省略 ...
    100-knock:
      topic-3:
        +materialized: view
        +schema: staging
      topic-4:
        +materialized: view
        +schema: intermediate
      # 100-knock-marts (Topic ⑤ 5-6): readonly_user に SELECT 自動付与。
      # +grants: は dbt 1.2+ の宣言的 grants 機能。on-run-end hook 不要。
      topic-5:
        +materialized: table
        +schema: marts
        +grants:
          select: ['readonly_user']
```

(別ブロック `100-knock-marts:` として独立させたい場合は `dbt-project.yml` の `models:` 配下にもう 1 階層書けるが、本リポジトリは path-based 階層を採用しているため `topic-5:` 配下に直接 `+grants:` を足すのが自然。)

> **採点との整合**: `5-6-mart-grants.grading.yaml` の `shell_command` は `grep -E 'grants:' dbt/dbt_project.yml` で grants ブロックの存在を見るため、上記いずれの書き方でも PASS。

## Step 3: `dbt build` 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select 100-knock.topic-5 --profiles-dir .
```

ログに `applied grants` が出るはず:

```
12:34:01  1 of 5 START sql table model marts.mart_top_rated_products_100knock ...... [RUN]
12:34:01  1 of 5 OK created sql table model marts.mart_top_rated_products_100knock ... [SELECT 1 in 0.20s]
12:34:01  1 of 5 OK applied grants on marts.mart_top_rated_products_100knock ......... [GRANT in 0.02s]
... (他 mart も同様) ...
Done. PASS=N WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=N
```

## Step 4: readonly_user で再 SELECT

```bash
docker exec -it local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_top_rated_products_100knock;"
#  count
# -------
#    142
# (1 row)
```

`has_table_privilege` でも:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
SELECT
  has_table_privilege('readonly_user',
                      'marts.mart_top_rated_products_100knock', 'SELECT') AS can_select;
SQL
-- can_select: t
```

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-6-mart-grants.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | grants-block-in-project-yml         | 20/20 |
| OK | dbt-build-100knock-marts-success    | 25/25 |
| OK | apply-grants-log-line               | 15/15 |
| OK | readonly-can-select-mart            | 25/25 |
| OK | no-on-run-end-hook-added            | 15/15 |
```

## ポイント

- **`+grants:` の最大の価値**: `schema.yml` / `dbt_project.yml` を読むだけで「誰が SELECT できるか」が分かる。Ex.09 の hook 解だと macro 内部を読まないと分からない。lineage / docs / コードレビューが「権限の宣言」も対象に取り込める。
- **`+grants:` の発動タイミング**: dbt の **build / run の post step** として自動的に `GRANT SELECT` を発行。新 mart を追加しても、その mart を build した瞬間に grant も付く。Ex.09 hook 解は project 全体の `on-run-end` で 1 回まとめて発行するので、設計思想が違う。
- **冪等性**: `GRANT SELECT` は何度発行しても権限が増えるだけ (= 同じ権限を再付与しても no-op)。毎 build で発行されるが副作用なし。
- **既存 grant の上書き**: dbt は実は「現状の grant 状態を読み、宣言と差分があれば `GRANT` / `REVOKE` を発行」する戦略を取る (`materialized='table'` 等で挙動が変わる場合あり)。`config(grants={...}, copy_grants=True)` で table の RECREATE 時に grant を維持するオプションもある (postgres adapter は限定サポート)。
- **`grant usage on schema` は別**: `+grants:` は **table 単位** の SELECT のみを管理する。schema 自体への USAGE 権限は Terraform / bootstrap SQL で 1 度付ければよい。本リポジトリは bootstrap で `GRANT USAGE ON SCHEMA marts TO readonly_user` 済み。
- **個別 model で上書き**: 一部 mart だけ別 user に grant したい場合は当該 model の冒頭で `{{ config(grants={'select': ['analyst_user']}) }}` と書く。dbt は **マージではなく上書き** で扱うため、両方欲しいなら明示的にリストに両方並べる。

## 実行例 (採点 shell_command 視点)

```bash
$ grep -E 'grants:' dbt/dbt_project.yml
        +grants:
$ grep -A1 '+grants:' dbt/dbt_project.yml | grep readonly_user
          select: ['readonly_user']

$ cd dbt && dbt build --select 100-knock.topic-5 --profiles-dir . 2>&1 | grep 'applied grants' | wc -l
5     # 5 mart 全部に grant が反映

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA -c \
    "SELECT has_table_privilege('readonly_user', 'marts.mart_top_rated_products_100knock', 'SELECT')::int;"
1
```

## 解説まとめ

- **なぜ `+grants:` で hook 不要？**: Ex.09 で書いた `on-run-end` macro は「実行時に SQL を組み立てて発行」する **手続き的** な解。`+grants:` は「この model はこの role に SELECT を許可する」という **宣言** で、dbt が裏で同じ SQL を発行してくれる。手続きから宣言への置き換えで、(1) コードが減る (2) 関係が manifest に乗る (3) lineage / docs と整合する、という 3 つの利点が一度に手に入る。
- **dbt 1.5+ の宣言ファースト思想**: `contract: enforced` (列の型契約 = 5-3) / `groups:` + `access:` (公開範囲 = 5-7) / `+grants:` (権限の宣言 = 本問) は同じ思想の 3 つの実装。**「mart は対外契約の塊」** という Topic ⑤ Intro の主張をコードで実現するための機能群。
- **「誰が見るか」も DAG の一部**: BI ツールは `readonly_user` で接続するのが普通。`+grants:` を書き忘れると「dbt build は通っているのに BI が permission denied」という症状が出る。これは lineage に grant 情報が乗っていない (Ex.09 hook 解) と気づきにくい。`+grants:` で宣言しておけば、`dbt docs` の model description にも「SELECT: readonly_user」が出る。
- **hook を完全に置き換えるべきか？**: 本問の範囲では yes。ただし以下は依然として hook 向き:
  - **schema 単位の権限** (`GRANT USAGE ON SCHEMA ...`): `+grants:` は table 単位のみ
  - **複数 schema を横断する一括処理** (例: 全 schema に対して `ALTER DEFAULT PRIVILEGES`): hook の方が書きやすい
  - **環境別の動的分岐** (`if target.name == 'prod'`): `+grants:` には書けない
  - これらは「hook が必要な領域」として残る。本問は「mart の SELECT」というスコープなので `+grants:` がベスト。
- **CI で `apply grants` を grep する意味**: 「実際に grant が発行された」ログ証跡を CI で確認することで、`+grants:` 宣言を消した PR や `dbt-postgres` ダウングレードによる機能消失を検知できる。

## 拡張アイデア

- **mart ごとに別 role**: `mart_customer_lifetime_value_100knock` (= 5-7 で書く mart) は finance 用なので `finance_readonly` に grant、その他は `readonly_user` に grant、と分けてみる。`config(grants={...})` で個別宣言可能
- **`copy_grants: True`**: `materialized='table'` で table を rebuild するときに既存 grant を保持する設定 (`config(copy_grants=True)`) を試す。
- **Ex.09 hook と同居**: `on-run-end` hook を残したまま `+grants:` も書き、`pg_class` の grant を観察する。冪等なので壊れないことを確認。
- **manifest を読んで grant lineage を可視化**: `target/manifest.json` の各 model node の `config.grants` フィールドを Python で読み、「mart → role」の図を生成する。Ex.06 の exposure 可視化と同じ発想。
