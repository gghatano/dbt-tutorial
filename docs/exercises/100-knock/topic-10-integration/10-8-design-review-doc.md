# 10-8: (open-ended) 自分の DAG 設計を design_review.md にまとめる

## シナリオ

10-1〜10-6 で **新ドメインの DAG** を構築した:

- 要件定義 (10-1) → ER 図 (10-2) → source + freshness (10-3) → staging contract (10-4) → groups + access (10-5) → exposure (10-6)

10-7 で CI 化までやった。技術的には DAG が動いている。しかし **「他者がこの DAG を読んだとき何が分かるか」** はまだ言語化されていない。

本問では `learner/design_review.md` にまとめる:

- ER 図 (10-2 の流用 OK)
- DAG screenshot リンク (`dbt docs serve` の lineage 画面)
- 主要 mart の SLA (10-6 の `meta.sla_hours` をまとめ直す)
- 「**ここで判断に迷った**」と書く設計判断 3 つ

> **重要**: 本問は **正解が一つではない** open-ended 問。完成版に正解はなく、**設計ノートとして残すこと自体が成果物**。
>
> 採点は機械的だが、「内容の質」は評価しない。**「書かれていれば部分点」** の方針。
> 評価軸は本来 **人間レビュー前提**。CI で見るのは「形式が整っているか」のみ。

## 学べること

- 自分の設計判断を **言語化** する力 (これが一番習得しづらい)
- ER 図 / DAG screenshot / SLA / 設計判断の 4 点セットで「他者にレビューしてもらえる単位」を作る感覚
- 「迷った」と書く勇気 (実務では「迷った点を後輩に伝える」が最も価値が高い)
- markdown のセクション構造化スキル (ER, DAG, SLA, 設計判断 の 4 見出し)

## 前提

- 10-1 〜 10-7 完了 (新ドメイン DAG が技術的に動いている)
- `dbt docs generate && dbt docs serve` で lineage を見られる状態
- 学習者の成果物配置: `docs/exercises/100-knock/topic-10-integration/learner/design_review.md`

## 入力データ

なし。学習者の設計判断を文章化するだけ。

## 課題

### Step 1: ファイル作成

```bash
mkdir -p docs/exercises/100-knock/topic-10-integration/learner
touch docs/exercises/100-knock/topic-10-integration/learner/design_review.md
```

### Step 2: 必須セクション 4 つを書く

`design_review.md` に以下 4 セクションを **必ず** 含める (見出しは H2 = `## ` で):

1. **`## ER 図`** — 10-2 で書いた Mermaid `erDiagram` を再掲 (or リンク)
2. **`## DAG`** — `dbt docs serve` の lineage screenshot リンク (画像 path or 外部 URL)
3. **`## SLA`** — 主要 mart / exposure の SLA 表 (例: 24h / 1h)
4. **`## 設計判断`** — 「ここで迷った」と書く 3 つ以上の設計判断

### Step 3: 文字数 / キーワードの確認

- 全体で **1500 文字以上**
- 本文中に「**迷った**」「**判断**」 のキーワードが合計 3 回以上 (= 設計判断の数 3 つ)

### Step 4: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-10-integration/10-8-design-review-doc.grading.yaml
```

## 完了条件

- [ ] `learner/design_review.md` が存在する
- [ ] H2 見出しに `ER 図` / `DAG` / `SLA` / `設計判断` の 4 つが含まれる
- [ ] 文字数 1500 以上
- [ ] 「迷った」「判断」キーワードが 3 つ以上
- [ ] (人間レビュー軸): **設計判断が他者から読んで意味が取れるか**

## 評価軸 (人間レビュー前提、CI では検証しない)

機械採点は「形が整っているか」のみ。本来の評価軸は以下:

| 軸 | 評価ポイント |
|---|---|
| **言語化されているか** | 「なぜそう設計したか」が **理由付きで** 書かれている (`A にした` だけではなく `B / C も検討したが trade-off で A を選んだ` まで書く) |
| **他者が読めるか** | 専門用語の補足、図 / 表の活用、結論を最初に置く構造 (PREP 法など) |
| **依存方向が説明できるか** | DAG の上流 / 下流の依存方向と、それを selector でどう辿るかが書かれている |
| **迷いが正直か** | 「**ここで迷った**」が形式的でなく、実際の trade-off を伴っているか (例: 「mart を分割するか統合するか」「snapshot を使うか slowly changing dimension type 2 を実装するか」) |

人間レビュー (チームメンバー / 将来の自分) が読み返したとき **「6 ヶ月後の自分が当時の判断を再現できるか」** が究極の評価軸。

## ヒント (詰まったら)

- **「迷った 3 つ」のネタ案**:
  1. **mart の粒度**: 「churn を 1 mart に集約 vs 月次 / コホート別で 3 mart に分割」
  2. **snapshot vs SCD type 2 自前実装**: 「dbt snapshot を使うか、staging で type 2 を自前で書くか」
  3. **incremental の merge strategy**: 「`merge` vs `delete+insert` vs `append` のどれにしたか」
  4. **groups の境界**: 「subscription_internal を 1 group にするか、events と subscriptions で分けるか」
  5. **exposure の maturity**: 「最初から `high` にするか、`medium` から始めて昇格させるか」
- **DAG screenshot の取り方**:
  1. `cd dbt && dbt docs generate --profiles-dir .`
  2. `dbt docs serve --profiles-dir .` でブラウザ起動
  3. lineage アイコン (左下) → 自分の mart や exposure を選択
  4. ブラウザの screenshot (Cmd+Shift+4 等) → `learner/dag_screenshot.png` に保存
  5. md からは `![DAG](dag_screenshot.png)` で参照
- **ER 図は 10-2 の流用で OK**: 10-2 で Mermaid `erDiagram` を書いている前提なので、それをそのまま貼る or 「10-2 を参照」のリンクで十分。
- **完成版に正解はない**: 形式が整っていれば PASS。**「迷い 1 つ書くだけで満点 / 3 つ書いても満点が変わらない」のは仕様** (機械採点の限界)。質的評価は人間レビューに委ねる設計。
- **「迷った」を書きづらい場合**: 形式的に「~~ にした (理由: ~~)。代替案として ~~ も検討したが、trade-off で前者を採用」のテンプレに当てはめる。形式さえ書けば言語化できる。
- **将来の自分が読む前提**: 6 ヶ月後の自分は他人。「あの時なんでこう設計したっけ」を防ぐドキュメント。

## 解答例

詳細は [`10-8-design-review-doc.solution.md`](10-8-design-review-doc.solution.md) を参照。**「3 つの典型解 + trade-off」** を比較表で示しており、唯一の正解ではない。
