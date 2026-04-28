# 3-8: `stg_*` の materialization を `view` に統一する設定を `dbt_project.yml` の `+materialized:` で一括宣言

> ⚠️ **本問のみ `dbt/dbt_project.yml` を学習者が編集する**。MVP の `staging:` セクションを壊さないこと。Step 5 にロールバック手順あり。

## シナリオ

3-1〜3-7 で作った `stg_*_100knock` model 群は、`{{ config(materialized='view') }}` を **各 SQL ファイルの先頭に毎回書く** か、書かない (デフォルト = view) かのどちらかになっているはず。だが「staging は全部 view」という規約を 1 行ずつ繰り返すのは DRY 違反であり、後で「staging は全部 incremental に」と方針を変えたいときに 4 ファイルを書き換えることになる。

`dbt_project.yml` の `+materialized:` 設定は、**ディレクトリ単位で materialization を宣言** できる仕組み。`models.local_analytics.100-knock.topic-3:` 階層に `+materialized: view` を書くだけで、配下の全 model に view が伝播する。これは「レイヤー contract をプロジェクト config で表現する」という dbt の核心思想。

今回は `dbt/dbt_project.yml` に **MVP 設定を壊さずに** `100-knock:` セクションを追記し、`stg_*_100knock` 全てが view として実体化されることを manifest で確認する。

## 学べること

- `dbt_project.yml` の `models:` 階層の dot-path / nested syntax
- `+materialized:` の継承ルール (子ディレクトリは親を継承、子の宣言が優先)
- レイヤー単位の materialization 統一 contract
- 個別 SQL の `{{ config() }}` よりプロジェクト config が「規約」、SQL config が「例外」という設計
- 共有ファイル (`dbt_project.yml`) を編集するときの安全運転 (diff レビュー、ロールバック手順)

## 前提

- 3-1〜3-7 完了 (`stg_*_100knock` model 群と schema.yml が存在)
- 各 SQL の中に `{{ config(materialized='view') }}` が **書かれていても書かれていなくても OK** (本問でプロジェクト config に巻き上げる)
- `dbt parse` が通る
- `git status` でクリーンな状態 (本問の編集をロールバックできるように)

## 入力データ

不要。学習者が `dbt/dbt_project.yml` を編集するだけ。

## 課題

### Step 1: 現状の dbt_project.yml を確認

```bash
cat dbt/dbt_project.yml
```

`models.local_analytics.staging:` には MVP 用の `+materialized: view` が既にある。これを **触らない**。

### Step 2: 100-knock 用セクションを追加

`models.local_analytics:` 配下に新しく `100-knock:` ブロックを追記する:

```yaml
models:
  local_analytics:
    staging:        # ← MVP。触らない
      +materialized: view
      +schema: staging
    intermediate:   # ← MVP。触らない
      +materialized: view
      +schema: intermediate
    marts:          # ← MVP。触らない
      +materialized: table
      +schema: marts
    100-knock:      # ← 追加 (本問)
      topic-3:
        +materialized: view
        +schema: staging_100knock
```

注意:

- `100-knock` は数字始まりだが YAML キーとしては OK (クォート不要)
- `+schema:` は MVP の `staging` schema と物理的に分離するため `staging_100knock` を選ぶ (Topic ② 2-2 で `raw_100knock` schema を作った思想と同じ)
- `+materialized: view` を `topic-3:` ブロックに書くことで、`dbt/models/100-knock/topic-3/` 配下の **全 model** が view 化される

### Step 3: 個別 SQL の config() を削除 (任意)

各 `stg_*_100knock.sql` の先頭に `{{ config(materialized='view') }}` がある場合、**プロジェクト config と重複** するので削除して良い (DRY)。残しても動作は変わらない (子の宣言が優先される)。

### Step 4: dbt parse + manifest_config で確認

```bash
cd dbt
dbt parse --profiles-dir .
python3 -c "
import json
with open('target/manifest.json') as f:
    m = json.load(f)
node = m['nodes']['model.local_analytics.stg_orders_100knock']
print('materialized=', node['config']['materialized'])
print('schema=', node['config']['schema'])
"
# materialized= view
# schema= staging_100knock
```

### Step 5: ロールバック手順

何かおかしくなったら:

```bash
# dbt_project.yml だけを HEAD に戻す
git checkout HEAD -- dbt/dbt_project.yml

# あるいは追加した 100-knock: ブロックだけ手で削除して保存
```

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-3-staging/3-8-materialization-config.grading.yaml
```

## 完了条件

- [ ] `dbt/dbt_project.yml` に `100-knock:` セクションが追加されている
- [ ] `100-knock.topic-3:` 配下に `+materialized: view` がある
- [ ] MVP の `staging: / intermediate: / marts:` セクションは **一切変更されていない**
- [ ] `dbt parse` が exit 0
- [ ] `manifest.json` の `stg_orders_100knock` の `config.materialized` が `view`

## ヒント (詰まったら)

- **YAML インデント事故**: `models:` 配下のインデントは 2 スペース統一。タブ混入で parse がバラバラに失敗する。`dbt parse` がエラーを吐いたらまずインデント疑い。
- **`100-knock` のキー名**: ハイフン入りの数字始まりキーは YAML で問題なく使える。だが Python から辞書アクセスするときは `["100-knock"]` の形になる (属性アクセスは不可)。
- **MVP セクションは一切触らない**: 本問の唯一のリスクは「MVP の `+materialized:` を誤って消す」こと。Step 5 の `git checkout HEAD -- dbt/dbt_project.yml` で即ロールバックできる前提で作業。
- **個別 SQL の `{{ config() }}` を消すと「明示性」を失うトレードオフ**: プロジェクト config は「離れた場所」にあるので、SQL を見ただけでは materialization が分からない。チームの好みで「両方書く」(プロジェクト config + SQL config の二重宣言) も実務ではよくある。
- **schema が `staging_100knock` に変わる**: `+schema:` を変えたら `dbt run` 後に `staging_100knock` schema が新規作成される。MVP の `staging` schema とは物理的に別。

## 解答例

詳細は [`3-8-materialization-config.solution.md`](3-8-materialization-config.solution.md) を参照。
