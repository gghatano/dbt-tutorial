# Topic ① ダミーデータ生成

> **テーマ**: データ仕様を Python で宣言する。dbt は raw より上流を管轄しないが、PK / FK / enum / null 比率 / カーディナリティ を Python 側で **宣言として書き残す** ことで、後続の `source.yml` / `schema.yml` / `relationships` テストが空虚にならない土台を作る。

## このトピックで学ぶこと

- Faker / pandas を「データ仕様の DSL」として使う
- `Faker.seed_instance()` による **再現性のある** ダミーデータ生成
- PK の一意性、FK の参照範囲、enum 値の閉じた集合を **コードで宣言**
- null 比率を意図的に混ぜる (NULL を許す列の宣言)
- 入力の冪等性 (再生成しても同じ結果)
- データ生成スクリプトに自前の "data contract" (行数・列・null 比率) を持たせる

## 前提

- main HEAD の MVP がローカルで動いている
- Python 3.12 + `requirements.txt` インストール済み
- `Faker` + `pandas` が使える状態

## 出力先

学習者が書くスクリプト: `scripts/100-knock/topic-1/generate_1_<NN>_<keyword>.py`
生成 CSV: `data/100-knock/topic-1/*.csv` (gitignored)

## 10 問

| # | 問 | 出力 | 採点 (主な check) |
|---|---|---|---|
| 1-1 | customers 1,000 行を Faker で生成、PK 1..1000 / type-stable seed | `customers.csv` 1000+1 行 | csv_assert (行数 / unique PK) |
| 1-2 | products 100 行、`category` 列は 5 値の enum で固定 | `products.csv` 100+1 行 | csv_assert (行数 / category accepted_values) |
| 1-3 | stores 20 行、`prefecture` 列を都道府県 47 個から抽選 | `stores.csv` 20+1 行 | csv_assert (行数 / prefecture in 47-set) |
| 1-4 | orders 10,000 行、FK 範囲を Python 側で先に宣言 | `orders.csv` 10000+1 行 | csv_assert + shell_command (FK 整合性 SQL チェック) |
| 1-5 | `orders.unit_price` は `product_id` から決定論的に算出 (同 product 同単価) | 1-4 と同 CSV を再生成 | shell_command (`product_id × unit_price` の関数性検証) |
| 1-6 | `customer_id` のうち 1% を `orders` に登場させない (休眠顧客) | 1-4 と同 CSV を再生成 | shell_command (orders に出ない customer 数を検証) |
| 1-7 | `orders.order_date` を 2025-01-01 〜 2026-04-30 の範囲で分散 | 1-4 と同 CSV を再生成 | csv_assert + shell_command (date 範囲) |
| 1-8 | `comment` 列に約 10% NULL を混ぜる (reviews 想定) | `reviews.csv` 2000+1 行 | csv_assert (行数 / comment null 率 ~10%) |
| 1-9 | 生成スクリプトに `--rows` / `--date` 引数を追加、複数日分を冪等に | スクリプト改修 | shell_command (2 回呼んで同一出力) |
| 1-10 | 生成データの行数・列・null 比率を `_stats.json` に書き出す | `_stats.json` | file_exists + csv_assert (生成された stats の値域) |

## 採点

各問の `1-N-<keyword>.grading.yaml` を grader が読む。CI でブランチ名に `exercise-100-knock-1-N` を含めて push すると自動採点。

ローカルなら:

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-3-stores.grading.yaml
```
