# 10-1: 新規ドメインの要件定義を 1 ページにまとめる

## シナリオ

Topic ① 〜 ⑨ で身につけた dbt の各機能を、いきなり SQL から書き始めると **「何を解こうとしているか」が消えた DAG** が出来上がる。半年後にレビューに入った人 (あるいは未来の自分) は、`mart_subscription_mrr.sql` を読んでも「なぜ MRR を mart にしたのか」「誰がこの数字を見るのか」「いつまでに更新されているべきか」が分からない。

Topic ⑩ の最初の 1 問は **「DAG を書く前に書くべき 1 ページ」** を残すこと。学習者は新規ドメイン (推奨: subscriptions = 顧客の月額課金。または在庫 / 配送 / 広告でも可) を選び、`docs/exercises/100-knock/topic-10-integration/learner/requirements.md` に以下を 800 文字以上で書き起こす。

- **ステークホルダー** (誰が何の判断にこの DAG を使うか)
- **KPI 3 つ** (それぞれの定義、粒度、更新頻度)
- **提供したい mart 3 本** (各 mart の grain と主な列)
- **想定アクセス頻度** (1 日何回読まれるか、ピーク時間帯)
- **SLA** (鮮度 / 障害時の連絡先 / 復旧目標時間)

これが後続の 10-2 (ER 図) / 10-3 (source) / 10-4 (staging contract) / 10-5 (groups) のすべての出発点になる。**この 1 ページが書けないドメインは、DAG にする準備ができていない**。

## 学べること

- 「要件定義 → 技術成果物」の対応を 1 ページで描く習慣
- ステークホルダーを **named list** で書く価値 (口伝の限界)
- KPI を 3 つに **絞り込む** ことの設計判断 (= 何を mart にしないかの宣言)
- SLA を最初に決めることで `freshness:` / `groups:` の owner が自ずと決まる
- ドキュメントが「書かれていれば部分点」になる grading の運用感

## 前提

- Topic ① 〜 ⑨ 完了 (既存ドメイン EC = customers / products / orders / stores の DAG を 1 周している)
- `docs/exercises/100-knock/topic-10-integration/learner/` ディレクトリが存在 (`.gitkeep` のみ。学習者がこのディレクトリにファイルを置く)

## 入力データ

不要。学習者が文章を書くだけ。

## 課題

### Step 1: ドメインを 1 つ選ぶ

推奨: **subscriptions** (顧客の月額契約)。既存の `customers` を再利用できるため、後続の 10-3 で source を追加するだけで済む。

代替候補:

- **在庫** (`stock_movements` / `warehouses`) — 既存の `products` / `stores` を再利用
- **配送** (`shipments` / `couriers`) — 既存の `orders` を再利用
- **広告** (`ad_impressions` / `campaigns`) — 既存の `products` を再利用

本問〜10-7 まで、選んだドメインで一貫させる。

### Step 2: requirements.md を書く

`docs/exercises/100-knock/topic-10-integration/learner/requirements.md` を新規作成。以下のセクションを **必ず含める** (見出しは `## ステークホルダー` のように `##` で書く):

1. **ステークホルダー** — 例: 「経営企画 (週次の MRR レビューで参照)」「カスタマーサクセス (チャーン顧客リストで日次運用)」「経理 (月次決算で MRR を会計報告に転記)」
2. **KPI** 3 つ — 例: MRR (月次経常収益) / Churn Rate (月次解約率) / ARPU (顧客あたり平均収益)。各 KPI は **定義 + 粒度 + 更新頻度** を 1 行で書く
3. **mart** 3 本 — 例: `mart_subscription_mrr_100knock` (月次 grain) / `mart_subscription_churn_100knock` (顧客 × 月 grain) / `mart_subscription_active_100knock` (顧客 grain、最新スナップショット)
4. **想定アクセス頻度** — 例: 「経営定例 (毎週月曜 9:00) に手動 read」「Metabase ダッシュボード経由で 1 日 50 read」
5. **SLA** — 例: `freshness: warn 24h / error 48h`、「障害時は #data-platform に連絡」、「復旧目標時間 4h」

最低 800 文字 (採点で文字数チェックされる)。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-10-integration/10-1-requirements.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-10-integration/learner/requirements.md` が存在
- [ ] ファイル内に `ステークホルダー` / `KPI` / `mart` / `SLA` の 4 キーワードがすべて出現
- [ ] ファイルの本文が 800 文字以上
- [ ] 「KPI 3 つ」が箇条書き (or 番号付き) で 3 項目以上列挙されている
- [ ] 「mart 3 本」が箇条書きで 3 項目以上列挙されている

## ヒント (詰まったら)

- **「800 文字」は小説ではない**: 1 セクションあたり 150〜200 文字程度の現実的な分量。「KPI: MRR (月次経常収益、月単位、毎月 1 日に更新)」のような 1 行 50〜80 文字を 10〜15 個書けば届く。
- **正解は 1 つではない**: subscriptions ドメインを選んでも、KPI を MRR / Churn / ARPU の組み合わせから何を選ぶかは設計判断。「自分が経営者なら何を見たいか」で決めて構わない。
- **future tense で書く**: 「mart_xxx を提供する」「Metabase で可視化する」など、これから作るものを宣言する文体。後続 10-2 〜 10-7 で実際にそれを作っていく。
- **「SLA」は厳格でなくてよい**: 個人学習なので 24h / 48h で十分。重要なのは「数字を入れて宣言した」こと。
- **既存ドメインの再利用を意識**: `subscriptions ↔ customers` の FK 関係を要件定義に書いておくと、10-2 (ER 図) と 10-3 (source) の対応が自然になる。
- **ステークホルダーは「役割」で書く**: 個人名ではなく「経営企画」「経理」「カスタマーサクセス」などの **role**。半年後に人事異動があっても文書が腐らない。
- **KPI の粒度に必ず触れる**: 「MRR」だけでは grain が曖昧。「月次の MRR」「顧客 × 月の Churn Rate」のように **何を 1 行とするか** を書くと、10-2 / 10-3 の設計が一気に楽になる。

## 解答例

詳細は [`10-1-requirements.solution.md`](10-1-requirements.solution.md) を参照。
