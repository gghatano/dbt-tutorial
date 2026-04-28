# Topic ③ staging (整形)

> **テーマ**: staging contract を宣言する。raw の物理事情 (列名・型・null 表現・表記揺れ) を staging で必ず吸収し、`schema.yml` に `tests:` / `description:` をモデルの隣にコロケート。下流が「staging が嘘をついていない前提」で書ける状態を作る。

## このトピックで学ぶこと

- `ref()` で source → staging のエッジを DAG に作る
- 列ごとの明示型 cast (`::date`, `::numeric(10,2)`)
- `lower(trim(...))` 等の正規化を staging で吸収
- `schema.yml` に `not_null` / `unique` / `relationships` を宣言
- 自作 generic test (`positive_value`) を再利用
- model / column の `description:` で docs カタログ化
- materialization (`view`) をプロジェクト config で一括宣言
- `dbt run --select +stg_X+` で DAG 演算子を使う
- `dbt build --select <selector>` でレイヤー単位の合格判定

## 前提

- Topic ② 2-1〜2-5 完了 (`dbt/models/100-knock/topic-2/sources.yml` で `raw_100knock` source が宣言済み)
- MVP の `dbt/macros/get_custom_schema.sql` がそのまま使える
- 学習者の staging model は `dbt/models/100-knock/topic-3/` に置く (MVP の `dbt/models/staging/` は触らない)
- model 命名は `stg_<table>_100knock` (MVP との衝突回避)

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 3-1 | `stg_customers_100knock` を view + 型 cast | source → staging エッジ |
| 3-2 | `stg_products_100knock` で category を `lower(trim(...))` | 表記揺れの吸収 |
| 3-3 | `stg_orders_100knock` で日付・numeric 明示型 | 型契約 |
| 3-4 | `schema.yml` で not_null / unique / relationships | PK / FK 契約 |
| 3-5 | 自作 generic test `positive_value` を適用 | ドメインルール契約 |
| 3-6 | description を model / column に書く | docs カタログ化 |
| 3-7 | 命名規約を README 化、`dbt parse` を CI に | 暗黙規約の明示 |
| 3-8 | `dbt_project.yml` で materialization 一括宣言 | レイヤー contract |
| 3-9 | `dbt run --select +stg_X+` で依存伝播確認 | DAG 演算子 |
| 3-10 | `dbt build --select staging` でレイヤー合格 | run + test の同時実行 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-3-4-schema-yml-tests
```

CI: ブランチ名に `exercise-100-knock-3-N-...` を含めて push。

## 注意

- 3-8 のみ `dbt/dbt_project.yml` を学習者が編集する想定。Step 5 にロールバック手順を記載
- それ以外の問は MVP ファイルを一切触らず、`dbt/models/100-knock/topic-3/` に閉じ込める
