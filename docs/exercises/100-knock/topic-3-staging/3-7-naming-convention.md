# 3-7: `stg_*` のファイル名 / column 名のルール (snake_case / `_id` suffix / 単複) を README 化

## シナリオ

3-1〜3-6 で `stg_customers_100knock` / `stg_orders_100knock` / `customer_id` といった命名を「自然と」使ってきた。だが、命名規約を **明文化していない** プロジェクトは、半年後に「`order_dt` と `order_date` が混在」「`product_ID` (大文字) が紛れ込む」「`stg_user` (単数) と `stg_users` (複数) が併存」という地獄を必ず迎える。命名規約は「コードレビューの根拠」であり、書かれていない規約はレビューで指摘できない。

今回は `docs/exercises/100-knock/topic-3-staging/naming-convention.md` を **学習者自身の言葉で** 書き、`stg_*` model に対する命名ルールを宣言する。これは将来の自分・チームへの **一筆契約書** であり、CI で `dbt parse` と一緒に grep される対象でもある。

## 学べること

- 命名規約を「文書」として残す価値 (口伝の限界)
- `snake_case` / `_id` suffix / 単複の選択を **理由付きで** 書く
- dbt-labs の公式 style guide を参考にしつつ自プロジェクト用に carve out する
- `dbt parse` を CI に組み込んで「命名違反を含む schema.yml」が通らないようにする
- 規約は「書いて終わり」ではなく「grep / lint で検査可能な形」にする

## 前提

- 3-1〜3-6 完了 (`stg_*_100knock` model 群が存在)
- `dbt parse` が通る

## 入力データ

不要。学習者がドキュメントを書くだけ。

## 課題

### Step 1: naming-convention.md を書く

`docs/exercises/100-knock/topic-3-staging/naming-convention.md` を新規作成。以下のセクションを **必ず含める**:

1. **ファイル名 (model 名)** — `stg_<table>_100knock` の形を理由付きで宣言
2. **snake_case** ルール — 大文字・キャメルケースは禁止、その理由
3. **`_id` suffix** ルール — 主キー / 外部キーは `<entity>_id` で揃える、その理由
4. **単数 vs 複数** — テーブルは複数 (`customers`)、列の ID は単数 (`customer_id`) と決める
5. **理由 (WHY)** — なぜそう決めたか。レビューで「これは規約違反」と指摘できる根拠

最低限のキーワード (採点で grep される):

- `snake_case`
- `_id`
- `plural` または `複数`
- `singular` または `単数`

### Step 2: dbt parse で命名違反がないか確認

```bash
cd dbt
dbt parse --profiles-dir .
```

`stg_*_100knock` が schema.yml と SQL ファイル名で一致していること、列名が snake_case であることを目視と parse で担保。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-3-staging/3-7-naming-convention.grading.yaml
```

## 完了条件

- [ ] `docs/exercises/100-knock/topic-3-staging/naming-convention.md` が存在する
- [ ] 上記 4 ルール (`snake_case` / `_id` / 単数 / 複数) の言及が文書内にある
- [ ] `dbt parse` が exit 0 で通る
- [ ] 文書内に「なぜそう決めたか」の理由 (WHY) が 1 文以上ある

## ヒント (詰まったら)

- **dbt-labs の style guide が起点**: [dbt Labs SQL style guide](https://github.com/dbt-labs/corp/blob/main/dbt_style_guide.md) と Modeling style guide が公式参考。ただし「自プロジェクト用」に carve out して書く (公式の URL を貼って終わりではない)。
- **テーブル名は複数 / 列の ID は単数**: 業界標準。`customers` テーブル / `customer_id` 列。「customer の集合」と「ある 1 行が指す customer」で意味が違うので語形も変える。
- **`stg_<table>_100knock` の `_100knock` suffix**: MVP の `stg_customers` と衝突しないため。これは本プロジェクト固有のルールなので必ず明記する。
- **`dbt parse` が CI で命名規約を検査するわけではない**: parse は YAML / SQL の文法だけ見る。命名違反を機械検査したいなら `dbt-checkpoint` や `sqlfluff` を別途入れる必要がある。今回は **文書化** + **parse 通過** までを範囲とする。
- **規約は短く**: 1 ページに収まらない規約は誰も読まない。今回は 30〜80 行を目安。

## 解答例

詳細は [`3-7-naming-convention.solution.md`](3-7-naming-convention.solution.md) を参照。
