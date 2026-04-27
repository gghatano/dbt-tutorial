# Topic ④ 中間モデル (intermediate)

> **テーマ**: 結合 grain と派生計算を宣言、DAG の中継ハブを設計する。複数 staging を「業務的に意味のある grain」に揃え直して束ね、下流 mart は `ref()` 1 行から「どの grain を相手にしているか」を読み取れる状態にする。

## このトピックで学ぶこと

- grain を冒頭コメント + `schema.yml` description + `unique` test の 3 点セットで宣言
- 複数 staging を `ref()` で結合し DAG の中継ノードを作る
- `dbt_utils.generate_surrogate_key` で複合 PK を 1 列化
- `int を切る/切らない` の判断軸 (再利用回数 + grain 統一 + テスト集約)
- materialization (view / table / ephemeral) の選択基準
- macro による開発の依存集約 (`calc_tax(amount, rate)` など)
- model versions (1.5+) で「下流を壊さない schema 進化」

## 前提

- Topic ② ③ 完了 (`stg_*_100knock` が存在)
- 4-3 / 5-2 / 5-9 で dbt-utils + dbt-expectations を `packages.yml` に追加 (任意問の前提)
- 学習者の int model は `dbt/models/100-knock/topic-4/` に置く
- model 命名: `int_<name>_100knock` (MVP の int_order_details と衝突回避)

## 10 問

| # | テーマ | 主な学び |
|---|---|---|
| 4-1 | int_order_details の grain 宣言 | grain 3 点セット |
| 4-2 | grain 違反を singular test で検知 | grain 契約のテスト依存 |
| 4-3 | int_customer_daily_activity (複合 PK) | dbt_utils + 複合 grain |
| 4-4 | int あり vs int なしを比較 | int を切る判断 |
| 4-5 | int の fan-out (1 中継 → N mart) | 依存伝播の感覚 |
| 4-6 | 税計算 macro で開発依存集約 | 1 macro → N model |
| 4-7 | view → table 切替で build 時間比較 | materialization トレードオフ |
| 4-8 | ephemeral で CTE 展開 | 物理を持たない依存 |
| 4-9 | description でカタログ化 | スキーマ依存の宣言 |
| 4-10 | model versions で v1/v2 並走 | 壊さない schema 進化 |

## 採点

```bash
python3 scripts/grader/grade.py --exercise 100-knock-4-1-int-order-details
```

CI: ブランチ名に `exercise-100-knock-4-N-...` を含めて push。
