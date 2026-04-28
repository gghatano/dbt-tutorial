# 9-6: `dbt_project.yml` の `models:` で materialization をレイヤーごとに宣言、1 model だけ `config()` で override

> ⚠️ **本問は `dbt/dbt_project.yml` を学習者が編集する**。MVP の `staging:` / `intermediate:` / `marts:` セクションは触らないこと。Step 5 にロールバック手順あり。

## シナリオ

ここまで `100-knock` の各 model SQL に毎回 `{{ config(materialized='view') }}` や `materialized='table'` を書いてきた。だが「staging は全部 view」「intermediate は全部 ephemeral」「marts は全部 table」というのは **プロジェクト規約** であって、SQL ファイルに毎回繰り返すのは DRY 違反。後で「intermediate を一律 table に変えたい」となった時に N ファイルを書き換える羽目になる。

dbt の `dbt_project.yml` には `models:` 階層に `+materialized:` を宣言する仕組みがあり、**ディレクトリ単位で materialization を 1 行で宣言** できる。さらに個別 model の `{{ config() }}` がプロジェクト config を **override** する precedence もある。これにより「**規約はプロジェクトで、例外は model で**」という階層的設定が可能になる。

本問では `dbt/dbt_project.yml` の `100-knock:` セクションに **3 レイヤーの materialization を宣言** し、`mart_*_100knock` のうち 1 本だけ `config(materialized='incremental')` で override して、precedence ルールを確認する。

## 学べること

- `dbt_project.yml` の `models:` ネスト階層 (project → folder → subfolder) と `+materialized:` の継承
- staging=view / intermediate=ephemeral / marts=table のレイヤー規約
- 個別 model の `{{ config() }}` がプロジェクト config を上書きする precedence
- ephemeral materialization の意味 (DB に物理化されず CTE として展開される)
- 共有ファイル編集時の安全運転 (diff レビュー + ロールバック手順)

## 前提

- Topic ② 〜 ⑦ + ⑧ + 9-1〜9-5 完了
- `dbt/models/100-knock/topic-3/stg_*_100knock.sql` 4 本
- `dbt/models/100-knock/topic-4/int_*_100knock.sql` 1 本以上
- `dbt/models/100-knock/topic-5/mart_*_100knock.sql` 1 本以上
- `dbt parse` が通る
- `git status` がクリーン (本問の編集をロールバックできるように)

## 入力データ

不要。学習者は `dbt/dbt_project.yml` と 1 本の mart SQL を編集するのみ。

## 課題

### Step 1: 現状の dbt_project.yml を確認

```bash
cat dbt/dbt_project.yml
```

`models.local_analytics:` 配下に MVP の `staging:` / `intermediate:` / `marts:` があり、3-8 で追加した `100-knock:` セクションも見える。後者を本問でさらに育てる。

### Step 2: 100-knock セクションに 3 レイヤーの materialization 宣言を追加

`models.local_analytics.100-knock:` 配下を以下のように整える:

```yaml
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
    100-knock:      # 学習者が育てる
      topic-3:
        +materialized: view
        +schema: staging_100knock
      topic-4:
        +materialized: ephemeral   # 追加: 中間層は ephemeral (CTE 展開)
        +schema: intermediate_100knock
      topic-5:
        +materialized: table       # 追加: marts は table
        +schema: marts_100knock
```

### Step 3: 1 本だけ config() で override

`dbt/models/100-knock/topic-5/mart_orders_incremental_100knock.sql` (9-2 で作成済み) の先頭で `config(materialized='incremental')` を **明示** する:

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge'
) }}
```

これによって `topic-5: +materialized: table` を **この 1 本だけ override** する。残りの `mart_*_100knock` は table のまま。

### Step 4: dbt parse + manifest で確認

```bash
cd dbt
dbt parse --profiles-dir .
python3 -c "
import json
with open('target/manifest.json') as f:
    m = json.load(f)
for name in [
    'model.local_analytics.stg_orders_100knock',
    'model.local_analytics.int_order_details_100knock',
    'model.local_analytics.mart_customer_sales_100knock',
    'model.local_analytics.mart_orders_incremental_100knock',
]:
    node = m['nodes'].get(name)
    if node:
        print(name.split('.')[-1], '->', node['config']['materialized'])
"
# stg_orders_100knock              -> view
# int_order_details_100knock       -> ephemeral
# mart_customer_sales_100knock     -> table
# mart_orders_incremental_100knock -> incremental    ← override 効いている
```

### Step 5: ロールバック手順

何かおかしくなったら:

```bash
git checkout HEAD -- dbt/dbt_project.yml
git checkout HEAD -- dbt/models/100-knock/topic-5/mart_orders_incremental_100knock.sql
```

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-9-performance/9-6-materialization-hierarchy.grading.yaml
```

## 完了条件

- [ ] `dbt/dbt_project.yml` の `100-knock.topic-3` に `+materialized: view`
- [ ] `dbt/dbt_project.yml` の `100-knock.topic-4` に `+materialized: ephemeral`
- [ ] `dbt/dbt_project.yml` の `100-knock.topic-5` に `+materialized: table`
- [ ] `mart_orders_incremental_100knock.sql` の `config()` で `materialized='incremental'` 宣言
- [ ] manifest 上、`mart_orders_incremental_100knock` の `materialized` が `incremental` (override 確認)
- [ ] MVP の `staging:` / `intermediate:` / `marts:` セクションは無傷

## ヒント (詰まったら)

- **YAML インデント事故**: `models:` 配下のインデントは 2 スペース統一。タブ混入で parse が失敗する。`dbt parse` がエラーを吐いたらまずインデント疑い。
- **ephemeral は DB に table を作らない**: 中間層を ephemeral にすると `intermediate_100knock` schema には何も作られず、下流 SQL に CTE として展開される。`dbt show --select int_order_details_100knock` で確認できる。これは「中間層は物理化せず計算量だけ移譲したい」場合の選択。
- **precedence の順序**: dbt の config 解決順は `(model 内 config) > (dbt_project.yml 末端) > (dbt_project.yml 親) > (default)`。SQL 内の `config()` が常に最強。
- **9-2 の mart_orders_incremental_100knock が無い場合**: 9-2 完了が前提だが、未実装なら `mart_customer_sales_100knock` など他の mart で override を試して、本問の主旨「project config + 1 model override」が成立すればよい (採点 yaml の対象 model 名は読み替え可能)。
- **MVP セクションを誤って消す**: 唯一のリスク。Step 5 の `git checkout HEAD --` で即ロールバックできる前提で作業。

## 解答例

詳細は [`9-6-materialization-hierarchy.solution.md`](9-6-materialization-hierarchy.solution.md) を参照。
