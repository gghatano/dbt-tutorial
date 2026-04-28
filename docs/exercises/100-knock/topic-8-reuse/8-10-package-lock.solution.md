# 8-10 解答例

## ゴール再掲

`dbt/packages.yml` の `dbt-utils` / `dbt-expectations` の `version` を範囲指定 (`[">=1.3.0", "<2.0.0"]`) から **正確 1 patch のピン留め** (`1.3.0`) に書き換え、`dbt deps --upgrade` で `package-lock.yml` の差分を観察し、`docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md` に lock の役割を 3 行で言語化する。

## Step 1: 現状確認

8-2 / 8-3 完了直後の `dbt/packages.yml`:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<1.0.0"]
```

`dbt deps` 直後の `dbt/package-lock.yml` (例):

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0
  - package: calogica/dbt_expectations
    version: 0.10.4
sha1_hash: 4f8a2c91...
```

範囲指定 → 解決された具体 version (1.3.0 / 0.10.4) が lock に記録されている。これを基準値として控えておく。

## Step 2: `dbt/packages.yml` をピン留めに書き換え

```yaml
# 100-knock Topic ⑧ 8-10: version を範囲指定から正確 1 patch のピン留めに変更。
# 意図: 「マイナー upgrade で勝手に挙動が変わらない」 再現可能なビルドを保証する。
# 自動更新が必要になったときは dbt deps --upgrade で lock を再生成する手順を踏む。
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0
  - package: calogica/dbt_expectations
    version: 0.10.4
```

ポイント:

- **ピンする version は Step 1 で確認した lock の値**: 「現状を再現可能化する」 が本問の目的なので、lock と同じ値にすれば動作は何も変わらない (= 安全側)
- **コメントで意図を残す**: 「なぜ範囲ではなく pin か」 を明記。次の人 (= 半年後の自分) が `dbt-utils` を上げたい時、コメントを読んで「pin を外す or 上げる」 を選択できる

## Step 3: `dbt deps --upgrade` で lock を更新

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --upgrade --profiles-dir .
```

期待される出力:

```
Running with dbt=1.7.x
Updating lock file in file path: /path/to/dbt/package-lock.yml
Installing dbt-labs/dbt_utils
  Installed from version 1.3.0
  Up to date!
Installing calogica/dbt_expectations
  Installed from version 0.10.4
  Up to date!
```

git diff を確認:

```bash
cd ..
git diff dbt/package-lock.yml
```

```diff
- packages:
-   - package: dbt-labs/dbt_utils
-     version: 1.3.0
-   - package: calogica/dbt_expectations
-     version: 0.10.4
- sha1_hash: 4f8a2c91...
+ packages:
+   - package: dbt-labs/dbt_utils
+     version: 1.3.0
+   - package: calogica/dbt_expectations
+     version: 0.10.4
+ sha1_hash: 7b2e1f33...   # ← packages.yml の hash 変更で sha1 が更新
```

`version:` 数値は同じ (= 既に lock 値と一致) だが、`sha1_hash` が更新される (= `packages.yml` の文面が変わった証跡)。

## Step 4: `package-lock-notes.md` を書く

`docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md` (新規):

```markdown
# 8-10: package-lock.yml の役割と運用方針

## packages.yml と package-lock.yml の関係 (3 行で言語化)

1. **再現可能性**: `package-lock.yml` は `dbt deps` 実行時に解決された具体 version
   を記録する lockfile。これを git 管理することで、別マシン / 別時刻でも `dbt deps`
   が同じ依存ツリーを再現する (= ビルドの再現可能性が保証される)。

2. **自動更新**: `package-lock.yml` がない / 削除された / `dbt deps --upgrade` を
   実行すると、`packages.yml` の範囲指定が再評価され、その時点の最新マイナー /
   patch が引かれる。これは「セキュリティ patch を自動受領」 のメリットがあるが、
   逆に「気づかぬうちに依存実体が変わる」 リスクも持つ。

3. **運用方針 (本プロジェクト)**: `packages.yml` は **意図 (許容範囲)** を、
   `package-lock.yml` は **事実 (実際に引いた version)** を分けて宣言する責務分離。
   本問では `packages.yml` を pin に変更したことで「意図 = 範囲」 すら剥奪し、
   prod は **完全固定**、`dbt deps --upgrade` を意図的に実行した PR レビューを
   経由してのみ依存を上げる、という運用に倒した。

## 補足

- Python の `requirements.txt` (range) vs `pip freeze` (pin) と同じ思想
- Node の `package.json` vs `package-lock.json` と同じ思想
- dbt 1.7+ で `package-lock.yml` が自動生成されるようになった
```

3 行に**「再現可能性」** **「自動更新」** のキーワードを含めるのが必須。3 番目の運用方針は学習者の判断 (本プロジェクトでは pin を採用、を推奨)。

## Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-10-package-lock.grading.yaml
```

期待結果:

```
## Grading Result: OK (100%)
Score: 100 / 100
| OK | packages-yml-pinned                | 25/25 |
| OK | package-lock-yml-exists            | 15/15 |
| OK | package-lock-notes-exists          | 15/15 |
| OK | notes-keywords-reproducibility     | 15/15 |
| OK | notes-keywords-auto-update         | 15/15 |
| OK | dbt-parse-after-pin                | 15/15 |
```

## ポイント

- **「意図」 と 「事実」 の分離**: `packages.yml` は **意図** (= 何を許容するか)、`package-lock.yml` は **事実** (= 実際に引いた何か)。両方を git 管理することで、PR レビューでは「意図の変更 (= packages.yml の diff)」 と 「事実の変更 (= lock の diff)」 を別々に評価できる。例えば「意図は変えていないのに lock の version が上がった」 = 「セキュリティ自動更新」 vs 「意図そのものを上げた」 = 「明示的 upgrade」 が区別可能
- **pin 一辺倒ではなく状況次第**:
  - **prod / 大規模チーム**: pin 推奨。「気づかぬうちに依存変更」 を最小化
  - **dev / 個人**: range 可。`dbt-utils` の bug fix を自動受領できる
  - **OSS dbt project**: range が一般的 (= 利用者側で pin する余地を残す)
- **`package-lock.yml` の `sha1_hash:`**: `packages.yml` の SHA1。`packages.yml` を編集 → hash が変わる → 次回 `dbt deps` で「lock と packages.yml が乖離」 を検知してエラー or 再生成。これにより「`packages.yml` 変更後に `dbt deps` を打ち忘れる」 事故を防ぐ
- **`dbt deps --upgrade` の使いどころ**: 「依存を最新に上げたい」 PR を作る時に明示実行 → lock の diff をレビュー対象にする。普段の `dbt deps` は lock を保つ
- **dbt 1.7 未満は lock がない**: 古い dbt project では `packages.yml` だけが依存宣言。現在のリポジトリは dbt 1.7+ 想定なので lock を活用できる
- **3 行で言語化する意義**: 機能を **コードで使えるようになる** ことと、**チームに説明できる** ことは別スキル。lock 機能を使えても運用方針を言えないと PR レビューで詰まる。本問は「言語化スキル」 まで含めて学習目標にしている

## 実行例 (採点 shell_command 視点)

```bash
$ grep -E "^\s+version:\s+[0-9]+\.[0-9]+\.[0-9]+\s*$" dbt/packages.yml | wc -l
2     # dbt-utils + dbt-expectations の version が pin 形式

$ grep -E "^\s+version:\s+\[" dbt/packages.yml | wc -l
0     # 範囲指定 [">=", "<"] が残っていない

$ test -f dbt/package-lock.yml && echo "lock exists"
lock exists

$ test -f docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md && echo "notes exists"
notes exists

$ grep -ciE '再現可能性|reproducibility' \
    docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md
1     # 必須キーワードが含まれる

$ grep -ciE '自動更新|auto.*update' \
    docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md
1
```

## 解説まとめ

- **lockfile という発明**: range 指定だけだと「ビルド時刻が違うマシンで違う実体」 が引かれる。lock があれば「lock を git で共有」 → 「全マシンで同じ実体」 が保証される。これは Python / Node / Ruby / Go など、ほぼ全ての言語のパッケージマネージャが採用している王道パターン。dbt は 1.7 でやっと追従した
- **「意図」 と 「事実」 を別ファイルに分けるメリット**: 1 ファイルに pin だけ書くと「ここは pin、ここは range」 を 1 ファイル内に混在させることになり読みにくい。**意図 (packages.yml) は人が書く、事実 (lock) は機械が書く**、と責務分離することで「人が読むべきもの」 が短く保たれる
- **再現可能性 vs 自動更新の二律背反**: pin = 再現可能 = security patch 取りこぼし。range = 自動更新 = 再現性低下。**両方欲しい** 場合は (a) range で書き、(b) lock を git 管理し、(c) `dbt deps --upgrade` を CI の定期 job (例: 週次) で実行 → lock 更新 PR を bot が作る、という運用が成立する。Renovate / Dependabot がこれを担う
- **本問の限界**: 「3 行で言語化」 はあえて短い。本物の運用ドキュメントは「`dbt deps --upgrade` を誰がいつ実行する」 「lock 更新 PR の review owner は誰」 「lock 取消 (rollback) 手順」 まで 1 ページ書く必要がある。本問は **概念をつかむ最小単位**
- **8-2 / 8-3 (packages 追加) との連続性**: 8-2 / 8-3 で「packages を追加する」、本問で「packages を **pin する / lock する** 」。**追加した依存の運用責任** まで含めて Topic ⑧ が完結する設計

## 拡張アイデア

- **lock を意図的に消して `dbt deps` する**: range 指定の `packages.yml` で lock を消す → 次の `dbt deps` で「その時の最新」 が引かれる。range の罠を体感
- **`dbt-utils` の major upgrade を試す**: `version: 1.3.0` を `version: 2.0.0` に変えてみる (実在 version で)。range の `<2.0.0` 制約に守られていなければ通る、を観察
- **CI で lock の整合性を保証**: GitHub Actions で `dbt deps && git diff --exit-code dbt/package-lock.yml` を走らせ、「lock がコミット忘れ」 を検知
- **Renovate 導入**: `.github/renovate.json` を書いて、依存 upgrade PR を自動生成。lock 運用を半自動化
- **複数 dbt project で `packages.yml` を共有**: 同じ pin 情報を 2 project で持ちたい場合、`packages.yml` を git submodule で共有する手もある (やや過剰)
- **`packages.yml` に local path 指定**: `packages: [{local: "../shared_macros"}]` で別 dbt project の macro を参照。8-9 の metric_revenue を共有する練習にも使える
