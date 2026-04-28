# Problem 1-4: orders 10,000 行、FK 範囲を Python 側で先に宣言

## シナリオ

EC のトランザクションを担う `orders` ファクトを作る。1-1〜1-3 で定義した
`customers` (1..1000) / `products` (1..100) / `stores` (1..20) の PK を **FK**
として参照する。10,000 行を Faker + 乱数で生成しつつ、**FK の取りうる範囲を
スクリプト冒頭で定数化** することで、後段の `relationships` テストや
`accepted_values` テストと「同じソースから同じ事実」が読み取れる状態を作る。

これは「Faker をデータ仕様の DSL として使う」という Topic ① のテーマの
中で、もっとも重要な習慣 — **生成側と検証側で FK 範囲を一元管理する** —
を体に叩き込む回。

## 学べること

- 複数の FK を抱えるトランザクションテーブルの生成
- **FK 範囲をコード冒頭で宣言** することで、生成側 / 検証側の食い違いを防ぐ
- `random.Random(seed)` による再現性のある乱数列
- `csv.writer` で軽量 CSV を出力する (pandas 不要)
- 採点に「awk + sort + uniq」で済む確認をどう設計するか

## 前提

- `scripts/100-knock/topic-1/` に作業用ディレクトリが切れる
- `.venv/bin/python` が動き、`Faker` が import できる
- 1-1, 1-2, 1-3 の出力 CSV (`customers.csv` / `products.csv` / `stores.csv`)
  は **存在しなくても** この問題は解ける (PK 範囲だけ参照する)

## 入力データ

なし。`Faker` + `random` で全部生成する。

## 出力データ

スキーマ:

| 列            | 型        | 備考                                 |
|---------------|-----------|--------------------------------------|
| `order_id`    | bigint    | 1..10000 の連番、PK                  |
| `order_date`  | date      | 直近 1 年の任意日付 (ISO 8601)       |
| `customer_id` | bigint    | 1..1000 から抽選 (FK to customers)   |
| `product_id`  | bigint    | 1..100  から抽選 (FK to products)    |
| `store_id`    | bigint    | 1..20   から抽選 (FK to stores)      |
| `quantity`    | int       | 1..10                                |
| `unit_price`  | int       | 100〜9990 円程度 (1-5 で決定論化する) |

サンプル:

```csv
order_id,order_date,customer_id,product_id,store_id,quantity,unit_price
1,2025-08-13,712,42,9,3,2890
2,2025-12-04,158,77,2,7,1240
3,2026-04-18,401,5,17,1,9870
```

## 課題

### Step 1: スクリプトを作る

`scripts/100-knock/topic-1/generate_1_04_orders.py` を作る。

- 出力先: `data/100-knock/topic-1/orders.csv`
- 行数: 10,000 (+ ヘッダ 1)
- 冒頭で **FK 範囲を定数化**: `NUM_CUSTOMERS = 1_000` / `NUM_PRODUCTS = 100` /
  `NUM_STORES = 20`
- 乱数 seed は `204` を使う (再現性 + 他問と衝突しない)
- pandas でも csv.writer でも可

### Step 2: スクリプトを実行

```bash
.venv/bin/python scripts/100-knock/topic-1/generate_1_04_orders.py
wc -l data/100-knock/topic-1/orders.csv  # => 10001
head -3 data/100-knock/topic-1/orders.csv
```

### Step 3: FK 範囲をローカルで自前確認

```bash
# customer_id の最大値が 1000 以下か
awk -F, 'NR>1{print $3}' data/100-knock/topic-1/orders.csv | sort -n | tail -1
# => <= 1000

# product_id の最大値
awk -F, 'NR>1{print $4}' data/100-knock/topic-1/orders.csv | sort -n | tail -1
# => <= 100
```

## 完了条件

- [ ] `data/100-knock/topic-1/orders.csv` が存在する
- [ ] 行数が 10,001 (ヘッダ + 10,000)
- [ ] `order_id` がユニークで 1..10000 を埋めている
- [ ] `customer_id` の最大値 <= 1000
- [ ] `product_id` の最大値 <= 100
- [ ] `store_id` の最大値 <= 20
- [ ] PK と FK 列に NULL が一切ない

## ヒント

- **FK 範囲を関数引数や別ファイルに散らさない**: スクリプト先頭で定数化する。
  後で 1-2 の products.csv を読み込んで join する 1-5 の改修に効いてくる。
- **`random.Random(seed)` を使う**: モジュールレベル `random.seed()` でも
  動くが、テスト中に他コードが `random` を消費すると再現性が崩れる。
  自分専用 RNG をインスタンス化するのが安全。
- **`Faker.seed_instance(204)`**: Faker は内部に独立 RNG を持つ。
  クラスメソッド `Faker.seed()` ではなくインスタンスメソッド
  `seed_instance()` を使うと、複数 Faker を並走させても互いに干渉しない。
- **`order_date` の生成**: `REFERENCE_DATE = date(2026, 4, 26)` を基準に
  `timedelta(days=rng.randint(0, 364))` を引くと、`datetime.today()` への
  依存を切れる (CI で日付が変わっても byte-identical な CSV になる)。

## 解答例

[`1-4-orders.solution.md`](./1-4-orders.solution.md) を参照。
