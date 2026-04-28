# 10-7 解答例

## scripts/100-knock/topic-10/ci/dbt_check.sh

```bash
#!/usr/bin/env bash
# 100-knock Topic 10-7: CI 1 行コマンド (deps + freshness + state-modified build)
#
# 使い方 (CI 想定):
#   bash scripts/100-knock/topic-10/ci/dbt_check.sh
#
# 前提:
#   - .env が source 済み (DB 接続情報)
#   - prod-manifest/ ディレクトリが存在 (空でも可、本番環境では target/manifest.json を置く)
#
# このスクリプトの責務:
#   1. dbt deps        - packages.yml を解決
#   2. dbt source freshness - raw データの鮮度確認
#   3. dbt build --select state:modified+ --defer --state ./prod-manifest/
#                      - 変更箇所と下流だけを高速 build (上流は本番参照)

set -euo pipefail

PROJECT_DIR="dbt"
PROFILES_DIR="."        # dbt ディレクトリからの相対 (cd 後)
STATE_DIR="../prod-manifest"   # repo root からの相対を dbt cwd に合わせて変換

cd "${PROJECT_DIR}"

echo "==> [1/3] dbt deps"
dbt deps --profiles-dir "${PROFILES_DIR}"

echo "==> [2/3] dbt source freshness"
# freshness は warn でも継続 (error なら set -e で停止)
dbt source freshness --profiles-dir "${PROFILES_DIR}" || {
  rc=$?
  # freshness の exit code: 0=PASS, 1=ERROR (致命的), 2=WARN (継続可)
  if [ "${rc}" -eq 2 ]; then
    echo "WARN: source freshness reported warnings, continuing..."
  else
    echo "ERROR: source freshness failed with exit code ${rc}"
    exit "${rc}"
  fi
}

echo "==> [3/3] dbt build --select state:modified+ --defer --state ${STATE_DIR}"
if [ -f "${STATE_DIR}/manifest.json" ]; then
  dbt build \
    --profiles-dir "${PROFILES_DIR}" \
    --select state:modified+ \
    --defer \
    --state "${STATE_DIR}"
else
  echo "WARN: ${STATE_DIR}/manifest.json not found - falling back to full build"
  dbt build --profiles-dir "${PROFILES_DIR}"
fi

echo "==> All checks PASSED"
```

**ポイント**:

- **`set -euo pipefail`**: 4 つのガードを 1 行で。CI スクリプトの最初の 1 行に必ず入れる
- **`PROJECT_DIR="dbt"` の変数化**: 後で repo 構成が変わっても 1 箇所修正で済む
- **`STATE_DIR="../prod-manifest"`**: `cd dbt` 後の相対パスに変換。学習者が混乱しがちな部分
- **`dbt source freshness` の exit code 分岐**: dbt の freshness は `0=PASS / 1=ERROR / 2=WARN` の 3 値。WARN は build に進む、ERROR は止める、という運用契約をスクリプトに刻む
- **prod-manifest 不在時の fallback**: `manifest.json` がなければ defer できないので full build。学習段階では空ディレクトリのことが多いのでこのガードがあると親切
- **進捗 echo**: `[1/3]` `[2/3]` `[3/3]` で CI ログ上で見やすく

## 実行例

### 構文チェック

```bash
$ bash -n scripts/100-knock/topic-10/ci/dbt_check.sh
$ echo $?
0
```

### 実際の実行 (prod-manifest なし)

```bash
$ set -a; source .env; set +a
$ bash scripts/100-knock/topic-10/ci/dbt_check.sh
==> [1/3] dbt deps
04:00:00  Running with dbt=1.11.x
04:00:00  Updating lock file in file path: ...
04:00:01  Installing dbt-labs/dbt_utils
04:00:01    Installed from version 1.x.x

==> [2/3] dbt source freshness
04:00:02  Running with dbt=1.11.x
04:00:03  Found N sources, ...
04:00:04  PASS freshness of raw_100knock.orders ...
04:00:04  Done.

==> [3/3] dbt build --select state:modified+ --defer --state ../prod-manifest
WARN: ../prod-manifest/manifest.json not found - falling back to full build
04:00:05  Running with dbt=1.11.x
04:00:06  Found 12 models, 5 sources, 2 exposures, 21 tests
... (full build) ...
04:00:30  Done. PASS=33 WARN=0 ERROR=0 SKIP=0

==> All checks PASSED
```

### 実際の実行 (prod-manifest あり)

```bash
$ cp dbt/target/manifest.json prod-manifest/   # 1 回 dbt build した後
$ git checkout -b feature-test-state-modified
$ # dbt/models/100-knock/topic-3/stg_orders_100knock.sql を 1 行変更
$ bash scripts/100-knock/topic-10/ci/dbt_check.sh
==> [3/3] dbt build --select state:modified+ --defer --state ../prod-manifest
04:01:00  Found 12 models, ... | 1 modified, 4 children
04:01:01  Concurrency: 4 threads
04:01:02  1 of 5 START sql view model ... stg_orders_100knock
04:01:02  ... (変更 model + 下流 4 つだけ build)
04:01:10  Done. PASS=5 WARN=0 ERROR=0 SKIP=0

==> All checks PASSED
```

5 model だけで完了 (full build の 33 → 差分 5)。**defer の威力 = 6 倍速**。

## 3 行版 (より簡略)

「学習者が最初に書く版」 として、解答例にはより短いバージョンも示す:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd dbt
dbt deps --profiles-dir . \
  && dbt source freshness --profiles-dir . \
  && dbt build --profiles-dir . --select state:modified+ --defer --state ../prod-manifest/
```

**`&&` 連結版** は短くて読みやすいが:

- freshness の WARN (exit 2) で `set -e` により全体停止 → CI が freshness 警告で落ちる (運用上望ましくないことが多い)
- prod-manifest 不在の fallback がない

学習段階ではどちらでも採点 PASS。実務では上の long version (exit code 分岐 + fallback あり) を推奨。

## 解説まとめ

- **なぜ CI を 1 行 (= 1 script) にまとめるか**:
  - **属人性の排除**: 「CI で何を呼ぶか」は新人 / 途中 join したメンバーが最も詰まる場所。`bash dbt_check.sh` を呼ぶだけにすれば、`.github/workflows/*.yml` を読まずに CI を理解できる
  - **CI / ローカルの一致**: 手元で `bash dbt_check.sh` を回せば CI と完全に同じことが起きる → デバッグ可能
  - **責務分離**: workflow yaml は「いつ呼ぶか」(trigger / schedule)、script は「何を呼ぶか」(コマンド本体)。両者が混ざると改修コストが上がる
- **`dbt deps → freshness → build` の順序の意味**:
  - **deps 最初**: build は packages 解決済み前提。CI は毎回 fresh checkout
  - **freshness 真ん中**: 「raw が古い」を build 失敗の前に検出 (失敗ログがクリーン)
  - **build 最後**: 重い処理は最後。前の段階で詰まれば実行されない (高速 fail)
- **`state:modified+` `--defer` `--state` の三位一体**:
  - **`state:modified`**: manifest 差分で「変わった model」 を抽出
  - **`+`**: 下流方向に展開
  - **`--defer`**: 変わってない上流は本番参照 (build しない)
  - **`--state ./prod-manifest/`**: 「本番」がどこか教える (本番 manifest 置き場)
  - 4 つ揃って初めて「PR の差分だけ build」 が成立する。1 つでも欠けると full build に戻る
- **prod-manifest を空でも問題ない理由**: 学習段階では「本番」がない (= 全部開発環境)。`--state` で渡したディレクトリに `manifest.json` がなければ dbt は warn して **full build に fallback** する (本解答例の if 文がそれ)。本番運用では nightly job が `dbt build` 後の `target/manifest.json` を `./prod-manifest/` にコミット / S3 push する pipeline を組む
- **`bash -n` で構文チェック**: CI の前段に `bash -n script.sh` を入れると、コマンド実行前に構文エラーを検出できる。dbt の重い処理を走らせる前に「typo した括弧」を 0.01 秒で発見できる
- **freshness の WARN を build に進ませるか?**: 設計判断ポイント。本解答例では「WARN なら継続、ERROR なら停止」 にしたが、保守的運用なら「WARN でも停止」もアリ。`--warn-error` で WARN を ERROR に昇格させる方法もある (10-7 では扱わない、運用判断)
- **次の問への接続**: 10-7 までで「DAG + CI 自動化」が揃った。10-8 / 10-9 / 10-10 では **このパッケージ全体を「他者がレビューできる / 引き継げる」状態にまとめる open-ended 問** へ進む。コードと運用の両方が揃って初めて「成果物」と呼べる、という Topic ⑩ の総括。
