# 3-8 解答例

## dbt/dbt_project.yml (差分)

`models:` ブロックに `100-knock:` セクションを追記する。MVP の `staging: / intermediate: / marts:` は一切触らない。

```yaml
name: 'local_analytics'
version: '1.0.0'
config-version: 2

profile: 'local_analytics'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  local_analytics:
    staging:        # MVP - 触らない
      +materialized: view
      +schema: staging
    intermediate:   # MVP - 触らない
      +materialized: view
      +schema: intermediate
    marts:          # MVP - 触らない
      +materialized: table
      +schema: marts
    100-knock:      # ← 追加 (本問)
      topic-3:
        +materialized: view
        +schema: staging_100knock
```

**ポイント**:

- **既存 3 セクション (`staging` / `intermediate` / `marts`) は無傷**: MVP の挙動を一切壊さないことが本問の最大の制約。`git diff dbt/dbt_project.yml` で追加行のみが diff に出ることを確認。
- **`100-knock.topic-3:` の階層**: ファイルパス `dbt/models/100-knock/topic-3/` と階層が一致している。dbt は **物理パス → 階層** の対応で config を引く。Topic ④ (intermediate) を将来追加するときは `100-knock.topic-4:` を別ブロックで足せばいい。
- **`+materialized: view`**: `+` は「この階層配下の全 model に伝播させる」記号。書かないと「この階層 1 個だけに適用」の意味になり、子ディレクトリには伝わらない。
- **`+schema: staging_100knock`**: 物理 schema を MVP と分離。`raw_100knock` (Topic ②) → `staging_100knock` (Topic ③) という命名で「100-knock の世界」を物理的にも独立させる。
- **個別 SQL の `{{ config() }}` は削除可**: `stg_*_100knock.sql` の先頭にあった `{{ config(materialized='view') }}` はプロジェクト config に巻き上がったので削除して良い。残しても挙動は同じ (子の宣言が親を上書きするだけで、両方が `view` なら同じ結果)。

## 確認手順

### 1. parse + manifest 確認

```bash
$ cd dbt
$ dbt parse --profiles-dir .
12:00:00  Found 8 models, 4 sources, 21 tests, ...

$ python3 -c "
import json
with open('target/manifest.json') as f:
    m = json.load(f)
for nid in [
    'model.local_analytics.stg_customers_100knock',
    'model.local_analytics.stg_products_100knock',
    'model.local_analytics.stg_stores_100knock',
    'model.local_analytics.stg_orders_100knock',
]:
    n = m['nodes'][nid]
    print(nid, '->', n['config']['materialized'], '/', n['config']['schema'])
"
model.local_analytics.stg_customers_100knock -> view / staging_100knock
model.local_analytics.stg_products_100knock  -> view / staging_100knock
model.local_analytics.stg_stores_100knock    -> view / staging_100knock
model.local_analytics.stg_orders_100knock    -> view / staging_100knock
```

### 2. dbt_project.yml の diff 確認

```bash
$ git diff dbt/dbt_project.yml
@@ -23,3 +23,7 @@ models:
     marts:
       +materialized: table
       +schema: marts
+    100-knock:
+      topic-3:
+        +materialized: view
+        +schema: staging_100knock
```

追加行のみが diff に出ていれば OK。MVP セクションに変更が入っていたら **即ロールバック**。

### 3. ロールバック (失敗時)

```bash
# 全部戻す
git checkout HEAD -- dbt/dbt_project.yml

# 部分的に戻したい (差分エディタで手作業)
git diff dbt/dbt_project.yml
# ↑で出た追加行を手で削除
```

## 解説まとめ

- **なぜプロジェクト config に巻き上げる?**: 「staging は全部 view」というレイヤー contract を 1 箇所で宣言するため。SQL ファイル毎に `{{ config(materialized='view') }}` を書くと、4 ファイル全てを同じルールで揃える保証が無い (1 個だけ table のままが紛れる事故が起きる)。
- **継承の仕組み**: dbt は `models.local_analytics.100-knock.topic-3:` の config を、配下の全ファイルに **暗黙に適用** する。子 SQL に `{{ config(materialized='table') }}` があれば、それが親を上書きする (子優先)。これにより「規約 = プロジェクト config」「例外 = 個別 SQL config」の責任分担が成立する。
- **`+` プレフィックスの意味**: dbt の YAML 階層では `+` 付きキーが「config」、`+` 無しキーが「子ディレクトリ」を意味する。`+materialized:` と `materialized:` は別物 (後者は `materialized` という名前のディレクトリを指してしまう)。
- **物理 schema 分離 (`staging_100knock`)**: MVP の `staging` schema と物理的に分けることで、本トピックの作業が MVP の `dbt run` を壊さないことを保証。`raw_100knock` (Topic ②) と命名規約も揃う。
- **共有ファイルを編集する責任**: `dbt_project.yml` はプロジェクト全体の挙動を決める。本問でしか触らない (3-9 / 3-10 では触らない) ことを明確化。「学習者がプロジェクト config を編集する練習」自体が本問の隠れた目的。
- **MVP の `+materialized:` を消すと?**: `dbt run` 全体が壊れる。MVP の test (`dbt build`) が失敗する。本問の最大の落とし穴。Step 5 のロールバック手順を **作業前に** 試しておくのが安全。
