# 10-10 解答例

> **Topic ⑩ 集大成**: 100 本ノック最終問。1 つの正解はない。本解答は **「3 つの典型解 + 各 trade-off」** を比較表で示す。

## 3 つの典型解の比較

| 軸 | 典型解 A: 必要最小 (2000 字、6 要素のみ) | 典型解 B: 標準 (4000 字、図 + 表 + 運用 runbook) | 典型解 C: 全面 (8000 字+、ADR + DR plan + on-call 手順) |
|---|---|---|---|
| **想定引き継ぎ先** | 後任 1 人、1 日で onboarding | 後任 + チームメンバー数名 | 別チーム / 監査対応 / 災害復旧計画含む |
| **要件定義の扱い** | 10-1 へ link のみ | link + サマリ 1 段落 | link + 全 KPI を列挙 + 過去変更履歴 |
| **ER 図** | Mermaid 1 枚 | Mermaid + 物理 schema 図 | Mermaid + DDL + 関係性の根拠 + 異常系の対応 |
| **KPI ↔ source 表** | 3 KPI × 1 source | 3 KPI × 複数 source + 計算式 | 3 KPI + 中間計算 + 過去 6 ヶ月の変動 |
| **運用フロー** | コマンド + 頻度 | runbook (手順 + 失敗時対応) | runbook + on-call rotation + escalation matrix |
| **TODO / リスク** | 3 つを 1 文ずつ | 3 つを各 1 段落 (impact 評価付き) | 全 risk を severity 別に表化、mitigation 計画付き |
| **展望** | 1 段落 | 1 段落 + 半年後 / 1 年後 | roadmap (Q1 / Q2 / Q3) |
| **PR の作り方** | 1 commit | 段階的に commit、PR 内で議論 | RFC 形式、複数レビュアー approve |
| **執筆コスト** | 2 時間 | 半日 | 数日〜1 週間 |
| **trade-off** | 速い、機械採点 PASS、後で読み返すと薄い | バランス◎、新人 onboarding 直接利用可 | 厳密、書く時間長い、保守コスト高 |
| **推奨ケース** | 個人 / 小チーム、急ぎ引き継ぎ | 通常のチーム引き継ぎ | 全社プラットフォーム、SOC2 監査、災害復旧計画 |

**機械採点はどれも PASS** (6 キーワード + 2000 字)。質的評価は引き継ぎ先の状況による。

---

## 典型解 A: 必要最小 (約 2000 字)

```markdown
# HANDOVER: 100-knock subscription ドメイン DAG

PR: https://github.com/.../pull/N (本ドキュメントの diff)
最終更新: 2026-04-26
著者: gakikame0405@gmail.com

## 0. このドキュメントの目的

100-knock Topic ⑩ で構築した subscription ドメインの dbt DAG を次の担当者に引き継ぐ。
本書 1 通で「明日からこの DAG を運用できる」 ことを目標とする。

## 1. 要件定義

詳細: [`requirements.md`](requirements.md) (10-1 で作成)

- ステークホルダー: 経営定例 / Sales Ops / Finance
- KPI 3 つ: churn rate / MRR / active subscribers
- SLA: 24h (BI) / 1h (reverse ETL) / 24h (月次レポート)
- 想定アクセス頻度: BI = 週次、reverse ETL = 1h ごと

## 2. ER 図

詳細は 10-2 / 10-8 の Mermaid `erDiagram` を参照。

要点: `customers ↔ subscriptions` 1:N、`subscriptions ↔ subscription_events` 1:N。FK は orders→customers と同じ向き。

## 3. KPI と source の対応表

| KPI | mart | source 主要列 |
|---|---|---|
| churn rate | mart_churn_summary_100knock | raw.subscription_events.event_type='cancel' |
| MRR | mart_subscription_revenue_100knock | raw.subscriptions.plan_amount |
| active subscribers | mart_active_subscribers_100knock | raw.subscriptions.status='active' |

KPI 計算式の正本は各 mart の `description:` フィールドに記載。

## 4. 運用フロー

| 頻度 | コマンド | 失敗時連絡先 |
|---|---|---|
| 日次 (毎朝 6:00) | `bash scripts/100-knock/topic-10/ci/dbt_check.sh` | #data-on-call |
| PR ごと | GitHub Actions が `dbt_check.sh` を実行 | PR コメント |
| 週次 (月曜) | `dbt source freshness` 単独実行 | #data-platform |

freshness 失敗 → raw 投入 job (Airflow / cron) を確認。
build 失敗 → PR の差分 model を確認 → revert or 修正。

## 5. 既知の TODO / リスク 3 つ

1. **snapshot の strategy が timestamp**: `updated_at` が更新されない異常系で変更検知できない。check strategy への移行が望ましい。
2. **`mart_active_subscribers` の grain が customer**: 1 customer 複数プランの場合の集約ルールが暗黙。明示宣言が必要。
3. **prod-manifest が手動更新**: 10-7 の `--state` defer の前提となる prod-manifest を nightly で自動更新する pipeline が未着手。今は手動コピー。

## 6. 展望

次に追加するなら `subscription_pricing_history` snapshot で価格変更を時系列追跡したい。MRR の精度が上がる。半年後には ML 用の churn prediction feature を `mart_ml_features` として切り出すと自然。1 年後の理想は、本 HANDOVER.md が新人 onboarding の起点になり、本ドキュメントを読むだけで subscription ドメインの全体像が掴める状態。
```

(約 2000 字、6 必須要素すべてを網羅)

---

## 典型解 B: 標準 (構成のみ、約 4000 字想定)

```markdown
# HANDOVER: subscription ドメイン DAG (v1)

## 0. 目次 + TL;DR

## 1. 要件定義
- link
- サマリ 1 段落
- ステークホルダー連絡先

## 2. ER 図
- Mermaid 再掲
- 物理 schema 図
- 1:N の根拠

## 3. KPI ↔ source 対応表
- KPI 計算式詳細
- source の鮮度 SLA
- 過去のデータ品質事故 1 件 (再発防止策)

## 4. 運用 runbook
### 4.1 通常運用
- 日次 / 週次 / 月次のコマンド一覧
### 4.2 失敗時対応
- freshness 失敗 → 手順 1, 2, 3
- build 失敗 → 手順 1, 2, 3
- exposure 影響 → 手順 1, 2, 3
### 4.3 手動再実行
- `dbt build --full-refresh` の使い方
- `--exclude` で特定 model を外す方法

## 5. TODO / リスク (3 つ + impact 評価)
### 5.1 snapshot strategy (impact: medium)
- 詳細
- mitigation 案
### 5.2 mart_active_subscribers の grain (impact: high)
### 5.3 prod-manifest 自動更新 (impact: low)

## 6. 展望
- 半年後の追加機能候補 3 つ
- 1 年後の理想形
- 5 年後の方向性
```

(約 4000 字、各セクションに impact 評価と段階的詳細)

---

## 典型解 C: 全面 (構成のみ、約 8000 字+)

```markdown
# HANDOVER: subscription ドメイン DAG (RFC v1.0)

## 1. Executive Summary
[3 段落]

## 2. 要件定義 + 過去変更履歴
[link + 全 KPI 列挙 + 過去 1 年の要件変更]

## 3. ER 図 + DDL
[Mermaid + 物理 DDL + 関係性根拠 + 異常系対応]

## 4. KPI ↔ source ↔ 中間計算 ↔ 過去変動
[完全な対応表 + 計算式 + 過去 6 ヶ月のグラフ]

## 5. 運用 runbook + on-call rotation
### 5.1 Daily / Weekly / Monthly
### 5.2 Incident response (Sev 1 / 2 / 3)
### 5.3 Escalation matrix
### 5.4 On-call rotation (週次 / 4 人体制)
### 5.5 Postmortem template

## 6. Risk register
| Severity | Risk | Mitigation | Owner | Due |
[全 risk を表化]

## 7. 展望 (Roadmap)
### Q1 2026
### Q2 2026
### Q3 2026
### 1 year horizon

## Appendix A: ADR (Architecture Decision Records)
- ADR-001 〜 ADR-NNN

## Appendix B: Disaster Recovery Plan
- 障害シナリオ 5 種別の復旧手順
```

(約 8000 字+、RFC / SOC2 監査対応レベル)

---

## どれを選ぶか?

- **個人 / 小チーム / 急ぎ引き継ぎ**: 典型解 A
- **通常のチーム引き継ぎ / 新人 onboarding**: 典型解 B
- **全社プラットフォーム / 監査対応 / 災害復旧計画**: 典型解 C

**機械採点はどれも PASS** なので、引き継ぎ先の状況に合わせて選ぶ。

---

## 解説まとめ

- **なぜ HANDOVER doc?**: dbt の DAG は **コードだけでは引き継げない**。「KPI 計算の意図」「freshness が古いときの対応」「過去の設計判断」 などコードに書かれない情報が大量にある。HANDOVER.md はそれらを 1 つの md に集約する成果物。
- **6 要素の必然性**:
  1. **要件定義 link**: 「なぜ作ったか」 が分からないと運用判断ができない
  2. **ER 図**: 「何を扱っているか」 の物理イメージ
  3. **KPI ↔ source 対応表**: 「どう計算しているか」 の正本 (= データリネージュの集約)
  4. **運用フロー**: 「明日から誰が何を回すか」
  5. **TODO / リスク**: 「何が脆いか」 (= 未来の障害の予告)
  6. **展望**: 「次に何を考えるべきか」 (= 引き継ぎ先のインスピレーション源)
- **PR で残す意義**:
  - **git log に残る**: 「いつ HANDOVER したか」 が時系列で辿れる
  - **レビューを受けられる**: 引き継ぎ先がコメント / approve で参加できる
  - **diff が記録される**: HANDOVER v2 / v3 の改訂履歴が辿れる
  - **README からリンク**: 新人 onboarding の起点になる
  - 単に Confluence / Notion に書くより **コードと同じレビュー文化** に乗せられる
- **「次の人」 が想像できない人へ**: 「6 ヶ月後の自分」 が他人。当時の設計理由は必ず忘れる。HANDOVER.md は **将来の自分への手紙** でもある。1 人で学習中でも HANDOVER を書く価値は十分。
- **TODO / リスクが本物かの判定**: 「テスト不足」 は形式的すぎる。**「snapshot の strategy が timestamp なので、updated_at が更新されない異常系で変更検知できない」** のような **具体的な条件 + 影響** まで書けるかが分かれ目。これが書ければ実務で「リスク管理ができる」 と評価される。
- **展望が次の判断に繋がるか**: 「もっと良くしたい」 ではなく「**XX を追加すれば YY が改善される**」 まで踏み込むと引き継ぎ先のインスピレーション源になる。「自分なら次はこう拡張する」 の 1 段落は本問の隠れ重要要素。
- **100 本ノック完走の意味**:
  - **入力 (Topic ① ② ③)** で「物理から論理への翻訳」を宣言として残す
  - **モデリング (④ ⑤)** で「grain と KPI 契約」を宣言として残す
  - **品質 (⑥)** で「不変条件」を宣言として残す
  - **時間軸 (⑦)** で「同一性の歴史」を宣言として残す
  - **再利用 (⑧)** で「共通変換ロジック」を 1 箇所に集約
  - **物質化 (⑨)** で「実行戦略」を宣言として残す
  - **統合 (⑩)** で「DAG 全体を他者が読める形」 にまとめる
  - 100 問すべてが「**何かを宣言として書き残す**」の繰り返しだったことに気づく。dbt の本質は SQL ではなく **依存関係の宣言** にある。
- **HANDOVER.md は集大成**: 100 問の全成果物の **入り口** になる。新人がこの 1 ページを読めば DAG 全体に潜入できる状態を作るのが理想。100 本ノックを終えた今、自分にはそれが書けるはず。
- **次は実務 / 自分のプロジェクトで**: 100 本ノックを終えたら、自分の業務 / OSS プロジェクトで同じことを実践する。**「動く SQL を書く人」 から「他チームに引き継げる依存関係グラフを設計する人」 へ** の移行は、本問の HANDOVER.md を書ききった瞬間に完了する。
