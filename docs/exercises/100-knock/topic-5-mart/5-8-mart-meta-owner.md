# 5-8: `mart_top_rated_products_100knock` の `meta:` に `owner` / `slack_channel` / `sla_hours` を宣言、docs で表示

## シナリオ

5-7 で `groups:` を使い「この mart は finance チームの管理下」というオーナーシップを宣言した。これで「責任主体」は決まったが、運用上の質問はまだ残っている:

- 「このマートが朝の 9:00 までに更新されないとき、誰に Slack を投げればいい？」
- 「このマートの SLA は何時間？ 4 時間以内？ 24 時間以内？」
- 「障害時の連絡先は？ 個人 email か、チャンネルか？」

これら **運用契約 (operational contract)** は SQL のロジックや schema 契約に直接表れない。代わりに `schema.yml` の **`meta:` ブロック** に宣言として書ける。dbt はこの `meta` を:

1. `manifest.json` に保存する → BI / 監視ツールから機械的に読める
2. `dbt docs generate` で auto-doc に出す → コードを読まずにブラウザで確認できる
3. `dbt ls --select 'config.meta.owner:foo@example.com'` で検索可能 → 「Foo さんが owner の mart 一覧」が抽出可能

このエクササイズでは `mart_top_rated_products_100knock` (= 5-1 で作った mart) の `schema.yml` に `meta:` を追加し、`owner` / `slack_channel` / `sla_hours` の 3 キーを必ず含める。

## 学べること

- `schema.yml` の `meta:` ブロックの位置 (model 直下 vs config 配下)
- `meta` に書ける任意キーの慣習 (`owner` / `slack_channel` / `sla_hours` / `team` / `dashboard_url` など)
- `manifest.json` の `nodes.<id>.meta` への反映
- `dbt docs generate` で meta が表示されること
- 「mart は技術契約 (`contract`) と運用契約 (`meta`) の二重宣言を持つ」感覚

## 前提

- Topic ② ③ ④ + Topic ⑤ 5-1 完了 (`mart_top_rated_products_100knock` が存在)
- `dbt/models/100-knock/topic-5/schema.yml` に `mart_top_rated_products_100knock` の宣言が既にある
- `dbt docs generate` が通る (manifest が壊れていない)

## 入力データ

不要。schema.yml に meta を書き足すだけ。

## 課題

### Step 1: `schema.yml` に `meta:` を追加

`dbt/models/100-knock/topic-5/schema.yml` の `mart_top_rated_products_100knock` 直下に以下のような `meta:` ブロックを足す:

```yaml
models:
  - name: mart_top_rated_products_100knock
    description: "高評価商品マート (avg_rating >= 4 AND review_count >= 10)"
    meta:
      owner: marketing-analytics@example.com
      slack_channel: "#mart-marketing"
      sla_hours: 4
    columns:
      # ... (5-1 で書いた columns 群はそのまま) ...
```

3 キー (`owner`, `slack_channel`, `sla_hours`) は **全て必須** とする (採点で grep する)。`sla_hours` は数値でも文字列でも OK だが、本問は数値推奨。

### Step 2: `dbt parse` で構文確認

```bash
cd dbt
dbt parse --profiles-dir .
```

`meta:` は free-form dict なので構文エラーは出にくい。出たら yaml indent を確認。

### Step 3: `dbt docs generate` を実行

```bash
dbt docs generate --profiles-dir .
```

`target/manifest.json` + `target/catalog.json` + `target/index.html` が生成される。`dbt docs serve` でブラウザを立ち上げると `mart_top_rated_products_100knock` の "Meta" タブに 3 キーが表示される (CI ではブラウザは開かないが、生成物に meta が入っていることを採点で確認する)。

### Step 4: manifest 確認

```bash
python3 -c "
import json
m = json.load(open('dbt/target/manifest.json'))
node = m['nodes']['model.local_analytics.mart_top_rated_products_100knock']
print(node['meta'])
"
# {'owner': 'marketing-analytics@example.com', 'slack_channel': '#mart-marketing', 'sla_hours': 4}
```

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-8-mart-meta-owner.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/schema.yml` の `mart_top_rated_products_100knock` 直下に `meta:` ブロックがある
- [ ] `meta:` に `owner` / `slack_channel` / `sla_hours` の 3 キーが揃っている
- [ ] `dbt parse` PASS
- [ ] `dbt docs generate` が成功する
- [ ] manifest の `nodes[mart_top_rated_products_100knock].meta` に 3 キーが入っている

## ヒント (詰まったら)

- **`meta:` の書ける場所**: model 直下 (`models[*].meta`) と column 直下 (`models[*].columns[*].meta`)。本問は model 直下。
- **`config.meta` でもいい**: `config:` ブロック内に `meta:` を書く方式もある (`config.meta.owner: foo`)。dbt は両方を merge して manifest の `meta` に展開する。本問は model 直下方式 (= シンプル)。
- **キー名は free-form**: `owner` / `slack_channel` / `sla_hours` は dbt の組み込みキーではなく、コミュニティ慣習で広く使われている命名。組織内で統一して、CI で「meta に owner が無い model は不合格」のような lint を回せばよい。
- **`sla_hours` を文字列にする派**: `"4h"` / `"24h"` のような文字列で書く流派もある。numeric の方が機械的に集計しやすい (「全 mart の平均 SLA は何時間？」)。
- **`dbt docs serve` でローカル確認**: `dbt docs generate` した後 `dbt docs serve --port 8080 --profiles-dir .` でブラウザに表示される。"Resources" → mart を選ぶと右側に Meta タブ。
- **`dbt ls` で meta による検索**: `dbt ls --select 'config.meta.owner:marketing-analytics@example.com'` で owner 指定の model 一覧が出る (dbt 1.4+)。
- **`exposure:` の owner との関係**: 5-5 で書いた `exposures.yml` の `owner:` は exposure (= dashboard) の連絡先。`meta.owner` は mart 自体の連絡先。両方書いてよい (=「この mart の責任者」と「このダッシュボードの責任者」を分離)。
- **Snowflake / BigQuery では table comment 化**: 一部 adapter は `meta` を物理 table の comment や label に転記する。dbt-postgres はそこまでしない (manifest には残る)。

## 解答例

詳細は [`5-8-mart-meta-owner.solution.md`](5-8-mart-meta-owner.solution.md) を参照。
