# Topic ② raw 投入

> **テーマ**: source の物理境界を宣言する。dbt が触れない外部世界 (CSV) と dbt の論理世界 (`source(...)`) の境界をここで初めて定義し、freshness / loaded_at の鮮度契約まで持たせる。

## このトピックで学ぶこと

- 物理 schema / table と dbt 上の論理 source 名 (`source('raw', 'customers')`) を切り離す
- `sources.yml` で source ブロックを宣言、column-level description / test を付ける
- `freshness:` で「データの鮮度 SLA」を source 側に持たせる
- `dbt source freshness` で鮮度違反を warn / error で検知
- `dbt ls --select source:raw.*` で source 起点の DAG クエリ
- raw 層は `tests:` を staging より前に張れる (上流契約)

## 前提

- Topic ① 1-1〜1-9 完了 (`data/100-knock/topic-1/*.csv` が存在)
- MVP の dbt が動く (`dbt run` / `dbt test` 通る)
- `dbt/profiles.yml` の dev target が Postgres に繋がる

## 出力先

学習者が書くもの:
- `scripts/100-knock/topic-2/load_raw.py` — raw 投入スクリプト
- `dbt/models/100-knock/topic-2/sources.yml` — source 宣言
- `dbt/models/100-knock/topic-2/sources_alt.yml` — 別名 source (2-7)
- `docs/exercises/100-knock/topic-2-raw-load/runbook.md` — 投入手順 (2-10)

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 2-1 | 4 raw テーブル DDL + COPY | 物理境界の確定 |
| 2-2 | sources.yml に `name: raw_100knock` | 物理 ↔ 論理マッピング |
| 2-3 | column description | docs に raw 列の意味を載せる |
| 2-4 | freshness 宣言 | 鮮度 SLA を source に付ける |
| 2-5 | freshness で warn を発火 | SLA 違反の体感 |
| 2-6 | loaded_at 列の型 / TZ 整合 | Python 仕様と source 契約 |
| 2-7 | 別名 source (`raw_alt`) 追加 | 名前空間衝突回避 |
| 2-8 | `dbt ls --select source:` | source 起点 DAG クエリ |
| 2-9 | source レベルの test (unique / not_null) | staging より前の契約 |
| 2-10 | runbook.md 化 | dbt の前にやることを言語化 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-2-2-sources-yml
```

CI 採点はブランチ名に `exercise-100-knock-2-N-...` を含めて push。
