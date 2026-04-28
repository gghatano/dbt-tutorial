# dbt 100 本ノック

[Issue #2](https://github.com/gghatano/dbt-tutorial/issues/2) の 100 本ノック実装。設計の根拠と全体構成は [`docs/exercises/100-knock-plan.md`](../100-knock-plan.md) を参照。

> ⚠️ 進行中: 全 10 トピック × 各 10 問のうち、現在実装済みの問は下表で `[x]` のものだけ。

---

## 全体マップ

| Topic | テーマ | 状況 |
|---|---|---|
| ① ダミーデータ生成 | データ仕様を Python で宣言 | 実装中 |
| ② raw 投入 | source の物理境界を宣言 | 未着手 |
| ③ staging | staging contract の宣言 | 未着手 |
| ④ 中間モデル | grain と派生計算を宣言 | 未着手 |
| ⑤ KPI / マート | BI 契約を宣言 | 未着手 |
| ⑥ データ品質・テスト | 不変条件を契約として宣言 | 未着手 |
| ⑦ 履歴管理 (snapshot) | 時間軸の同一性を宣言 | 未着手 |
| ⑧ 再利用 (Jinja) | 共通変換ロジックを集約 | 未着手 |
| ⑨ パフォーマンス | 物質化戦略を宣言 | 未着手 |
| ⑩ 統合 (実務再現) | DAG 全体を設計、レビュー可能に | 未着手 |

---

## ファイル配置

```text
docs/exercises/100-knock/
  README.md                              # 本ファイル
  topic-1-data-generation/
    README.md                            # トピック ① のイントロと到達点
    1-1-customers.md                     # 問題本文
    1-1-customers.solution.md            # 解答例
    1-1-customers.grading.yaml           # 採点定義 (CI が読む)
    1-2-products.md
    ...
scripts/100-knock/
  topic-1/
    generate_1_1_customers.py            # 解答に書かれた script の置き場 (学習者が自分で書く)
data/100-knock/
  topic-1/
    customers.csv                        # 生成出力 (gitignored)
    products.csv
```

各問は 3 ファイル (`*.md` + `*.solution.md` + `*.grading.yaml`)、必要に応じて 1 ファイル (generator script) のセット。

---

## 学習者の進め方

1. `topic-1-data-generation/README.md` で全体観を掴む
2. `1-N-*.md` を読み、自分で `scripts/100-knock/topic-1/generate_1_N_*.py` を書く
3. 実行して `data/100-knock/topic-1/*.csv` が生成されることを確認
4. 採点を試す: `python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-N-*.grading.yaml`
5. CI 採点: ブランチ名に `exercise-100-knock-1-N` を含めて push

---

## 採点 CI との接続

各問の `grading.yaml` は `docs/exercises/grading.md` の check 種別を組み合わせて構成。Topic ① では特に:

- `file_exists` — 生成スクリプトの存在
- `shell_command` — スクリプトを CI で実際に走らせる
- `csv_assert` — 生成 CSV の行数・列・unique・null 比率の検証

を多用する。

CI workflow `.github/workflows/grade.yml` がブランチ名から exercise を抽出。100 本ノックの命名規約は `exercise-100-knock-<topic>-<num>[-keyword]` (例: `exercise-100-knock-1-3-stores`) を予定。
