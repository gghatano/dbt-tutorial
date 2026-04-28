# 10-8 解答例

> **Topic ⑩ 後半は open-ended**: 1 つの正解はない。本解答は **「3 つの典型解 + 各 trade-off」** を比較表で示し、学習者が自分のコンテキストに合わせて選べるようにする。

## 3 つの典型解の比較

| 軸 | 典型解 A: 簡素版 (1500 字ぴったり) | 典型解 B: 中庸版 (3000 字、図表多め) | 典型解 C: 重厚版 (5000 字+、判断履歴 + ADR 形式) |
|---|---|---|---|
| **想定読者** | 自分 (リマインダー) | チームの新人 (1 人で読める) | 全社のデータエンジニア (公式ドキュメント) |
| **ER 図の扱い** | 10-2 の Mermaid をリンク | Mermaid を再掲 + 補足 1 段落 | Mermaid + 物理 schema 図 + 1:N の根拠 |
| **DAG screenshot** | 1 枚 (mart 中心) | 3 枚 (全体 / mart 拡大 / exposure 拡大) | 5 枚 + lineage の動画 (gif) |
| **SLA 表** | 主要 3 mart のみ | 全 mart + exposure の SLA | SLA + 過去 6 ヶ月の達成率 + 未達ケース |
| **設計判断** | 3 つを箇条書き | 3 つを各 200 字で説明 | ADR (Architecture Decision Record) 形式で 5 つ、却下案も記録 |
| **「迷い」の記述** | 「迷った」を最低 1 回 | 各判断に 1〜2 段落の trade-off 議論 | 採用案 / 代替案 / 棄却理由 の 3 段構成 |
| **執筆コスト** | 30 分 | 2 時間 | 1 日〜数日 |
| **trade-off** | 早い、形だけ揃う、後で読み返しても薄い | バランス◎、新人 onboarding に使える、書く時間あり | 圧倒的品質、書く時間なし、保守コスト高 |
| **推奨ケース** | 個人プロジェクト、初稿、急ぎ | チーム開発、初回 join 者向け | 全社プラットフォーム、SOC2 / ISO 監査対応 |

**機械採点はどの解でも PASS** (1500 字以上 + 4 セクション + 「迷った」「判断」3 回以上)。質的評価は読み手の用途次第。

---

## 典型解 A: 簡素版 (約 1500 字)

```markdown
# 100-knock Topic ⑩ 設計レビュー (簡素版)

## ER 図

10-2 で書いた `learner/er_diagram.md` を参照。subscriptions ↔ customers (1:N), subscription_events ↔ subscriptions (1:N) を Mermaid `erDiagram` で表現。

## DAG

`dbt docs serve` の lineage screenshot:

![DAG](dag_screenshot.png)

mart_churn_summary_100knock を中心に、上流 5 source + 4 staging + 2 intermediate、下流 2 exposure (churn_dashboard / active_subscribers_reverse_etl) が確認できる。

## SLA

| mart | 用途 | SLA |
|---|---|---|
| mart_churn_summary_100knock | 経営定例ダッシュボード | 24h |
| mart_active_subscribers_100knock | reverse ETL → Salesforce | 1h |
| mart_subscription_revenue_100knock | MRR 月次レポート | 24h |

## 設計判断

1. **mart の粒度を 3 つに分けた**: churn / revenue / active_subscribers。1 つにまとめると 50 列の wide mart になり読みにくい。**ここで迷った** が、用途別に分けて後で join できる方針を採用。
2. **groups: subscription_internal を 1 つにした**: events と subscriptions を同じ group に。理由は staging が型契約だけなので分ける必要を感じなかった。**判断**: 将来 mart の private 化が必要になれば分割する。
3. **exposure の maturity を最初から high に**: 経営定例で見られる前提なので medium スキップ。**判断**: 試作段階の exposure は別途 _draft suffix で分ける運用に。
```

(約 1500 字、最低限の 4 セクション + 「迷った」「判断」3 回以上)

---

## 典型解 B: 中庸版 (構成のみ、約 3000 字想定)

```markdown
# 100-knock Topic ⑩ 設計レビュー (中庸版)

## TL;DR
- 新ドメイン subscriptions を 1 周設計
- 主要 mart 3 本、exposure 2 つ (BI + reverse ETL)
- SLA: 経営 KPI 24h、営業 sync 1h

## ER 図
[Mermaid 再掲 + 1:N の根拠 1 段落]

## DAG
[全体 screenshot] + [mart 拡大] + [exposure 拡大] の 3 枚

## SLA
[全 mart + exposure の表 + 失敗時の連絡フロー]

## 設計判断 (3 つ)

### 判断 1: mart の粒度 (分割 vs 統合)
**採用**: 用途別 3 mart 分割
**代替案**: 1 wide mart
**理由**: 用途別の方が読みやすく、grant も分けやすい
**迷った点**: BI で join するコスト vs 列が多いコスト

### 判断 2: snapshot vs SCD type 2 自前実装
**採用**: dbt snapshot
**代替案**: staging で type 2 を自前実装
**理由**: snapshot は dbt が test も用意してくれる
**迷った点**: snapshot の strategy (timestamp vs check) どちらにするか

### 判断 3: exposure maturity の決め方
**採用**: 経営定例 / SaaS 連携は最初から high
**代替案**: 全部 medium で開始、本番リリースで high に昇格
**理由**: 開発段階から「壊したらダメ」を表明したい
**迷った点**: 試作 exposure をどう区別するか
```

(約 3000 字、各判断に trade-off 議論あり)

---

## 典型解 C: 重厚版 (構成のみ、約 5000 字+)

```markdown
# 100-knock Topic ⑩ 設計レビュー (ADR 形式)

## Executive Summary
[3 段落で背景 / 採用設計 / 残課題]

## ER 図 (論理 + 物理)
[Mermaid + 物理 schema DDL の対応表]

## DAG 全体図
[5 枚の screenshot + lineage gif]

## SLA & 達成率
[SLA 表 + 過去 6 ヶ月の達成率 + 未達 3 ケースの postmortem]

## ADR (Architecture Decision Records)

### ADR-001: mart 粒度の決定
- **Status**: Accepted (2026-04)
- **Context**: subscriptions ドメインで KPI が 3 種類 (churn / revenue / active)
- **Options**:
  - Option 1: 1 wide mart
  - Option 2: 用途別 3 mart 分割 (採用)
  - Option 3: 5 mart 細分化
- **Decision**: Option 2
- **Consequences**: BI 側で join 必要、grant 設定簡素

### ADR-002: snapshot 戦略
[同様]

### ADR-003: exposure maturity の運用
[同様]

### ADR-004: groups の境界 (却下案あり)
[同様]

### ADR-005: incremental strategy の選定
[同様]
```

(約 5000 字+、ADR 形式で各判断に Status / Context / Options / Decision / Consequences を構造化)

---

## どれを選ぶか?

学習者の状況で:

- **初めて Topic ⑩ をやる**: 典型解 A で十分。書いて出すことに価値がある
- **チーム開発を想定**: 典型解 B。新人 onboarding に使える
- **公開 OSS / 監査対応**: 典型解 C。ADR 形式で後から判断履歴を辿れる

**機械採点はどれも PASS** なので、自分のコンテキストに合わせて選ぶ。

---

## 解説まとめ

- **なぜ open-ended か**: 設計判断は **コンテキスト依存** で、唯一の正解がない。「mart を 1 つに統合する vs 3 つに分割する」 は会社規模 / チーム数 / BI ツールでベストプラクティスが変わる。教材で「正解はこうです」 と教えると **学習者が自分の頭で trade-off を考えなくなる** ので、open-ended にする。
- **なぜ「迷った」を書かせるか**: 実務で最も価値が高いドキュメントは **「採用案」よりも「却下した案とその理由」**。後で「なぜ A にしなかったのか」を後輩 / 将来の自分が必ず聞く。それに答えるためのドキュメント。ADR (Architecture Decision Record) 形式が最も厳密だが、簡易版でも「迷い」を書く習慣をつけるのが本問の狙い。
- **機械採点の限界**: 「形が整っているか」しか見ない。「内容が深いか」「他者が読んで理解できるか」は **必ず人間レビュー** が要る。本問の grading.yaml で「文字数 >= 1500」「キーワード 3 回以上」 だけを見るのはこの限界の表明。
- **「6 ヶ月後の自分」は他人**: 当時の判断理由は必ず忘れる。設計レビュー doc は **将来の自分への手紙**。これを書く習慣がつけば、コードと運用の両方が長持ちする。
- **3 つの典型解の本質的違い**: A は「自分への手紙」、B は「チーム onboarding 教材」、C は「全社の意思決定履歴」。**用途が違うだけで、どれが優れているという話ではない**。学習者は自分のコンテキストを理解して選ぶ。
- **次の問への接続**: 10-9 では「他者の DAG をレビューする」側に回る。本問で「自分の DAG を他者から読んでもらう側」を経験したので、視点反転がしやすい。10-10 では本問の design_review.md を発展させて HANDOVER.md (集大成) を書く。
