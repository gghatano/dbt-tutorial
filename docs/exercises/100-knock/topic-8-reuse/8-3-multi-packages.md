# 8-3: dbt-expectations を packages.yml に追加、dbt-utils と共存を package-lock で確認

## シナリオ

8-2 で `dbt-utils` を入れた。Topic ⑥ 6-8 で「`dbt-expectations` の regex test を
使いたい」 という別の動機が出てくる。**2 つのパッケージを同居** させると、
内部で `dbt-expectations` が `dbt-utils` に依存しているため、`dbt deps` の依存
解決ロジック (どのバージョンを実体化するか) が動く。

`packages.yml` に **2 entries 並べて** `dbt deps` を 1 回叩くだけで、依存解決が
完了し `dbt_packages/` に両方が展開される。**`package-lock.yml`** には
「実際にインストールされたバージョンの組み合わせ」 が記録され、CI / 他環境で
**同じバージョン組み合わせ** を再現できるようになる。これは Python の
`requirements.txt` vs `poetry.lock`、Node の `package.json` vs `package-lock.json`
の関係と同じ。

8-3 では「2 packages 同居 + lock ファイル生成」 を体験し、依存解決の挙動と
`package-lock.yml` の役割を学ぶ。

## 学べること

- `packages.yml` に複数 entries を並べる構文
- 依存パッケージの自動解決 (`dbt-expectations` → `dbt-utils` の依存をどう解くか)
- `dbt deps` 実行で `dbt_packages/` 配下に複数展開される様子
- `package-lock.yml` の役割 (= 「再現性」 を担保する固定ファイル)
- `dbt deps` の冪等性 (2 回叩いても同じ結果)

## 前提

- 8-2 完了 (`dbt-utils` が packages.yml に既に宣言され、インストール済み)
- インターネット接続 (`dbt deps` で hub.getdbt.com から取得)
- `dbt/package-lock.yml` は 8-2 の段階で生成されているはず

## 入力データ

不要。`packages.yml` を編集して `dbt deps` を叩くだけ。

## 課題

### Step 1: packages.yml に dbt-expectations を追加

`dbt/packages.yml` (8-2 の状態に追記):

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.3.0", "<2.0.0"]
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

> **注**: `dbt_expectations` は内部で `dbt_utils` に依存している。`packages.yml` に
> `dbt_utils` を明示しておくと、依存解決が `dbt_utils` を **共有** してくれる。
> 明示しなくても自動で取得されるが、明示する方が「自分のプロジェクトで何を使っているか」
> が宣言できる (8-2 で既に明示済み = 一貫した設計)。

### Step 2: dbt deps を実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt deps --profiles-dir .
```

期待 (依存解決ログ):

```text
Installing dbt-labs/dbt_utils
  Installed from version 1.3.0
Installing calogica/dbt_expectations
  Installed from version 0.10.x
```

`dbt/dbt_packages/` 配下に **2 ディレクトリ** ができる:

```text
dbt/dbt_packages/
  dbt_utils/
  dbt_expectations/
```

### Step 3: package-lock.yml を確認

```bash
cat dbt/package-lock.yml
```

期待される中身:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0
  - package: calogica/dbt_expectations
    version: 0.10.x
sha1_hash: ...
```

> **意味**: 「次回 `dbt deps` を叩いた時に、ここに記録された **正確なバージョン** を
> インストールする」 ことを保証するファイル。team の他メンバや CI が同じバージョン
> 組み合わせを再現できるようになる。

### Step 4: 冪等性の確認

`dbt deps` をもう 1 回叩く:

```bash
../.venv/bin/dbt deps --profiles-dir .
```

期待:

```text
Installing dbt-labs/dbt_utils
  Up to date!
Installing calogica/dbt_expectations
  Up to date!
```

「Up to date!」 が出れば冪等。何もダウンロードせず終わる。

### Step 5: parse の確認

`packages.yml` を変更しても `dbt parse` は通る:

```bash
../.venv/bin/dbt parse --profiles-dir .
```

> **注**: 8-3 ではまだ `dbt-expectations` の test を schema.yml に追加していないので、
> 「インストールしただけ、まだ呼んでいない」 状態。次の問 (Topic ⑥ 6-8 既習者は
> そちらで使用、本演習で実際に使うのは Topic ⑧ 後半 or Topic ⑥ 6-8) で活用する。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-8-reuse/8-3-multi-packages.grading.yaml
```

## 完了条件

- [ ] `dbt/packages.yml` に **2 entries** (`dbt_utils` + `dbt_expectations`) が宣言済み
- [ ] `dbt/dbt_packages/dbt_utils/dbt_project.yml` と
      `dbt/dbt_packages/dbt_expectations/dbt_project.yml` が両方存在
- [ ] `dbt/package-lock.yml` に 2 packages が記録されている
- [ ] `dbt deps` が成功する (2 回連続叩いても冪等)
- [ ] `dbt parse` が成功

## ヒント (詰まったら)

- **`packages.yml` の並べ方**: list の YAML なので `-` で区切って複数 entries。順序は
  原則どちらでも OK だが、依存解決上の優先度を明示したい場合はメインで使うものを上に。
- **依存解決の競合**: 仮に `dbt_expectations` が `dbt_utils >=2.0` を要求し、こちらが
  `<2.0` を pin していると、`dbt deps` で **`Resolution conflict`** エラーが出る。
  本演習の version range はそれぞれ互換性が確認済みなので競合しない。
- **`package-lock.yml` を commit するか**: 「team で再現性を取りたい」 なら commit、
  「常に latest を取りたい」 なら gitignore + `dbt deps` を CI で毎回回す。
  本リポジトリは 100-knock 学習用なので **commit する派** を推奨 (CI が毎回同じ
  バージョンで採点できる)。
- **`dbt_packages/` をコミットしない**: 容量が大きい (数 MB) ので gitignore 推奨。
  `package-lock.yml` だけ commit すれば再現性は取れる。
- **PyPI のパッケージとの違い**: dbt パッケージは Python パッケージではなく **dbt 専用の
  jinja macro 集**。`pip install` ではなく `dbt deps` で取得。中身は `.sql` ファイル群。
- **Topic ⑥ 6-8 を先にやっていれば**: `dbt-expectations` は既にインストール済みのはず。
  本問は冪等な操作 (再 deps しても問題なし) として安全に通る。

## 解答例

詳細は [`8-3-multi-packages.solution.md`](8-3-multi-packages.solution.md) を参照。
