# Topic ⑤ KPI / マート (mart)

> **テーマ**: mart は dbt の世界が外 (BI / ML / API) と接続する境界面。grain・列契約 (`contract: enforced`)・誰が使っているか (`exposure:`) の 3 つを揃えて初めて完成する。

## このトピックで学ぶこと

- mart の grain 宣言 (BI が GROUP BY する単位)
- 業務しきい値 (`avg_rating>=4 AND review_count>=10` など) を SQL で表現
- 複合 grain には `dbt_utils.generate_surrogate_key`
- **`contract: enforced` (1.5+)** で型まで含めた対外契約
- 契約違反 → CI red の体験
- `exposure:` で BI 依存を機械可読化
- `+grants:` config で readonly_user に SELECT 自動付与 (hook 不要)
- `groups:` + `access:` で公開範囲を宣言 (1.5+)
- `meta:` で運用情報 (owner, slack_channel, sla_hours) を持たせる
- `dbt-expectations` で業務範囲テスト
- model version + 並走 mart で「BI を壊さずに段階移行」

## 前提

- Topic ② ③ ④ 完了 (`stg_*_100knock`, `int_*_100knock` が存在)
- dbt-utils + dbt-expectations を `packages.yml` に追加 (Topic ⑦ 相当の前提、5-2 / 5-9)
- 学習者の mart は `dbt/models/100-knock/topic-5/` に置く
- model 命名: `mart_<name>_100knock` (MVP と衝突回避)

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 5-1 | mart_top_rated_products 再構築 + grain 宣言 | grain + 業務しきい値 |
| 5-2 | mart_monthly_sales_by_category (複合 PK) | dbt_utils + 複合 grain |
| 5-3 | mart_daily_sales に contract: enforced | 型まで含めた対外契約 |
| 5-4 | わざと型を変えて contract violation | 契約違反の経路を体感 |
| 5-5 | exposure で Metabase ダッシュボード宣言 | mart → BI 依存の機械可読化 |
| 5-6 | +grants: config で readonly_user 付与 | hook を使わない宣言的 grant |
| 5-7 | groups: + access: で公開範囲宣言 | mart のオーナーシップ |
| 5-8 | meta: で owner / SLA 宣言 | 運用契約の宣言 |
| 5-9 | dbt-expectations で業務範囲テスト | パッケージ test の活用 |
| 5-10 | int v2 を参照する並走 mart | 段階移行の手順 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-5-3-mart-contract-enforced
```

CI: ブランチ名に `exercise-100-knock-5-N-...` を含めて push。

## 注意

- 5-3 / 5-4 は dbt 1.5+ の `contract: enforced` 機能を使う
- 5-7 は dbt 1.5+ の `groups:` + `access:` 機能を使う
- 5-6 は MVP `dbt_project.yml` を編集する想定 (Step 5 にロールバック手順)
