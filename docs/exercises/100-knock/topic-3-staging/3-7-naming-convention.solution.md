# 3-7 解答例

## docs/exercises/100-knock/topic-3-staging/naming-convention.md

```markdown
# 100-knock Topic ③ staging 命名規約

> 本プロジェクト (`dbt/models/100-knock/topic-3/`) における model 名・列名の命名規約。
> dbt-labs の公式 style guide を起点に、本プロジェクト固有のルール (`_100knock` suffix 等) を carve out した。

## 1. ファイル名 (model 名)

### ルール

- staging model は `stg_<entity>_100knock.sql` の形で命名する
- `<entity>` は **複数形** (英語) かつ **snake_case**
  - 例: `stg_customers_100knock.sql`, `stg_orders_100knock.sql`
- 1 SQL ファイル = 1 model

### なぜ?

- `stg_` prefix は「staging レイヤー」であることを model 名から即判定できるようにするため。dbt の `--select staging` セレクタとも整合する。
- `_100knock` suffix は MVP の `stg_customers` (suffix なし) と **物理スキーマ / 論理 model 両方で衝突回避** するため。本プロジェクト固有の事情。
- 複数形は「テーブルは行の集合 = customer**s** の集合」という意味論を反映 (後述の column の単数形と対比される)。

## 2. snake_case

### ルール

- model 名・列名は全て **snake_case** で書く
- 大文字 (`UpperCamelCase`) / lowerCamelCase / kebab-case は **禁止**
- 数字は OK (`stg_orders_2026q1` のような時間軸 suffix は許可)

### なぜ?

- Postgres / Snowflake / BigQuery 全てで「クォートなしで参照可能」な形は snake_case のみ。`SELECT "customerId" FROM ...` のクォート地獄を避ける。
- dbt の `ref('stg_customers_100knock')` 関数引数も大文字小文字を区別する。snake_case 統一で参照ミスを減らす。
- 既存 MVP (`dbt/models/staging/`) も snake_case で統一されており、混在を避ける。

## 3. `_id` suffix

### ルール

- 主キー (PK) と外部キー (FK) は必ず `<entity>_id` の形で命名
  - PK 例: `stg_customers_100knock.customer_id`
  - FK 例: `stg_orders_100knock.customer_id` (FK to stg_customers_100knock.customer_id)
- 「自分のテーブル名と同じ entity の `_id`」が PK
- 「他テーブル名 + `_id`」が FK
- ID 列は **整数 (bigint)** または **uuid** を想定。文字列の業務コードは `<entity>_code` で区別

### なぜ?

- ID 列が一目で分かる。`SELECT * FROM ...` の出力で `customer_id` を見れば「customer FK だな」と即解る。
- relationships test 宣言時に `to: ref('stg_customers_100knock')`, `field: customer_id` のペアが定型化できる。
- `id` 単独 (suffix なし) は禁止。複数テーブルを JOIN したときに `id` が衝突して `id_x`, `id_y` のような pandas / Postgres の自動 rename が発生する地獄を防ぐ。

## 4. 単数 vs 複数 (singular / plural)

### ルール

- **テーブル名 / model 名は複数形** (`customers`, `orders`, `products`, `stores`)
- **列の ID 名は単数形** (`customer_id`, `order_id`, `product_id`, `store_id`)
- 集計列の名前は単数 + 集計動詞 (`total_quantity`, `avg_unit_price`)

### なぜ?

- テーブルは「行の集合」なので複数 (英語の数の文法に整合)。1 行は「ある customer」だが、テーブル全体は「customers の集合」。
- 列の ID は「その行が指す 1 つの entity」なので単数。`customer_id` は「ある 1 顧客の ID」を指す (複数の ID を持つことはない)。
- 業界標準 (Kimball / dbt Labs / Snowflake のドキュメント) も基本これに揃っている。逆に揃えない流派 (Microsoft 系の単数形 table 命名) もあるが、本プロジェクトでは複数形に統一。

## 5. CI での検査 (現状)

- `dbt parse` を CI に組み込み、`schema.yml` の YAML 文法 + SQL ファイル名と model 名の一致を担保
- 命名違反 (大文字混入 / `_id` 漏れ / 単複の不整合) を自動検出する `sqlfluff` / `dbt-checkpoint` 連携は未導入 (今後の宿題)
- 当面は **PR レビュー時に本ドキュメントを根拠に指摘** する運用

## 参考

- dbt Labs SQL style guide: https://github.com/dbt-labs/corp/blob/main/dbt_style_guide.md
- 本プロジェクトの MVP staging 命名: `dbt/models/staging/stg_*.sql`
```

**ポイント**:

- **必須キーワード**: `snake_case` / `_id` / `plural` (or `複数`) / `singular` (or `単数`) を本文に含める。採点で grep される。
- **理由 (WHY) 必須**: 各ルールの「なぜ?」セクションが本ドキュメントの本体。「ルールだから守れ」では半年後に廃れる。レビュー時に「なぜこの規約があるか」を引ける状態を作る。
- **公式 URL は引用するが丸写ししない**: dbt Labs style guide はパブリックだが、本プロジェクト固有の事情 (`_100knock` suffix、MVP との共存) を明文化する責任は本ドキュメントにある。
- **CI 検査は将来の宿題と明記**: 現状 `dbt parse` だけでは命名違反の自動検出は不可能。`sqlfluff` 等の追加導入を「TODO」として書き残すことで、規約と実装のギャップを言語化する。
- **30〜80 行に収める**: 長い規約は読まれない。1 スクロールで読める量に圧縮するのが運用上の鉄則。

## 実行例

```
$ ls docs/exercises/100-knock/topic-3-staging/naming-convention.md
docs/exercises/100-knock/topic-3-staging/naming-convention.md

$ grep -E 'snake_case|_id|plural|複数|singular|単数' docs/exercises/100-knock/topic-3-staging/naming-convention.md | head -10
- model 名・列名は全て **snake_case** で書く
- 主キー (PK) と外部キー (FK) は必ず `<entity>_id` の形で命名
- **テーブル名 / model 名は複数形** (`customers`, `orders`, `products`, `stores`)
- **列の ID 名は単数形** (`customer_id`, `order_id`, `product_id`, `store_id`)

$ cd dbt && dbt parse --profiles-dir .
12:00:00  Found 8 models, 4 sources, 21 tests, ...
```

## 解説まとめ

- **なぜ命名規約を書く?**: 「規約は書いてあるか」と「規約は守られているか」は別問題。だが書いていない規約は守りようがない。命名規約は「PR レビューで指摘するための根拠」を作る作業。
- **dbt-labs style guide の carve out**: 公式 style guide をそのまま使うのではなく、自プロジェクトの事情 (`_100knock` suffix / MVP との衝突回避) を反映した「自プロジェクト版」を書く。これが「規約をオーナーシップする」第一歩。
- **単複の選択は宗派**: Microsoft 系は単数形 table 命名 (`Customer` table、`CustomerId` 列) が多い。Postgres / dbt 系は複数形 table が多数派。本プロジェクトは後者を選ぶが、**選んだ理由を書き残す** ことが本質。
- **CI で機械検査するには別ツールが要る**: `dbt parse` は文法だけ。命名規約を機械検査するには `sqlfluff` (SQL lint) / `dbt-checkpoint` (pre-commit hook) / `dbt-project-evaluator` (project-level rules) を別途入れる。本問は「文書化」までが範囲、機械検査は将来の宿題。
- **規約は git の歴史と一緒に育てる**: 後で「やっぱり単数形にしよう」と思ったら、本ドキュメントを PR で更新する。「いつ・なぜ変えたか」が git log に残る。これが「規約の進化」を可能にする運用基盤。
