# dbt 練習問題セット

`local-data-platform` の MVP（spec §13 完了状態）の上に、**自分で手を動かして dbt の主要機能を一通り触る** ことを目的にした 5 問の練習問題。

## 想定する学習者

- README のクイックスタートを一通り終わらせ、`dbt run` / `dbt test` がローカルで通る状態にできた
- staging / intermediate / marts の 3 層構造をなんとなく理解した
- 「次は何を触ったらいいか」を探している

## 5 問の概要

| #  | タイトル                                  | 学べる主要機能                                                         | 目安  |
|----|-------------------------------------------|--------------------------------------------------------------------------|-------|
| 01 | [顧客レビューの取り込み](01-ingest-reviews.md)               | CSV → raw、source 追加、staging、`accepted_values` / `relationships` テスト | 30 分 |
| 02 | [商品評価マートの作成](02-mart-product-rating.md)           | intermediate、複数 staging の JOIN、集計、しきい値フィルタ          | 30 分 |
| 03 | [新規注文を incremental に取り込む](03-incremental-orders.md) | `materialized: incremental`, `is_incremental()`, `unique_key`, `--full-refresh` | 60 分 |
| 04 | [価格変動を snapshot で履歴化](04-snapshot-product-price.md) | `dbt snapshot`, `check` strategy, SCD Type-2, `valid_from` / `valid_to` | 60 分 |
| 05 | [都道府県マスタを seed 化、共通 macro 作成](05-seeds-and-macros.md) | `dbt seed`, jinja macro, `ref()` vs `source()`, DRY    | 45 分 |

## 進め方

1. 各問題は `docs/exercises/0N-*.md` を読み、書かれている **Step** に沿って自分で SQL / Python を書く
2. **書く対象の SQL（dbt model）は `dbt/models/exercises/<NN>/` 配下** に置くことを推奨。MVP 既存ファイルは触らない
   - 例: `dbt/models/exercises/01/stg_reviews.sql`、`dbt/models/exercises/01/schema.yml`
3. 詰まったら問題文末尾の **「ヒント」** を読む
4. それでもダメなら `solutions/` 配下の解答例を参照

`dbt/models/exercises/` ディレクトリは MVP には存在しないので、自分で `mkdir -p dbt/models/exercises/01` を実行して作成する。

> **NOTE**: 練習問題用の dbt model はリポジトリにコミットしない前提（学習者ごとに書く）。`.gitignore` には追加していないが、git に上げない運用を推奨する。

## 前提

- spec §13 完了状態（`dbt run` / `dbt test` が成功する）
- `.venv/` セットアップ済み、`.env` で DB 接続情報が読める
- `set -a; source .env; set +a` で env を流し込んでから dbt を叩く運用に慣れている

## 練習用 CSV の生成場所

各 Exercise の生成スクリプトは `scripts/exercises/` に置いてある。出力は `data/exercises/inbox/` に書かれ、ここは `.gitignore` 済み（`*.csv` は再生成可能）。

## ヒント / 解答の見方

- **ヒント**: 各問題文末尾の `## ヒント` セクションを読む。具体的だが完全な答えは書いていない
- **解答例**: 各問題文末尾の `## 解答例` リンクから `solutions/` 配下の `*.solution.md` を開く。`Step` ごとに完成形 SQL / Python と簡単な解説あり

## 既存 MVP への影響

これらの練習問題は **既存 MVP を一切壊さない** よう設計してある:

- 既存 model / source / test / macro / snapshot へは追記しない
- 練習問題で書く dbt model は `dbt/models/exercises/<NN>/` に閉じ込める
- raw 層に新たに作成するテーブル（reviews, orders_increment, ...）は MVP の `dbt run` 結果に影響しない
- `dbt seed` や `dbt snapshot` で増える成果物も別 schema (`staging` / `snapshots`) に分離

途中で詰まったら、いつでも `dbt/models/exercises/` を丸ごと削除し、自分で書いた generate スクリプトの出力を `rm -rf` すれば MVP の状態に戻る。
