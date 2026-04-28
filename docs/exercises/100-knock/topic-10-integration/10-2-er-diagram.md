# 10-2: ER 図を Mermaid `erDiagram` で書き、PK/FK/cardinality を明示する

## シナリオ

10-1 で要件を文章で書いた。次は **論理データモデル** を絵にする。「subscriptions は customers に N:1 で属する」「subscription_events は subscriptions に N:1 で属する」というカーディナリティは、文章で書くと曖昧になりがちだが、ER 図で書くと **記号で一意に定義** できる。

GitHub / VS Code / dbt docs はすべて Mermaid をネイティブレンダリングする。`erDiagram` ブロックを 1 つ書くだけで、レビュアーが「Mermaid Live Editor を開いて貼る」手間なしに図を見られる。**ER 図は 10-3 (sources.yml) / 10-4 (staging contract) で「列を何にするか」を決める参照点** になる — 後段ですべて使う。

本問では `docs/exercises/100-knock/topic-10-integration/learner/er-diagram.md` を作り、選んだドメイン (subscriptions 推奨、10-1 と同じ) のエンティティ最低 2 つ + 既存の `customers` を含めて、Mermaid `erDiagram` ブロック 1 つを書く。

## 学べること

- Mermaid `erDiagram` の基本シンタックス (`||--o{` / `||--||` / `}o--o{`)
- PK / FK を `PK` / `FK` ラベルで明示する書式
- 1:1 / 1:N / N:N の cardinality を **コードで** 表現する習慣
- ER 図 → source 宣言 (10-3) → staging 列定義 (10-4) のトレーサビリティ
- Markdown ファイル 1 つに ER 図を埋め込む運用 (PR レビューで diff が見える)

## 前提

- 10-1 完了 (要件定義 1 ページが書かれている)
- Mermaid 文法の超基礎 (任意): <https://mermaid.js.org/syntax/entityRelationshipDiagram.html>
- VS Code に Markdown Preview Mermaid Support 拡張を入れておくとプレビュー確認が楽

## 入力データ

不要。学習者が Mermaid を書くだけ。

## 課題

### Step 1: er-diagram.md を新規作成

`docs/exercises/100-knock/topic-10-integration/learner/er-diagram.md`:

```markdown
# Subscriptions ドメイン ER 図

> 100-knock Topic ⑩ 10-2 の成果物。要件定義 (10-1) で宣言した
> 「subscriptions ↔ customers の N:1」「subscription_events ↔ subscriptions の N:1」
> を Mermaid `erDiagram` で図示する。

## ER 図

\`\`\`mermaid
erDiagram
    customers ||--o{ subscriptions : "has"
    subscriptions ||--o{ subscription_events : "logs"

    customers {
        bigint customer_id PK
        text   customer_name
        text   email
        timestamptz created_at
    }
    subscriptions {
        bigint subscription_id PK
        bigint customer_id FK
        text   plan_code
        numeric monthly_price
        timestamptz subscribed_at
        timestamptz canceled_at
    }
    subscription_events {
        bigint event_id PK
        bigint subscription_id FK
        text   event_type
        timestamptz event_at
        jsonb  payload
    }
\`\`\`

## カーディナリティ解説

- `customers ||--o{ subscriptions`: 1 顧客は 0..N 個の subscription を持つ
- `subscriptions ||--o{ subscription_events`: 1 subscription は 0..N 個のイベントを持つ
- ER 図と要件定義 (10-1) の対応: ...
```

(ファイル本文の Mermaid ブロックは ` ``` ` で囲む。本 README ではエスケープ表記)

### Step 2: 必須要件

- ファイルに **`erDiagram`** 文字列が含まれる
- ファイルに cardinality 表記が **少なくとも 1 つ** 含まれる (`||--o{` / `||--||` / `}o--o{` のいずれか)
- ER 図にエンティティが **少なくとも 2 つ** 定義されている (`customers { ... }` / `subscriptions { ... }` のように `{ }` ブロック)
- 各エンティティに `PK` ラベルの列が 1 つ以上ある

### Step 3: プレビュー確認 (任意)

VS Code の Markdown Preview で `er-diagram.md` を開き、Mermaid ブロックが図として描画されることを目視。GitHub に push しても同じく描画される。

### Step 4: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-10-integration/10-2-er-diagram.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-10-integration/learner/er-diagram.md` が存在
- [ ] `mermaid` ブロックを開く ` ```mermaid ` が含まれる
- [ ] `erDiagram` キーワードが含まれる
- [ ] 少なくとも 1 つの cardinality 記号 (`||--o{` 等) が含まれる
- [ ] 少なくとも 2 つのエンティティブロック (`<name> { ... }`) が含まれる
- [ ] 各エンティティに `PK` 表記の列が 1 つ以上ある

## ヒント (詰まったら)

- **cardinality 記号の意味**:
  - `||--||` = 1:1 (両端 1)
  - `||--o{` = 1:N (左端 1、右端 0..N)
  - `}o--o{` = N:N (両端 0..N)
  - `||--|{` = 1:N (右端 1..N、必須側あり)
  - 左半分 / 右半分の記号それぞれが **片側のカーディナリティ** を示す
- **`PK` / `FK` ラベル**: 列定義の末尾に `PK` または `FK` を書く。複数主キーは `PK,FK` のような併記も可。
- **データ型は SQL 互換でなくてよい**: `bigint` / `text` / `timestamptz` のように Postgres 型を書いておくと 10-3 / 10-4 で sources.yml / staging に直訳できる。
- **既存ドメインの `customers` を入れる意義**: 新規ドメインが既存ドメインと **どこで接続するか** が一目で分かる。10-3 の source は新規 2 テーブルだけだが、ER 図には接続先 `customers` も必ず描く。
- **3 つ目以降のエンティティ**: `plans` (プラン マスタ) や `payment_methods` を足すと豊かになる。本問は最低 2 つ + 既存 1 つ = 3 つで十分。
- **Mermaid が GitHub で描画されない**: コードフェンスが ` ```mermaid ` で正しく開かれているか確認。タイポ ( ` ```mermade ` 等) で素の text として表示される事故が多い。
- **`erDiagram` 以外の Mermaid タイプ**: `flowchart` でも DAG は描けるが、エンティティ + 関係 + 列定義を 1 つの図で表現できるのは `erDiagram` だけ。本問は erDiagram 限定。
- **将来の拡張**: 10-8 (設計レビュー) では本 ER 図に **`groups:` 境界** を矩形で囲む拡張を入れることが推奨される。10-2 では最小構成で OK。

## 解答例

詳細は [`10-2-er-diagram.solution.md`](10-2-er-diagram.solution.md) を参照。
