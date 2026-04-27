# 2-7: 別名 source (`raw_alt`) を追加して名前空間衝突を回避する練習

## シナリオ

実務では「同じ物理 `raw` schema を、ある analytics チームは `source('raw', ...)` として、別の experimentation チームは `source('raw_alt', ...)` として参照したい」という需要が出る。たとえば「実験用に column 説明や test を別運用したい」「ある特定の分析パスだけ freshness 契約を厳しめにしたい」という分岐がここに収まる。

dbt 上の `source` 名は `package` 内でユニーク (= 同じプロジェクト内で `name: raw` を 2 回宣言できない) なので、別名 (`raw_alt`) として 4 テーブルを再宣言することで「**同じ物理を、別の論理 source として覗く**」というパターンを覚える。これは `dbt ls --select source:raw_alt.*` で別ビュー扱いになり、後で「raw_alt のみ freshness を厳しくする」「raw_alt のみ列名 description を実験用に書き換える」といった用途別の独立運用が可能になる。

## 学べること

- `sources.yml` の `name:` がプロジェクト内ユニーク制約を持つこと
- 1 つの物理 schema を **複数の論理 source 名** で宣言できる柔軟性
- ファイル分割 (`sources.yml` と `sources_alt.yml`) で「責務別に YAML を切る」運用パターン
- `dbt parse` が両方を manifest に登録すること、`dbt ls --select source:raw_alt.*` で独立に列挙できること

## 前提

- 2-2 で `dbt/models/100-knock/topic-2/sources.yml` が `name: raw` で 4 テーブル宣言済み
- ローカル Postgres + raw schema が起動している
- `cd dbt && dbt parse --profiles-dir .` が通る状態

## 入力データ

不要 (本問は宣言ファイルだけを追加する)。

## 課題

### Step 1: 別名 source ファイルを書く

`dbt/models/100-knock/topic-2/sources_alt.yml` を新規作成。要件:

- `version: 2`
- `sources:` 配下に 1 つの source を宣言
- `name: raw_alt` (これが別名のキモ)
- `schema: raw` (物理 schema は同じ `raw` を指す)
- `database:` は省略 (profile の default を使う)
- `tables:` に **4 件** すべて (`customers`, `products`, `stores`, `orders`)
- 各 table に `description:` を 1 行 (実験用ビューであることを明記)
- 列レベルの `tests:` は **書かない** (元の `sources.yml` 側で持つ。ここでは別名宣言だけが目的)

### Step 2: dbt parse で manifest 登録を確認

```bash
cd dbt && ../.venv/bin/dbt parse --profiles-dir .
# Found N sources, ... の表示で source 数が +4 されていれば登録済み

../.venv/bin/dbt ls --profiles-dir . --select 'source:raw_alt.*'
# source:local_analytics.raw_alt.customers
# source:local_analytics.raw_alt.products
# source:local_analytics.raw_alt.stores
# source:local_analytics.raw_alt.orders
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-7-source-namespace.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-2/sources_alt.yml` が存在する
- [ ] その中に `name: raw_alt` の source ブロックがある
- [ ] `schema: raw` で物理は元と同じ
- [ ] 4 テーブル (`customers` / `products` / `stores` / `orders`) が宣言されている
- [ ] `dbt parse` が成功する (構文エラー無し)
- [ ] manifest に `source.local_analytics.raw_alt.customers` が登録される

## ヒント (詰まったら)

- **同じ `name:` を 2 回は書けない**: 既存 `sources.yml` の `name: raw` と同じ名前で並行に書こうとすると `Duplicate source error` で `dbt parse` が落ちる。`raw_alt` のように **別名** にするのが必須条件。
- **ファイル分割の理由**: 物理的に 1 ファイルにマージしても dbt は動くが、責務が違う宣言を 1 ファイルに混ぜると「実験用なのか本運用なのか」が読み取れなくなる。**1 ファイル 1 責務** が読み手に優しい。
- **`schema:` を別にする選択肢**: `schema: raw_experimental` のように物理側も分けることも可能。本問は「**同じ物理を別論理で見る**」演習なので `schema: raw` を維持する。
- **manifest node id の規則**: `source.<project_name>.<source_name>.<table_name>` という形。本プロジェクトの `dbt_project.yml` は `name: 'local_analytics'` なので `source.local_analytics.raw_alt.customers` になる。
- **`dbt ls` のセレクタ**: `source:raw_alt.*` は「`raw_alt` 名前空間のすべての table」を列挙する。ワイルドカードを忘れると 0 件になる。

## 解答例

詳細は [`2-7-source-namespace.solution.md`](2-7-source-namespace.solution.md) を参照。
