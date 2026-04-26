# ADR 0005: dbt プロジェクト設定 (schema 解決 / dbt_utils 不採用 / target schema)

- 日付: 2026-04-26
- ステータス: Accepted
- コンテキスト: phase-04/task-001 `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/macros/get_custom_schema.sql`

## 背景

spec §4 で各層を Postgres schema (`raw`, `staging`, `intermediate`, `marts`) と 1:1 で対応させており、Terraform でも同名の schema が dbt_user owner で作成済み (ADR-0004 関連)。dbt 側でも各層の `+schema:` 指定がそのまま Postgres schema にマップされる必要がある。

## 決定

### 1. `generate_schema_name` macro を override する

`dbt/macros/get_custom_schema.sql` で標準 macro `generate_schema_name(custom_schema_name, node)` を override し、`custom_schema_name` が与えられたときはそれをそのまま返す。

```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

### 2. `profiles.yml` の `target.schema` を `staging` に固定

custom macro と組み合わせる前提で「明示指定が無いモデル」のフォールバックを `staging` にする。staging が一番モデル数が多い層なので fallback 先として自然。

### 3. dbt_utils を採用しない

`dbt/packages.yml` は `packages: []` として空にする。`unit_price >= 0` `quantity > 0` のような数値制約は phase-06 の **singular test (`tests/assert_*.sql`)** で実装する方針。

## 検討した案

### schema 解決方式

| 案 | 説明 | 採否 |
|---|---|---|
| A. macro override (採用) | `custom_schema_name` をそのまま返す | **採用** |
| B. profile 単位で別 target を切る | 各層ごとに target を分け、`schema:` を直接書く | 不採用 |
| C. デフォルト挙動を受け入れる | `<target_schema>_<custom>` の prefix を許容、Terraform 側を書き換え | 不採用 |

### dbt_utils 採用可否

| 案 | 説明 | 採否 |
|---|---|---|
| A. dbt_utils を入れる | `expression_is_true`, `accepted_range` などを使える | 不採用 |
| B. built-in + singular test (採用) | not_null/unique/relationships のみ + tests/*.sql | **採用** |

## 採用理由

### 1 (macro override)

1. **spec §4 と Terraform の schema 命名と完全一致する**: `marts.mart_daily_sales` のような spec 表記がそのまま実 schema 名になる。dbt_project.yml の `+schema: marts` と Postgres `marts` schema が 1:1。
2. **profile を 1 つに保てる**: 開発と本番が無いローカル学習環境で target を増やすのは過剰。
3. **dbt 公式が推奨するプラクティスの 1 つ**: `generate_schema_name` の override は dbt docs で正規の拡張ポイントとして紹介されている。

### 2 (target.schema = staging)

- custom macro により `+schema` 明示モデルは絶対 schema に解決される。`+schema` 未指定のモデル（あれば）は `target.schema = staging` にフォールバックするので、staging に置くのが妥当。
- もし target.schema を `public` 等にすると未分類モデルが想定外の場所に出る恐れがある。

### 3 (dbt_utils 不採用)

1. **学習用最小構成 (spec §14)**: 「最初からAirflow / クラウドDWHは入れない」と同じ思想で、dbt_utils も最初は入れない。
2. **task-001.md の判断ログ**: 「packages: 初期はdbt_utilsを入れない（最小構成）。必要になったら追加。」と明文化済み。
3. **spec §9 で要求されるテストは built-in + singular で全て表現可能**: `sales_amount >= 0` 等は `tests/assert_*.sql` で書ける（phase-06 の責務）。
4. **依存追加のたびに lock 衝突や hub 接続を気にしなくて済む**: ローカル学習環境のセットアップ時間を圧迫しない。

## 不採用案の理由

- **B (target 分け)**: profile を太くする割に得られる柔軟性が薄い。dev/prod 分離は将来 phase で追加すべき検討事項であり、層ごとの schema 分離とは独立。
- **C (prefix を受け入れる)**: spec/Terraform 側を曲げることになるので方向が逆。
- **dbt_utils 採用**: 現フェーズで必要なテストは built-in だけで網羅でき、追加コストに対する便益が低い。

## 関連する決定

- `relationships` テスト引数は dbt 1.11 から `arguments:` キー配下にネストすることが推奨される (deprecation `MissingArgumentsPropertyInGenericTestDeprecation`)。`schema.yml` ではこの新形式を採用する。
