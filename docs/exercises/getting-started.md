# 問題で学ぶ dbt — 入口

このリポジトリは「ガイド付きチュートリアルを順に追う」のではなく、**用意された問題を自分で解いて push すると CI が OK / NG を返す** スタイルで dbt を学ぶ。本ドキュメントが学習者の入口。

---

## 1. ゴール

- raw → staging → intermediate → marts の 4 層を、自分の手で書いて完成させられる
- dbt の主要機能 (source / model / test / seed / snapshot / incremental / exposure / hook / package) を最低 1 回ずつ触る
- 自分の解答が「動く」だけでなく「採点を通る」ことを CI で機械的に確認する

ガイド形式の "tutorial" は意図的に置いていない。詰まったら問題ごとの **ヒント** → **解答例** の順に開く。

---

## 2. 必要なセットアップ (1 回だけ)

ルート [README §クイックスタート](../../README.md#クイックスタート) に従って、

- Docker daemon が起動している
- `terraform apply` で schema / role が作成済み
- `.venv/` が出来て `.env` がコピー済み
- `dbt run` / `dbt test` が一度通っている

の状態にしておく。OS 別の手順は [`docs/setup.md`](../setup.md) を参照。

---

## 3. 問題マップ

| カテゴリ | 場所 | ボリューム | 推奨着手順 |
|---|---|---|---|
| **基本 10 問** | [`docs/exercises/README.md`](README.md) | 30〜60 分 × 10 | 01 → 10 (前提依存欄を確認) |
| **100 本ノック** | [`docs/exercises/100-knock/README.md`](100-knock/README.md) | 各 5〜15 分 × 100 | トピック ① から順番に |

100 本ノックも提出手順は本ドキュメントと同じ(ブランチ命名と問題 ID だけ変わる)。

---

## 4. 提出手順 (end-to-end)

Exercise 06 を解く例で、「ブランチ作成 → ローカル確認 → push → CI 採点」を 1 周通す。

### 4-1. 問題用ブランチを切る

```bash
# cwd: ~/repo
git checkout main && git pull --ff-only
git checkout -b exercise-06-my-attempt
```

> ⚠️ ブランチ名に **`exercise-NN`** が含まれていることが必須。CI (`.github/workflows/grade.yml`) はこれを正規表現で拾って、対象問題を特定する。100 本ノックは `exercise-NN-MM` 形式 (例: `exercise-05-06-my-attempt` で「Topic 5 の Q6」) だが、**実装側は `NN` 部分しか見ない** ので、PR タイトルや手動 dispatch で具体的な YAML パスを渡してもよい。詳細は [`grading.md`](grading.md)。

### 4-2. 解答を書く

問題 md の **Step** に沿って、`dbt/models/exercises/06/`(または問題が指定するパス)配下にファイルを足す。MVP の既存ファイルは触らない。

```bash
# 例: Exercise 06 は dbt/models/exposures/exposures.yml を作る
mkdir -p dbt/models/exposures
$EDITOR dbt/models/exposures/exposures.yml
```

### 4-3. ローカルで採点を回す

push する前に手元で同じ採点ロジックを回せる。

```bash
# cwd: ~/repo
# 一度だけ
uv pip install pyyaml

# 環境変数を流し込む (shell に DB_USER 等が残っていると .env が無視されるので、新しい shell を開くか unset)
unset DB_USER DB_PASSWORD METABASE_DB_RO_PASSWORD METABASE_ADMIN_PASSWORD 2>/dev/null
set -a; source .env; set +a

# 解答が動く前提を整える (まだなら)
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py
cd dbt && ../.venv/bin/dbt deps --profiles-dir . && ../.venv/bin/dbt build --profiles-dir .
cd ..

# 採点
.venv/bin/python scripts/grader/grade.py --exercise 06
```

stdout に `## Grading Result: OK (95%)` のような表が出れば手元では合格。CI はこれと同じ grader を使うので、ローカル OK ≒ CI OK と思って良い。

### 4-4. コミット → push

```bash
git add dbt/models/exposures/exposures.yml
git commit -m "Exercise 06: declare sales_overview exposure"
git push -u origin exercise-06-my-attempt
```

### 4-5. CI の結果を見る

- push の数十秒後に GitHub Actions が起動する。Actions タブから対象 run を開き、**Job summary** に採点結果の markdown 表が出る。
- PR を作っている場合は、同じ採点結果が PR コメントとして自動投稿される。
- ジョブ全体の成否 (✅ / ❌) は `passing_score` を満たしたかで決まる(満たさないと job が `exit 1` で落ちる)。

---

## 5. 採点ルール (要約)

- 各問題に `docs/exercises/NN-*.grading.yaml` が紐づき、複数の **check** に分割されている
- 例: `parse-success` (15 点) / `manifest_node_exists` (20 点) / `sql_assert` (30 点) … の合計 100 点
- 既定の合格ライン (`passing_score`) は **80 点**
- check の type 一覧と意味 (例: `dbt_command`, `manifest_lineage`, `sql_assert`, `csv_assert`) は [`grading.md` §check 種別](grading.md#check-種別-現状-9-種) を参照

---

## 6. 詰まったとき

| 症状 | 最初に見る場所 |
|---|---|
| 解答方針が分からない | 問題 md 末尾の **ヒント** セクション |
| ヒントを読んでも進まない | `docs/exercises/solutions/NN-*.solution.md`(完成形 + 解説) |
| 採点エラー (`error: no grading.yaml matched: NN`) | [`grading.md` §トラブルシュート](grading.md#トラブルシュート) |
| ローカルで `manifest.json not found` | `dbt build` を先に通す。一度通ったあとは `dbt parse` で十分 |
| `permission denied for table mart_*`(Metabase) | [`troubleshooting.md`](../troubleshooting.md#metabase-で-permission-denied-for-table-mart_) |

---

## 7. 提出後のリセット

問題用 model は MVP に影響しないよう `dbt/models/exercises/<NN>/` 配下に置く運用。学習が一区切りしたら、

```bash
rm -rf dbt/models/exercises/<NN>/
docker exec local-data-postgres psql -U analytics_user -d analytics -c \
  "DROP TABLE IF EXISTS raw.<exercise_table> CASCADE;"  # 必要なら
```

で MVP 状態に戻せる。問題ごとの後始末は問題 md 末尾を参照。
