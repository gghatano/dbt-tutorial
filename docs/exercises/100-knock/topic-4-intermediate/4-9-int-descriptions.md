# 4-9: int_order_details_100knock の `schema.yml` に全列 description を書き、docs カタログ化

## シナリオ

3-6 で staging 4 model に description を書いたのと同じことを **intermediate** でも行う。
intermediate は staging より **業務語彙** に近い (例: `sales_amount` は staging には無く
intermediate で初めて登場する派生列)。下流 mart はこの description を **継承的に** 参照するので、
**intermediate の description は分析チームの「データ辞書」 そのもの** になる。

本問では `int_order_details_100knock` の **全カラムに description** を書き、`dbt docs generate`
で manifest にカタログを焼き込み、`dbt docs serve` で BI 担当が日本語で説明を読める状態を作る。
intermediate に description が付いていないと、下流 mart の description も書きづらく
(継承元が空)、結局 BI ダッシュボードの「この数値は何?」 が答えられなくなる。

## 学べること

- intermediate model の `schema.yml` に **model 単位** + **全 column 単位** の description を書く
- `manifest.json` に description フィールドが入ることの確認
- `dbt docs generate` で `catalog.json` (実 DB の列メタ) も生成
- `dbt docs serve` で BI / アナリストが見るカタログサイトを開く
- intermediate の description は下流 mart の description のソースになる (継承的参照)

## 前提

- Topic ② ③ 完了 + Topic ④ 4-1 完了 (`int_order_details_100knock` が存在、`schema.yml` も最低限のテストは入っている)
- `dbt parse` / `dbt run --select int_order_details_100knock` が通る
- `dbt docs generate` が初回で成功する (catalog 用 DB 接続が生きている)

> **注**: 4-8 で ephemeral にしたままだと catalog に物理列メタが入らない。本問の前に
> `int_order_details_100knock` の materialization を **view (もしくは table)** に戻すこと。

## 入力データ

不要。学習者が `dbt/models/100-knock/topic-4/schema.yml` を編集するだけ。

## 課題

### Step 1: schema.yml に description を追加

`dbt/models/100-knock/topic-4/schema.yml` を開き、`int_order_details_100knock` の
ブロックに以下 2 種類の description を追記:

- **model description**: 「このモデルが何を表すか」 を 2〜3 行で。grain 宣言を含める
- **column description**: **全カラム (11 列)** に 1 行ずつ
  - ID 列は「PK」「FK to xxx」を明記
  - 金額・数量列は単位 / 桁数 / 算出式
  - 日付列は粒度 (date / timestamp) と TZ 有無

11 列の内訳: `order_id`, `order_date`, `customer_id`, `customer_name`,
`product_id`, `product_name`, `category`, `store_id`, `quantity`, `unit_price`,
`sales_amount`。

### Step 2: dbt docs generate

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt docs generate --profiles-dir .
```

`target/manifest.json` と `target/catalog.json` が更新される。

### Step 3: manifest で description が乗ったことを確認

```bash
python3 -c "
import json
with open('dbt/target/manifest.json') as f:
    m = json.load(f)
node = m['nodes']['model.local_analytics.int_order_details_100knock']
print('model description=', repr(node.get('description', ''))[:120])
print('column descriptions:')
for col_name, col in node.get('columns', {}).items():
    print(f'  {col_name}: {repr(col.get(\"description\", \"\"))[:60]}')
"
```

全カラム + model レベルで description が空でなければ OK。

### Step 4: docs serve で BI 視点を体感 (任意)

```bash
../.venv/bin/dbt docs serve --profiles-dir . --port 8080
```

ブラウザで `http://localhost:8080` を開き、`int_order_details_100knock` のページに
飛んで「列ごとの説明が日本語で読める」 状態を確認。Ctrl+C で停止。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-4-intermediate/4-9-int-descriptions.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-4/schema.yml` の `int_order_details_100knock` ブロックに **`description:` が 12 個以上** ある (model 1 + 11 column)
- [ ] `dbt parse` が exit 0
- [ ] `dbt docs generate` が exit 0
- [ ] `manifest.json` の `int_order_details_100knock` の **model description** が非空
- [ ] `manifest.json` の **全 11 列** で description が非空

## ヒント (詰まったら)

- **description の文字列フォーマット**: 改行を入れたいなら `description: |` のブロックスカラー。1 行なら普通のクォート文字列で十分。日本語 OK。
- **列名から意味が読み取れない場合は description で補う**: 例えば `category` は「商品カテゴリ (例: 食品 / 家電)」のように **具体例** を書く。`store_id` は「FK to stg_stores_100knock.store_id」と参照先を明記。
- **catalog.json と manifest.json の違い**: manifest は `schema.yml` から作られる「人が書いた仕様」、catalog は実 DB の `information_schema` から作られる「現実の物理スキーマ」。`dbt docs serve` は両方を統合して見せる。description は manifest 側に入る。
- **3-6 との違い**: 3-6 では staging の description を書いた。本問は intermediate の description。「下流 mart は intermediate を ref するので、intermediate の description は mart のカタログ品質を支配する」 というレイヤー上の責務の違いを意識する。
- **doc block (`{% docs %}`) は次レベル**: 長い description を YAML に書きたくないなら `dbt/models/100-knock/topic-4/_docs.md` に `{% docs col_xxx %}...{% enddocs %}` で外出しし、`description: "{{ doc('col_xxx') }}"` で参照する手もある (本問はインライン記述で十分)。

## 解答例

詳細は [`4-9-int-descriptions.solution.md`](4-9-int-descriptions.solution.md) を参照。
