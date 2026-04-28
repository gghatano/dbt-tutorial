# 10-10: (open-ended / 集大成) 自分の DAG を「次の人に引き継ぐ」HANDOVER.md を書き、PR で残す

## シナリオ

100 本ノック最終問。10-1 〜 10-9 で構築 / 設計 / レビューしてきた DAG を、**「次の人に引き継ぐ」** 想定で `HANDOVER.md` にまとめる。

10-8 (design_review.md) との違い:

- **10-8**: 設計判断 / 迷いを記録する **設計ノート** (将来の自分のリマインダー)
- **10-10**: 別の人 / 別チームに **引き継ぐ前提** の **公式ドキュメント** (運用フロー含む)

10-10 の本質は **「自分の DAG をチーム資産に昇華する」**。コードと運用の両方が揃って初めて成果物。本問はその両方を 1 つの md に記録し、**Pull Request として diff を残す**。

PR 化することで:

- 「いつ HANDOVER したか」 が git log に残る
- 引き継ぎ先のレビューを受けられる (コメント / approve)
- 後の HANDOVER 改訂 (v2 / v3) との差分が辿れる
- README からリンクされ、新人 onboarding の起点になる

> **重要**: これも open-ended。完成版に正解はない。**「6 要素が網羅されているか」 が機械採点、内容の質は人間レビュー前提**。

## 学べること

- HANDOVER ドキュメントの **6 要素**:
  1. 要件定義 link (10-1 へ)
  2. ER 図 (10-2 / 10-8 から再掲)
  3. KPI と source の対応表 (10-1 で書いた KPI 3 つを source 列にマッピング)
  4. 運用フロー (`dbt build` と `dbt source freshness` をいつ誰が回すか)
  5. 既知の TODO / リスク 3 つ
  6. 「自分なら次はこう拡張する」 展望 1 段落
- **PR でドキュメントを残す** 文化 (= ドキュメントもコードと同じレビュー対象)
- 100 本ノックを通じて学んだ **「依存宣言 5 軸 (データ / スキーマ / 開発 / テスト / 可視化)」 を 1 つのドキュメントに統合する** 力
- **「次の人」を想像する** 力 (= 引き継ぎ先がいない場合は「6 ヶ月後の自分」)

## 前提

- 10-1 〜 10-9 完了
- 学習者の成果物配置: `docs/exercises/100-knock/topic-10-integration/learner/HANDOVER.md`
- git PR を作る環境 (GitHub) があること

## 入力データ

なし。

## 課題

### Step 1: ファイル作成 (PR ブランチで)

```bash
git checkout -b exercise-100-knock-10-10-handover
mkdir -p docs/exercises/100-knock/topic-10-integration/learner
touch docs/exercises/100-knock/topic-10-integration/learner/HANDOVER.md
```

### Step 2: 必須 6 要素を書く

`HANDOVER.md` に以下 6 要素を **必ず** 含める。各要素に対応するキーワードを本文中に必ず登場させる:

| # | 要素 | 必須キーワード (grep 対象) |
|---|---|---|
| 1 | 要件定義 link | `要件定義` |
| 2 | ER 図 | `ER` |
| 3 | KPI と source の対応表 | `KPI` |
| 4 | 運用フロー | `運用` |
| 5 | 既知の TODO / リスク 3 つ | `TODO` |
| 6 | 展望 1 段落 | `展望` |

最低 1 回はキーワードが本文に登場すること。

### Step 3: 文字数 2000 以上

集大成なので 10-8 (1500) より長め。2000 文字以上を目安に。

### Step 4: PR を作る

```bash
git add docs/exercises/100-knock/topic-10-integration/learner/HANDOVER.md
git commit -m "100-knock 10-10: HANDOVER.md (DAG 引き継ぎドキュメント)"
git push origin exercise-100-knock-10-10-handover
gh pr create --title "100-knock 10-10: HANDOVER" --body "Topic ⑩ 集大成。次の人に引き継ぎ用の DAG ドキュメント。"
```

PR の URL を `learner/HANDOVER.md` の冒頭にも書いておく (= 自己参照)。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-10-integration/10-10-handover-doc.grading.yaml
```

## 完了条件

- [ ] `learner/HANDOVER.md` が存在
- [ ] 6 必須キーワード (`要件定義` / `ER` / `KPI` / `運用` / `TODO` / `展望`) が本文中にある
- [ ] 文字数 2000 以上
- [ ] PR として diff が残っている (= GitHub 上に PR が存在)
- [ ] (人間レビュー軸): 引き継ぎ先が読んで「明日からこれで運用できる」 と感じる内容か

## 評価軸 (人間レビュー前提、CI では検証しない)

| 軸 | 評価ポイント |
|---|---|
| **要件定義 link が機能しているか** | 10-1 で書いた `requirements.md` への相対 link が壊れていない、要件と KPI が紐づいて読める |
| **KPI ↔ source の対応表が具体的か** | 「churn rate ← raw.subscription_events」 のように KPI 行 ↔ source 列まで具体的に表化 |
| **運用フローが「明日から回せる」か** | `dbt build --select +exposure:*_100knock` の頻度 / 失敗時の連絡先 / 手動再実行の手順が明記 |
| **TODO / リスク 3 つが本物か** | 「テスト不足」 のような形式的なものではなく、「**snapshot の strategy が timestamp なので、updated_at が更新されない場合変更検知できない**」 のような具体的リスク |
| **展望が次の判断に繋がるか** | 「次は何を追加するか」「現在の限界はどこか」「いつ revisit すべきか」 が 1 段落で書かれている |

人間レビュー (引き継ぎ先 / 上長) が読んで **「明日からこれで運用できる」 と感じれば PASS**、「まだ口頭で説明が必要」 なら不足。

## ヒント (詰まったら)

- **6 要素テンプレ**:
  ```markdown
  # HANDOVER: subscription ドメイン DAG

  ## 0. このドキュメントの目的
  次の担当者に subscription ドメインの dbt DAG を引き継ぐ。

  ## 1. 要件定義
  → [`learner/requirements.md`](requirements.md) (10-1 で作成)
  - ステークホルダー: ...
  - KPI 3 つ: churn / MRR / active_subscribers
  - SLA: 24h / 1h / 24h

  ## 2. ER 図
  → 10-2 の Mermaid `erDiagram` を再掲 or リンク
  ```mermaid
  erDiagram ...
  ```

  ## 3. KPI と source の対応表
  | KPI | mart | source |
  |---|---|---|
  | churn rate | mart_churn_summary | raw.subscription_events.event_type='cancel' |
  | MRR | mart_subscription_revenue | raw.subscriptions.plan_amount |
  | active subscribers | mart_active_subscribers | raw.subscriptions.status='active' |

  ## 4. 運用フロー
  - **日次 (毎朝 6:00)**: `bash scripts/100-knock/topic-10/ci/dbt_check.sh`
  - **freshness 失敗時**: #data-on-call slack に通知、raw 投入 job を確認
  - **build 失敗時**: PR の差分 model を確認 → revert or 修正

  ## 5. 既知の TODO / リスク 3 つ
  1. **snapshot の strategy が timestamp**: updated_at が更新されない場合変更検知できない → check strategy への移行を検討
  2. **`mart_active_subscribers` の grain が customer**: subscriptions が複数プランある場合の集約ルールが暗黙
  3. **prod-manifest が手動更新**: nightly job 化が未着手

  ## 6. 展望
  次に追加するなら subscription_pricing_history snapshot で価格変更を時系列追跡したい。MRR の精度が上がる。半年後には ML 用の churn prediction feature を mart_ml_features として切り出すと自然。
  ```

- **「次の人」 がいない単独学習者の場合**: 「6 ヶ月後の自分」 を引き継ぎ先と想定。これは 10-8 / 10-9 と同じ思想。
- **PR 化のコツ**: PR description にも HANDOVER の TL;DR を貼る (= 引き継ぎ先が PR 一覧から内容を把握できる)。
- **6 要素を全部書いて 2000 字に届かない場合**: 各要素に「**なぜそうしたか**」 を 1 文ずつ追加すると自然に膨らむ。形式埋めではなく理由を書く習慣。
- **TODO / リスク 3 つの選び方**: 「まだ着手していない改善」 だけでなく **「現在の運用の脆い部分」 を含める**。脆さは未来の障害の予告であり、引き継ぎ時に最も伝えるべき情報。
- **展望は 1 段落で OK**: 「次の人がインスピレーションを得るための種」。詳細な計画ではなく方向性を示す。

## 解答例

詳細は [`10-10-handover-doc.solution.md`](10-10-handover-doc.solution.md) を参照。**「3 つの典型解 + 各 trade-off」** を比較表で示しており、唯一の正解ではない。

## 100 本ノック 全完走おめでとう

10-10 が PASS したら、100 本ノック完走。

- **動く SQL を書く人** から **他チームに引き継げる依存関係グラフを設計する人** へ
- 100 問すべての宣言 (data / schema / dev / test / viz) が 1 つの DAG として組み上がった
- HANDOVER.md (本問) は **その全成果物の入り口** になる

PR を merge する前に、もう一度自分の DAG を `dbt docs serve` で眺めてみよう。100 問前と比べて、何が見えるようになっただろうか。
