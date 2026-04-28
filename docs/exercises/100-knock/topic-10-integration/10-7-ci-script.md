# 10-7: CI 想定 1 行コマンドを scripts/100-knock/topic-10/ci/dbt_check.sh にまとめる

## シナリオ

10-1〜10-6 で `要件 → ER → source → staging → mart → exposure` の DAG が完成した。

ところが、PR ごとの CI で「**何を build すれば壊れた箇所だけ最小コストで再検証できるか**」 はまだ言語化されていない。dbt は強力な selector (`state:modified+`, `--defer`, `--state`) を持っているが、毎回 PR で「どれを build したっけ」を考えていると CI が遅く / 抜けが出る。

本問では、`dbt deps && dbt source freshness && dbt build --select state:modified+ --defer --state ./prod-manifest/` を **1 つのシェルスクリプト** にまとめる。これにより:

- **新人エンジニアが CI に何を入れるか迷わない** — `bash scripts/100-knock/topic-10/ci/dbt_check.sh` を呼ぶだけ
- **CI 設定 (`.github/workflows/*.yml`) と dbt コマンドの責務分離** — workflow は「いつ呼ぶか」、script は「何を呼ぶか」
- **ローカル dry-run も同じ script で再現可能** — 手元で `bash dbt_check.sh` を回せば CI と同じことが起きる

これが「CI を 1 行にまとめる」の本質。コマンドの暗黙知を script という宣言に昇華する。

## 学べること

- `dbt deps` → `dbt source freshness` → `dbt build` の **CI における正しい順序**
- `--select state:modified+` で「変更 model + その下流」だけを build する仕組み
- `--defer --state ./prod-manifest/` で「変更されてない上流は本番 manifest を参照」する高速化
- シェルスクリプトの基本ガード (`set -euo pipefail`)
- `bash -n` で構文チェックだけする (実行せず CI で構文エラーを早期検知)
- prod-manifest を空ディレクトリで OK とする学習用簡易セットアップ

## 前提

- 10-6 完了 (exposures.yml が存在し、`+exposure:` selector で起点 build が回る)
- 学習者は `scripts/100-knock/topic-10/ci/` ディレクトリを作成可能 (本問で作る)
- prod-manifest は本問では空ディレクトリで OK (defer の効果は出ないが、構文チェックは通る)

## 入力データ

なし。

## 課題

### Step 1: ディレクトリ作成

```bash
mkdir -p scripts/100-knock/topic-10/ci
mkdir -p prod-manifest   # 空ディレクトリ。本来は本番 dbt run の manifest.json を置く
```

### Step 2: scripts/100-knock/topic-10/ci/dbt_check.sh を作る

要件:

- `#!/usr/bin/env bash` shebang
- `set -euo pipefail` でエラー時即停止
- 以下 3 コマンドを順序実行:
  1. `dbt deps` — packages.yml を解決 (毎回必要、idempotent)
  2. `dbt source freshness` — raw が古くないか確認 (warn だけなら継続)
  3. `dbt build --select state:modified+ --defer --state ./prod-manifest/` — 変更箇所と下流だけ build
- `--profiles-dir .` を渡す (CI 環境想定)
- `cd dbt` で dbt プロジェクトに移動してから実行
- 各ステップ前に `echo "==> step name"` で進捗表示
- 失敗時の終了コードをそのまま伝搬

### Step 3: 実行可能にする

```bash
chmod +x scripts/100-knock/topic-10/ci/dbt_check.sh
```

### Step 4: 構文チェック (ローカル)

```bash
bash -n scripts/100-knock/topic-10/ci/dbt_check.sh && echo "syntax ok"
```

### Step 5: 必要なら実行 (任意)

```bash
set -a; source .env; set +a
bash scripts/100-knock/topic-10/ci/dbt_check.sh
```

`prod-manifest` が空のため `--state` の defer 効果は出ないが、`dbt build` 自体は state:modified+ で「git diff で変わった model + 下流」を回す。Topic ⑩ までの全 model が build されることがある (defer の真価は本番 manifest を置いてから)。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-10-integration/10-7-ci-script.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-10/ci/dbt_check.sh` が存在する
- [ ] `bash -n` で構文チェックが通る
- [ ] script 内に `dbt deps` / `dbt source freshness` / `dbt build` の 3 キーワードが含まれる
- [ ] `--select state:modified+` `--defer` `--state` のフラグがある
- [ ] `set -euo pipefail` ガードがある
- [ ] (任意) script を実行して exit 0 になる、または非ゼロでも DAG レベルの理由 (rich error)

## ヒント (詰まったら)

- **なぜ `set -euo pipefail`?**:
  - `-e`: コマンド失敗で即終了 (エラー隠蔽防止)
  - `-u`: 未定義変数アクセスで失敗 (typo 防止)
  - `-o pipefail`: パイプの途中失敗でも全体を失敗扱い (`a | b` で a が失敗しても b の exit code だけ見る default 挙動を矯正)
  - CI スクリプトの最初の 1 行に必ず入れる慣習
- **なぜ `dbt deps` が最初?**: `dbt build` は packages を解決済み前提。CI は毎回 fresh checkout なので `dbt_packages/` が空。`dbt deps` を必ず最初に走らせる。idempotent なので何度呼んでも安全。
- **なぜ `dbt source freshness` を `dbt build` の前?**: 「raw が古い」が原因の build 失敗を、build 中ではなく **source freshness 段階で先に検出** する。CI の失敗ログが「source が古い」だけになり、原因究明が早い。`source freshness` が warn (= raw 古い、でもまだ動く) なら build に進む、error (= raw 致命的に古い) なら build 中止という運用も可能 (本問では warn / error 両方とも build に進む簡易版)。
- **`--select state:modified+`**: 「manifest が変わった model + その下流 (`+`)」を build。プレフィックスの `+` は上流、サフィックスの `+` は下流。CI では「変えた箇所 → 下流の影響」を見たいので **suffix `+`**。
- **`--defer --state ./prod-manifest/`**: 「`state:modified+` で選ばれなかった上流 model は本番 (`./prod-manifest/`) のものを参照する」。CI で staging だけ変えた PR で、mart は build 不要、ただし `ref()` 解決時には mart が「本番 schema にあるもの」として扱われる → 速い。
- **prod-manifest を空ディレクトリで OK な理由**: 学習段階では本番環境がないので `--state` の defer 効果は出ない。これは仕方ない。本番運用では nightly job が `target/manifest.json` を `./prod-manifest/` に push する pipeline が必要。本問ではコマンドの**書式**を学ぶことが目的。
- **`bash -n` の意義**: 構文チェックだけ (実行しない)。CI で「コマンド書式エラー」を早期に検知できる。`shellcheck` を入れればさらに静的解析できるが、本問では `bash -n` で十分。
- **`#!/usr/bin/env bash` vs `#!/bin/bash`**: 前者は PATH から bash を探す → macOS / Linux 両対応。後者は固定パス → macOS の古い bash (3.2) を引きがち。CI スクリプトは前者推奨。

## 解答例

詳細は [`10-7-ci-script.solution.md`](10-7-ci-script.solution.md) を参照。
