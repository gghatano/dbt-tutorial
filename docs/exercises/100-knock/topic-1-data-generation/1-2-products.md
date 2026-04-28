# 1-2: products 100 行を生成 (`category` は 5 値の閉じた enum)

## シナリオ

商品マスタを生成する。今回は `category` 列を **5 値の閉じた enum** に縛ることで、後段の
`accepted_values` テストが意味を持つ「契約として有効な enum」をデータ側で先に宣言する。
"電気" や "Electronics_v2" のようなブレが入らないことを Python 側で保証することで、
dbt 側のテストはダミーではなく **実データに裏打ちされた防壁** になる。

## 学べること

- enum 列を Python 定数 (`tuple` / `list`) として宣言し、`random.choice` で抽選するパターン
- なぜ enum 値は **コード内の単一の真実 (single source of truth)** であるべきか
- shell_command チェックで `awk` を使い、CSV の特定列の値域を検証する方法
- 数値列 (`unit_price`) の値レンジを Python の生成ロジック側で固定する意義

## 前提

- 1-1 と同様、Python 3.12 + `Faker` + `pandas` が使える
- 出力先 `data/100-knock/topic-1/` は 1-1 で作られているはず (なくてもスクリプト側で作る)

## 入力データ

不要 (この問は学習者が新規生成する)。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_2_products.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/products.csv` (ヘッダ込みで 101 行)
- 列: `product_id`, `product_name`, `category`, `unit_price`
- `product_id` は 1..100 の連番 (PK)
- `product_name` は `Faker(locale='ja_JP').word()` などで生成 (重複可、空でない文字列)
- `category` は 以下の **5 値からのみ** 抽選:
  - `food`
  - `electronics`
  - `clothing`
  - `home`
  - `sports`
- `unit_price` は 100〜9990 円 の範囲 (10 円単位推奨)
- シードは 42 で固定 (`Faker.seed_instance(42)` + `random.Random(42)`)
- 出力ディレクトリは `mkdir -p` 相当を実施

### Step 2: 実行

```bash
python3 scripts/100-knock/topic-1/generate_1_2_products.py
```

期待される表示例:

```
Generated data/100-knock/topic-1/products.csv: 100 rows
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-2-products.grading.yaml
```

採点には `awk` で `category` 列の distinct 値を取り、5 値のいずれかであることを検証する shell_command チェックが含まれる。

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_2_products.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/products.csv` が 100 データ行 + ヘッダ
- [ ] `product_id` がユニーク、NULL なし
- [ ] `product_name` / `category` / `unit_price` も NULL なし
- [ ] `category` 列の distinct 値が 5 値の部分集合 (= `food/electronics/clothing/home/sports` のみ)

## ヒント (詰まったら)

- enum 値はモジュール先頭に `CATEGORIES = ("food", "electronics", "clothing", "home", "sports")` のように **タプル定数** で置く。タプルは不変なのでうっかり変更を防げる
- `random.choice(CATEGORIES)` で OK。100 件あれば 5 値全てが出現するはず (`random.Random(42)` のシードでは経験的に必ず全て出る)
- `unit_price` を「10 円単位」にしたいなら `rng.randint(10, 999) * 10` のような書き方で 100〜9990 円が綺麗に揃う
- shell_command の `awk` は `awk -F, 'NR>1 {print $3}' products.csv | sort -u` のようにヘッダをスキップする。`expect_stdout_match` は **正規表現マッチ** なので、5 値以外が混じったら確実に落ちる正規表現を組む

## 解答例

詳細は [`1-2-products.solution.md`](1-2-products.solution.md) を参照。
