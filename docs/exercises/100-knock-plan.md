# 100 本ノック 設計ドラフト

[Issue #2](https://github.com/gghatano/dbt-tutorial/issues/2) で議論された「100 本ノック」教材の **素案**。チームで分担執筆した第 1 版。

> ⚠️ ドラフト段階: 各トピックの 10 問はタイトル＋意図のレベルで列挙されている。問題本文 (`シナリオ` / `課題 Step` / `解答例`) はまだ書かれていない。

---

## 再設計の核となる視点

Issue #2 原案は「データ生成 → 取り込み → 整形 → 結合 → 集計 → 品質 → 履歴 → 再利用 → 性能 → 統合」という機能トピック 10 個 × 各 10 問で 100 本を構成していた。設計としては妥当だが、フラットすぎて「**なぜ dbt なのか**」が問題ごとに分散しがちだった。

本ドラフトでは、リポジトリオーナーの再定義に従い、次の視点を **すべての問** に通す:

> dbt の強みは「**データ・スキーマ・開発・テストの依存・関係性の定義**」を宣言的に行えること。100 本ノックは、その依存・関係性の宣言を **段階的に体験させる** ものにする。

10 トピック構成自体は維持しつつ、各問を「何を宣言し、どんな依存・関係を作るか」で再フレームした。

---

## 「依存・関係性」の 5 軸

すべての問は以下のいずれかの宣言・関係性を題材とする:

| 軸 | 宣言の場 | 何が機械可読になるか | 主な dbt 機能 |
|---|---|---|---|
| **データの依存** | `ref()` / `source()` | DAG (上流 → 下流) | source / ref / lineage graph |
| **スキーマの依存** | `schema.yml` | 列名・型・description が model の隣にコロケート | columns / data_type / contract / description |
| **開発の依存** | macro / package / Jinja | 共通変換ロジックの呼び出し関係 | macros / packages.yml / dbt_utils / dbt-expectations |
| **テストの依存** | `tests:` / `dbt/tests/` | 不変条件・契約違反の検知点 | not_null / unique / relationships / generic test / singular test / contract: enforced |
| **可視化の依存** | `exposure:` / `dbt docs` | 「誰が誰を使っているか」 | exposures / dbt docs / `dbt ls --select +exposure:` |

各問は表で「**何を宣言・関係づけるか**」の列に、上記 5 軸のどれを扱っているかが読み取れる形式で書く。

---

## 5 段階の学習ラダー

各問は次の 5 段階のいずれかを目指す。トピック内で 10 問を組むときは、序盤 2-3 問が `declare`、中盤 4-5 問が `verify` / `visualize`、後半 2-3 問が `evolve` / `review` になるよう設計する:

1. **declare** — 何を宣言するか（`ref()` / `source()` / `schema.yml` / `exposure:` / `macro` / 等）
2. **verify** — 宣言したことがどう検証されるか（test / `dbt build` / `freshness`）
3. **visualize** — 関係性が DAG / docs でどう可視化されるか（`dbt docs serve` / `dbt ls --select`）
4. **evolve** — 壊さずに変える / 影響範囲を限定する（model version / contract / `--select state:modified+`）
5. **review** — 設計判断として他者と議論できる（open-ended、正解が一つでない問）

---

## 既存 10 Exercise との関係

リポジトリには既に 10 問の練習問題 ([docs/exercises/01-10](.)) がある。これらは **100 本ノックのサンプル / 上位互換ではない**。位置づけは次のとおり:

| 関係 | 解釈 |
|---|---|
| **既存 Ex.01〜10 = "ピックアップ 10 問"** | dbt の主要機能を一周する短編教材。100 本ノックを通しで解く前のウォームアップ |
| **100 本ノック = "依存・関係性"軸での再訪** | 同じ機能でも「declare → verify → visualize → evolve → review」の段階で角度を変えて再習得 |
| **重複は許容** | 例: 100 本ノック Topic ① の問の一部は Ex.01 と入力データを共有。100 本ノック Topic ⑦ の問は Ex.04 を発展させる |

各問の表の最終列「既存 Exercise との関連」で、`Ex.NN 拡張` / `Ex.NN 一部` / `(new)` と明示する。

---

## 全体構成（10 トピック × 各 10 問）

```text
入力層 (Topic ①〜③)
  ① ダミーデータ生成     — データ仕様を Python で宣言
  ② raw 投入             — source の物理境界を宣言
  ③ staging（整形）      — 型・列名の正規化を staging contract として宣言

モデリング層 (Topic ④〜⑤)
  ④ 中間モデル           — 結合 grain と派生計算を宣言、DAG の中継ハブを設計
  ⑤ KPI / マート         — ビジネス指標と粒度を宣言、BI に渡す契約を作る

品質・時間軸 (Topic ⑥〜⑦)
  ⑥ データ品質・テスト   — データの不変条件をモデルに付随する形で宣言
  ⑦ 履歴管理 (snapshot)  — 履歴化戦略を宣言、過去の事実を再現可能に

開発・運用 (Topic ⑧〜⑩)
  ⑧ 再利用 (Jinja/macro) — 共通変換ロジックを 1 箇所に集約、依存を宣言で表現
  ⑨ パフォーマンス       — 物質化戦略・差分処理・並列性を宣言で制御
  ⑩ 統合 (実務再現)      — 依存関係グラフ全体を設計し、レビュー可能な状態にする
```

Topic ⑩ の最後 3-4 問は **「正解が一つでない設計問」** にする方針。レビュー（他者の設計を読む）が含まれる。

---

## 前提資産（Issue #2 原案より引用、ほぼそのまま採用）

- **データドメイン**: EC（小売）。テーブル: `customers` / `products` / `stores` / `orders` / `order_items` / `events`
- **データパターン 2 種**:
  - クリーンデータ（序盤用）
  - 汚いデータ（後半用 — NULL / 重複 / 異常値 / 壊れた FK）
- **実行環境**: PostgreSQL ローカル + dbt Core + Metabase（既存リポジトリのスタックそのまま）

汚いデータへの切り替えは Topic ⑥ から本格化させる予定（途中で「壊れる」体験が品質対応力を育てる、Issue #2 原案の意図を継承）。

---

# 入力層 — Topic ① ② ③

> 30 問は、最下層（生データ → raw → staging）における **「物理から論理への翻訳」を宣言として書き残す** 体験に集中する。表面上は「Faker でデータを作って COPY して staging を書く」という地味な作業に見えるが、各問は必ず **何かしらの dependency / contract を成果物に残す** よう設計してある。

## ① ダミーデータ生成（10 問）

### Topic intro

dbt は raw より上流（CSV 生成 / 受信）を管轄しないが、**raw に流す前のデータ仕様を Python 側で宣言** しておかないと、source の型契約 (`column_types`) や `relationships` テストがすべて空虚になる。本トピックでは Faker / pandas を「データ仕様の DSL」として使い、**「PK は何か」「FK 関係は何か」「カーディナリティは何対何か」「null 比率はどれくらいか」を Python のコードに 1 箇所だけ宣言** させる。これが後続の `source.yml` / `schema.yml` の元ネタとなり、Python 仕様 ↔ dbt contract の双方向リンクが学習者の頭の中に張られる。

dbt 上で直接何かが宣言されるわけではないが、**「上流データ仕様を宣言として書かないと下流の test も docs も嘘になる」** という肌感覚をここで仕込むのが狙い。

### 10-question table

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 1-1 | `customers` 1,000 行を Faker で生成、`customer_id` を 1..1000 の PK、seed 固定で type-stable に | PK の存在と一意性、`Faker.seed_instance()` による再現性 | (dbt 外) `scripts/generate_dummy_data.py` | 「同じコマンドで毎回同じ raw が出来る」= dbt 側の test が flaky でなくなる | spec §11.1 / 既存 |
| 1-2 | `products` 100 行を生成、`category` 列は 5 値の enum で固定 | enum 値の閉じた集合（後の `accepted_values` 元ネタ） | (dbt 外) → 後の `accepted_values:` | enum 値の集合が Python と schema.yml の両方に書かれる二重管理を体感 | spec §11.1 / 既存 |
| 1-3 | `stores` 20 行、`prefecture` 列を都道府県 47 個から抽選 | マスタ系の「閉じた集合」、後の seed テーブル化の伏線 | (dbt 外) → 後の `dbt seed` | 「20 行しかないものはマスタ。マスタは seed 化候補」 | Ex.05 と接続 (new 部分あり) |
| 1-4 | `orders` 10,000 行、`customer_id` は 1..1000、`product_id` は 1..100、`store_id` は 1..20 から抽選 | FK 関係を **Python 側で先に宣言** しておく | (dbt 外) → 後の `relationships:` テスト | Python のサンプリング範囲 = dbt の `relationships` test と一致する | spec §11.1 / 既存 |
| 1-5 | `orders.unit_price` は `product_id` から決定論的に算出（同じ商品は常に同じ単価） | "派生" を Python で定義、後に staging で再計算しないと決める | (dbt 外) / 後の staging で `unit_price` をそのまま流す | 「同じ列の意味は 1 箇所で決める」DRY の前段 | (new) |
| 1-6 | `customer_id` のうち 1% は `orders` に登場しない（休眠顧客）よう生成 | カバレッジの非 100%（後の relationship 方向の理解） | (dbt 外) → 後の `relationships` の方向性 | FK は orders→customers のみ。逆向きには張らない設計判断 | (new) |
| 1-7 | `orders.order_date` を 2025-01-01 〜 2026-04-30 の範囲で分散生成 | 時間軸の境界、後の incremental の高水位線の素材 | (dbt 外) → 後の `is_incremental()` | 日次バッチ前提の date 列が 1 本決まる | Ex.03 と接続 |
| 1-8 | `comment` 列に約 10% の NULL を意図的に混ぜる (reviews 想定) | NULL 許容列の宣言、`not_null` を **付けない** 判断 | (dbt 外) → 後の `schema.yml` で `not_null` を外す | 「NULL を許す列」と「許さない列」を Python 側でも区別する | Ex.01 と接続 |
| 1-9 | 生成スクリプトに `--rows` / `--date` 引数を追加し、複数日分を冪等に再生成可能に | 入力の冪等性。後の re-run / `--full-refresh` の前提条件 | (dbt 外) → 後の `dbt run --full-refresh` | 「データを作り直しても dbt の出力が同じになる」契約 | Ex.03 一部 |
| 1-10 | 生成データの **行数・列・null 比率** を `data/raw/_stats.json` に書き出す（自前の data contract） | 上流データの最小プロファイル契約 | (dbt 外) → 後の `dbt-expectations` / freshness | Python 側の "data contract" と dbt 側の test がペアで存在する設計 | Ex.10 と接続 (new 部分あり) |

### Topic ① 完了後の到達点

- **PK / FK / enum / null 比率 / カーディナリティ** を「データ生成スクリプト」に明示的に書き残す癖がつく
- 後続の `source.yml` / `schema.yml` で何をテストすべきかが、Python のコードを読むだけで決まる状態になる
- 「Faker の seed を固定する」「行数を引数化する」など、dbt の冪等性を支える上流側の前提を自分で作れる

---

## ② raw 投入（10 問）

### Topic intro

raw 層は「**dbt が触れない外部世界との物理境界**」である。dbt 視点では `source:` が、その境界の唯一の宣言地点になる。本トピックでは「CSV を psycopg + COPY で raw に流す → `sources.yml` で論理名を与える → `dbt source freshness` / `dbt ls --select source:*` で外から見えるようにする」までを 10 問でなぞる。**「物理テーブル名 / 物理 schema 名」と「dbt 上の source 名」を意図的に切り離す** ことで、後で raw が S3 や BigQuery に置き換わっても staging 以下が無傷で済む構造の意味を体感させる。

dbt 上で宣言されるのは `source` の名前空間 (`source('raw', 'customers')`) と、その freshness / loaded_at の契約。これにより「**raw → staging の 1 本目の DAG エッジ**」が初めて lineage に現れる。

### 10-question table

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 2-1 | `raw.customers` テーブル定義を SQL DDL として書き、psycopg + COPY で 4 ファイル投入する | 物理 schema / table 名と DDL（型） | (dbt 外) `scripts/load_raw_data.py` | 物理境界が「`raw` schema の 4 テーブル」と確定 | spec §11.2 / 既存 |
| 2-2 | `dbt/models/sources.yml` に `name: raw` の source ブロックを書き、4 テーブルを宣言 | dbt 上の論理 source 名と物理 schema/table の写像 | `source:` / `database:` / `schema:` | 物理 (`raw.customers`) ↔ 論理 (`source('raw','customers')`) のマッピング | spec §8.1 / 既存 |
| 2-3 | 各 source column に `description:` を書き、`dbt docs generate` で見えることを確認 | 列レベルのドキュメント宣言（schema より上流） | `dbt docs generate` / `dbt docs serve` | docs サイト上で「raw 列の意味」が staging より上に並ぶ | (new) |
| 2-4 | `raw.orders` の `loaded_at` 列に対して `freshness:` を宣言、`warn_after`/`error_after` を 1 day で設定 | データの "鮮度契約" を source 側に持たせる | `freshness:` / `dbt source freshness` | source ノードに「鮮度 SLA」が付き、CI で古い raw を弾ける | (new) |
| 2-5 | `dbt source freshness` を実行し、わざと CSV を 2 日前のタイムスタンプで生成し直して warn を発生させる | freshness 契約が実際にトリガーされる体験 | `dbt source freshness --select source:raw.orders` | "鮮度違反" がログ＆exit code に現れる経路 | (new) |
| 2-6 | source の `loaded_at_field` と Python 側 `loaded_at` 列の型・タイムゾーンを揃える | Python 仕様と dbt source 契約の **型レベル** での整合 | `loaded_at_field:` / `freshness:` | Python の `datetime.utcnow()` と dbt の freshness 計算が同じ時刻軸で動く | (new) |
| 2-7 | Exercise 01 と同様に新規 source ファイル `exercises/02/sources.yml` を別名 (`raw_exercise`) で追加 | 既存 source 名と衝突させない名前空間設計 | `source:` の `name:` ユニーク制約 | 同じ物理 schema を複数の論理 source 名で覗ける（用途別ビュー） | Ex.01 一部 |
| 2-8 | `dbt ls --select source:raw.*` / `dbt ls --select source:raw.customers+` で source とその下流を列挙 | source を起点とした **DAG クエリ言語** の習得 | `dbt ls --select` / `+` 演算子 | 「この raw を変えたら何が壊れるか」を 1 コマンドで列挙できる | Ex.06 と接続 |
| 2-9 | `raw.customers` に `tests:` ブロック（`unique` / `not_null` on `customer_id`）を source 側に直接書く | テストを **staging より前** に張る (contract on source) | `tests:` on source column | source ノードに test が付き、staging を作る前に raw の不正を検知 | spec §8.2 一部 |
| 2-10 | 投入スクリプトを `pre-hook` 風に手動で順序化（generate → load → `dbt source freshness`）し README 化 | 「dbt の前にやるべきこと」を運用手順として固定 | `dbt source freshness` を CI 前段に挟む発想 | dbt run の前に raw 鮮度を確認する運用フローが言語化される | Ex.09 と接続 (hooks の前段) |

### Topic ② 完了後の到達点

- 「raw に何が居るか」が `sources.yml` に宣言で書き起こされ、`dbt ls --select source:*` で機械可読に列挙できる
- `freshness:` を使って「上流データが古いだけで CI を warn / error にできる」契約を体感する
- 物理 schema / table と dbt の source 名を切り離す意義（移植性、複数環境対応）を理解し、後の staging 以下が **物理を一切知らない** ことが当然と感じられる

---

## ③ staging（整形）（10 問）

### Topic intro

staging は **「raw の物理表現を、下流が安心して使える論理表現に翻訳する契約」** である。型・列名・タイムゾーン・null 表現・列順といった「物理由来の不揃い」を 1 段で吸収し、その契約を `schema.yml` に宣言として残す。本トピックでは `stg_*` を 1 個ずつ作りながら、**「列の rename / 型 cast / null 正規化を staging より下流に漏らさない」** という規律を、generic test と description の合わせ技で強制する。ここが staging contract である。

dbt 上で宣言されるのは `ref()` による source → staging のエッジ、`schema.yml` の column-level test、そして staging model の materialization (`view` 推奨)。これら 3 つが揃って初めて、intermediate / marts は「staging が嘘をついていない前提」で書ける。

### 10-question table

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 3-1 | `stg_customers` を `view` materialization で書き、`source('raw','customers')` から SELECT、明示型 cast を全列に | source → staging のエッジ、列ごとの型契約 | `{{ source(...) }}`, `{{ config(materialized='view') }}` | DAG に「raw.customers → stg_customers」のエッジが現れる | spec §8.2 / 既存 |
| 3-2 | `stg_products` を同様に書き、`category` 列を `lower(trim(category))` で正規化 | 「下流からは小文字 trim 済み」契約 | jinja / SQL 関数による軽量 normalization | カテゴリ表記揺れを **staging で必ず吸収する** という規律 | spec §8.2 / 既存 |
| 3-3 | `stg_orders` で `order_date` を `date` 型に、`unit_price` を `numeric(10,2)` に明示 cast | 数値 / 日付の型契約 | SQL `::type` / dbt の `column_types:` 思想 | 「数値の精度・日付の型」が staging 出口で確定 | spec §8.2 / 既存 |
| 3-4 | `schema.yml` で `stg_orders` の `order_id` に `not_null` + `unique`、FK 列に `relationships` to `ref('stg_customers')` 等 | PK / FK 契約をモデルにコロケート | `tests:`, `relationships:` | DAG 上の参照関係が test レベルでも検証される | spec §8.2 / Ex.01 一部 |
| 3-5 | `stg_orders.quantity` / `unit_price` に独自 generic test `positive_value` を書いて適用 | 値の制約契約（ドメインルール） | 自作 generic test (`{% test %}`) | 「商品単価は必ず正」を schema.yml に宣言で残す | Ex.08 と接続 |
| 3-6 | 全 staging model の `schema.yml` に `description:` を model / column 両方に書き、`dbt docs generate` で確認 | ドキュメント契約（人間用） | `description:`, `dbt docs generate` | docs サイト上で staging 列にツールチップが付く | Ex.06 と接続 |
| 3-7 | `stg_*` のファイル名 / column 名のルール（snake_case / `_id` suffix / 単複）を README 化、CI に `dbt parse` を組み込む | 命名規約という **暗黙契約を明示化** | `dbt parse` / `dbt build --select state:modified+` | 命名違反が PR 段階で機械的に弾ける | (new) |
| 3-8 | `stg_*` の materialization を `view` に統一する設定を `dbt_project.yml` の `+materialized:` で一括宣言 | レイヤー全体の materialization 契約 | `dbt_project.yml` の `models:` 配下 `+materialized:` | 「staging はクエリで都度評価される」設計判断が project レベルで可視化 | spec §8 / 既存 |
| 3-9 | `stg_orders` を変更したと想定して `dbt run --select +stg_orders+` を実行、上下流が両方走ることを確認 | DAG 演算子による依存伝播の確認 | `dbt run --select +model+` | 「変更が誰に波及するか」をコマンドで描ける | Ex.06 と接続 |
| 3-10 | `dbt build --select staging` を 1 発で通し、`stg_*` の run + test が原子的に成功することを確認 | レイヤー単位の build 契約（run と test の同時実行） | `dbt build`, `--select staging` | 「staging の合格 = run + test が両方緑」という運用上の単位が固まる | (new) |

### Topic ③ 完了後の到達点

- **raw の物理事情（列名・型・null 表現・表記揺れ）を staging が必ず吸収する** という規律が身体化する
- `schema.yml` の `tests:` / `description:` がモデルの隣にコロケートされる "schema contract" の形を覚える
- `dbt build --select staging` 1 発で「staging 層全体の合格 / 不合格」を語れるようになる
- 以降の intermediate / marts では「staging を疑わなくてよい」前提でロジックに集中できる

---

# モデリング層 — Topic ④ ⑤

> 中間モデルと mart の 20 問。intermediate は「複数 staging を統合する DAG の中継点」、mart は「ビジネス契約 + BI exposure 起点」。dbt の DAG と grain semantics が最も活きるレイヤー。

## ④ 中間モデル (intermediate)

### Topic intro

intermediate は **複数 staging を「業務的に意味のある grain」に揃え直して束ねる DAG の中継ハブ** である。staging は「物理テーブル 1 対 1」、mart は「BI 契約 1 対 1」だが、その間に「`1 注文 1 行` `1 顧客 1 日 1 行` のような **業務 grain で正規化された再利用可能ブロック**」を挟むことで、下流 mart は「どの grain を相手にしているか」を `ref()` 1 行から読み取れる。intermediate を切る/切らないの判断は、そのまま「**この変換は何箇所から再利用されるか / どの grain で語るか**」の宣言である。ここでは grain を口に出して書き、`ref()` で論理依存を張り、`schema.yml` で grain を `unique` テストで担保する一連の流れを 10 問で体験させる。

### 10-question table

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 4-1 | `int_order_details` を **再実装** し、grain を「1 `order_id` 1 行」と冒頭コメント + `schema.yml` description で宣言する | `ref()` で 4 staging 依存、grain 文書化、`unique` テストで grain 担保 | `{{ ref('stg_orders') }}` ほか 3 本、`tests: [not_null, unique]` on `order_id` | staging × 4 → `int_order_details` という「ハブ 1 点に 4 線が集まる」星形 DAG | spec §8.3 の再構築 (new 視点) |
| 4-2 | `int_order_details` の grain 宣言を裏切る重複行を **わざと** 注入する singular test を書き、CI で落とす | grain 契約のテスト依存、singular test のスコープ | `dbt/tests/exercises/04/assert_int_order_details_grain.sql`、`having count(*) > 1` | 「grain 違反 = build 失敗」を lineage 上の赤ノードで可視化 | Ex.08 の前哨戦 |
| 4-3 | `int_customer_daily_activity` を作る（顧客 × 日 grain） — 注文がない日は出さない方針を冒頭コメントで宣言 | grain 宣言（複合キー）、`generate_surrogate_key` で複合 PK を 1 列化 | `dbt_utils.generate_surrogate_key(['customer_id','activity_date'])` | 「同じ staging から **異なる grain** の int を 2 本派生できる」 | Ex.07 で導入した dbt_utils を modeling 側で再利用 |
| 4-4 | 「intermediate を切らずに mart 1 本で書いた版」と「int を挟んだ版」を両方書いて lineage graph を比較する | DAG の形と再利用回数の関係 | `dbt docs generate` → `dbt docs serve` で lineage 比較、`dbt ls --select +mart_xxx` | 「int を挟むと下流 mart 2 本が同じ集計を共有する」が graph で見える | (new) intermediate の存在意義を体感する核心問 |
| 4-5 | `int_order_details` を 2 本の mart (`mart_daily_sales` / `mart_product_sales`) から `ref()` するパターンを描く | 1 中継ノード → N 下流 の **fan-out** 依存 | `dbt run --select int_order_details+`、`dbt ls --select int_order_details+1` | 「int を 1 行修正したら、下流 N 本に伝播する」依存伝播の感覚 | spec §8.4 の追体験 |
| 4-6 | `int_order_with_tax` を作り、税計算 macro `calc_tax(amount, rate)` を呼ぶ | 開発の依存（macro 集約）、計算ロジックの一元化 | `{% macro calc_tax(amount, rate) %}`、`dbt/macros/exercises/04/` | 「税率変更時、int 1 行 + macro 1 箇所修正で全 mart に波及」 | Ex.05 (macros) を modeling 側で実用 |
| 4-7 | `int_orders_enriched` を **materialization view → table** に切り替え、実行時間を比較する | `materialized` 選択の宣言、コスト/鮮度トレードオフ | `{{ config(materialized='table' \| 'view' \| 'ephemeral') }}` | 「中継ノードを table 化すると下流 build が速い、view なら常に最新」 | (new) materialization 軸 |
| 4-8 | `int_order_details` を `materialized='ephemeral'` に変更し、コンパイル後 SQL で CTE に展開されることを確認 | ephemeral の依存表現（物理テーブルなし、SQL 展開） | `dbt compile --select mart_daily_sales`、`target/compiled/.../mart_daily_sales.sql` | 「ephemeral は DAG 上は依存だが物理は存在しない」を compiled SQL で確認 | (new) 上級 materialization |
| 4-9 | `int_order_details` の `schema.yml` に **全列 description** を書き、`dbt docs serve` で intermediate ノードのカタログ化を確認 | スキーマ依存（doc + 列定義のコロケーション） | `columns: - name: ... description: ...`、`dbt docs generate` | 「intermediate もカタログ対象」「下流 mart は int の description を継承的に参照」 | Ex.06 の docs を intermediate 側で深掘り |
| 4-10 | `int_order_details` を **同じ grain の version 2** に分岐（v1 は税抜、v2 は税込列を追加） — 既存 mart は v1 参照のまま | model versions (1.5+)、互換性保ちながらの schema 進化 | `versions:` in `schema.yml`、`{{ ref('int_order_details', v=2) }}` | 「下流の壊さない schema 進化」を依存グラフで管理 | (new) 1.5+ 機能、Topic ⑤ contract と接続 |

### 重要観点 — 中間モデルを「切る判断軸」

問 #4-4 と #4-5 を「int を切る/切らない」の判断軸を体感する核心問題として配置している:

- **#4-4** は同じ集計を 2 通り（int あり / int なし）で書かせて lineage を比較させる。「int を切らないと、同じ JOIN を mart 2 本に重複コピペすることになる」を **目で見せる**
- **#4-5** は 1 つの int から下流 mart が 2 本ぶら下がる構図 を作らせる。「再利用 ≥ 2 が int を切る最低ライン」という経験則を、`dbt ls --select int_xxx+` の出力で可視化
- 加えて #4-2 で「int の grain を test で守る = 下流が安心して `ref()` できる契約になる」を体験させ、「テスト集約」も int を切る理由のひとつとして提示

### Topic ④ 完了後の到達点

- 自分で書く新規モデルについて「これは何 grain か」を **冒頭コメント + `schema.yml` description + `unique` test の 3 点セット** で必ず宣言できる
- 「int を切るかどうか」を再利用回数 (`dbt ls --select +mart_xxx` の出力) と grain 統一の必要性で判断し、口頭で理由を述べられる
- materialization (view / table / ephemeral) の選択基準を「下流の build 頻度 × 鮮度要件 × ストレージ」のトレードオフで説明できる
- model version で「下流を壊さない schema 進化」ができることを知り、`v=2` を `ref()` に渡す書き方ができる

---

## ⑤ KPI / マート (mart)

### Topic intro

mart は **dbt の世界が外（BI / ML / API）と接続する境界面** であり、ここで初めて「列名・型・粒度・SLA」が **対外契約** になる。intermediate までの内部表現と違い、mart の列を変えると Metabase ダッシュボードが壊れ、CSV エクスポートを使う人が壊れ、下流 ML 特徴量が壊れる。だから mart は「**grain の宣言** + **列契約の宣言** (`contract: enforced`) + **誰が使っているかの宣言** (`exposure:`)」の 3 つを揃えて初めて完成する。Topic ⑤ では、この 3 点セットを 10 問で組み立て、最後に「contract に違反する model 変更 → CI red → 修正」のサイクルまで体験させる。

### 10-question table

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 5-1 | `mart_top_rated_products` を Ex.02 の延長で再構築し、grain (1 product 1 行) と業務しきい値 (`avg_rating>=4 AND review_count>=10`) を冒頭コメントで宣言 | mart の grain と業務ルールの宣言 | `{{ ref('int_product_reviews') }}`, `{{ ref('mart_product_sales') }}` | int 2 本 → mart 1 本の収束 DAG | Ex.02 拡張 |
| 5-2 | `mart_monthly_sales_by_category` を新規作成（月 × カテゴリ grain） | 複合 grain の宣言、PK は `generate_surrogate_key(['month','category'])` | `dbt_utils.generate_surrogate_key`、`tests: [unique]` on PK | 「mart の grain は BI が GROUP BY する単位」を体感 | Ex.07 の dbt_utils 再利用 |
| 5-3 | `mart_daily_sales` に **`contract: enforced`** を付け、各列に `data_type:` を宣言 | スキーマ契約 (1.5+)、列名 + 型の対外公開 | `config(contract={'enforced': true})`、`columns: - name: x; data_type: numeric(14,2)` | 「mart は型まで含めた契約」、build 時に schema diff で fail | (new) **1.5+ contract の核心問** |
| 5-4 | わざと `mart_daily_sales` の `total_sales_amount` を `numeric(14,2)` → `integer` に変える PR を作り、build が落ちることを確認 | contract 違反検知のテスト依存 | `dbt build --select mart_daily_sales` で `Contract Error` | 「契約違反 = build red = BI 影響事前検知」 | #5-3 の検証パート |
| 5-5 | `mart_daily_sales` に `exposure:` で Metabase ダッシュボードを宣言 | 可視化の依存（mart → BI）の機械可読化 | `exposures:` in `models/exposures.yml`, `type: dashboard`, `url:`, `owner:` | `dbt ls --select +exposure:daily_sales_dashboard` で「ダッシュボードが依存している全 model」が出る | Ex.06 拡張 |
| 5-6 | mart に `+grants:` config を付け、`readonly_user` に SELECT を自動付与 | 権限の依存宣言、`on-run-end` 不要の宣言的 grants | `config(grants={'select': ['readonly_user']})` | 「mart 公開 = 誰に見せるかの宣言まで含む」 | Ex.09 (hooks) との対比、宣言的解 |
| 5-7 | `mart_customer_lifetime_value` を新規作成し、`groups:` (1.5+) で `marts_finance` グループに所属させる | model のオーナーシップ・スコープ宣言 | `groups:` in `_groups.yml`、`config(group='marts_finance')` + `access: private/protected/public` | 「他チームが勝手に `ref()` できない private mart」 | (new) 1.5+ groups |
| 5-8 | `mart_top_rated_products` の `meta:` に `owner` / `slack_channel` / `sla_hours` を宣言し、`dbt docs` で表示 | 運用メタの宣言、ドキュメント依存 | `meta:` block in `schema.yml`、`dbt docs generate` | 「mart は技術的契約 + 運用契約の二重宣言」 | Ex.06 拡張 |
| 5-9 | mart に対し `dbt-expectations` の `expect_column_values_to_be_between` で 業務範囲テスト (`avg_rating between 1 and 5`) を宣言 | テストの依存（業務制約を機械可読化） | `packages.yml` に `dbt-expectations`、`tests:` 配下に expectations | 「BI に出す前にビジネスルールで止める」 | Ex.10 拡張 |
| 5-10 | Topic ④ #4-10 で作った `int_order_details v2` を参照する `mart_daily_sales_with_tax` を新規作成し、v1 mart と並走させる | model version + mart 並走による段階移行 | `{{ ref('int_order_details', v=2) }}`、新 mart 作成、旧 mart はそのまま | 「上流 v2 → 新 mart → 新 exposure」と「上流 v1 → 旧 mart → 旧 exposure」の **二系統 DAG** が共存 | (new) Topic ④ #4-10 と接続、Topic ⑤ の総仕上げ |

### 重要観点 — mart の「契約」

問 #5-3 と #5-4 を **`contract: enforced` (dbt 1.5+)** に充てている:

- `contract: enforced` は単なる test ではなく **build 時 fail** する強い宣言。`dbt run` で `Contract Error: column 'x' has type 'integer' but contract specifies 'numeric(14,2)'` のようなエラーで止まる
- 「mart は BI と契約している」感を出すため、#5-3 で契約宣言 → #5-4 で **わざと違反 PR** → CI red を体験させる順序にした
- `data_type:` は Postgres 型 (`numeric(14,2)`, `timestamp without time zone` など) を正確に書く必要があり、staging / int で揃えてきた型がここで一気に効いてくる
- 加えて #5-6 (`+grants`) と #5-7 (`groups: + access:`) で「誰がアクセスできるか」も契約の一部として宣言させる

### Topic ⑤ 完了後の到達点

- 新しい mart を作るとき、grain・列契約 (`contract: enforced` + `data_type:`)・exposure・grants・meta・group の **6 点セット** を反射的に揃えられる
- BI 担当から「この列の型は何？」「いつ更新される？」「誰が壊したら直す？」と聞かれたら `schema.yml` を見せて答えられる
- 上流 model の破壊的変更を検知する仕組み（contract）と、下流影響範囲を出す仕組み (`dbt ls --select +exposure:xxx`) を、両方コマンドで実演できる
- model version + 並走 mart で「BI を壊さずに段階移行」する具体的な手順を、二系統 DAG として描ける

---

# 品質・時間軸 — Topic ⑥ ⑦

> テストは「データへの不変条件契約」、snapshot は「時間軸での同一性宣言（SCD Type-2）」。両方とも、SQL の正しさではなく **データに対する宣言的な期待値** を扱う。

## ⑥ データ品質・テスト

### Topic intro

dbt のテストは「コードに書かれた振る舞い」を検証する単体テストではなく、**モデルそのものに付随する「データへの不変条件契約 (data contract)」** である。`schema.yml` で `not_null` / `unique` / `relationships` / `accepted_values` を宣言した瞬間、その列は「NULL があってはならない列」「他テーブルと参照整合する列」「取りうる値が有限集合の列」として **DAG の中で型のように扱われる**。コードレビューより前にデータ自身が「自分はこの契約を満たしている」と主張する。Topic ⑥ では、この契約宣言を「組み込み test → 列単位の domain 制約 → モデル間 FK → 自作 generic で再利用 → severity / store_failures で運用 SLO に格上げ」という順で段階的に身につける。最終的に「テストが落ちた → 失敗行 SQL を引いて根本原因を辿れる」 ループを完成させる。

### 10 問

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 6-1 | `stg_orders.order_id` に `not_null` + `unique` を schema.yml で宣言し、`dbt test --select stg_orders` で 2 件 PASS することを確認する | 主キー契約（identity 制約）を YAML に書く | `schema.yml` の `tests:`、`dbt test --select` | 「この列は主キーである」がモデルに付随する不変条件として残る | Ex.01 一部 |
| 6-2 | `stg_orders.customer_id` に `relationships: to: ref('stg_customers'), field: customer_id` を貼り、わざと存在しない customer_id を 1 行混ぜて FAIL させる | モデル間の **外部キー宣言** = lineage に意味的な「参照」エッジを足す | `relationships` test、`ref()` を test 内で使う | DAG が「依存」だけでなく「参照整合」も語れるようになる | Ex.01 拡張 (new) |
| 6-3 | `stg_orders.payment_method` に `accepted_values: ['card','cash','qr']` を宣言、CSV 側に `'paypay'` を 1 行混ぜて FAIL を確認する | 列の **値域 (enum / domain)** を契約として宣言 | `accepted_values` test | 「この列は有限集合」を YAML 1 行で型として表現 | Ex.01 一部 |
| 6-4 | `dbt/tests/assert_no_future_orders.sql` に `select * from {{ ref('stg_orders') }} where order_date > current_date` を書き、singular test として落とす | 1 つのモデル限定の **業務不変条件**（時間軸の妥当性）を SQL で表明 | singular test (`tests/*.sql`)、`ref()` を test 本体で使う | 「YAML に乗らない単発の業務ルール」を test 化する選択肢を持てる | (new) |
| 6-5 | `dbt/tests/generic/test_positive_value.sql` を自作し、`stg_orders.quantity` / `stg_products.unit_price` / `stg_orders.unit_price` に `tests: [positive_value]` を貼って 3 列に再利用する | **再利用可能な契約 macro** を 1 箇所に集約、複数モデルから ref する | `{% test %}` block、`{{ model }}` / `{{ column_name }}`、generic test 機構 | 「同じ不変条件を複数モデルに横展開」が DRY に書ける | Ex.08 そのもの |
| 6-6 | #6-5 の `positive_value` を `(model, column_name, allow_zero=False)` 引数付きに拡張、`marts.mart_daily_sales.total_sales_amount` に `allow_zero: true` で適用する | **パラメータ付き契約** で再利用範囲を広げる | 引数付き generic test、YAML から引数渡し | 「同じロジックでも対象ごとに微調整」を YAML 側で吸収できる | Ex.08 拡張 |
| 6-7 | `accepted_values` に `config: severity: warn` を付け、違反 1 行混ざっても CI exit code が 0 のまま WARN だけ出る挙動を再現する | テストの **重大度 = 運用 SLO** を契約に組み込む | `severity: warn` / `error_if: '>10'` / `warn_if` | 「データ品質は二値ではなくレベル」を運用設計として表現できる | Ex.10 一部 |
| 6-8 | `dbt-expectations` を `packages.yml` に追加、`expect_column_values_to_match_regex` で `stg_customers.email` をメール形式チェックする | **外部 test ライブラリ**で組み込みでは書けない契約を宣言 | `dbt deps`、`dbt_expectations.expect_column_values_to_match_regex` 等 | 「自作 vs パッケージ」の選択軸を持ち、車輪の再発明を避けられる | Ex.10 拡張 (Ex.07 前提) |
| 6-9 | **失敗行を SQL で追える**: `accepted_values` test に `config: store_failures: true` を付け、違反データを混ぜて `dbt test` → `dbt_test__audit.<test_name>` を psql で SELECT → 違反 5 行の `review_id` を特定 → raw を直して再 test して PASS に戻すまでを 1 セッションで完走する | 失敗を **データのまま観察できる** = テストとデバッグの依存関係を閉じる | `--store-failures` / `+store_failures: true`、`dbt_test__audit` schema、psql | 「test 落ちた」→「失敗行 select」→「raw 修正」→「再 test PASS」の 1 ループを身体化 | Ex.10 そのものの延長 |
| 6-10 | `dbt_project.yml` の `data_tests:` セクションで `+store_failures: true` をプロジェクト全体に適用、ただし `staging:` 配下だけに絞り、`marts:` には付けない設定にする | テスト運用ポリシーを **設定ファイルで一元宣言** する | `dbt_project.yml` の `data_tests:` 階層設定、`+severity` / `+store_failures` の継承 | 「test 設定もコード = レビュー対象」になり、test の運用が属人化しない | (new) |

### Topic ⑥ 完了後の到達点

- `schema.yml` を読めば「このモデルが満たすべきデータ契約」が一望できる、というメンタルモデルを持つ
- 組み込み test / 自作 generic test / singular test / パッケージ test の **使い分けの判断軸**を言語化できる
- テストが FAIL したとき、`dbt_test__audit` から失敗行を引いて raw まで遡るデバッグループを **数分で回せる**
- `severity: warn` / `error_if` / `store_failures` を組み合わせ、「壊しても気づける」運用を設計できる

---

## ⑦ 履歴管理 (snapshot)

### Topic intro

source の物理テーブルは「今この瞬間の事実」しか持たない。`raw.products.unit_price` が改定で上書きされた瞬間、過去の注文に紐づく「当時の価格」は失われる。dbt snapshot は **「この source は時間軸でどう同一性を保つか」を宣言する仕組み** であり、SCD Type-2 として `dbt_valid_from` / `dbt_valid_to` を機械的に生成する。これは「データの依存」を **時間軸に拡張した依存関係宣言** に他ならない。Topic ⑦ では、strategy の選択（check / timestamp）、削除の扱い (`hard_deletes`)、そして snapshot を ref する下流モデルまで含めて「過去のある時点の事実をクエリ 1 本で再現できる」状態を目指す。

### 10 問

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 7-1 | `dbt/snapshots/snap_products.sql` を `check` strategy / `check_cols=['unit_price']` で書き、1 回目 `dbt snapshot` で 100 行できることを確認する | 「`unit_price` が変わったら歴史を切る」契約を snapshot ファイルに宣言 | `{% snapshot %}` block、`strategy='check'`、`check_cols`、`unique_key` | source の **時間軸の同一性ルール**を 1 ファイルで定義できる | Ex.04 そのもの |
| 7-2 | `raw.products` の 20 行を v2 に差し替え、2 回目 `dbt snapshot` で 120 行になり、20 商品が v1 / v2 の 2 行ずつ持つことを `dbt_valid_from` / `dbt_valid_to` で確認 | 「上書き」を「履歴行の追加」に変換する dbt の挙動を体感 | `dbt snapshot` 2 回目、`dbt_valid_to is null` で「最新行」を表現 | 「最新の事実」と「過去の事実」の 2 つのクエリ視点を持てる | Ex.04 そのもの |
| 7-3 | `raw.products` に `updated_at` 列を足し、`timestamp` strategy で `snap_products_ts.sql` を別途作る。`check` 版との `dbt_valid_from` の精度差を比較する | strategy の選択は **source 側のスキーマに依存する**ことを宣言で示す | `strategy='timestamp'`、`updated_at` | 「source に更新時刻列があるか」が snapshot 戦略の境界条件と気づける | Ex.04 拡張 |
| 7-4 | `raw.products` から 5 行物理削除して `dbt snapshot --vars '{snapshot_meta_column_names: {dbt_is_deleted: is_deleted}}'` 相当 (1.9+ `hard_deletes: new_record`) を試し、削除も履歴に残す | **物理削除イベント**も時間軸の事実として宣言する | `hard_deletes: new_record` (dbt 1.9+)、`dbt_is_deleted` メタ列 | 「削除も歴史」 = source からの完全消失を許さない設計を選べる | Ex.04 拡張 (new) |
| 7-5 | `dbt/snapshots/exercises/schema.yml` で `snap_products` に `not_null: dbt_scd_id` / `unique: dbt_scd_id` test を貼る | snapshot 自身も **schema 契約**を持つ（メタ列が壊れていないことの保証） | snapshot 用 `schema.yml`、メタ列への test | 「snapshot は machine-generated だから安心」ではなく **明示契約**で守る習慣がつく | (new) |
| 7-6 | **過去のある時点を SQL 1 本で再現する**: `2026-04-15` 時点の全 product 価格表を `select * from snap_products where dbt_valid_from <= '2026-04-15' and ('2026-04-15' < dbt_valid_to or dbt_valid_to is null)` で取り出す | 時間軸 `as_of` の **point-in-time クエリ契約** を SQL に翻訳する | snapshot メタ列 (`dbt_valid_from`, `dbt_valid_to`) を使った range JOIN | 「過去の任意の時点の事実セットを SQL で再現できる」 = snapshot の本質的価値 | Ex.04 Step 6 の本格化 |
| 7-7 | `dbt/models/exercises/04/int_orders_with_historical_price.sql` を作り、`int_order_details` の `order_date` × `snap_products` を range JOIN して「注文時点の価格」列を持つ intermediate を作る | snapshot を `ref('snap_products')` で **下流モデルから参照**、DAG に正式に組み込む | `ref()` で snapshot 参照、range JOIN、intermediate 層への組み込み | snapshot が単なる横置きでなく、**lineage の一部として下流から使われる**ことを体感 | Ex.04 Step 6 |
| 7-8 | #7-7 の int model に対し、`dbt build --select +int_orders_with_historical_price` を打って snapshot → ref → test まで一気通貫で走らせる | snapshot と通常モデルの **依存解決順序**を build コマンドで体験 | `dbt build`、`+model` セレクタによる上流巻き込み | snapshot は dbt の DAG に「時間軸ノード」として組み込まれていると理解する | (new) |
| 7-9 | `snap_products` に対し `dbt snapshot --select snap_products` を **入力データを変えずに** 2 回叩き、no-op であること（`count(*)` が増えない）を確認 | snapshot の **冪等性宣言** = 同じ source なら何回叩いても歴史は壊れない | `dbt snapshot` の no-op 挙動、source 不変時の `dbt_valid_to` 不更新 | snapshot を CI / cron で「とりあえず叩いておく」運用にしてよい安心感を持てる | Ex.04 ヒント部の本格化 |
| 7-10 | `dbt_project.yml` の `snapshots:` セクションで `+target_schema: snapshots` / `+strategy: check` をプロジェクト全体に既定化、各 snapshot ファイル側を最小化する | snapshot の **運用ポリシーを設定ファイル側で宣言**する | `dbt_project.yml` の `snapshots:` 設定継承 | 個別ファイルの config を YAML 側に集約し、snapshot 群の運用が一望できる | (new) |

### Topic ⑦ 完了後の到達点

- 「source は今、snapshot は歴史」という二層メンタルモデルが定着する
- `check` / `timestamp` / `hard_deletes` を source の素性で使い分けられる
- `dbt_valid_from <= as_of < coalesce(dbt_valid_to, '9999-12-31')` の **point-in-time JOIN テンプレート** を即座に書ける
- snapshot を `ref()` 経由で intermediate / mart に組み込み、`dbt build` で一気通貫にビルドできる

---

# 開発・運用 — Topic ⑧ ⑨ ⑩

> 再利用 (macro / package)、性能 (materialization / incremental)、統合 (DAG 全体設計とレビュー)。dbt の宣言が **チームで使える資産** になる最後の 30 問。

## ⑧ 再利用 (Jinja / macro / package / seed)

### Topic intro

dbt の **「開発の依存」** を体現するトピック。SQL の繰り返し（型キャスト・列名統一・metric の式）を 1 箇所に集約し、参照側は「呼ぶだけ」で同じロジックが効くようにする。`{% macro %}` は自プロジェクト内で書くロジックの依存元を、`packages.yml` は外部プロジェクトへの依存を、`seed` は **コードと一緒に version 管理されるマスタデータ** への依存を、それぞれ宣言する手段である。Jinja の loop / variable / dispatch macro まで踏むと、「同じ macro が adapter ごと・環境ごとに違う SQL を吐く」という 1:N の依存も宣言で扱えるようになる。10 問を通じて、学習者は「重複があるならそれは macro / seed / package のいずれかに昇格できる」という嗅覚を身につける。Ex.05・Ex.07 の体験を出発点に、依存の **方向** と **粒度** を意識させる。

### 10 問

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 8-1 | `cast_jpy` macro を `numeric(14,2)` 専用から **桁数を引数化** した汎用版に拡張し、`stg_orders` / `stg_products` / `mart_*` 計 5 model から呼び出すよう書き換える | 「金額型の正規化ルール」をプロジェクト内 1 箇所に依存付け | `{% macro cast_money(col, precision=14, scale=2) %}` / `dbt run --select state:modified+` | 5 model → 1 macro の収束図 | Ex.05 拡張 |
| 8-2 | `dbt-utils` を `packages.yml` に追加し、`dbt deps` で取得。`generate_surrogate_key(['order_date','customer_id'])` を `int_order_details` の代理キー列に使う | 外部パッケージへのバージョン依存と、複合キーの単一列化 | `packages.yml` / `dbt deps` / `dbt_utils.generate_surrogate_key` / `package-lock.yml` | 自 project → 外部 package、複合 PK → surrogate PK | Ex.07 拡張 |
| 8-3 | `dbt-expectations` を packages に追加し、`expect_column_values_to_match_regex` を `stg_customers.email` に追加。**dbt-utils と dbt-expectations 2 パッケージの共存** を package-lock で確認 | 1 project が複数 package に依存する状況の宣言 | `packages.yml`（複数エントリ）/ `dbt-expectations` / `package-lock.yml` の lock 範囲確認 | project → {dbt_utils, dbt_expectations} の多重依存 | (new) |
| 8-4 | `seeds/exercises/jp_holidays_2026.csv`（祝日マスタ）を seed として登録し、`mart_calendar_sales` に `is_holiday` 列を追加。seed には `not_null`・`unique`・`accepted_values`（曜日）テストを付ける | 「外部から渡された静的マスタ」の version 管理と test を宣言 | `dbt seed` / `seeds:` config（`column_types`, `+schema`）/ `accepted_values` | seed → mart 1 経路、seed 自身も test 対象 | Ex.05 拡張 / Ex.07 補完 |
| 8-5 | `{% for %}` Jinja loop で `staging` 4 テーブル分の `last_updated_at` 列を一括追加する macro `add_audit_columns()` を書き、`pre_hook` 経由で全 staging に注入 | 「全 staging に共通する監査列」のテンプレート依存を宣言 | Jinja `{% for col in [...] %}` / `var()` / `pre_hook` | 1 macro → N model の fan-out | (new) |
| 8-6 | `vars` を `dbt_project.yml` に追加（`min_order_amount: 100`）。`int_order_details` で `where sales_amount >= var('min_order_amount')` とし、`dbt run --vars '{min_order_amount: 0}'` で上書きできることを確認 | 「ビジネスパラメータ」をコードから分離して宣言、CLI で上書き可 | `vars:` / `var('name', default)` / `dbt run --vars` | model → var 経由の暗黙依存、CLI 引数で動的差し替え | (new) |
| 8-7 | `dispatch` macro を書く。`{% macro default__safe_divide(num, den) %}` と `{% macro postgres__safe_divide(num, den) %}` を分け、adapter 別に NULL ガードの書き方を変える | 「同じインタフェース、複数実装」を adapter 軸で宣言（多態） | `{% macro %}` + `adapter.dispatch(...)` / `dispatch_packages` / `target.type` | 1 interface → adapter 別 N 実装 | (new) |
| 8-8 | `mart_*` の `+grants:` を `dbt_project.yml` の `models:` config に書き、`readonly_user` への select を **宣言的** に付与（hook を使わない方法）。`dbt run` 後 `\dp marts.*` で grant 状態を確認 | 「アクセス権限」をコード上に宣言、dbt が GRANT 文を自動生成 | `+grants: {select: ['readonly_user']}` / dbt-postgres 1.10 の grants サポート | model → role の権限依存を YAML で表明 | Ex.09 拡張 (hook 方式との対比) |
| 8-9 | 自作 macro `metric_revenue(model, date_col, amount_col)` を書き、`mart_daily_sales` / `mart_customer_sales` / `mart_product_sales` 3 model から **同じ集計式** を呼ぶ。式変更時に 1 箇所修正で 3 マート全部が更新されることを確認 | 「KPI 集計式」を 1 箇所に閉じ込める依存設計 | 自作 macro / `{{ return(...) }}` / `dbt build --select state:modified+` | 1 metric 定義 → N mart の収束、後の Semantic Layer の予感 | Ex.05 拡張 |
| 8-10 | `packages.yml` の version を `[">=1.3.0", "<2.0.0"]` から `1.3.0` ピン留めに変更し、`package-lock.yml` の差分を git diff で確認。**lock の役割**（再現可能性 vs 自動更新） を 3 行で言語化 | 「外部 package のバージョン依存」をプロジェクト固定にする宣言 | `packages.yml` 範囲指定 vs ピン / `package-lock.yml` / `dbt deps --upgrade` | project → package 特定バージョンへの固定依存 | Ex.07 拡張 |

### Topic ⑧ 完了後の到達点

- 「重複した SQL 片」を見たら macro / seed / package のどこに昇格すべきか即判断できる
- macro 引数の設計（必須/任意/デフォルト）と、dispatch macro による多態性の使い分けができる
- `packages.yml` と `package-lock.yml` の役割を区別し、外部依存を再現可能な状態に保てる
- seed を「コード化された小規模マスタ」として扱い、test まで含めて 1 単位で管理できる

---

## ⑨ パフォーマンス

### Topic intro

dbt の **「物理依存」** — 時間・コスト・リソース消費 — を宣言で抑えるトピック。`view` / `table` / `incremental` / `ephemeral` の **materialization** は「この model を物理的にどう保存するか」の宣言で、下流の rebuild 時間とストレージコストを直接決める。`incremental` の `strategy` は「差分をどう識別・マージするか」の宣言、`+threads` と `state:modified+` は「dbt run の並列性と build 範囲」の宣言、`pre_hook` / `post_hook` での `analyze` / `index` は「物理最適化の依存」を model に張り付ける宣言である。学習者は「正しさ」を保ったまま「物理的なコスト」を削るのが宣言で済むことを体験する。Ex.03（incremental）の拡張として、戦略選択・差分検出・並列度・部分 build の 4 軸を順に押さえる。

### 10 問

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 9-1 | `int_order_details` を `view` → `table` → `ephemeral` の 3 通りで build し、`mart_daily_sales` の build 時間と `intermediate.int_order_details` の存在/非存在を比較表にまとめる | 「中間層をどう物質化するか」が下流コストにどう波及するか | `{{ config(materialized='view'/'table'/'ephemeral') }}` / `dbt run --select +mart_daily_sales` / `compiled/` を読む | materialization 選択 → 下流 SQL の構造変化（ephemeral は CTE 展開） | Ex.03 補完 |
| 9-2 | `mart_orders_incremental` を `incremental` 化し、`unique_key='order_id'`、`strategy='merge'` で実装。新規 1,000 行を追加して再 run、insert/update が SQL 上どう変わるか `target/run/...sql` を読む | 差分マージ戦略を宣言で選択 | `materialized='incremental'` / `unique_key` / `incremental_strategy='merge'` / `is_incremental()` | 入力差分 → merge SQL の自動生成、PK 経由の upsert | Ex.03 拡張 |
| 9-3 | 同じ model を `strategy='append'` / `'delete+insert'` / `'merge'` で書き分け、重複 PK 投入時の挙動を比較。どれが「冪等」か答える | strategy ごとの一貫性保証を宣言レベルで理解 | `incremental_strategy` の 3 種 / `--full-refresh` / 重複 row 投入 | strategy 選択 → 冪等性・速度・ロック範囲の三すくみ | Ex.03 拡張 |
| 9-4 | `incremental` model に `merge_exclude_columns=['updated_at']` を追加（dbt 1.6+）し、updated_at 列だけは merge 時に上書きされない挙動を確認 | 「merge から除外する列」をコード側で宣言 | `merge_exclude_columns` / `is_incremental()` / `target/run/*.sql` の merge 文を読む | 列単位の merge 制御、源泉システムの値を残す設計 | (new) |
| 9-5 | `mart_orders_incremental` の `post_hook` で `create index if not exists ix_orders_order_date on {{ this }} (order_date)` を発行し、index 有無で `explain analyze` の cost が変わることを確認 | 「物理 index」を model に付随する宣言として表現 | `post_hook` / `{{ this }}` / `explain analyze` / Postgres `pg_indexes` | model → index の付随依存、コードと一緒に index 定義 | Ex.09 拡張 |
| 9-6 | `dbt_project.yml` の `models:` に `+materialized` をレイヤーごとに宣言（staging=view, intermediate=ephemeral, marts=table）。個別 model の `config()` で上書きできることを `mart_*` の 1 本だけ `incremental` にして確認 | 「規約はプロジェクトで、例外は model で」の階層的設定 | `dbt_project.yml` の `models:` 階層 / `+materialized` / model 内 `config()` の precedence | プロジェクト規約 → model 個別設定の override | (new) |
| 9-7 | `profiles.yml` の `threads: 4 → 8` で `dbt run` 時間がどう変わるか測定。**シリアル依存にある model 群**（staging→intermediate→marts）と、**並列可能な model 群**（4 staging 同士）の違いを DAG で説明 | 並列度を宣言、DAG 構造が許す並列性を理解 | `profiles.yml` の `threads:` / `dbt run` の所要時間ログ / `dbt ls --select staging` | 並列度の宣言 ↔ DAG 形状の関係（fan-out で並列、shared 依存で直列化） | (new) |
| 9-8 | `staging/stg_orders.sql` の 1 列を変更し、`dbt run --select state:modified+` で「自分と下流」だけが build されることを確認。`--state` に渡す manifest を前回 run の `target/manifest.json` にする | 「変更影響範囲」を manifest 差分から宣言で導出 | `state:modified+` / `--state path/` / `manifest.json` 差分 | 変更 model → 下流 N model の自動展開 | Ex.06 補完 |
| 9-9 | `dbt build --select +mart_customer_sales` を実行し、**run + test** がトポロジカル順に走ることを確認。途中で 1 test を `severity: error` で失敗させ、下流が SKIP されることを目視 | `build` における「test 失敗 → 下流停止」の依存ガード | `dbt build` / `severity: error` vs `warn` / `skip` ログ | upstream test 失敗 → downstream 自動停止の安全装置 | Ex.10 補完 |
| 9-10 | 大きめのダミーデータ（orders 100,000 行）を生成し、`mart_orders_incremental`（incremental, merge）と `mart_orders_full`（table, 全件再構築）の 2 本を 5 回連続 run。各 run の所要時間を表にして「incremental が x 倍速」を数値で示す | 物質化戦略の効果を時間軸で宣言、ROI を数値化 | `materialized='incremental' vs 'table'` / `--full-refresh` / `time dbt run` | 戦略選択 → コスト差の定量化、`incremental` の損益分岐点 | Ex.03 拡張 |

### Topic ⑨ 完了後の到達点

- materialization 4 種を「下流コスト」と「ストレージ」の 2 軸で語れる
- incremental の 3 strategy を冪等性・速度・ロックで比較し、要件から選べる
- 変更影響範囲（`state:modified+`）と並列度（`threads`）を組み合わせて、CI で「壊れた箇所だけ最小コストで再 build」できる
- 物理最適化（index, analyze）を model 定義の隣に置き、コードと運用の二重管理をなくせる

---

## ⑩ 統合 (実務再現)

### Topic intro

ここまでに身につけた「データ・スキーマ・開発・テスト・可視化」5 種の依存宣言を **一つの DAG として組み上げる** トピック。新規ドメイン（例: サブスクリプション課金、または在庫管理）を題材に、要件定義 → ER 図 → source 宣言 → staging contract → mart 設計 → exposure 登録 → CI 設定 → docs 公開 までを 1 周し、**他者がレビューできる成果物** を残す。後半 3 問は「正解が一つでない」設計判断・トレードオフ・他者レビュー型の問。dbt は「個々の model が動くこと」より「DAG 全体が他者から読める・直せる・拡張できる」ことに価値がある。学習者は「動く SQL を書く人」から「他チームに引き継げる依存関係グラフを設計する人」へ移行する。

> **題材の示唆**: 既存の `customers / products / orders / stores` ドメインに、新たに `subscriptions`（顧客の月額契約）と `subscription_events`（解約・再開・プラン変更ログ）を追加する想定で進める。学習者が別ドメイン（在庫・配送・広告）を選んでもよい。

### 10 問

| # | 問 | 何を宣言・関係づけるか | 使う dbt 機能 / コマンド | 学習者が描けるようになる関係 | 既存 Exercise との関連 |
|---|---|---|---|---|---|
| 10-1 | 新規ドメインの **要件定義** を 1 ページにまとめる。ステークホルダー、KPI 3 つ、提供したい mart 3 本、想定アクセス頻度、SLA を文章で書く | 「これから作る DAG が解こうとしている問題」を宣言 | Markdown のみ（`docs/exercises/10/requirements.md`） | ビジネス要件 → 技術成果物の対応表 | (new) |
| 10-2 | ER 図を Mermaid で書き、PK/FK/cardinality を明示。`subscriptions ↔ customers` の 1:N、`subscription_events ↔ subscriptions` の 1:N を Mermaid `erDiagram` で表現 | 物理 schema 化前の **論理関係** を宣言 | Mermaid `erDiagram` / Markdown プレビュー | エンティティ → 関係 → cardinality の 3 段宣言 | (new) |
| 10-3 | `dbt/models/sources.yml` に新規 source（`raw.subscriptions`, `raw.subscription_events`）を追加。`description` / `loaded_at_field` / `freshness: {warn_after: 24h, error_after: 48h}` を宣言し、`dbt source freshness` で監視 | 「外部から流入するデータの鮮度 SLA」を宣言 | `sources:` ブロック / `freshness:` config / `dbt source freshness` | source → 鮮度監視ルールの依存 | Ex.01 拡張 |
| 10-4 | staging 層で **dbt model contract**（dbt 1.5+）を有効化: `config(contract={enforced: true})` + `schema.yml` の `columns:` で型を全列宣言。型違反時に dbt run が失敗することを確認 | 「staging が下流に約束する型」をコードで宣言、契約違反を CI で検知 | `contract: {enforced: true}` / `data_type:` / `dbt run` の contract error | staging → 下流間の **型契約**、break しても上流 model に責任が残る | (new) |
| 10-5 | `groups:` と `access:` を導入: `models/intermediate/_int_models.yml` で `group: subscription_internal`、`access: private` を宣言。別 group の model から `ref()` 参照すると parse エラーになることを確認 | model の **公開範囲** を宣言、依存方向を group 境界で制御 | `groups:` / `access: private/protected/public` / `dbt parse` のエラー | model → group → 公開範囲の 3 層宣言、モジュラリティ | (new) |
| 10-6 | 新ドメインに対する exposure を 2 つ宣言（dashboard 用 + reverse_etl 用）。それぞれ `depends_on` / `owner` / `maturity: high` を書き、`dbt ls --select +exposure:churn_dashboard` で起点 build できる状態にする | 「BI と reverse ETL という終端依存」を DAG 上に宣言 | `exposures.yml` / `type: dashboard` / `type: application` / `+exposure:` selector | mart → exposure → owner / maturity の連鎖 | Ex.06 拡張 |
| 10-7 | `dbt build --select +exposure:churn_dashboard` を CI 想定で 1 コマンドにまとめ、`scripts/ci/dbt_check.sh` を書く。中身は `dbt deps && dbt source freshness && dbt build --select state:modified+ --defer --state ./prod-manifest/` | CI における「build / test / docs」をひとまとめに宣言 | `dbt build` / `--defer` / `--state` / シェルスクリプト | PR 単位の差分 build → test → docs の 1 fly-through | Ex.10 補完 |
| 10-8 | **(open-ended / レビュー型)** 自分が設計した DAG (10-1〜10-6) を `docs/exercises/10/design_review.md` にまとめ、以下を必ず含める: (1) ER 図、(2) DAG スクリーンショット、(3) 主要 mart の SLA、(4) 「ここで判断に迷った」と書く設計判断 3 つ。**完成版に正解はない** — 設計ノートとして残すこと自体が成果物 | 設計判断と迷いを「他者が読めるドキュメント」として宣言 | Markdown / `dbt docs generate` の screenshot / 自由記述 | 自分の DAG → 他者がレビューできる単位への昇華 | (new) |
| 10-9 | **(open-ended / レビュー型)** ペアの学習者（または将来の自分）が書いた DAG を読み、`design_review_feedback.md` として **3 種類のレビューコメント** を書く: (a) 依存方向に違和感がある箇所、(b) 命名が一貫していない箇所、(c) 「ここを変えると影響が大きい」と気づいた箇所。指摘の正しさより「指摘できたこと」を評価する | 他者の DAG への **依存性レビュー** を言語化 | `dbt docs serve` の lineage / `dbt ls --select +model_name` で影響範囲確認 / Markdown | 他者の DAG → 自分のレビュー眼の言語化 | (new) |
| 10-10 | **(open-ended / 集大成)** 自分の DAG を「次の人に引き継ぐ」想定で `HANDOVER.md` を書く。必ず含む: (1) 要件定義への link、(2) ER 図、(3) 主要 KPI と source の対応表、(4) `dbt build` と `dbt source freshness` の運用フロー、(5) 既知の TODO / リスク 3 つ、(6) 「自分なら次はこう拡張する」という展望 1 段落。提出物は GitHub の Pull Request として diff を残す | プロジェクト全体を「他者に引き継げる成果物」として宣言 | `dbt docs generate` / `git diff` / Pull Request / Markdown | 自分の DAG → チーム資産への昇華、依存関係グラフの社会化 | 全 Exercise の集大成 |

### Topic ⑩ 完了後の到達点

- 新規ドメインに対し、要件 → ER → source → staging → mart → exposure を **同じ温度感で** 設計でき、各レイヤの責任を説明できる
- contract / groups / access / freshness の 4 機能で「壊れにくい・壊しても誰の責任か明確な」DAG を組める
- 自分の設計を他者がレビュー可能な状態（DAG + ドキュメント + 設計判断ノート）で残せる
- 他者の DAG を読んで依存方向・命名・影響範囲の 3 観点で指摘できる。チーム開発に乗れる人になる

---

# 設計判断ノート (チーム集約)

各エージェントが個別に書いた設計ノートを統合した、ドラフト全体に通底する判断と未解決事項。

## 採用した設計

- **「依存・関係性 5 軸」を全 100 問に通す**: 各問の「何を宣言・関係づけるか」列がその縦糸の見える化。フラットな機能トピックではなく、機能横断の「dbt らしさ」を体験させる
- **5 段階学習ラダー (declare → verify → visualize → evolve → review)**: トピック内 10 問の並びがこのラダーになるよう設計。後半に行くほど「正解が一つでない問」へ
- **dbt 1.5+ の新機能を積極採用**: `contract: enforced` / `groups:` / `access:` / `model versions` / `+grants:` を Topic ⑤ ⑩ に集中投下。「壊さずに変える」を支える宣言が dbt 1.5+ で揃ったのを反映
- **既存 Exercise 01〜10 と "重複を許容"**: 上位互換ではなく「同じ機能を別軸で再訪する」位置づけ。学習者は既存 10 問を解いた後でも、100 本ノックで違う角度から学べる
- **Topic ⑩ 後半は open-ended / レビュー型**: 「動く DAG」より「他者が読める DAG」がゴール。問 10-8 / 10-9 / 10-10 は HANDOVER / レビューコメント / 設計ノートを成果物にする

## 迷った点 / 次の議論ポイント

- **`hard_deletes` (dbt 1.9+) を入れるか**: Topic ⑦ の問 7-4 として 1 問だけ入れたが、本リポジトリの dbt-core 1.11 で動作確認していない。動かなければヒントレベルに格下げ
- **dispatch macro (問 8-7) の必要性**: 本リポジトリは Postgres 専用なので深入りさせない方針だが、「最低 1 問は触る」価値があると判断。学習者が挫折するなら削除候補
- **Topic ⑨ の `dbt build` 配置**: 性能トピックに置いたが、本来は ⑩ 統合フェーズの題材。⑨ では「test 失敗で下流が止まる依存ガード」(無駄な build を抑える) として捉え、⑩ で CI 化 + groups で再登場させる二重露出
- **Topic ⑥ と ⑤ (macro) の役割重複**: 自作 generic test (問 6-5) は macro でもあるが、「契約の宣言」軸で ⑥ に置いた。Topic ⑧ では同じ仕組みを「変換ロジックの DRY」軸で再登場 → 二面性の体験
- **入力データ "汚いデータ" への切替タイミング**: Topic ⑥ から本格化と書いたが、Topic ⑤ の `contract: enforced` 検証 (問 5-4) も「壊れたデータ」を要する。生成スクリプト側の切替ポイント設計が未着手

---

# 次のステップ

このドラフトを **実問題セット** に育てるための工程:

1. **レビュー** — 既存リポジトリオーナー + 既存 10 Exercise の解答確認者に、本ドラフトの 100 問をスキャンしてもらう。観点は (a) 抜けトピックがあるか (b) 重複がないか (c) Issue #2 の意図と乖離していないか
2. **問題本文の執筆** — 各問を `docs/exercises/100-knock/NN-MM-<keyword>.md` のような命名で個別ファイル化。既存 Exercise 01〜10 の構成 (シナリオ / 学べること / 前提 / 入力データ / 課題 / 完了条件 / ヒント / 解答例) に揃える。100 ファイル × 平均 80 行 = 約 8,000 行
3. **解答 markdown の執筆** — 各問に対し `solutions/NN-MM-<keyword>.solution.md` を書く。100 ファイル × 平均 150 行 = 約 15,000 行
4. **生成スクリプト** — Topic ① (ダミーデータ生成) の問は `scripts/100-knock/` にスクリプトを追加。Topic ⑥ で「壊れたデータ」を生成するための差分パッチも必要
5. **段階的リリース** — 100 問を一度にリリースせず、トピック単位で 5 PR に分割（入力層 / モデリング層 / 品質・時間軸 / 開発運用前半 / 開発運用後半 + 統合）。各 PR は 20 問ペース
6. **CI / docs 連携** — `dbt docs generate` 結果を GitHub Pages にデプロイする運用も同時に検討。100 問の lineage が一覧できる状態が目標

工数感: 1 トピック (10 問本文 + 解答) を 1 人日とすると、合計 10 人日。レビューと修正で +5 人日、計 **15 人日** 程度が素案。
