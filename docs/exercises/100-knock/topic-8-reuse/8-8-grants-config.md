# 8-8: `mart_*_100knock` の `+grants:` を `dbt_project.yml` に宣言する (hook を使わない再利用解)

## シナリオ

Topic ⑤ 5-6 でも同じ題材を扱ったが、Topic ⑤ では「mart は対外契約の塊」という **Topic ⑤ の主張を `+grants:` で表現する** 文脈だった。本問 (Topic ⑧) では同じ機能を **「再利用 (= 宣言の集約)」** の軸で再訪する。

`+grants:` の真価は **「同じ宣言を 1 箇所で書けば配下全モデルに展開される」** という再利用性にある。具体的には:

- Ex.09 の hook 解 → grant SQL は macro に閉じ込められ、対象 model は macro 内部の文字列にエンコードされる (= grant 関係が **コード本体に隠れる**)
- 本問の `+grants:` 解 → `dbt_project.yml` の階層に `+grants: {select: ['readonly_user']}` を 1 行書けば、その **配下の N model 全て** に同じ grant が自動で発行される (= **1 宣言 → N model 反映** の fan-out)

これは Topic ⑧ で繰り返し見る再利用パターン (8-1: 1 macro → 5 model、8-5: 1 audit macro → 4 staging、8-9: 1 metric macro → 3 mart) と同じ形。**「重複した SQL/権限/設定を 1 箇所に集約し、参照は宣言で済ませる」** という Topic ⑧ の中核思想を、権限管理の文脈で体感する。

このエクササイズでは Topic ⑤ までで作った `mart_*_100knock` 全モデルに `+grants:` を効かせ、**さらに Topic ⑧ で新規追加した mart (例えば 8-7 の `mart_customer_avg_order_100knock`) にも自動で grant が伝播する** ことを確認する。これが再利用の証跡。

## 学べること

- `+grants:` config (dbt 1.2+ / dbt-postgres 1.10) を `dbt_project.yml` に宣言する
- 階層継承で「このディレクトリ配下全部に同じ grant」を 1 行で表現
- 新規 mart 追加時に grant が **自動伝播** する経路 (= 再利用)
- hook 解 (Ex.09 / 5-6 と同じ題材) との設計比較
- `has_table_privilege()` で grant 状態を確認する

## 前提

- Topic ② 〜 ⑤ + Topic ⑧ 8-1〜8-7 完了
- `dbt/models/100-knock/topic-5/` 配下に `mart_*_100knock` が複数存在
- (推奨) `dbt/models/100-knock/topic-8/` 配下に 8-7 の `mart_customer_avg_order_100knock` (相当) が 1 本ある — 再利用の確認に使う
- `marts` schema が存在し `readonly_user` role が bootstrap 済み (`scripts/ci/bootstrap_schemas.sql` 用意済)
- dbt-postgres 1.10+

## 入力データ

不要。既存 / 8-7 で増えた mart に `+grants:` を効かせるだけ。

## 課題

> **MVP への影響に注意**: 本問は `dbt/dbt_project.yml` を直接編集する。MVP の `dbt build` も `apply grants` 行が増えるが無害。ロールバックは Step 5 を参照。
> **Topic ⑤ 5-6 との関係**: 5-6 を未実施なら本問でまとめて入れる。実施済みなら本問では「**topic-8 配下にも grants が伝播するか**」 を新たに確認する。

### Step 1: 現状確認 (新 mart に grant が付いていない)

```bash
docker exec -i local-data-postgres psql -U readonly_user -d analytics -c \
  "SELECT count(*) FROM marts.mart_customer_avg_order_100knock;"
# ERROR: permission denied for table mart_customer_avg_order_100knock
```

`has_table_privilege` でも:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT
  has_table_privilege('readonly_user',
                      'marts.mart_customer_avg_order_100knock', 'SELECT');
SQL
# f
```

### Step 2: `dbt_project.yml` の `models:` 階層に `+grants:` を追加

`dbt/dbt_project.yml` の `models.local_analytics:` 配下、**100-knock の topic-5 / topic-8 双方に効く位置** に `+grants:` を宣言する。

具体的な書き方は解答例参照。ポイント:

- `100-knock:` ブロック直下に書けば topic-5 / topic-7 / topic-8 の **全配下に伝播** する (が、staging / intermediate には grant 不要なので個別 topic に書く方が安全)
- `+grants:` は `select: ['readonly_user']` の dict
- 階層継承の感覚: `models:` → `local_analytics:` → `100-knock:` → `topic-5:` → ... の順に下に行くほど特化、上位の `+grants:` は下位で **上書き or 継承**

### Step 3: dbt build で grant が効くことを確認

```bash
set -a; source .env; set +a
cd dbt

# topic-5 の mart 群
../.venv/bin/dbt build --select 100-knock.topic-5 --profiles-dir .

# topic-8 で新規に作った mart (8-7 の mart_customer_avg_order_100knock 等)
../.venv/bin/dbt build --select 100-knock.topic-8 --profiles-dir .
```

各 build のログ末尾に `applied grants` 行が **mart 数だけ** 出ることを確認。

### Step 4: readonly_user で全 mart に SELECT できる

```bash
docker exec -i local-data-postgres psql -U readonly_user -d analytics <<'SQL'
SELECT count(*) FROM marts.mart_top_rated_products_100knock;     -- 5-1 由来
SELECT count(*) FROM marts.mart_customer_avg_order_100knock;     -- 8-7 由来
SQL
# 両方とも数値返却 (ERROR にならない)
```

`has_table_privilege` で **bulk 確認**:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics -tA <<'SQL'
SELECT count(*) FILTER (WHERE has_table_privilege('readonly_user',
                                                  schemaname || '.' || tablename,
                                                  'SELECT')) AS granted_count,
       count(*) AS total_marts
FROM pg_tables
WHERE schemaname = 'marts' AND tablename LIKE 'mart_%_100knock';
SQL
# granted_count = total_marts (全 mart で grant 済)
```

### Step 5: 採点 / ロールバック

採点:

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-8-grants-config.grading.yaml
```

ロールバック:

```bash
# 1. dbt_project.yml の +grants: 行を削除
# 2. 再 build せず DB 上の grant を消したい場合のみ:
docker exec -i local-data-postgres psql -U dbt_user -d analytics -c \
  "REVOKE SELECT ON ALL TABLES IN SCHEMA marts FROM readonly_user;"
```

## 完了条件

- [ ] `dbt/dbt_project.yml` の `models:` 配下に `+grants: {select: ['readonly_user']}` (相当) が宣言され、100-knock の **topic-5 と topic-8 双方に伝播** している
- [ ] `dbt build --select 100-knock.topic-5 100-knock.topic-8` のログに `applied grants` が **複数行** 出る
- [ ] `readonly_user` が `marts.mart_*_100knock` (topic-5 / 8 両方) を SELECT できる
- [ ] `on-run-end` hook で grant SQL を発行する macro を **追加していない** (= 宣言的解単体)

## ヒント (詰まったら)

- **`+grants:` は dict**: `+grants: {select: ['readonly_user']}` または yaml block 形式どちらでも可
- **階層継承の落とし穴**: `models.local_analytics: { +grants: {...} }` のように高い階層に書くと、staging / intermediate にも grant が走り、`readonly_user` に余計な権限が漏れる。**topic-5 / topic-8 配下にだけ** 書くのが安全
- **`apply grants` が出ない**: dbt-postgres のバージョンが古いか、`materialized: view` の view に対しては `+grants:` が dbt 1.6+ でないと効かない場合がある。本問の mart は `materialized: table` 想定なので OK
- **新 mart が増えても自動追従**: `+grants:` の真価。これが Topic ⑧ でこの題材を再訪する理由 — **「1 宣言 → N model」 の再利用パターン**
- **schema 単位の `grant usage`**: `+grants:` は table 単位のみ。`grant usage on schema marts to readonly_user` は別途 bootstrap で 1 度実行が必要 (本リポジトリ済)
- **target 別分岐**: `+grants:` には `if target.name == 'dev'` を直接書けない (静的宣言のため)。本番別 grant が必要なら target 別 project / vars で分岐
- **既存 hook (Ex.09 / Topic ⑤ 5-6) と共存可能**: 同じ grant を hook と `+grants:` の両方で発行しても冪等
- **個別 model で上書き**: 一部 mart だけ別 user に grant したい場合は当該 model の冒頭で `{{ config(grants={'select': ['analyst_user']}) }}` と書く

## 解答例

詳細は [`8-8-grants-config.solution.md`](8-8-grants-config.solution.md) を参照。
