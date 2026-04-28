# 1-3: stores 20 行を生成 (`prefecture` は 47 都道府県から抽選)

## シナリオ

店舗マスタを生成する。今回は `prefecture` 列を **47 都道府県の閉じた集合** から抽選する。
重複は許す (= 同じ県に複数店舗がある現実をモデル化)。1-2 の enum と違って値の数が多いが、
"東京" / "東京都" / "Tokyo" のような表記揺れを Python 側で先に殺すことで、後段の地域別マートが
clean な集計になる土台を作る。

## 学べること

- カーディナリティが大きい (47) enum を扱うパターン
- 重複可の抽選 (`random.choices` / `random.choice`) と PK 一意性の両立
- shell_command で「47 都道府県のホワイトリスト外が混ざらない」ことを `grep -v` で検証する書き方
- 既存 `scripts/generate_dummy_data.py` の `PREFECTURES` 定数 (20 県だけ) を **拡張する** という再利用パターンの逆 (= 47 県全列挙)

## 前提

- 1-1 / 1-2 と同様、Python 3.12 + `Faker` + `pandas` が使える
- 出力先 `data/100-knock/topic-1/` (なくてもスクリプト側で作る)

## 入力データ

不要 (この問は学習者が新規生成する)。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_3_stores.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/stores.csv` (ヘッダ込みで 21 行)
- 列: `store_id`, `store_name`, `prefecture`
- `store_id` は 1..20 の連番 (PK)
- `store_name` は `Faker(locale='ja_JP').last_name()` などを使った日本語の店舗名
- `prefecture` は **47 都道府県のいずれか** (重複可)。Python 側で 47 県のリストを全列挙し、`random.choice` で抽選すること
- シードは 42 で固定 (`Faker.seed_instance(42)` + `random.Random(42)`)
- 出力ディレクトリは `mkdir -p` 相当を実施

### Step 2: 実行

```bash
python3 scripts/100-knock/topic-1/generate_1_3_stores.py
```

期待される表示例:

```
Generated data/100-knock/topic-1/stores.csv: 20 rows
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-3-stores.grading.yaml
```

採点には `awk` で `prefecture` 列を抜き出し、47 都道府県以外が含まれていないことを `grep -v` ベースの shell_command で検証するチェックが含まれる。

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_3_stores.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/stores.csv` が 20 データ行 + ヘッダ
- [ ] `store_id` がユニーク、NULL なし
- [ ] `store_name` / `prefecture` も NULL なし
- [ ] `prefecture` 列の全行が 47 都道府県リストに含まれる (= ホワイトリスト外 0 行)

## ヒント (詰まったら)

- 47 都道府県は北から南へ順に並べた `tuple` でモジュール先頭に置く。既存 `scripts/generate_dummy_data.py` には 20 県だけ書いてあるが、**それを参考に残り 27 県を補完する** スタイルで OK
- 20 行しかないので `random.choice(PREFECTURES)` で十分。47 県すべてが出る必要はない (重複前提)
- shell_command 採点は `awk -F, 'NR>1 {print $3}' stores.csv | grep -vxFf <(printf '%s\n' "${PREFECTURES[@]}")` のような bash trick も可だが、もっと素直に **47 県を 1 行に区切った正規表現で alternation する** 方が汎用的
- `expect_stdout_match` は **正規表現マッチ**。「ホワイトリスト外があれば必ずマッチしない」式を書くより、「ホワイトリスト外が 0 個」を `wc -l` で数えて `^0$` を期待する方がシンプル

## 解答例

詳細は [`1-3-stores.solution.md`](1-3-stores.solution.md) を参照。
