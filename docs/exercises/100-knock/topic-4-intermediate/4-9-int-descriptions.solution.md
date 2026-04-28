# 4-9 解答例

## dbt/models/100-knock/topic-4/schema.yml (4-9 で description を埋めた版)

```yaml
version: 2

models:
  - name: int_order_details_100knock
    description: |
      Grain: 1 row = 1 order_id。stg_orders_100knock を主軸に customers / products /
      stores の master 3 本を INNER JOIN し、sales_amount = quantity * unit_price を
      算出した「分析対象の最小単位」 の intermediate。下流 mart はここから集計する。
      税込金額が必要なら派生 model `int_order_with_tax_100knock` (4-6) を参照。
    columns:
      - name: order_id
        description: "注文 ID。Primary key (= grain key)。stg_orders_100knock.order_id を継承。"
        tests:
          - not_null
          - unique
      - name: order_date
        description: "注文日 (date 型, TZ なし)。日次バッチ集計の基準列。"
        tests:
          - not_null
      - name: customer_id
        description: "顧客 ID。FK to stg_customers_100knock.customer_id。INNER JOIN なので必ず master が引ける。"
        tests:
          - not_null
      - name: customer_name
        description: "顧客名 (text)。stg_customers_100knock から JOIN で取得。BI 表示用。"
      - name: product_id
        description: "商品 ID。FK to stg_products_100knock.product_id。"
        tests:
          - not_null
      - name: product_name
        description: "商品名 (text)。stg_products_100knock から JOIN で取得。BI 表示用。"
      - name: category
        description: "商品カテゴリ (例: 食品 / 家電 / 衣類)。stg_products_100knock.category を継承。下流 mart のグループ軸として頻用。"
      - name: store_id
        description: "店舗 ID。FK to stg_stores_100knock.store_id。"
        tests:
          - not_null
      - name: quantity
        description: "注文数量 (integer, 正の値)。stg_orders_100knock.quantity を継承。"
        tests:
          - not_null
      - name: unit_price
        description: "商品単価 (numeric(10,2), 円)。stg_orders_100knock.unit_price を継承 (注文時点の価格)。"
        tests:
          - not_null
      - name: sales_amount
        description: "売上金額 (numeric(14,2), 円, 税抜) = quantity * unit_price。本 intermediate で初めて算出される派生列。"
        tests:
          - not_null
```

**ポイント**:

- **model description にブロックスカラー `|` を使う**: 改行を保ったまま 3〜4 行で
  「grain」「JOIN 構造」「派生列」「下流での使われ方」 を簡潔に説明。1 行に詰め込むより
  読みやすい。
- **全 11 列に description**: schema.yml に書いた `columns:` 配下すべてに description
  を追加。ID 列は FK の宛先を明記、金額列は単位 (円) と桁数 (numeric(14,2)) を必ず書く。
- **継承元を明示**: `stg_xxx_100knock.<col> を継承` のように、staging 側の出処を書くことで
  「型変更や仕様変更の影響範囲」 を読み取りやすくする。
- **派生列 `sales_amount` の説明**: 「本 intermediate で初めて算出される」 と明記。下流 mart
  のレビュー時に「この列はどこで生まれた?」 と探す手間を省ける。
- **業務語彙 (BI 表示用 / グループ軸として頻用)**: 単に列名と型を書くだけでなく、
  「**この列はどう使われる**」 まで含めるのがカタログの本質。dbt docs を BI 担当が見たとき
  「これを GROUP BY して良いんだな」 と分かる。

## 実行例

```bash
$ set -a; source .env; set +a
$ cd dbt
$ ../.venv/bin/dbt parse --profiles-dir .
04:31:00  Found 11 models, 5 sources, ...

$ ../.venv/bin/dbt docs generate --profiles-dir .
04:31:10  Building catalog
04:31:11  Catalog written to /.../target/catalog.json
04:31:11  Done.
```

manifest で description が乗ったか確認:

```bash
$ python3 -c "
import json
with open('dbt/target/manifest.json') as f:
    m = json.load(f)
node = m['nodes']['model.local_analytics.int_order_details_100knock']
print('model description=', repr(node.get('description', ''))[:120])
print('column descriptions:')
for col_name, col in node.get('columns', {}).items():
    print(f'  {col_name}: {repr(col.get(\"description\", \"\"))[:60]}')
"
model description= 'Grain: 1 row = 1 order_id。stg_orders_100knock を主軸に...'
column descriptions:
  order_id: '注文 ID。Primary key (= grain key)。stg_orders_100knock.o...'
  order_date: '注文日 (date 型, TZ なし)。日次バッチ集計の基準列。'
  customer_id: '顧客 ID。FK to stg_customers_100knock.customer_id。...'
  customer_name: '顧客名 (text)。stg_customers_100knock から JOIN で取得。...'
  product_id: '商品 ID。FK to stg_products_100knock.product_id。'
  product_name: '商品名 (text)。stg_products_100knock から JOIN で取得。...'
  category: '商品カテゴリ (例: 食品 / 家電 / 衣類)。stg_products_100k...'
  store_id: '店舗 ID。FK to stg_stores_100knock.store_id。'
  quantity: '注文数量 (integer, 正の値)。stg_orders_100knock.quantity ...'
  unit_price: '商品単価 (numeric(10,2), 円)。stg_orders_100knock.unit_p...'
  sales_amount: '売上金額 (numeric(14,2), 円, 税抜) = quantity * unit_price。本...'
```

11 列 + model レベル すべてに description が入っている。

## 採点 shell_command 視点

```bash
# description の数を数える (model 1 + 11 columns = 12 個)
$ grep -cE '^\s+description:' dbt/models/100-knock/topic-4/schema.yml
12  # (もしくは 4-1 / 4-6 の他 model 込みで > 12)

# manifest で int_order_details_100knock の description が非空か
$ python3 -c "
import json
m = json.load(open('dbt/target/manifest.json'))
node = m['nodes']['model.local_analytics.int_order_details_100knock']
assert node['description'].strip(), 'model description is empty'
empty_cols = [c for c, v in node['columns'].items() if not v.get('description', '').strip()]
assert not empty_cols, f'columns without description: {empty_cols}'
print('all OK')
"
all OK
```

## 解説まとめ

- **なぜ intermediate に description を書く?**: dbt の lineage は「上流 → 下流」 と流れるので、
  下流 mart は intermediate を ref する。**intermediate に description が無い** = 下流 mart の
  description も書きづらい (継承元が空)。逆に **intermediate に description が充実** していれば、
  下流 mart は「intermediate を要約 + α」 で description が書ける = カタログ品質が上がる。
- **description の 3 つの読者**:
  1. **半年後の自分**: 「この列なんだっけ?」 を 30 秒で解決
  2. **新メンバー**: オンボーディング時に SQL ではなくカタログで仕様を読める
  3. **BI / 分析チーム**: dbt docs サイトを開いて「この数値は何?」 を解決 → SQL 担当に
     聞かなくて済む = エンジニアの割り込みが減る
- **どこまで書くか? (実務指針)**:
  - **ID 列**: FK の宛先を必ず書く (`FK to xxx.yyy`)
  - **金額列**: 通貨 + 桁数 + 税の有無 (税抜 / 税込) を明記
  - **数量列**: 単位 (個 / kg / 時間) を明記
  - **日付列**: 粒度 (date / timestamp) + TZ 有無
  - **派生列**: 算出式 (例: `quantity * unit_price`) を必ず書く
  - **業務概念列** (例: `category`, `status`): 取りうる値の例を書く
- **manifest と catalog の二層構造**:
  - **manifest.json** ← `schema.yml` の description (人が書いた仕様)
  - **catalog.json** ← `information_schema` (実 DB の物理スキーマ)
  - `dbt docs serve` は両者を JOIN して 1 つのカタログサイトを生成
  - description が無いと「列名 + 型」 だけのカタログになり、半分役立たず
- **継承的 description (1.6+)**: dbt 1.6 から `{% docs %}` ブロック + `{{ doc('xxx') }}` で
  description を外出しして再利用できる。「同じ列が複数 model に出る場合に 1 箇所定義」 という
  パターンが組める。本問はインライン記述で十分だが、列が爆発したら検討。
- **description = データ辞書 = 監査の基礎**: 金融系 / 医療系では「この列は何を表すか」 を
  文書化することがコンプライアンス要件。dbt docs はこの監査要件を **コードと近い場所** で
  満たせる仕組み (Word ドキュメントが古くなる問題を回避)。
- **本演習後**: 4-10 で `int_order_details_100knock` の v2 を作る時、本問で書いた v1 の
  description をベースに「v2 で何が増えたか」 を差分として書ける。description は
  **schema 進化の根拠** にもなる。
