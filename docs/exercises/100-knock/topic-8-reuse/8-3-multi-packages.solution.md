# 8-3 解答例

## dbt/packages.yml (8-2 の状態に追記)

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

**ポイント**:

- **list 構文**: `packages:` 配下に `-` で区切った dict を並べる。順序はどちらでも
  動作上の差は無いが、「メインで使うもの」 を上に書くと意図が伝わる。
- **どちらも `<MAJOR>.0.0` で上限を切る**: メジャーアップデートは破壊的変更を
  含む可能性があるので、明示的に手動アップデートする運用にする。マイナー /
  パッチアップデートは自動取り込みを許容。
- **依存の重複は問題なし**: `dbt_expectations` も内部で `dbt_utils` に依存しているが、
  こちらの `>=1.3.0, <2.0.0` 制約と重なる範囲なので **共有** される (重複 install は
  起きない)。

## Step 2: dbt deps の実行ログ

```text
$ ../.venv/bin/dbt deps --profiles-dir .
14:30:01  Running with dbt=1.11.x
14:30:01  Updating lock file in file path: /path/to/dbt/package-lock.yml
14:30:02  Installing dbt-labs/dbt_utils
14:30:03    Installed from version 1.3.0
14:30:03    Up to date!
14:30:03  Installing calogica/dbt_expectations
14:30:04    Installed from version 0.10.4
14:30:04    Up to date!
```

`dbt/dbt_packages/` を覗くと:

```text
$ ls dbt/dbt_packages/
dbt_expectations  dbt_utils
```

両方が展開されている。`dbt_expectations` の中身を見ると:

```text
$ ls dbt/dbt_packages/dbt_expectations/
CHANGELOG.md  README.md  dbt_project.yml  integration_tests/  macros/  ...

$ cat dbt/dbt_packages/dbt_expectations/dbt_project.yml | head -3
name: 'dbt_expectations'
version: '0.10.4'
```

## Step 3: package-lock.yml の中身

```text
$ cat dbt/package-lock.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0
  - package: calogica/dbt_expectations
    version: 0.10.4
sha1_hash: <hex digest>
```

**ポイント**:

- **「実際にインストールされたバージョン」 が固定**: `packages.yml` は version range、
  `package-lock.yml` は **解決後の正確な版** を記録する。後者を commit すれば
  CI / 同僚と「全く同じ macro セット」 で動かせる。
- **`sha1_hash`**: `package-lock.yml` 全体の hash。手で書き換えると `dbt deps` が
  「lock が壊れている」 と検知する仕組み。
- **lock ファイルだけ commit、`dbt_packages/` は gitignore**: `requirements.txt` +
  `dbt_packages/` を両方 commit するのは冗長で repo を肥大化させる。「lock を信頼して
  毎回 `dbt deps` で取り直す」 のが標準運用。

## Step 4: 冪等性の確認

```text
$ ../.venv/bin/dbt deps --profiles-dir .
14:35:01  Installing dbt-labs/dbt_utils
14:35:01    Installed from version 1.3.0
14:35:01    Up to date!
14:35:01  Installing calogica/dbt_expectations
14:35:01    Installed from version 0.10.4
14:35:01    Up to date!
```

「Up to date!」 が両方に出ていれば、**何もダウンロードせずに完了** = 冪等。

## Step 5: parse の確認

```text
$ ../.venv/bin/dbt parse --profiles-dir .
14:36:01  Found 11 models, 5 sources, 75 data tests, ...
14:36:01    1 macro from cast_money (100-knock topic-8)
14:36:01    18 macros from dbt_utils
14:36:01    50+ macros from dbt_expectations
```

`dbt parse` が **両パッケージの macro 全部を読み込んだ後でも成功** する。
これが「2 packages 共存可能」 の最終確認。

## 物理確認 (展開された macro の数)

```bash
$ find dbt/dbt_packages/dbt_utils/macros -name "*.sql" | wc -l
30+   # dbt_utils が提供する macro 数

$ find dbt/dbt_packages/dbt_expectations/macros -name "*.sql" | wc -l
80+   # dbt_expectations が提供する macro 数 (test 系含む)
```

`dbt-expectations` のほうが macro 数が多いのは、**test 系 macro が大量にある**
(各 `expect_*` test が独立した macro 実装) ため。

## 解説まとめ

- **複数 packages 共存の鍵 = lock ファイル**: `packages.yml` だけだと「次回 deps 時に
  どの版が入るか」 が不確定。`package-lock.yml` を介在させて **「version range の
  解決結果」 を固定** することで再現性が取れる。Python の poetry / Node の npm と同じ。
- **依存共有の最適化**: `dbt-expectations` は内部で `dbt-utils` を使っているが、
  `dbt deps` は **同じパッケージを 2 回 install しない**。共有された 1 コピーを
  両方が参照する。これは disk 容量と読み込み時間の両面で効率化される。
- **`packages.yml` に明示する vs しない**: `dbt-utils` を packages.yml に明示せず
  `dbt-expectations` だけ宣言しても、依存解決で `dbt-utils` は自動取得される。
  ただし「自プロジェクトで何を直接使っているか」 を宣言する観点では明示する方が
  良い (8-2 で `generate_surrogate_key` を直接使っているので明示する意義がある)。
- **version conflict の解決**: 仮に `dbt_expectations` が `dbt_utils >= 2.0` を要求
  (実際にはそうではない仮定) した場合、`packages.yml` 側の `<2.0.0` 制約と矛盾して
  `Resolution conflict` エラー。解消策は (1) こちらの上限を緩める (2) `dbt_expectations`
  の古い版を pin する のいずれか。lock ファイルが「衝突発見の早期検知」 に効く。
- **CI との関係**: 採点 CI は `.github/workflows/grade.yml` で `dbt deps` を build
  ステップに含めている前提。lock ファイルが commit されていれば CI 側も
  「同じ版」 で採点する。
- **「macro = 共有資産」**: dbt 界では macro パッケージが Python の標準ライブラリ
  相当になりつつある。`dbt-utils` (汎用ヘルパ) + `dbt-expectations` (test 拡張) が
  事実上の standard library。慣れたら自社の業務 macro を **internal package 化** して
  `git: <internal-repo>` で読み込む流派もある (ADR ネタ)。
- **8-2 → 8-3 → (将来 8-N) の流れ**: 8-2 で 1 個入れ、8-3 で 2 個共存させ、後続の
  問 (例えば 6-8 既習者は別途 dbt_expectations の test を実際に使う) で具体的な
  ROI を体験する。「インストール → lock → 使用」 の 3 段階を分けて学ぶ設計。
