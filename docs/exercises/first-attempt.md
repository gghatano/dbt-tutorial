# 最初の 1 問を解いてみる

「練習問題を一通り眺めたが、どこから手を付ければいいか分からない」人向けの最短スタート手順。
[getting-started.md](getting-started.md) が提出フローの全体像、本ドキュメントは **「最初の 1 問」を選び、実際に手を動かし始めるところまで** を切り出した実践版。

---

## 1. 最初に解く問題: Exercise 01 (顧客レビューの取り込み)

| 項目 | 値 |
|---|---|
| 問題 md | [`01-ingest-reviews.md`](01-ingest-reviews.md) |
| 前提依存 | なし |
| 目安時間 | 30 分 |
| 触る機能 | CSV → raw、`source` 追加、staging、built-in tests (`not_null` / `unique` / `accepted_values` / `relationships`) |

なぜ 01 から:

- 前提依存がない (他の問題を先に解いている必要がない)
- raw → staging の最小一周で、dbt の中心概念 (source / model / test) を 1 問で全部触れる
- 採点項目が比較的素直 (`manifest_node_exists` / `dbt_test_passes` / `csv_assert` 中心)

---

## 2. 取りかかり手順

### 2-1. 問題用ブランチを切る

```bash
# cwd: ~/repo
git checkout main && git pull --ff-only
git checkout -b exercise-01-my-attempt
```

> ⚠️ ブランチ名に **`exercise-01`** が含まれていることが必須。CI (`.github/workflows/grade.yml`) はブランチ名から問題 ID を拾う。

### 2-2. 問題本文を読む

```bash
$EDITOR docs/exercises/01-ingest-reviews.md
```

「## 課題」配下の Step 1〜6 が実装する手順、「## 完了条件」が成果物のチェックリスト。

### 2-3. 入力 CSV を生成する

```bash
.venv/bin/python scripts/exercises/generate_01_reviews.py
# => data/exercises/inbox/reviews.csv (2,000 行 + ヘッダ)
```

`data/exercises/inbox/` は `.gitignore` 済み (再生成可能)。

---

## 3. 書く対象 (このスコープに留める)

問題 md の Step に沿って、以下のファイルを **新しく作る**。MVP の既存ファイル (`dbt/models/staging/`, `dbt/models/sources.yml` など) は触らない。

| ファイル | 役割 |
|---|---|
| `data/raw/reviews.csv` への CSV ロードを行う Python (loader) または `psql \copy` | raw.reviews テーブルを 2,000 行で作る |
| `dbt/models/exercises/01/sources.yml` | `name: raw_exercise` で reviews を source 宣言 |
| `dbt/models/exercises/01/stg_reviews.sql` | 型キャスト + `posted_date` 派生列を持つ staging view |
| `dbt/models/exercises/01/schema.yml` | `not_null` / `unique` / `accepted_values` / `relationships` テスト |

詳細な要件は問題 md の Step 2〜5 に書いてある。

---

## 4. ローカルで採点を回す

push する前に手元で同じ採点ロジックを通せる。CI が落ちる前にここで気付くと速い。

```bash
# cwd: ~/repo
# 1) shell に残った export を退避してから .env を流し込む
unset DB_USER DB_PASSWORD METABASE_DB_RO_PASSWORD METABASE_ADMIN_PASSWORD 2>/dev/null
set -a; source .env; set +a

# 2) dbt build (= run + test) で manifest を生成して採点対象を揃える
cd dbt && ../.venv/bin/dbt build --profiles-dir . && cd ..

# 3) 採点
.venv/bin/python scripts/grader/grade.py --exercise 01
```

stdout に `## Grading Result: OK (XX%)` が出れば手元では合格。CI も同じ grader を使うので、ローカル OK ≒ CI OK。

push 〜 CI 結果確認の流れは [getting-started.md §4-4 / §4-5](getting-started.md#4-4-コミット--push) と共通。

---

## 5. 詰まったときの動き方

1. **問題 md 末尾の「ヒント」セクション** を読む (具体的だが完答ではない)
2. それでも進まなければ [`solutions/01-ingest-reviews.solution.md`](solutions/01-ingest-reviews.solution.md) を開く (Step ごとに完成形 SQL + 解説)
3. エラー文字列で詰まった場合は [`docs/troubleshooting.md`](../troubleshooting.md) の逆引き表

サポートを求めるとき (人間や AI に質問するとき) は、

- 何を試したか
- どんなエラー / 出力が出たか
- どの Step で詰まったか

を貼ると、いきなり解答を渡されるのではなく **次の一手のヒント** をもらいやすい。

---

## 6. 1 問解き終わったら

- 02 以降は前提依存 (table の「前提依存」列) を見ながら進める。01 の上に積む問題 (02) もあれば、独立して解ける問題 (03 / 04 / 05 / 07 / 08 / 09) もある。
- 提出後のリセット手順は [getting-started.md §7](getting-started.md#7-提出後のリセット) を参照。
- もっと量をこなしたくなったら [100 本ノック](100-knock/README.md) (10 トピック × 10 問) に進む。手順は同じ。
