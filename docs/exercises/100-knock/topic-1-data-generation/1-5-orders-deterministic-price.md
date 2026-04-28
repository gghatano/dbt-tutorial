# Problem 1-5: orders.unit_price を product_id から決定論的に算出

## シナリオ

1-4 で作った `orders.csv` には致命的な問題がある — **同じ product_id でも
注文ごとに `unit_price` が違う**。実世界では「商品の単価」は商品マスタに
紐づく属性で、注文行に勝手に書き換える権限はない (=価格改定や snapshot は
別の問題で扱う)。

このギャップを埋めるため、`orders.csv` を再生成する。今度は 1-2 で作った
`products.csv` の `unit_price` を読み込んで `{product_id: unit_price}` の
辞書を引き、order 行に正しい値を埋める。

これは「**生成データに整合性 (referential integrity) を持たせる**」という
データ契約上の最重要パターンの 1 つ。dbt 側では「同じ product_id は常に
同じ unit_price」をテストする schema test (custom generic test や
`dbt_utils.expression_is_true`) を後で書くことになる。

## 学べること

- 既存 CSV (`products.csv`) を `csv.DictReader` で読み込み辞書化する
- ファクトテーブル生成時の **lookup join パターン**
- 「決定論的算出」と「ランダム抽選」の混在: product_id は乱択、
  unit_price は決定論
- shell の awk + sort + uniq だけで「関数性 (functional dependency)」を
  検証する手筋

## 前提

- 1-4 のスクリプト `scripts/100-knock/topic-1/generate_1_04_orders.py` が
  動いている
- 1-2 の出力 `data/100-knock/topic-1/products.csv` が存在する
  (列: `product_id,product_name,category,unit_price`)
- もし 1-2 がまだ未完了なら、最低限 `product_id,unit_price` の 2 列だけ
  でも自分で products.csv を用意すれば本問題は解ける

## 入力データ

- `data/100-knock/topic-1/products.csv` (1-2 で生成済み)

## 出力データ

スキーマは 1-4 と同一:

| 列            | 型     | 備考                                            |
|---------------|--------|-------------------------------------------------|
| `order_id`    | bigint | 1..10000                                         |
| `order_date`  | date   | 直近 1 年                                        |
| `customer_id` | bigint | 1..1000                                          |
| `product_id`  | bigint | 1..100                                           |
| `store_id`    | bigint | 1..20                                            |
| `quantity`    | int    | 1..10                                            |
| `unit_price`  | int    | **products.csv の同 product_id の値と完全一致** |

出力先: `data/100-knock/topic-1/orders.csv` (1-4 と同じ。**上書き** する)。

## 課題

### Step 1: スクリプトを作る

`scripts/100-knock/topic-1/generate_1_05_orders.py` を作る。

- 1-4 のスクリプトをコピーして改修するのが楽
- products.csv を `csv.DictReader` で読み込み、`{int(product_id): int(unit_price)}`
  の辞書を作る
- order 1 行ごとに `unit_price = price_lookup[product_id]` で引く
- seed は `205` を使う (1-4 と意図的に変えて、order_date / customer_id 等の
  乱数列も 1-4 とは別であることを示す)

### Step 2: 実行

```bash
.venv/bin/python scripts/100-knock/topic-1/generate_1_05_orders.py
wc -l data/100-knock/topic-1/orders.csv  # => 10001
```

### Step 3: 関数性をローカル確認

「同じ product_id は常に同じ unit_price」 = `product_id → unit_price` の
**関数依存** が成り立つことを 1 行 awk で確認する:

```bash
awk -F, 'NR>1{print $4","$7}' data/100-knock/topic-1/orders.csv \
  | sort -u \
  | awk -F, '{print $1}' \
  | sort \
  | uniq -c \
  | awk '$1!=1 {print "VIOLATION: product_id=" $2 " has " $1 " distinct prices"}'
# 何も出力されなければ OK
```

`(product_id, unit_price)` の distinct 集合を取り、`product_id` だけで
グループ化して件数をカウントする。1 つの product_id に複数 unit_price が
紐づくと出力に出る。

### Step 4: products.csv との一致確認

```bash
join -t, -1 1 -2 4 \
  <(sort -t, -k1,1 data/100-knock/topic-1/products.csv) \
  <(awk -F, 'NR>1{print $0}' data/100-knock/topic-1/orders.csv | sort -t, -k4,4) \
  | awk -F, '$4 != $11 {print "MISMATCH: product_id=" $1}' | head
# 何も出なければ products.csv と完全一致
```

(列番号は環境で揺れるので、出題側は psycopg / pandas で join 検証してもよい)

## 完了条件

- [ ] orders.csv が 10,001 行
- [ ] `(product_id, unit_price)` の distinct 集合が 100 件 ちょうど
  (= product_id 1..100 に 1 単価ずつ紐づく)
- [ ] orders.unit_price が products.unit_price と完全一致
- [ ] 1-4 で確認した FK 範囲 / PK ユニーク性は引き続き満たす

## ヒント

- **辞書化の型変換**: `csv.DictReader` は全フィールドを `str` で返すので、
  `int(row["product_id"])` / `int(row["unit_price"])` で明示変換する。
  忘れると lookup miss で KeyError が出る。
- **products.csv が存在しない場合の挙動**: スクリプト先頭で
  `if not PRODUCTS_CSV.exists(): print("先に 1-2 を解いてね"); sys.exit(1)`
  のように親切エラーを出すと、出題者として印象がよい。
- **1-4 のシードと変える理由**: もし seed を 1-4 と同じ 204 にすると、
  product_id の抽選列も同じになり「price だけが変わった」差分が読みづらく
  なる。意図的に 205 にして「これは別の生成回」だと示す。
- **awk の検証コマンド**: 採点の `shell_command` でそのまま使えるよう、
  「違反があれば 1 行出力する」設計にする。空出力 = OK と判定しやすい。

## 解答例

[`1-5-orders-deterministic-price.solution.md`](./1-5-orders-deterministic-price.solution.md)
を参照。
