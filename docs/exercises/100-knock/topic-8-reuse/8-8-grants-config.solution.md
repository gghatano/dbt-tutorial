# 8-8 解答例

## ゴール再掲

`dbt/dbt_project.yml` の `models:` 階層に `+grants: {select: ['readonly_user']}` を **100-knock 配下の topic-5 / topic-8 双方に効く位置** で宣言し、`dbt build` 後に readonly_user が `marts.mart_*_100knock` の **既存 + 新規** 全てに SELECT できる状態を作る。hook を追加しない。

## Step 1: 現状確認

```bash
docker exec -i local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_customer_avg_order_100knock;"
# ERROR: permission denied
```

`mart_customer_avg_order_100knock` (8-7 で作った) は `marts` schema にあるが grant が無いので readonly では permission denied。

## Step 2: `dbt/dbt_project.yml` を編集

Topic ⑤ 5-6 を実施済みの場合、`models.local_analytics.100-knock.topic-5:` 配下に既に `+grants:` が入っているはず。本問では **topic-8 にも同じ宣言を伝播** させる。

最も再利用性の高い書き方は **`100-knock:` ブロック直下**ではなく、**marts 系 topic の親に共通宣言を寄せる** こと。ただし topic-3 (staging) や topic-4 (intermediate) が同じ階層にあるので、**topic-5 と topic-8 にだけ** 個別に書くのが副作用なしで安全:

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
      # 100-knock-marts: Topic ⑤ 5-6 / Topic ⑧ 8-8 共通
      # +grants: で readonly_user に SELECT 自動付与。新 mart 追加時も自動で grant が伝播する。
      topic-5:
        +materialized: table
        +schema: marts
        +grants:
          select: ['readonly_user']
      topic-7:
        +materialized: table
        +schema: snapshots
      # Topic ⑧ で新規追加した mart も同じ grant を継承させる
      topic-8:
        +materialized: table
        +schema: marts
        +grants:
          select: ['readonly_user']
```

ポイント:

- **topic-5 と topic-8 に同じ宣言**: 重複に見えるが、別 topic は別ディレクトリ階層なので物理的には別宣言。これを 1 行にまとめたい場合は `100-knock-marts` のような **論理ブロック** に切り出すこともできる (が path-based config と相性が悪いので本リポジトリでは個別宣言を推奨)
- **topic-7 (snapshot) には grant 不要**: snapshot は履歴テーブルで BI 直接参照しない用途想定。grant をつけても無害だが原則最小権限で
- **コメントで意図を残す**: 「再利用の意図」「新規 mart 追加時の自動伝播」 を明記。半年後の自分への手紙

## Step 3: dbt build 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --select 100-knock.topic-5 100-knock.topic-8 --profiles-dir .
```

期待されるログ (抜粋):

```
12:34:01  1 of 6 START sql table model marts.mart_top_rated_products_100knock ......... [RUN]
12:34:01  1 of 6 OK created sql table model marts.mart_top_rated_products_100knock .... [SELECT 1 in 0.20s]
12:34:01  1 of 6 OK applied grants on marts.mart_top_rated_products_100knock .......... [GRANT in 0.02s]
... (他 mart も同様) ...
12:34:05  6 of 6 OK applied grants on marts.mart_customer_avg_order_100knock .......... [GRANT in 0.02s]
Done. PASS=12 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=12
```

`applied grants` 行が **mart 数だけ** 出ていれば OK。

## Step 4: readonly_user で再 SELECT

個別確認:

```bash
docker exec -i local-data-postgres psql -U readonly_user -d analytics <<'SQL'
SELECT count(*) FROM marts.mart_top_rated_products_100knock;
-- count: 142 など、ERROR にならない

SELECT count(*) FROM marts.mart_customer_avg_order_100knock;
-- count: 1000 など (8-7 で作った mart も grant 自動伝播)
SQL
```

bulk 確認 (= 全 mart に grant が付いているか):

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
WITH marts AS (
  SELECT schemaname || '.' || tablename AS fqn
  FROM pg_tables
  WHERE schemaname = 'marts' AND tablename LIKE 'mart_%_100knock'
)
SELECT
  count(*) AS total,
  count(*) FILTER (WHERE has_table_privilege('readonly_user', fqn, 'SELECT')) AS granted
FROM marts;
SQL
# 例: 6|6 (全 mart に grant 済)
```

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-8-grants-config.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | grants-block-in-project-yml         | 20/20 |
| OK | dbt-build-100knock-marts-success    | 20/20 |
| OK | apply-grants-log-multiple           | 20/20 |
| OK | readonly-can-select-topic5-mart     | 20/20 |
| OK | readonly-can-select-topic8-mart     | 20/20 |
```

## ポイント

- **「1 宣言 → N model」 の自動伝播が再利用の本体**: 5-6 の文脈は「mart は対外契約の塊」 だったが、本問の文脈は「**同じ宣言を書き直さない**」 という再利用そのもの。topic-5 で 5 個の mart、topic-8 で 1 個の mart、合計 6 個の mart に対し `+grants:` 宣言は 2 行だけ (topic-5 用と topic-8 用)。Ex.09 の hook 解だと macro 1 個 + project.yml の hook 宣言 + macro 内に対象 schema を hard-code、と複数箇所に依存が散る
- **「新しい mart が増えたら何をすべきか」 という運用リスクの差**:
  - hook 解 → 新 mart の table 名を macro 内 SQL に追記、または `grant on all tables in schema` で全 table 対象にする (= 範囲が雑) のどちらかが必要
  - `+grants:` 解 → 新 mart の `.sql` を `topic-8/` に置くだけで自動 grant、追加作業ゼロ
- **Topic ⑤ 5-6 と本問の使い分け**: 5-6 を実施済みなら本問は **「topic-8 にも同じ宣言を増やす」** だけで本質は同じ。5-6 を読み返したい場合は `docs/exercises/100-knock/topic-5-mart/5-6-mart-grants.md` を参照
- **「マージではなく上書き」 の罠**: 親階層に `+grants: {select: ['user_a']}` を書き、個別 model の `config(grants={'select': ['user_b']})` で上書きすると、`user_a` への grant は **消える**。両方欲しいなら `['user_a', 'user_b']` と明示
- **`grant usage on schema` は別途**: `+grants:` は table 単位のみ。schema USAGE は bootstrap (`scripts/ci/bootstrap_schemas.sql`) で 1 度発行されている

## 実行例 (採点 shell_command 視点)

```bash
$ grep -cE '^\s*\+?grants:' dbt/dbt_project.yml
2     # topic-5 / topic-8 で 2 箇所

$ grep -cE 'readonly_user' dbt/dbt_project.yml
2

$ cd dbt && ../.venv/bin/dbt build --select 100-knock.topic-8 \
    --profiles-dir . 2>&1 | grep -c 'applied grants'
1     # 8-7 の mart 1 本に grant 適用

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA \
    -c "SELECT has_table_privilege('readonly_user',
                                   'marts.mart_customer_avg_order_100knock',
                                   'SELECT')::int;"
1     # 8-7 で作った mart に grant 自動伝播
```

## 解説まとめ

- **`+grants:` の本質は宣言の集約**: 「権限の決定」 をコードの 1 箇所に閉じ込めることで、**「マートが増える / readonly_user の権限が変わる」 という変更の影響範囲が project.yml の数行だけ** に局所化される。Topic ⑧ で繰り返し見る再利用パターン (1 macro → N model、1 var → N call) と同じ形を権限管理で実現
- **Ex.09 hook 方式との中長期コスト比較**:
  | | hook (Ex.09) | `+grants:` (本問) |
  |---|---|---|
  | 新 mart 追加時の作業 | macro 修正 or all-tables ワイルドカード | 不要 (自動伝播) |
  | grant 関係の可視性 | macro 中身を読む | dbt_project.yml の階層を見る |
  | manifest / docs への乗り | 載らない | 載る |
  | target 別分岐 | macro 内で `if target.name` 書ける | 静的、書けない |
  | schema 単位 USAGE | hook で書ける | できない (bootstrap で別途) |
  - 結論: **table SELECT は `+grants:`、schema USAGE / 環境別分岐は hook**、という棲み分けが現実解
- **Topic ⑧ の中での位置づけ**: 8-1 (macro 1 → 5 model)、8-5 (Jinja loop で 1 macro → 4 staging)、8-9 (1 metric → 3 mart)、と並んで **「1 つの宣言が N 箇所に効く」** 系列の問題。`+grants:` だけ DB 権限という別レイヤーを扱うが、再利用の構造は同じ
- **dbt 1.5+ の宣言ファースト思想**: `contract: enforced` (型契約) / `groups:` + `access:` (公開範囲) / `+grants:` (権限) は同じ思想の 3 実装。**「mart の周りの全ての契約を YAML/config で宣言」** という方向性で dbt は進化している

## 拡張アイデア

- **mart ごとに別 role**: `mart_customer_lifetime_value_100knock` だけ `finance_readonly` に grant、その他は `readonly_user` に grant、を `config(grants={...})` で個別宣言
- **`copy_grants: True`** (Snowflake のみフルサポート): `materialized='table'` で table を rebuild するときに既存 grant を保持。Postgres では一部対応
- **Ex.09 hook と同居 + 観測**: `on-run-end` hook を残したまま `+grants:` も書き、`pg_class` の grant を観察。冪等なので壊れない
- **manifest を読んで grant lineage を可視化**: `target/manifest.json` の各 model node の `config.grants` フィールドを Python で読み、`mart → role` の図を生成。Ex.06 の exposure 可視化と同じ発想
- **CI で grant 漏れ検知**: 採点 yaml を拡張し、「`marts.*_100knock` の **全 table** で `has_table_privilege('readonly_user', ..., 'SELECT')` が true」 を sql_assert で確認。新 mart が追加されたが grant 宣言を忘れた、を検知できる
