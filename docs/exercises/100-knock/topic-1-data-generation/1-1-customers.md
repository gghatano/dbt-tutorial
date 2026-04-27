# 1-1: customers 1,000 行を生成

## シナリオ

新しい分析基盤の最初の一歩として、顧客マスタのダミーデータを Python で「宣言的に」作る。
PK が 1..1000 の連番、シードを固定して再現性を確保することで、後続の `source.yml` / `schema.yml`
で書く `not_null` / `unique` テストが空虚な保証ではなく **実データに裏付けられた契約** になる土台を作る。

## 学べること

- `Faker.seed_instance()` と `random.Random(seed)` による再現性のある生成
- PK を `range(1, N+1)` で発番する「データ仕様としてのコード」
- pandas で CSV を書き出すときの列順固定 (`columns=[...]`) の意義
- `Faker(locale='ja_JP')` で日本語名 + 日本ぽいメールアドレスを得る

## 前提

- main HEAD の MVP がローカルで動いている
- `requirements.txt` から `Faker` / `pandas` がインストール済み (`.venv/bin/python -c "import faker, pandas"` が通る)
- 出力先 `data/100-knock/topic-1/` は存在しなくてよい (スクリプトが `mkdir -p` する)

## 入力データ

不要 (この問は学習者が新規生成する)。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_1_customers.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/customers.csv` (ヘッダ込みで 1001 行)
- 列: `customer_id`, `customer_name`, `email`, `created_at`
- `customer_id` は 1..1000 の連番 (PK)
- `customer_name` は `Faker(locale='ja_JP').name()` で生成
- `email` は `Faker.unique.email()` で全行ユニーク (NULL 不可)
- `created_at` は ISO 8601 (`YYYY-MM-DD`) の文字列、過去 730 日内のいずれか
- **シードは 42 で固定** (`Faker.seed_instance(42)` + `random.Random(42)`)。再実行で同一バイト列が出ること
- 出力ディレクトリは `pathlib.Path.mkdir(parents=True, exist_ok=True)` で先に作る

### Step 2: 実行

```bash
python3 scripts/100-knock/topic-1/generate_1_1_customers.py
```

期待される表示例:

```
Generated data/100-knock/topic-1/customers.csv: 1000 rows
```

`wc -l data/100-knock/topic-1/customers.csv` が `1001` (ヘッダ + 1000) になることを目視確認。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-1-customers.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_1_customers.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/customers.csv` が 1000 データ行 + ヘッダ
- [ ] `customer_id` がユニーク、NULL なし
- [ ] `customer_name` / `email` も NULL なし
- [ ] 2 回実行しても CSV のバイト列が変わらない (シード固定の動作確認)

## ヒント (詰まったら)

- `Faker.seed(42)` (クラスメソッド) と `Faker.seed_instance(42)` (インスタンスメソッド) は別物。**インスタンスごとの再現性** が欲しいので後者を使う
- `Faker.unique.email()` は内部に重複追跡セットを持っていて、1000 件くらいなら衝突なく回せる。万一 `UniquenessException` が出たら seed や生成数を見直す
- pandas の `to_csv(index=False)` を忘れると先頭に index 列が混入して列数が増える
- 日付は `datetime.date(2026, 4, 26) - timedelta(days=rng.randint(0, 730))` のように **基準日を固定** すると、実行日に依存せず冪等になる

## 解答例

詳細は [`1-1-customers.solution.md`](1-1-customers.solution.md) を参照。
