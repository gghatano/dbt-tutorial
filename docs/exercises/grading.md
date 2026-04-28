# 採点 CI の使い方

学習者が自分の解答を push すると、GitHub Actions が自動で採点して **OK / NG** を返す仕組み。

---

## 全体像

```text
学習者: feature ブランチで解答コミット → push
             │
             ▼
GitHub Actions (.github/workflows/grade.yml) が起動
  1. Postgres コンテナ起動
  2. schema / role を bootstrap
  3. ダミーデータ生成 + raw 投入
  4. dbt deps + dbt build (MVP 部分が成立する前提を担保)
  5. python scripts/grader/grade.py --exercise NN を実行
             │
             ▼
採点結果:
  - GitHub Actions のジョブ Summary に markdown 表示
  - PR の場合は PR コメントとして投稿
  - exit code 0 (OK) / 1 (NG) で job の成否が決まる
```

---

## 学習者の使い方

### 1. ブランチ命名で対象 Exercise を指定

ブランチ名に `exercise-NN` を含める:

```bash
git checkout -b exercise-06-my-attempt
# ... dbt/models/exposures/exposures.yml などを編集 ...
git add .
git commit -m "Exercise 06: my first attempt"
git push origin exercise-06-my-attempt
```

PR の場合、PR タイトルに `exercise-NN` を含めても同じ。Workflow の入力 `exercise` で手動指定もできる (`workflow_dispatch`)。

### 2. 採点結果の見方

GitHub Actions の Summary または PR コメントに次のような表が出る:

```markdown
## Grading Result: OK (95%)

**Exercise**: 06-exposures-and-docs — Exercise 06: BI を dbt の lineage に組み込む
**Score**: 95 / 100 (passing >= 80%)
**Verdict**: **PASS**

| | Check | Score | Note |
|---|---|---|---|
| OK | `parse-success` — dbt parse が成功する | 15/15 | ok |
| OK | `exposure-file-exists` — exposures.yml が存在する | 10/10 | file exists |
| OK | `exposure-declared` — manifest 登録 | 20/20 | node found |
| NG | `exposure-depends-on-3-marts` — 3 mart 依存 | 0/30 | upstream count 2 < required 3 |
| OK | `docs-generate-success` — dbt docs generate OK | 25/25 | ok |
```

**[NG]** が出た check は `Note` 列に理由が出る。詳細はジョブログの `<details>` ブロックに。

### 3. ローカルで先に試す

CI を回す前にローカルでも回せる:

```bash
# 1. .env を流し込む
set -a; source .env; set +a

# 2. ダミーデータ + 投入 + dbt build (まだなら)
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py
cd dbt && ../.venv/bin/dbt deps --profiles-dir . && ../.venv/bin/dbt build --profiles-dir .
cd ..

# 3. 学習者の解答を編集 (例: dbt/models/exposures/exposures.yml)

# 4. 採点
.venv/bin/python scripts/grader/grade.py --exercise 06
```

PyYAML が必要: `uv pip install pyyaml`。

---

## Exercise を採点対象にする (出題者向け)

新しい Exercise (例: `NN-foo`) に採点 CI を効かせるには、`docs/exercises/NN-foo.grading.yaml` を作る:

```yaml
exercise: NN-foo
title: "Exercise NN: 何々を学ぶ"
passing_score: 80   # 0-100. 合格しきい値

checks:
  - id: <ユニーク ID>
    description: <何を確認するか>
    type: <check 種別>
    points: 20
    # ... type 固有の params
```

### check 種別 (現状 7 種)

| type | 用途 | 主な params |
|---|---|---|
| `dbt_command` | `dbt parse` / `dbt docs generate` などコマンドの成否 | `command:` (list) |
| `manifest_node_exists` | `target/manifest.json` に node が登録されているか | `node:` (e.g. `model.local_analytics.mart_foo`) |
| `manifest_lineage` | depends_on の数・必須上流 | `node:`, `upstream_min_count:`, `upstream_must_include:` |
| `manifest_config` | model config の値 (例: `materialized: incremental`, `contract.enforced: true`) | `node:`, `expected:` (dict, dotted key OK) |
| `dbt_test_passes` | `dbt test --select <selector>` が PASS | `select:`, `min_pass:` |
| `sql_assert` | psql でクエリ実行、結果と比較 | `sql:`, `op:` (eq/ne/gte/gt/lte/lt/in/between), `expected:` |
| `file_exists` | リポジトリ内の任意パス存在チェック | `path:` |

### 設計指針

- **構造チェック (manifest 系)** は DB 不要で速い。「宣言が書かれているか」を見る → 序盤の点
- **データチェック (sql_assert / dbt_test_passes)** は DB が要る。「宣言が実データを正しく扱っているか」を見る → 後半の点
- **passing_score = 80** が標準。低めにするほど学習者に優しい (= 部分点で合格)
- 各 check の **description** は学習者がそのまま読む。「何を確認するか」を簡潔に

### サンプル (Ex.06)

`docs/exercises/06-exposures-and-docs.grading.yaml` を参照。

---

## ローカル CI と本物 CI の差

| | ローカル grader | GitHub Actions |
|---|---|---|
| Postgres | 既存 docker compose の Postgres | service container として新規起動 |
| schema bootstrap | Terraform | `scripts/ci/bootstrap_schemas.sql` (軽量版) |
| dbt build | 学習者が事前に通しておく | CI が毎回フルで通す |
| 結果 | stdout のみ | Summary + PR comment + job 成否 |

---

## トラブルシュート

### `error: no grading.yaml matched: 06`

`docs/exercises/06-*.grading.yaml` が存在しない。新規問題なら作る、既存問題なら命名を確認 (`grading.yaml` の前が `.` で始まる必要がある)。

### `manifest.json not found`

`dbt parse` または `dbt docs generate` が走っていない。CI では `dbt build` ステップの後に grader を呼ぶので、その前で失敗していないか確認。

### `psycopg not installed` (sql_assert で)

`uv pip install -r requirements.txt` 後に `psycopg[binary]` が入っているはず。CI で出る場合は wheel ビルド失敗が疑わしい。

### grader が常に PASS を返す

YAML の `points:` が 0 になっていないか。`points` 合計が 0 だと total が 0/0 で 100% 計算になる (TODO: 0 除算ガード強化)。

### CI が exercise を検出できない

ブランチ名 / PR タイトルに `exercise-NN` を含める。または手動 `workflow_dispatch` で `exercise` 入力を指定。
