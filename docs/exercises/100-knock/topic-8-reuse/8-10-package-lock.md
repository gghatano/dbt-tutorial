# 8-10: `packages.yml` の version をピン留めし、`package-lock.yml` の差分と役割を 3 行で言語化する

## シナリオ

8-2 / 8-3 で `dbt-utils` / `dbt-expectations` を `packages.yml` に追加した。その時 version は範囲指定 (`[">=1.3.0", "<2.0.0"]`) で書いていたはず。これは「マイナー upgrade は受け入れる」 という宣言で、`dbt deps` を再実行すると **その時点で利用可能な最新マイナー** が引かれてくる。

範囲指定の利点は「セキュリティ patch を自動受領できる」 こと。欠点は「**ビルド時刻の異なるマシンで違う実体が引かれる**」 = 再現性が崩れること。CI が通った PR を 1 ヶ月後に rebase して動かすと、`dbt-utils` が 1.3.0 → 1.5.2 に上がっていて、突然挙動が変わる、というのが典型事故。

`package-lock.yml` (dbt 1.7+) はこの問題に対する dbt の解。`dbt deps` 実行時に **実際に解決された具体 version** を記録する lockfile で、次回以降は lockfile に書かれた version をそのまま使う。`packages.yml` は「**意図 (許容する範囲)**」、`package-lock.yml` は「**事実 (実際に引いた version)**」 を分けて宣言する仕組みで、Python の `requirements.txt` vs `pip freeze` 結果、Node の `package.json` vs `package-lock.json` と同じ思想。

このエクササイズでは `packages.yml` の version 範囲指定を **特定 patch にピン留め** に書き換え、`dbt deps --upgrade` で `package-lock.yml` の差分を観察し、**lock の役割** を `docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md` に 3 行で言語化する。**「再現可能性」 「自動更新」** の 2 軸で運用ポリシーを言語化できれば本問の到達点。

## 学べること

- `packages.yml` の version 指定形式 (範囲 / pin / branch / tag)
- `package-lock.yml` (dbt 1.7+) の自動生成と役割
- `dbt deps --upgrade` で lock を更新する流れ
- 「意図 (range)」 と 「事実 (pin)」 の分離 という依存管理の基本原則
- 再現可能性 vs 自動更新 のトレードオフを言語化

## 前提

- Topic ② 〜 ⑦ + Topic ⑧ 8-1〜8-9 完了
- `packages.yml` に `dbt-utils` (8-2 で追加) と `dbt-expectations` (8-3 で追加) が範囲指定 (`>=`, `<`) で入っている
- dbt 1.7+ (= `package-lock.yml` を自動生成するバージョン)

## 入力データ

不要。`packages.yml` を編集して `dbt deps` を実行するだけ。

## 課題

### Step 1: 現状の `packages.yml` と `package-lock.yml` を確認

```bash
cat dbt/packages.yml
# packages:
#   - package: dbt-labs/dbt_utils
#     version: [">=1.3.0", "<2.0.0"]
#   - package: calogica/dbt_expectations
#     version: [">=0.10.0", "<1.0.0"]

cat dbt/package-lock.yml 2>/dev/null
# packages:
#   - package: dbt-labs/dbt_utils
#     version: 1.3.0      # ← 解決された具体 version
#   - package: calogica/dbt_expectations
#     version: 0.10.4
# sha1_hash: ...
```

`package-lock.yml` がまだ無ければ `cd dbt && dbt deps` で生成。

### Step 2: `packages.yml` をピン留めに変更

`dbt/packages.yml` の version 指定を範囲から **正確 1 patch のピン** に書き換える。例:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0     # ← ピン留め (= [">=1.3.0", "<2.0.0"] からの変更)
  - package: calogica/dbt_expectations
    version: 0.10.4    # ← ピン留め
```

ピンする version は **現在 lock されている version** に合わせる (= 何も変わらない再現可能状態)。version 番号は環境/時期で異なるので、Step 1 で確認した lock の値を使う。

### Step 3: `dbt deps --upgrade` で lock を更新

```bash
cd dbt
../.venv/bin/dbt deps --upgrade --profiles-dir .
```

`package-lock.yml` の差分を git diff で確認:

```bash
cd ..
git diff dbt/package-lock.yml
```

差分は (a) `version` 行が範囲解決された値からピンの値に変わる (= 同じ値なので変化なし or 微小)、(b) `sha1_hash:` が `packages.yml` の hash 変更で更新される、の 2 種類が出る。

### Step 4: lock の役割を 3 行で言語化

`docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md` を新規作成し、以下 3 行 (前後説明含めて 5-15 行で OK) を **自分の言葉** で書く:

```markdown
# 8-10 package-lock の役割

## packages.yml と package-lock.yml の関係 (3 行)

1. (再現可能性) ...
2. (自動更新) ...
3. (運用方針) ...
```

3 行に必ず含めるキーワード:

- **「再現可能性」** (lock があると同じビルドが何度でも再現できる)
- **「自動更新」** (lock がないと毎 deps で違う version が引かれうる)
- 自分なりの運用方針 (例: 「prod は pin、dev は range」)

### Step 5: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-8-reuse/8-10-package-lock.grading.yaml
```

## 完了条件

- [ ] `dbt/packages.yml` の `version:` が範囲指定 (`>=`, `<`) ではなく **単一 version 文字列** (例: `1.3.0`) になっている
- [ ] `dbt deps --upgrade` が成功し、`package-lock.yml` が更新されている
- [ ] `docs/exercises/100-knock/topic-8-reuse/package-lock-notes.md` が存在し、本文に **「再現可能性」** と **「自動更新」** の両方のキーワードを含む
- [ ] `dbt parse` が pin 後も成功する (= pin した version で実体が解決される)

## ヒント (詰まったら)

- **`packages.yml` の version 指定形式 5 種**:
  - `version: 1.3.0` — pin (= 完全固定)
  - `version: ">=1.3.0"` — 下限のみ
  - `version: [">=1.3.0", "<2.0.0"]` — 範囲 (= マイナーまで許容)
  - `revision: <git_sha>` — git 系 packages の場合
  - `branch: main` / `tag: v1.3.0` — git の場合
- **`package-lock.yml` がコミットされていない**: `.gitignore` で除外されていないか確認。lockfile は **必ずコミット** が原則 (= チームで再現性を共有)
- **`dbt deps` vs `dbt deps --upgrade`**:
  - `dbt deps` (lock 優先): lockfile があれば lock の version を引く
  - `dbt deps --upgrade`: lock を再生成、`packages.yml` の最新解決を引く
- **`package-lock.yml` の `sha1_hash:`**: `packages.yml` の hash。`packages.yml` を編集すると次回 `dbt deps` で hash が変わったことを検知して lock を更新する
- **pin ではなく `~> 1.3` を書きたい**: dbt は npm の chevron 表記に対応していない。`>=1.3.0, <1.4.0` のように明示的範囲を書く
- **本番でも range のまま運用したい**: その場合は **CI で lock を生成 → 本番デプロイ時に lock を fix** する手順を踏む。`packages.yml` は意図、運用は lock で固定、という分離ができる
- **lock を消したらどうなる**: 次の `dbt deps` で再生成される。ただし「再生成時の最新 version」 が選ばれるので **過去の build と再現性が崩れる可能性** がある
- **3 行に何を書くか迷ったら**: (1) **何が再現可能になるか** (= 同じ lock なら同じ依存ツリー) / (2) **lock がないと何が起きるか** (= deps を打つたびに version drift) / (3) **チーム運用としてどう使い分けるか** (= prod は pin、dev は range など) を順に書くと収まる

## 解答例

詳細は [`8-10-package-lock.solution.md`](8-10-package-lock.solution.md) を参照。
