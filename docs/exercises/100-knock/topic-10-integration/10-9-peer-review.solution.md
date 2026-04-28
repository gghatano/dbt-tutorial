# 10-9 解答例

> **Topic ⑩ 後半は open-ended**: 1 つの正解はない。本解答は **「3 つの典型解 + 各 trade-off」** を比較表で示し、学習者がレビュー対象 / 自分のスタイルに合わせて選べるようにする。

## 3 つの典型解の比較

| 軸 | 典型解 A: 簡素レビュー (3 指摘 × 1 文ずつ) | 典型解 B: 標準レビュー (3 指摘 + 改善案 + 影響範囲数値) | 典型解 C: 厳密レビュー (各指摘に分析 + 修正案 patch) |
|---|---|---|---|
| **想定状況** | ペアレビュー会の初回、お互い遠慮あり | チームの定例コードレビュー | OSS リリース前の最終レビュー |
| **指摘の粒度** | 1 セクション 1 指摘 (3 指摘合計) | 1 セクション 2〜3 指摘 (合計 6〜9) | 1 セクション 5 指摘以上 (合計 15+) |
| **改善案の有無** | なし (気づきだけ) | 1 文の代替案 | patch / commit 単位で具体提案 |
| **影響範囲の客観化** | 「大きそう」 の感覚 | `dbt ls` 結果で N model に影響 | manifest 比較ツール (dbt-checkpoint) で数値化 |
| **言い方** | 「気になった」 | 「~~ するとより読みやすい」 | 「Before / After + 理由」 形式 |
| **執筆コスト** | 30 分 | 1〜2 時間 | 半日 |
| **trade-off** | 形だけ整う、深い議論にならない | バランス◎、PR レビューに直接転用可 | 厳密、書く時間が長い、相手の負担も大きい |
| **推奨ケース** | 初めてペアレビュー、心理安全性優先 | チーム内の通常レビュー | 公開前の最終チェック、新人 onboarding |

**機械採点はどの解でも PASS** (3 セクション + 各 >= 100 文字)。質的評価は人間レビュー軸。

---

## 典型解 A: 簡素レビュー (約 400 字)

```markdown
# 100-knock Topic ⑩ 設計レビューフィードバック (簡素版)

レビュー対象: 6 ヶ月前の自分の DAG (subscription ドメイン)

## 依存方向

`mart_churn_summary_100knock` が `stg_subscriptions_100knock` を直接 ref している箇所が気になった。本来は `int_subscription_lifecycle_100knock` を経由すべきで、staging 直接参照は **層の責務違反** に見える。staging の grain が変わると mart が壊れる結合度がある。

## 命名

`mart_*_100knock` と `mart_*` (suffix なし) のファイルが混在している。`mart_subscription_revenue` (suffix なし) と `mart_churn_summary_100knock` (suffix あり) の不揃い。MVP との衝突回避が目的なら **全 mart に suffix 統一** が望ましい。

## 影響範囲

`stg_subscription_events_100knock` を `dbt ls --select +stg_subscription_events_100knock+` で確認すると **下流 8 model + 2 exposure** に影響することが分かった。staging 1 列追加 / 変更で広範囲に波及するので、変更時は必ず PR で `--select state:modified+` の dry-run を共有する運用が望ましい。
```

(各セクション 100〜150 字、合計約 400 字、3 セクション + キーワード OK)

---

## 典型解 B: 標準レビュー (構成のみ、約 1500 字想定)

```markdown
# 100-knock Topic ⑩ 設計レビューフィードバック (標準版)

レビュー対象: pair-learner の DAG / commit hash: abc123

## 依存方向

### 指摘 1: mart → staging 直接参照
`mart_churn_summary` が `stg_subscriptions` を直接 ref。intermediate 抜きで結合度が高い。
**改善案**: `int_subscription_lifecycle` を新設し、mart はそこから ref する。

### 指摘 2: intermediate 同士の参照
`int_subscription_revenue` が `int_subscription_lifecycle` を ref。層内参照は混乱の元。
**改善案**: 共通計算を更に上流の `int_subscription_base` に切り出し、両者がそこから ref する DAG に。

## 命名

### 指摘 1: suffix 揺れ
`_100knock` 付き / なしが混在。
**改善案**: 全 100-knock model に suffix 統一。

### 指摘 2: 集計列の揺れ
`total_amount` / `sum_amount` の混在。
**改善案**: 全 mart で `total_*` か `sum_*` に統一、CONTRIBUTING.md に明記。

## 影響範囲

### `stg_subscription_events_100knock` の影響
`dbt ls --select +stg_subscription_events_100knock+` で **下流 8 model + 2 exposure** に影響。
変更時は影響範囲を PR description に貼る運用が望ましい。

### `mart_active_subscribers_100knock` の影響
`dbt ls --select +exposure:active_subscribers_reverse_etl_100knock` で確認すると、本 mart 失敗 = Salesforce 同期停止 = 営業活動データ古化、と影響が業務側に伝播する。SLA 1h を徹底する根拠。
```

(約 1500 字、各セクションに複数指摘 + 改善案 + 影響範囲数値)

---

## 典型解 C: 厳密レビュー (構成のみ、約 3000 字+)

```markdown
# 100-knock Topic ⑩ 設計レビューフィードバック (厳密版)

レビュー対象: pair-learner DAG / PR #42 / commit abc123def456

## サマリ
- Critical: 2 件 (依存方向 1 / 影響範囲 1)
- Major: 3 件 (命名 2 / 依存方向 1)
- Minor: 5 件 (命名 3 / 影響範囲 2)

## 依存方向

### Critical 1: mart → staging 直接参照 (mart_churn_summary)
**Before**:
```sql
-- mart_churn_summary_100knock.sql
select ... from {{ ref('stg_subscriptions_100knock') }}
```
**After**:
```sql
-- mart_churn_summary_100knock.sql
select ... from {{ ref('int_subscription_lifecycle_100knock') }}
```
**理由**: staging の grain (1 行 = 1 subscription record) と mart の grain (1 行 = 1 customer の churn 状態) が違う。intermediate で grain 変換すべき。
**影響**: stg_subscriptions に列追加すると mart が壊れる結合度が下がる。

### Major 1: intermediate 層内参照
[同様]

## 命名
[3 指摘、各 Before / After]

## 影響範囲

### Critical 1: stg_subscription_events_100knock の高 fan-out
`dbt ls --select +stg_subscription_events_100knock+`:
- 下流: 8 model + 2 exposure
- うち maturity: high の exposure: 1
**推奨**: PR テンプレに `--select state:modified+` 結果を貼る欄を追加。
[Minor 2 指摘]

## まとめ
- Critical 2 件は merge 前に修正必須
- Major 3 件は次の sprint で改修
- Minor 5 件は backlog で issue 化
```

(約 3000 字+、Severity 区分 + Before/After + Reasoning)

---

## どれを選ぶか?

- **初めてペアレビュー / 心理安全性優先**: 典型解 A
- **チーム定例レビュー / PR 標準フロー**: 典型解 B
- **OSS / 監査前最終チェック**: 典型解 C

**機械採点はどれも PASS**。状況に合わせて選ぶ。

---

## 解説まとめ

- **なぜ 3 観点 (依存方向 / 命名 / 影響範囲)?**: dbt の DAG レビューで **最も価値ある観点** がこの 3 つ。
  - **依存方向**: 層 (raw / staging / intermediate / mart) の責務違反を見つける。staging → mart の直接参照、intermediate 同士の参照などが "悪い匂い"
  - **命名**: 一貫性は読みやすさと検索性を左右する。`mart_daily_*` vs `mart_*_daily` の揺れがあるだけで `dbt ls` で grep できなくなる
  - **影響範囲**: `dbt ls --select +<model>+` で機械的に出せる。「変更前にこれを必ず見る」 文化を作る根拠になる
- **「指摘の正しさより指摘できたこと」を評価する理由**: 初学者がレビューに参加するハードルは「指摘が間違っていたら恥ずかしい」 という心理。本問は **指摘の数 / 形を評価軸にし、内容の正しさは人間レビューに委ねる** ことで心理障壁を下げる。「とにかく指摘を 3 つ書く」 を体験することで、レビュー筋力がつく。
- **なぜ open-ended か**: レビューは **コンテキスト依存**。同じ DAG でも、新人 onboarding 用なら命名規約を厳しく見る、本番リリース前なら影響範囲を厳しく見る、と力点が変わる。「正解はこうです」 と教えるのは害悪で、本問では学習者自身が状況に合わせて重み付けする練習をする。
- **「将来の自分」レビューの威力**: 自分が書いたコードを 1 週間後に読み返すと **半分は他人が書いたコードに見える**。これがコードレビューの最良の練習場。1 人で学習している場合でも本問を実践できる。
- **指摘の言い方の重要性**: 「ダメ」 ではなく「気になった」、「悪い」 ではなく「~~ するとより読みやすい」、「なんでこうしたの」 ではなく「~~ の理由を教えてほしい」。**心理安全性のあるレビュー** が良いレビュー文化の前提。本問の人間レビュー軸でこれを評価する。
- **自分の DAG にも同じ問題が**: 他者を見て指摘した問題の半分は自分の DAG にも潜んでいる。レビューを書きながら **自分の修正点メモ** も作ると、自分の DAG が同時に改善される。これは「他者を見ることが自分を見ること」の実例。
- **`dbt ls --select +<model>+` の力**: 影響範囲を **数値で語れる** のが dbt の強み。「大きく影響する」 という主観ではなく「下流 8 model に影響」 という客観で議論できる。レビュー時に必ず使うコマンド。
- **次の問への接続**: 10-10 (集大成 HANDOVER.md) では本問のレビュー観点が「**自分の DAG を引き継ぐとき何を書き残すべきか**」 に直結する。「依存方向 / 命名 / 影響範囲」 の 3 観点は HANDOVER.md の必須項目になる。
