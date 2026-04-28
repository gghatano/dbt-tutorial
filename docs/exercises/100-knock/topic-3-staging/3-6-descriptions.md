# 3-6: 全 staging model の `schema.yml` に `description:` を model / column 両方に書き、`dbt docs generate` で確認

## シナリオ

3-4 で `schema.yml` に `not_null` / `unique` / `relationships` を書いたところまでは「機械が読めるカタログ」になった。だがチームメンバーが docs サイトを開いたとき、`stg_orders_100knock.customer_id` が「何の ID か」を 1 行で説明できないなら、それは **人間にとってのカタログ**ではない。`description:` こそが docs の本体であり、列名から意味が読み取れない場合の唯一のセーフティネット。

今回は 3-4 で書いた `dbt/models/100-knock/topic-3/schema.yml` を拡張して、4 model 全てに **モデル description** + **全カラム description** を載せる。`dbt docs generate` で `manifest.json` に description が乗ることを確認し、最終的に docs サイトで日本語で説明が読める状態を作る。

## 学べること

- model レベル description (テーブルが何を表しているか)
- column レベル description (列の意味・単位・制約)
- `manifest.json` に description が `description` フィールドとして格納されること
- `dbt docs generate` が manifest + catalog.json を作るまでのライフサイクル
- description を **書かないと docs カタログが空文字で並ぶ** という痛みを体感

## 前提

- 3-1〜3-5 完了 (`dbt/models/100-knock/topic-3/stg_*_100knock.sql` × 4 と `schema.yml` が存在)
- `dbt parse` / `dbt run --select 100-knock` が通る
- `dbt docs generate` が初回でエラーにならない (catalog 用の DB 接続が生きている)

## 入力データ

不要。学習者が既存 `schema.yml` を編集するだけ。

## 課題

### Step 1: schema.yml に description を追加

`dbt/models/100-knock/topic-3/schema.yml` を開き、4 model それぞれに以下 2 種類の description を書く:

- **model description**: 「このモデルは何の view か」を 1〜2 行
- **column description**: 全カラムに 1 行ずつ。意味・単位・FK 関係を書く

最低限の指針:

- `customer_id` のような ID 列は「PK」「FK to xxx」を明記
- 金額列は通貨と桁数 (`unit_price` は円・整数 など)
- 日付列は粒度 (date / timestamp) と TZ 有無

### Step 2: dbt docs generate で manifest を作る

```bash
cd dbt
dbt parse --profiles-dir .
dbt docs generate --profiles-dir .
```

`target/manifest.json` と `target/catalog.json` が更新される。

### Step 3: manifest で description が空でないことを確認

```bash
# 4 model 全てで description フィールドが非空
python3 -c "
import json
with open('dbt/target/manifest.json') as f:
    m = json.load(f)
for node_id, node in m['nodes'].items():
    if 'stg_' in node_id and '100knock' in node_id:
        print(node_id, '->', repr(node.get('description', ''))[:80])
"
```

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-3-staging/3-6-descriptions.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-3/schema.yml` に `description:` キーが **20 個以上** ある (4 model + 約 16 column)
- [ ] `dbt docs generate` が exit 0 で完了
- [ ] `manifest.json` の `model.local_analytics.stg_orders_100knock` の `description` が非空
- [ ] `dbt docs serve` で開いたときに 4 model の description が日本語で読める

## ヒント (詰まったら)

- **description は YAML の文字列**: 改行を入れたいなら `description: |` のブロックスカラーを使う。1 行なら普通のクォート文字列で十分。
- **column の description が無いと、docs サイトで列名だけが並ぶ**: 「customer_id」だけだと「どの customer か」が分からない。FK なら `description: "FK to stg_customers_100knock.customer_id"` のように **どこを指しているか** を必ず書く。
- **description は manifest に入る**: `dbt parse` の時点で `manifest.json` に乗る。`dbt docs generate` は **追加で** `catalog.json` (実 DB の列メタ) を作る。description だけ確認なら `dbt parse` で十分。
- **MVP の `dbt/models/staging/schema.yml`** が良い参考。MVP では一部 description が空のままだが、本問では **全カラムに付ける** ことを目標とする。

## 解答例

詳細は [`3-6-descriptions.solution.md`](3-6-descriptions.solution.md) を参照。
