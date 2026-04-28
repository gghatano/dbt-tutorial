# 2-7 解答例

## dbt/models/100-knock/topic-2/sources_alt.yml (新規)

```yaml
version: 2

# Alternate logical source over the same physical raw schema.
# Use this namespace for experimental/analytics views that need their own
# description / test / freshness contract without touching the canonical
# `raw` declarations in sources.yml.
sources:
  - name: raw_alt
    schema: raw
    description: |
      Alternate logical view of the same physical `raw` schema.
      Use `source('raw_alt', '<table>')` when you want experimental column
      docs / tests / freshness rules independent from the canonical `raw`.
    tables:
      - name: customers
        description: "Customers (raw_alt namespace; same physical table as raw.customers)."
      - name: products
        description: "Products (raw_alt namespace)."
      - name: stores
        description: "Stores (raw_alt namespace)."
      - name: orders
        description: "Orders (raw_alt namespace)."
```

**ポイント**:

- **`name: raw_alt`**: ここがプロジェクト内ユニーク制約のキー。元の `sources.yml` 側 `name: raw` と衝突しない別名にすることで、`dbt parse` が両方を独立した source ノードとして manifest に登録する。
- **`schema: raw`**: 物理 schema は元と同じ。別の論理ラベルを貼るだけで物理は共有する、というのが本問の意図。
- **`tables:` 4 件すべて宣言**: 物理が同じでも、論理 source で「どの table を公開するか」は独立に選べる。たとえば実験用に `orders` だけ raw_alt 経由で覗く、という設計も可能。本問では学習目的で 4 件すべて宣言する。
- **列レベル test は書かない**: 元の `sources.yml` 側で `customer_id` などに `not_null` / `unique` が付いている。ここで重複して書くと「同じ物理に対して同じ test が 2 回走る」ことになり、CI 時間が増える。raw_alt 側の test は「別観点の test を足したいときだけ」追加する規律にする。

## 確認コマンド

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# Found N sources (4 つ増えている)

../.venv/bin/dbt ls --profiles-dir . --select 'source:raw_alt.*'
# source:local_analytics.raw_alt.customers
# source:local_analytics.raw_alt.products
# source:local_analytics.raw_alt.stores
# source:local_analytics.raw_alt.orders

# ついでに元の raw も列挙して衝突していないことを確認
../.venv/bin/dbt ls --profiles-dir . --select 'source:raw.*'
# source:local_analytics.raw.customers
# source:local_analytics.raw.products
# source:local_analytics.raw.stores
# source:local_analytics.raw.orders
```

## manifest.json での見え方

```bash
jq '.sources | keys | map(select(test("raw_alt")))' dbt/target/manifest.json
# [
#   "source.local_analytics.raw_alt.customers",
#   "source.local_analytics.raw_alt.orders",
#   "source.local_analytics.raw_alt.products",
#   "source.local_analytics.raw_alt.stores"
# ]
```

各 node id は `source.<project>.<source_name>.<table>` の規則。`<project>` は `dbt_project.yml` の `name:` (本プロジェクトでは `local_analytics`) から来る。

## 想定アンチパターン

### ❌ 同じ名前で並行宣言

```yaml
# sources_alt.yml
sources:
  - name: raw          # ← 既存 sources.yml と同じ名前
    schema: raw
    tables:
      - name: customers
```

→ `dbt parse` が `Compilation Error: dbt found two sources with the name "raw"` で落ちる。**name: は package 内でユニーク**。

### ❌ schema を間違える

```yaml
sources:
  - name: raw_alt
    schema: raw_experimental   # ← 物理が違う
```

→ 構文的には通るが、`raw_experimental` schema が存在しないと `select * from {{ source('raw_alt', 'customers') }}` を `ref` した model が runtime で `relation does not exist` で落ちる。本問の意図は「同じ物理を別論理で見る」なので `schema: raw` を維持する。

### ❌ database を不用意に書く

```yaml
sources:
  - name: raw_alt
    database: another_db       # ← profile の database と違う
    schema: raw
```

→ 別 DB 扱いになり、dbt が `another_db.raw.customers` を参照しようとして失敗。本プロジェクトは単一 DB なので `database:` は省略するか `analytics` (profile の値) を明示する。

## 解説まとめ

- **なぜ別名 source？**: 「同じ物理に複数の論理視点を貼れる」という dbt の柔軟性を体感させるため。実務では「dashboard 用の安定 source」「ML 用の鮮度厳格 source」「実験用の緩い source」といった切り分けに使う。
- **物理と論理の分離**: dbt の `source` は **論理名 (= 契約の単位)**、`schema` / `database` は **物理アドレス**。別名宣言は「同じ物理アドレスに別の契約を貼る」操作と理解できる。Web の DNS で同じ IP に複数の hostname を貼る発想に近い。
- **後続トピックでの使い道**: Topic ⑩ で「新ドメインを既存 source と分離して登録する」演習があるが、その下準備として「別名 source を増やす」という機械的操作に慣れておく価値がある。
- **YAML 分割の規律**: 1 ファイルに全 source を詰めると 200 行を超えやすい。`sources.yml` (canonical) / `sources_alt.yml` (alternate) のように **責務別に切る** のが大規模 dbt プロジェクトで生き残る秘訣。dbt は `models/**/*.yml` をすべて読むので、ファイル数が増えても登録順や lazy loading を気にする必要はない。
- **manifest 視点**: `dbt ls --select source:raw_alt.*` で「この別名でどの table が登録されているか」が機械的に列挙できるのは、後の selector 演習 (2-8) と同じ DAG クエリ言語の一部。
