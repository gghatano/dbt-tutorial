# Topic ⑨ パフォーマンス

> **テーマ**: 物理依存 (時間・コスト・リソース) を宣言で抑える。materialization は「物理的にどう保存するか」、incremental strategy は「差分をどう扱うか」、`+threads` と `state:modified+` は「並列性と build 範囲」、`pre/post hook` の `analyze` / `index` は「物理最適化を model に張る」宣言。

## このトピックで学ぶこと

- materialization 4 種 (view / table / incremental / ephemeral) の選択基準
- `incremental_strategy` 3 種 (append / delete+insert / merge) の冪等性比較
- `merge_exclude_columns` (1.6+) で列単位の merge 制御
- `post_hook` で index / analyze を model に付随
- `dbt_project.yml` の階層的 materialization 宣言と config() override
- `threads` で並列度宣言、DAG が許す並列性の理解
- `--select state:modified+` で変更影響範囲を manifest 差分から導出
- `dbt build` における run + test の依存ガード (test 失敗 → 下流 SKIP)
- incremental の ROI を時間で定量化

## 前提

- Topic ② 〜 ⑦ + ⑧ 完了
- 9-6 / 9-7 は dbt_project.yml / profiles.yml 編集 (Step 5 ロールバック)
- 9-10 は大規模ダミー (10万行) を生成するため CI で時間がかかる

## 10 問

| # | テーマ |
|---|---|
| 9-1 | materialization 3 通りで build 時間比較 |
| 9-2 | mart_orders を incremental + merge |
| 9-3 | 3 strategy (append / delete+insert / merge) 比較 |
| 9-4 | merge_exclude_columns で列単位制御 |
| 9-5 | post_hook で index 発行、explain analyze |
| 9-6 | dbt_project.yml で materialization 階層宣言 |
| 9-7 | threads 4 → 8 で並列性測定 |
| 9-8 | --select state:modified+ で差分 build |
| 9-9 | dbt build で test 失敗 → 下流 SKIP |
| 9-10 | 10万行で incremental の ROI を数値化 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-9-2-incremental-merge
```
