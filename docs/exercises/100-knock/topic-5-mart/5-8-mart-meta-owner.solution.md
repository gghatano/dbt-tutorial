# 5-8 解答例

## ゴール再掲

`dbt/models/100-knock/topic-5/schema.yml` の `mart_top_rated_products_100knock` 直下に `meta:` ブロックを追加し、`owner` / `slack_channel` / `sla_hours` の 3 キーを宣言する。`dbt docs generate` でこれらが manifest に乗ることを確認。

## Step 1: `schema.yml` を編集

`dbt/models/100-knock/topic-5/schema.yml` (5-1 で作成済みの schema.yml に meta を追記):

```yaml
version: 2

models:
  - name: mart_top_rated_products_100knock
    description: |
      高評価商品マート。条件: avg_rating >= 4 AND review_count >= 10。
      grain = 1 product 1 row。
    # ----- 5-8: 運用契約 (operational contract) を meta に宣言 -----
    # owner / slack_channel / sla_hours の 3 キーは社内ルールで必須化。
    # CI で grep で missing を検知する想定 (詳細は本 exercise の grading.yaml)。
    meta:
      owner: marketing-analytics@example.com
      slack_channel: "#mart-marketing"
      sla_hours: 4
    columns:
      - name: product_id
        description: "Primary key. FK to stg_products_100knock.product_id"
        tests:
          - not_null
          - unique
      - name: product_name
        tests:
          - not_null
      - name: avg_rating
        description: "平均レビュー評点 (1-5 の numeric(3,2))"
        tests:
          - not_null
      - name: review_count
        description: "対象商品のレビュー件数 (>=10 が条件)"
        tests:
          - not_null
      # ... 他列は 5-1 の解答に合わせる ...

  # 他 mart (mart_monthly_sales_by_category_100knock 等) の宣言が続く...
```

> 既存 `schema.yml` の構成 (5-1 / 5-2 / 5-3 / 5-5 で順次足してきた状態) によって他 model のブロックも並ぶ。本問では `mart_top_rated_products_100knock` の `meta:` だけが採点対象。

## Step 2: `dbt parse`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# 22:30:01  Found 12 models, 4 sources, 25 tests, ...
```

## Step 3: `dbt docs generate`

```bash
../.venv/bin/dbt docs generate --profiles-dir .
# 22:30:11  Found 12 models, 4 sources, 25 tests, ...
# 22:30:12  Concurrency: 4 threads (target='dev')
# 22:30:13  Building catalog
# 22:30:15  Catalog written to /path/to/target/catalog.json
```

`target/manifest.json` と `target/catalog.json` が更新される。

## Step 4: manifest 確認

```bash
../.venv/bin/python <<'PY'
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.mart_top_rated_products_100knock']
print('meta =', node['meta'])
PY
# meta = {'owner': 'marketing-analytics@example.com', 'slack_channel': '#mart-marketing', 'sla_hours': 4}
```

`dbt docs serve` でブラウザ確認:

```bash
../.venv/bin/dbt docs serve --port 8080 --profiles-dir .
# http://localhost:8080 を開いて
#   Project: local_analytics → Models → mart_top_rated_products_100knock
#   右ペインの "Meta" タブに 3 キーが表示される
```

(CI では serve は不要。manifest に乗っていれば OK)

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-8-mart-meta-owner.grading.yaml
```

期待:

```
## Grading Result: OK (100%)
| OK | schema-yml-has-meta-block          | 15/15 |
| OK | meta-has-owner-key                 | 10/10 |
| OK | meta-has-slack-channel-key         | 10/10 |
| OK | meta-has-sla-hours-key             | 10/10 |
| OK | dbt-parse-success                  | 15/15 |
| OK | dbt-docs-generate-success          | 20/20 |
| OK | manifest-meta-owner                | 10/10 |
| OK | manifest-meta-sla                  | 10/10 |
```

## ポイント

- **`meta:` の書ける場所 — model 直下 vs config 配下**:
  - **model 直下** (本解答): `models[*].meta.owner` のように指す
  - **config 配下**: `models[*].config.meta.owner`
  - dbt は manifest に展開するとき両方を merge して `node.meta` にまとめる。読みやすさで model 直下を推奨。
- **キー名は社内合意で決める**: `owner` / `slack_channel` / `sla_hours` は dbt の予約キーではない。チーム / 組織でルールを決め、新規 mart が同じキーを揃えて追加されるように lint で守る。
- **owner: email vs Slack handle**: `email` は監査向け (誰の責任か固定する) / `slack_channel` は障害連絡向け (チャンネル単位なので不在対応も可)。両方書く。
- **`sla_hours` を `monitoring` ツールに渡す**: 監視ツール (Datadog / PagerDuty) と連携する場合、manifest を読んで「sla_hours=4 を超える未更新 mart にアラート」設定を自動生成する。
- **`exposure:` の `owner:` との対比**: `exposures.yml` の owner は **dashboard / API / report の連絡先** (= データを使う側)。本問の `meta.owner` は **mart 自体の連絡先** (= データを出す側)。両方書くのが正解。
- **`dbt docs` での見え方**: model 詳細ページの右上に "Owner: marketing-analytics@example.com" のような見出しが出る (template 依存)。Slack / SLA は "Meta" セクションに dict として表示。

## 実行例 (採点 shell_command 視点)

```bash
$ grep -E '^\s*meta:' dbt/models/100-knock/topic-5/schema.yml
    meta:
$ grep -E 'owner:\s+\S+@' dbt/models/100-knock/topic-5/schema.yml
      owner: marketing-analytics@example.com
$ grep -E 'slack_channel:' dbt/models/100-knock/topic-5/schema.yml
      slack_channel: "#mart-marketing"
$ grep -E 'sla_hours:' dbt/models/100-knock/topic-5/schema.yml
      sla_hours: 4

$ cd dbt && dbt docs generate --profiles-dir . 2>&1 | tail -3
22:30:15  Catalog written to /path/to/target/catalog.json

$ python3 -c "import json; m=json.load(open('dbt/target/manifest.json')); print(m['nodes']['model.local_analytics.mart_top_rated_products_100knock']['meta']['owner'])"
marketing-analytics@example.com
```

## 解説まとめ

- **なぜ `meta:` で運用情報？**: SQL 本体には書けない (= 集計ロジックではない) し、`description:` に書くと自然言語に埋もれて機械可読性が落ちる。**構造化 dict** として宣言することで、`manifest.json` 経由で監視 / 監査 / Slack bot などのツールが読める。
- **「mart は技術契約 + 運用契約」**:
  - **技術契約** (5-3 `contract: enforced`, 5-9 `dbt-expectations`): 列名・型・値の範囲。BI が壊れないことを保証
  - **運用契約** (本問 `meta:`, 5-7 `groups:`): 障害時の連絡先・SLA・オーナーシップ。組織が壊れないことを保証
  - 両方を `schema.yml` に並べると、コードレビューで「この PR で技術契約は守られているが、SLA が変更されている」のような議論ができる。
- **manifest 経由で自動化につなげる**: `target/manifest.json` を CI で artifact として保存しておくと、別プロセス (Slack bot / 監視自動セットアップ) から「mart の `sla_hours` が 24 を超えるなら PagerDuty に登録」のような自動化が回せる。dbt の出力は **コードと外部システムの境界面** として設計されている。
- **lint としての meta 必須化**: `pre-commit` か CI のチェックスクリプトで「mart_*.sql に対応する schema.yml の `meta` に `owner` キーが無ければ fail」を組み込める。本問の grading.yaml がまさにその雛形 (`grep -E 'owner:' ...`)。
- **将来的に `dbt-checkpoint` や `dbt-meta-testing`**: コミュニティパッケージとして「`meta` の必須キー bot」が存在する。組織で増やしたいキー (例: `data_classification`) を YAML で宣言し、それをチェックする lint を追加するのが一般的。

## 拡張アイデア

- **column 単位の meta**: `columns[*].meta` に `pii: true` / `data_classification: confidential` を書き、PII 列を `dbt ls` で抽出
- **全 mart の SLA を一覧化**: `manifest.json` を python で読んで `(model_name, owner, sla_hours)` の CSV を出力するスクリプトを書き、Topic ⑥ 以降のレポート出題に使う
- **`dbt-checkpoint` を導入**: pre-commit 段階で「mart は meta.owner が必須」をチェックする
- **Slack bot 連携**: GitHub Actions で manifest を artifact 化し、別ワークフローで `meta.slack_channel` に「今 PR で mart 変更が入った」を通知
- **`exposure:` の owner と meta.owner の差を docs で可視化**: 「mart の owner」と「dashboard の owner」が違うときに警告を出す
