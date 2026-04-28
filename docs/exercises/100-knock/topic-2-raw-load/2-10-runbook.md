# 2-10: 投入スクリプトを `pre-hook` 風に手動順序化 (generate → load → freshness) し runbook 化

## シナリオ

dbt の `pre-hook` / `post-hook` は model 単位で SQL を流す機能だが、「dbt **そのものを** 走らせる前に何を順序通りやるか」は YAML には書けない。これは **runbook (運用手順書)** として人間が読める形で言語化する責務になる。

具体的には「① ダミーデータを generate → ② raw に load → ③ `dbt source freshness` で鮮度を確認 → ④ `dbt build` を走らせる」という Topic ② までの流れを、`runbook.md` 1 ページに固める。これがあると新規メンバが翌週ジョインしても再現できるし、CI の job ステップ設計の元ネタにもなる。

## 学べること

- 「dbt の前に必要な作業」を文章化して再現性を担保する習慣
- 順序依存ステップを **番号付きリスト** で明示する書き方 (Markdown の serial step)
- runbook に必ず含めるべき要素: 前提 / 手順 / 検証 / トラブルシュート
- `dbt source freshness` を `dbt build` の **前段** に置くことで、上流が古いままの build を防ぐ運用設計
- 後の Topic ⑨ (hooks) で扱う `pre-hook` との違い (model 単位 vs 全体ワークフロー)

## 前提

- 2-1 〜 2-9 をすべて完了していると、runbook に書く手順がそのまま動く状態になる
- ローカル Postgres + raw schema が起動している
- `.env` が `.env.example` からコピーされている

## 入力データ

不要 (本問は Markdown の文書作成のみ)。

## 課題

### Step 1: runbook.md を書く

`docs/exercises/100-knock/topic-2-raw-load/runbook.md` を新規作成。最低限以下のセクション構成 + キーワードを含む:

- **# Topic ② Runbook** (見出し)
- **## Prerequisites**: `.env` / `docker compose` / `.venv` の準備
- **## Steps**: 番号付きリスト (1. → 2. → 3. → 4.)
  1. **generate**: ダミーデータ生成 (`generate_dummy_data.py` 系または Topic ① の generator を呼ぶ)
  2. **load**: `raw` schema への投入 (`load_raw_data.py` または Topic ② 2-1 の loader)
  3. **freshness**: `dbt source freshness` で鮮度契約をチェック (build 前)
  4. **build**: `dbt build` で staging 以下を構築
- **## Verification**: 各ステップの成功確認 (psql / dbt ls)
- **## Troubleshooting**: よく出るエラーと対処
- 必須キーワード (採点対象): `generate`, `load`, `freshness`, `dbt build`, `pre-hook` (この語に言及。発展セクションで「dbt の pre-hook とは違う」と一言書く形でよい)

### Step 2: 動作確認 (実機で順番にコマンドを叩いてみる)

書いた runbook の通りに、ローカルで一通りコマンドを叩いて「自分が書いた手順で本当に再現できるか」を確認する。

```bash
# 1. generate
.venv/bin/python scripts/generate_dummy_data.py
# 2. load
.venv/bin/python scripts/load_raw_data.py
# 3. freshness (build より前に)
cd dbt && ../.venv/bin/dbt source freshness --profiles-dir .
# 4. build
../.venv/bin/dbt build --profiles-dir .
```

(Topic ② 2-1 の loader を使うなら 2 のコマンドを差し替え。runbook 内も同じものを書く。)

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-10-runbook.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-2-raw-load/runbook.md` が存在する
- [ ] runbook 内に `generate` の手順が書かれている
- [ ] runbook 内に `load` の手順が書かれている
- [ ] runbook 内に `freshness` の手順が書かれている (= `dbt source freshness` を build の前に置く)
- [ ] runbook 内に `dbt build` の手順が書かれている
- [ ] `pre-hook` の語に言及がある (= dbt の pre-hook と本問の "pre-build runbook" の違いを意識している)

## ヒント (詰まったら)

- **runbook の書き方の鉄則**: 「**コピペで回せる**」状態を目指す。コマンドは fenced code block で囲み、相対パスではなく `cd` から書く。説明文は「なぜそのステップが必要か」を 1 行ずつ添える。
- **順序の意味**: `generate → load → freshness → build` の順序には意味がある:
  1. generate と load は外部世界 (Python) → DB の境界。dbt は無関係。
  2. freshness を build の前に挟むのは「上流が古いままで build しても無駄」を防ぐため。
  3. build は staging → mart まで一気通貫。
- **`pre-hook` との対比**: dbt の `pre-hook` は **model build の直前に SQL を流す** 機能 (例: 一時 GRANT)。本問の runbook は **dbt 全体を走らせる前の人間の手順** であり、別レイヤー。同じ "pre" でも対象スコープが違うことを runbook の最後で 1 行触れておくと、Topic ⑨ (hooks) との繋がりが明確になる。
- **CI 化への伏線**: runbook が書けると、その手順をそのまま `.github/workflows/grade.yml` の `steps:` に写経できる。runbook = 人間用 / CI yaml = 機械用、の対応関係を意識すると、両者を同期させる習慣が身につく。
- **形式自由**: 厳密なテンプレは強制しない。grader は「キーワードが本文に含まれているか」だけを grep でチェックする。読み手に伝わる構成であれば自由に書いてよい。

## 解答例

詳細は [`2-10-runbook.solution.md`](2-10-runbook.solution.md) を参照。
