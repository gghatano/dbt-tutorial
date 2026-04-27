# Topic ⑥ データ品質・テスト

> **テーマ**: モデルに付随するデータ契約 (data contract)。`schema.yml` で `not_null` / `unique` / `relationships` / `accepted_values` を宣言した瞬間、その列は DAG の中で型のように扱われる。コードレビューより前にデータ自身が契約遵守を主張する。

## このトピックで学ぶこと

- 組み込み generic test (`not_null` / `unique` / `relationships` / `accepted_values`) を schema.yml に宣言
- 自作 generic test (引数付き含む) で再利用可能契約
- singular test (`tests/*.sql`) でモデル限定の業務不変条件
- `severity: warn` で運用 SLO レベルの宣言
- `dbt-expectations` パッケージで regex / 範囲 / 統計テスト
- `--store-failures` で失敗行を `dbt_test__audit` に永続化
- `dbt_project.yml` の `data_tests:` でテスト運用ポリシーを宣言

## 前提

- Topic ② ③ ④ ⑤ 完了 (`stg/int/mart_*_100knock` が揃っている)
- 学習者の generic test は `dbt/tests/generic/`、singular test は `dbt/tests/100-knock/topic-6/`
- 6-10 だけ `dbt/dbt_project.yml` を編集 (Step 5 ロールバック)

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 6-1 | not_null + unique 宣言 | 主キー契約 |
| 6-2 | relationships で FK 契約 | 参照整合のテスト依存 |
| 6-3 | accepted_values で enum | 値域契約 |
| 6-4 | singular test (no_future_orders) | モデル限定の業務不変条件 |
| 6-5 | 自作 generic test (positive_value) | 再利用可能契約 |
| 6-6 | 引数付き generic test (allow_zero) | パラメータ付き契約 |
| 6-7 | severity: warn | 運用 SLO 宣言 |
| 6-8 | dbt-expectations regex | 外部 test ライブラリ |
| 6-9 | --store-failures で失敗行追跡 | デバッグループ |
| 6-10 | dbt_project.yml data_tests: 設定 | テスト運用ポリシーの宣言 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-6-1-not-null-unique
```

CI: ブランチ名に `exercise-100-knock-6-N-...` を含めて push。
