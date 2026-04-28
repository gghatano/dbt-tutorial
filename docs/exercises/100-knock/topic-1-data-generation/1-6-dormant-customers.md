# 1-6: customer_id の 1% は orders に登場しない (休眠顧客)

## シナリオ

実データの世界では「登録はしたけど一度も買っていない顧客 = 休眠顧客」が必ず存在する。
1-4 / 1-5 までで作った orders.csv は `customer_id` を `randint(1, 1000)` で抽選していたため
全顧客がほぼ均等に発注している状態 (= 非現実的) だった。
ここでは **抽選範囲を `[1..990]` に絞る** ことで、`[991..1000]` の 10 顧客 (= 1%) を
意図的に「orders に出てこない顧客」にする。

これは「FK のカバレッジは 100% ではない」という事実を Python 側で **データ仕様として宣言**
する練習で、後続トピックで `customers LEFT JOIN orders` を書くときの「null になる側」を
ちゃんと作っておく地ならしになる。

## 学べること

- FK の参照範囲を Python 側で `randint(1, 990)` のように **狭めて宣言** するパターン
- 「全件 100% カバレッジを満たさない FK」が現実的に存在するという感覚
- `relationships` テスト ( `customers.customer_id` → `orders.customer_id` 方向ではなく逆向き) が
  なぜ片方向にしか書けないのかの体感
- Python の `set` 演算でカバレッジ差集合を計算する書き方

## 前提

- 1-1 (customers.csv) と 1-4 / 1-5 (orders.csv) が既に走っていること
  - `data/100-knock/topic-1/customers.csv` (1000 行 + ヘッダ)
  - `data/100-knock/topic-1/orders.csv` (10000 行 + ヘッダ)
- `requirements.txt` の `Faker` / `pandas` がインストール済み
- 1-5 で固定した `product_id × unit_price` の決定論的ロジックは引き続き保つこと

## 入力データ

`data/100-knock/topic-1/products.csv` (100 行 + ヘッダ) を **読み込み**、
`unit_price` ルックアップに使う (1-5 と同じ手法)。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_6_dormant_customers.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/orders.csv` を **上書き** 再生成 (10000 行 + ヘッダ)
- 列: 1-4 と同じ `order_id, order_date, customer_id, product_id, store_id, quantity, unit_price`
- `customer_id` の抽選は `rng.randint(1, 990)` に **絞る** (= 991..1000 の 10 顧客は登場しない)
- `product_id`, `store_id`, `quantity`, `order_date` の生成ロジックは 1-4 / 1-5 と同等
- `unit_price` は `products.csv` の `product_id` キーで決定論的に取る (1-5 の規約)
- **シードは 206 で固定** (`Faker.seed_instance(206)` + `random.Random(206)`)
- 列順は `columns=[...]` で固定

### Step 2: 実行 + 動作確認

```bash
python3 scripts/100-knock/topic-1/generate_1_6_dormant_customers.py
```

期待表示例:

```
Generated data/100-knock/topic-1/orders.csv: 10000 rows
Distinct customer_id in orders: 990 (dormant: 10)
```

カバレッジを目視:

```bash
python3 -c "
import csv
with open('data/100-knock/topic-1/orders.csv') as f:
    r = csv.DictReader(f)
    seen = {int(row['customer_id']) for row in r}
all_ids = set(range(1, 1001))
print('dormant:', sorted(all_ids - seen))
"
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-6-dormant-customers.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_6_dormant_customers.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/orders.csv` が 10000 行 + ヘッダ
- [ ] orders に登場する distinct customer_id 数が 990 ± 10
- [ ] customers の全 ID と orders 出現 ID の差集合が 10 個 ± 数個 (= 約 1%)

## ヒント (詰まったら)

- 「1% を意図的に休眠にする」の素直な実装は **抽選母集団を `[1..990]` に絞る**こと。
  事後的に「先に 1..1000 で振ってから 991..1000 を 1..990 に置き換える」より素直で読みやすい
- シードによっては `[1..990]` で振っても 990 個全員が出るとは限らない (10000 試行なら現実的に
  全員出るが、少数の 1..990 内 ID もたまたま 0 件になる可能性は理論上ある)。採点はあくまで
  「**約 10 個**」(8〜12) 程度のレンジで評価する
- 1-4 / 1-5 / 1-6 / 1-7 は全て同じ orders.csv を上書きするので、最後に走らせたスクリプトの
  仕様が CSV に残る。1-6 のあとに 1-4 を再実行すると休眠制約は消える点に注意 (= 学習者は
  「複数の宣言を同時に満たす」最終形を 1-9 / 1-10 で組み立てる)

## 解答例

詳細は [`1-6-dormant-customers.solution.md`](1-6-dormant-customers.solution.md) を参照。
