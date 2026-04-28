# 1-8: comment 列に約 10% NULL を混ぜる (reviews 想定)

## シナリオ

EC のレビュー機能では「星だけ付けてコメントは書かない」ユーザーが一定数いる。
業務上は当然ありうる挙動なので、`reviews.comment` 列は **NULL を許す** のが正解。

ところが「全列に `not_null` を付けると安心」という思い込みで `comment` にも `not_null` を
付けると、本物のデータが流れた瞬間に `dbt test` が大量に落ちる。これは「テストが厳しすぎる」
という典型的な学習者ミス。

ここでは `reviews.csv` を **約 10% の comment が NULL** な状態で生成し、後の
`schema.yml` で **`comment` には敢えて `not_null` を付けない** という判断につながる素材を作る。

## 学べること

- NULL 許容列を Python 側で **意図的に作る** (= 仕様としての NULL)
- pandas で `None` を `to_csv` すると CSV では空文字 (`,,`) として書かれる挙動
- `not_null` テストを「全列に付けるべきか？」を実データから判断する感覚
- `Faker(locale='ja_JP').text(max_nb_chars=...)` で自然な日本語コメントを生成する書き方

## 前提

- 1-1 (customers.csv 1000 行) と 1-2 (products.csv 100 行) が既に走っていること
  - reviews.customer_id / product_id の参照範囲はそれぞれ 1..1000 / 1..100
- `requirements.txt` の `Faker` / `pandas` がインストール済み
- 出力先 `data/100-knock/topic-1/` は既に存在する想定 (1-1 で作られている)

## 入力データ

不要 (この問は新規生成)。FK の参照先は customers/products の **ID 範囲** だけを参照する。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_8_nullable_comments.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/reviews.csv` (2000 行 + ヘッダ)
- 列: `review_id, customer_id, product_id, rating, comment, posted_at`
  - `review_id`: 1..2000 の連番 (PK)
  - `customer_id`: 1..1000 の抽選 (`raw.customers` への FK)
  - `product_id`: 1..100 の抽選 (`raw.products` への FK)
  - `rating`: 1..5 の整数
  - `comment`: 約 **10%** が NULL、残り 90% は `Faker(locale='ja_JP').text(max_nb_chars=80)`
  - `posted_at`: ISO 8601 タイムスタンプ (`YYYY-MM-DDTHH:MM:SS`)、過去 200 日分くらいに分散
- **シードは 208 で固定**
- 列順は `columns=[...]` で固定
- pandas で `None` を入れて `to_csv` すれば CSV 上は空文字 (`,,`) になる

### Step 2: 実行 + 確認

```bash
python3 scripts/100-knock/topic-1/generate_1_8_nullable_comments.py
```

期待表示例:

```
Generated data/100-knock/topic-1/reviews.csv: 2000 rows
comment NULL ratio: 10.3% (206 / 2000)
```

NULL 比率を目視:

```bash
awk -F, 'NR>1 {if ($5 == "") n++; t++} END {printf "null=%d total=%d ratio=%.1f%%\n", n, t, n/t*100}' \
  data/100-knock/topic-1/reviews.csv
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-8-nullable-comments.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_8_nullable_comments.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/reviews.csv` が 2000 データ行 + ヘッダ
- [ ] `review_id` がユニーク
- [ ] `review_id`, `customer_id`, `product_id`, `rating`, `posted_at` に NULL なし
- [ ] `comment` 列の NULL 比率が 10% ± 3% (= 7〜13%)

## ヒント (詰まったら)

- 「約 10% NULL」は `if rng.random() < 0.10: comment = None` の素直な分岐で実装できる
- pandas は `None` / `np.nan` を `to_csv` するとデフォルトで空文字を書き出す。逆に `na_rep="NULL"` で
  リテラル `NULL` を書くこともできるが、Postgres COPY のデフォルト挙動と整合させるなら **空文字のまま** が正解
- `Faker(locale='ja_JP').text(max_nb_chars=80)` は文末に句点、改行混じりのこともある。CSV に
  改行が混じると後続の `wc -l` が狂うので、`comment.replace("\n", " ")` で改行除去しておくと安全
- comment 列に **絶対** `expect_no_nulls: [comment]` を付けない。付けると 1-8 の **意図そのもの**
  に違反することになる (= 「NULL を許す列を作る」が課題なのに、テストで NULL を禁止してしまう)

## 設計メモ: なぜ comment に no_nulls を付けないか

採点 YAML の `csv_assert.expect_no_nulls` には `review_id, customer_id, product_id, rating, posted_at` の
5 列だけを並べ、**`comment` は意図的に外す**。これは「NULL 許容列をテストでも NULL 許容として扱う」
という設計判断そのものを採点項目化している。学習者が `expect_no_nulls` に `comment` を入れると、
その時点で「ビジネス仕様 (10% NULL) と検査 (NULL 禁止) が矛盾している」状態が生まれる。
本問は **付けない判断** が正解の学習素材。

## 解答例

詳細は [`1-8-nullable-comments.solution.md`](1-8-nullable-comments.solution.md) を参照。
