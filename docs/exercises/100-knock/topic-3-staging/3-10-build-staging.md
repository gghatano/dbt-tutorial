# 3-10: `dbt build --select staging` を 1 発で通し、`stg_*` の run + test が原子的に成功

## シナリオ

3-1〜3-9 までの作業の **集大成**。`stg_*_100knock` 4 model + `schema.yml` + `descriptions` + `naming-convention.md` + `materialization config` + `DAG selector` 全てを揃えて、`dbt build` 1 コマンドで「100-knock の staging レイヤーが run + test 両方 PASS」する状態を作る。

`dbt build` は `dbt run` + `dbt test` を **1 ノードずつ atomic に** 実行する。run が PASS したら即その node の test を走らせ、test が FAIL したらその node の下流を SKIP する。これが `dbt run && dbt test` の 2 段運用 (run 全部成功してから test 全部) と決定的に違う点で、「失敗の局所化」と「下流の汚染防止」を 1 コマンドで実現する。

レイヤー単位の `dbt build` を CI で常用すれば、「staging 層は常に契約を満たしている」状態を継続的に保証できる。これが Topic ③ の最終ゴール。

## 学べること

- `dbt build` と `dbt run + dbt test` の違い (atomic per-node vs phase-separated)
- レイヤー単位の selector (`--select 100-knock.topic-3` または path-based)
- build の出力サマリ (`Done. PASS=N WARN=N ERROR=N SKIP=N`) の読み方
- 失敗時の SKIP 連鎖 (FAIL ノードの下流が SKIP される)
- 実行ログを `build-log.md` に残して再現性を担保

## 前提

- 3-1〜3-9 完了 (`stg_*_100knock` 4 model + schema.yml の test 群 + dbt_project.yml の `100-knock:` セクション)
- Topic ② で `raw_100knock` の 4 テーブルがロード済み
- `dbt parse` が通る
- `dbt run --select 100-knock` でも一応通る (本問は `dbt build` で test も含めて通す)

## 入力データ

不要。学習者が `dbt build` を実行してログを取るだけ。

## 課題

### Step 1: dbt build を試走 (run のみで通ること確認)

念のため build 前に run だけで通ること確認:

```bash
cd dbt
dbt run --select 100-knock.topic-3 --profiles-dir .
```

PASS=4 で完了するはず。FAIL なら 3-1〜3-3 の SQL に戻る。

### Step 2: dbt build で run + test を一気に通す

```bash
cd dbt
dbt build --select 100-knock.topic-3 --profiles-dir .
```

別の selector でも同じ意味:

```bash
# パスベース
dbt build --select dbt/models/100-knock/topic-3 --profiles-dir .

# 名前ワイルドカード (3-1 で stg_*_100knock 命名にしたなら)
dbt build --select 'stg_*_100knock' --profiles-dir .
```

### Step 3: 出力を build-log.md に記録

`docs/exercises/100-knock/topic-3-staging/build-log.md` を作成。以下を含める:

- 実行コマンド (どの selector を使ったか)
- 実行日時
- 出力サマリ (`Done. PASS=N WARN=N ERROR=N SKIP=N`)
- 各 model / 各 test の PASS 件数
- (任意) 失敗→修正のループがあれば、その経緯

形式は自由。20〜80 行を目安。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-3-staging/3-10-build-staging.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-3-staging/build-log.md` が存在する
- [ ] `dbt build --select 100-knock.topic-3` (または同等 selector) が exit 0 で完了
- [ ] 出力に `ERROR=0 SKIP=0` がある (test 含めて全 PASS)
- [ ] build-log.md に `dbt build` コマンドと出力サマリが書かれている

## ヒント (詰まったら)

- **`dbt build` vs `dbt run + dbt test`**: build は per-node atomic。stg_orders の run が PASS したら即その node の relationships test を走らせる。run / test を分けると「全 run 完了してから test 開始」になり、stg_orders の test 失敗が判明するのは run 全部終わった後。
- **selector の使い分け**:
  - `--select 100-knock.topic-3` — `dbt_project.yml` の階層名で指定。3-8 でセクション名を `100-knock.topic-3` にしたので使える
  - `--select dbt/models/100-knock/topic-3` — 物理パスで指定。dbt の cwd からの相対パス
  - `--select 'stg_*_100knock'` — model 名のワイルドカード。シェルの glob と衝突するのでクォート必須
- **SKIP が出たら**: FAIL ノードの下流が SKIP される。例えば stg_customers の test が FAIL すると、stg_orders の relationships test が SKIP (因果が辿れないので走らせない)。SKIP は失敗の症状であって失敗ではない。
- **`Done. PASS=N WARN=N ERROR=N SKIP=N`**: 最終行のこのサマリだけ見れば結果が分かる。ERROR + SKIP = 0 なら全 PASS。WARN は freshness 違反等で出る (test の FAIL ではない)。
- **build-log.md は CI 後に貼ってもいい**: ローカルでは長すぎるログが出るので、`tee /tmp/build.log` でファイル化してから抜粋を貼るのが現実的。

## 解答例

詳細は [`3-10-build-staging.solution.md`](3-10-build-staging.solution.md) を参照。
