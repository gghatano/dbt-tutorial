# Topic ⑩ 統合 (実務再現)

> **テーマ**: ここまでに身につけた「データ・スキーマ・開発・テスト・可視化」5 種の依存宣言を **一つの DAG として組み上げる**。新規ドメイン (subscriptions / 在庫 / 配送) を題材に、要件 → ER → source → staging → mart → exposure → CI → docs まで 1 周し、**他者がレビューできる成果物** を残す。

## このトピックで学ぶこと

- 要件定義 → ER → source → staging → mart → exposure の温度感を統一
- 新規ドメインを 0 から DAG に組み込む手順
- `contract: enforced` / `groups:` / `access:` / `freshness:` で「壊れにくい・誰の責任か明確な」DAG
- CI 化 (`dbt build --select state:modified+ --defer --state ./prod-manifest/`)
- **設計判断 / 迷い / レビュー** を成果物として残す
- 他者の DAG を読んで指摘するスキル

## 前提

- Topic ① 〜 ⑨ 完了 (全 90 問が下地)
- 学習者の新規ドメイン成果物は `docs/exercises/100-knock/topic-10-integration/learner/` に置く
- 新規 source / model は `dbt/models/100-knock/topic-10/` 配下

## 10 問

| # | テーマ | 形式 |
|---|---|---|
| 10-1 | 要件定義 | 通常 |
| 10-2 | ER 図 (Mermaid erDiagram) | 通常 |
| 10-3 | 新規 source 宣言 + freshness | 通常 |
| 10-4 | staging contract: enforced (1.5+) | 通常 |
| 10-5 | groups: + access: で公開範囲 (1.5+) | 通常 |
| 10-6 | exposure 2 つ (dashboard + reverse_etl) | 通常 |
| 10-7 | CI スクリプト 1 行 | 通常 |
| 10-8 | **(open-ended)** 設計レビュー doc | レビュー型 |
| 10-9 | **(open-ended)** ペア (or 将来の自分) の DAG レビュー | レビュー型 |
| 10-10 | **(open-ended / 集大成)** HANDOVER.md を PR で残す | レビュー型 |

## open-ended 問の採点について

10-8 / 10-9 / 10-10 は **「正解が一つでない」設計判断問**。

- 採点 (機械): 必須セクションの存在、最小文字数、必須キーワード grep — **「書かれていれば部分点」**
- 評価 (人手前提): 「設計判断が言語化されているか」「他者が読めるか」「依存方向が説明できるか」
- 解答例: `1 つの正解` ではなく **「3 つの典型解 + 各 trade-off」** を比較表で示す

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-10-1-requirements
```

## ゴール

「動く SQL を書く人」から「**他チームに引き継げる依存関係グラフを設計する人**」へ。

dbt は「個々の model が動くこと」より「DAG 全体が他者から読める・直せる・拡張できる」ことに価値がある。Topic ⑩ の HANDOVER.md (10-10) を PR で残せば、それがそのままチーム資産になる。
