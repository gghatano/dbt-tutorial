# Topic ⑧ 再利用 (Jinja / macro / package / seed)

> **テーマ**: 共通変換ロジックを 1 箇所に集約し、参照側は「呼ぶだけ」で同じロジックが効く。`{% macro %}` は自プロジェクト内のロジック依存元、`packages.yml` は外部プロジェクトへの依存、`seed` はコードと一緒に version 管理されるマスタへの依存。

## このトピックで学ぶこと

- macro による再利用 (`cast_money(col, precision, scale)` のような汎用 macro)
- `dbt_utils.generate_surrogate_key` で複合 PK を 1 列化
- 複数 packages の共存 (dbt-utils + dbt-expectations)
- seed (静的マスタの version 管理 + テスト)
- Jinja loop で全 staging に audit 列を一括追加 (`{% for %}` + pre_hook)
- `vars` で「ビジネスパラメータ」をコードから分離、CLI で上書き
- dispatch macro (`adapter.dispatch(...)`) で adapter 別実装 (多態)
- `+grants:` config で hook を使わない宣言的アクセス権限
- 自作 metric macro で KPI 集計式を 1 箇所に閉じ込め
- packages.yml の version pin と `package-lock.yml` の役割

## 前提

- Topic ② 〜 ⑦ 完了 (`stg/int/mart/snap_*_100knock` 系が揃っている)
- 学習者の macro は `dbt/macros/100-knock/topic-8/`、seed は `dbt/seeds/100-knock/topic-8/`
- 8-6 / 8-8 は dbt_project.yml 編集 (Step 5 ロールバック)

## 10 問

| # | テーマ |
|---|---|
| 8-1 | cast_money macro を 5 model から呼ぶ |
| 8-2 | dbt_utils.generate_surrogate_key で複合 PK |
| 8-3 | dbt-utils + dbt-expectations 共存 |
| 8-4 | seed: 祝日マスタ + accepted_values テスト |
| 8-5 | Jinja loop で audit 列一括追加 |
| 8-6 | vars でビジネスパラメータ + --vars 上書き |
| 8-7 | dispatch macro (default + postgres 別実装) |
| 8-8 | +grants: config で readonly_user 自動付与 |
| 8-9 | metric_revenue macro で KPI 式の集約 |
| 8-10 | packages.yml の version pin と lock の役割 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-8-1-cast-money-macro
```
