# 2-3: source の各 column に description を書き、`dbt docs generate` で見えるようにする

## シナリオ

2-2 で作った `sources.yml` には `name:` だけが並んでいて、列の意味は誰にも伝わっていない。
今回は **各列に `description:` を追記** して、`dbt docs generate` で生成される docs サイトに
「raw 列の意味」が並ぶ状態を作る。

description は staging より上流 (= raw / source レイヤー) に書くと、staging の `schema.yml` の
description は **「raw からどう変換したか」** だけを語れば済む。最上流のドキュメントが揃って
初めて、下流の "差分ドキュメント" が綺麗に書ける。

## 学べること

- `sources.yml` の column 単位 `description:` の書き方
- description は **staging より前 (raw / source レイヤー) に置くべき** という設計判断の根拠
- `dbt docs generate` が `target/manifest.json` と `target/catalog.json` を生成する流れ
- description が manifest に取り込まれていることを `grep` で軽く検証する方法

## 前提

- 2-2 完了: `dbt/models/100-knock/topic-2/sources.yml` が存在し、`dbt parse` が緑
- 2-1 で raw 4 テーブルが投入済み (`dbt docs generate` は実体テーブルにも触る)

## 入力データ

データ自体は不要。2-2 で書いた sources.yml を **学習者が編集する**。

## 課題

### Step 1: sources.yml に description を追記

`dbt/models/100-knock/topic-2/sources.yml` を開いて、**全ての column に `description:` を追記** する。

最低限の指針:

- PK (`customer_id` / `product_id` / `store_id` / `order_id`) は「主キー」と書く
- FK (`orders.customer_id` / `orders.product_id` / `orders.store_id`) は「~~ への外部キー」と書く
- enum 列 (`products.category`) は「カテゴリ。<enum>のいずれか」のように **値域** を含める
- 数値列 (`unit_price` / `quantity`) は単位を含める (`円` / `個`)
- 日付列 (`order_date` / `created_at`) は型と意味 (`注文日` / `登録日`) を含める

### Step 2: dbt docs generate

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt docs generate --profiles-dir .
```

`Done.` で `target/manifest.json` と `target/catalog.json` が更新される。

### Step 3: description が manifest に入っているか軽く確認

```bash
grep -c 'description' dbt/models/100-knock/topic-2/sources.yml
# => 20 以上 (4 テーブル × 平均 5 列 + ヘッダ 5 つ程度)
```

### Step 4: docs を立ち上げて目視確認 (任意)

```bash
cd dbt
../.venv/bin/dbt docs serve --profiles-dir . --port 8088
# http://localhost:8088 で sources → raw_100knock を辿る
```

各列の説明欄が埋まっていれば成功。

### Step 5: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-2-raw-load/2-3-source-descriptions.grading.yaml
```

## 完了条件

- [ ] `dbt/models/100-knock/topic-2/sources.yml` に `description:` が **20 個以上** 含まれる
- [ ] `dbt docs generate` が exit 0
- [ ] `target/manifest.json` が更新されている (mtime チェックでも目視でも)
- [ ] docs サイト上で 4 テーブル × 全列に説明が表示される

## ヒント (詰まったら)

- **どこに書く？**: column ごとの `description:` は `name:` の **直下** にネストする。インデントを
  `tests:` と同じレベルに合わせる。
- **多言語**: dbt docs は description を Markdown としてレンダリングするので、日本語 + コードブロック
  (`` ` ``) を混ぜても綺麗に出る。
- **何故 raw 側に書くのか**: staging で書くと「物理列の意味」と「変換後の意味」が同じ description に
  混ざる。raw に書いておけば staging 側は **差分** だけを描ける。
- **`dbt docs generate` が遅い**: catalog.json は **DB に対して列メタを問い合わせる** ので、初回は
  数秒かかる。manifest だけで十分なら `dbt parse` で済む。description を確かめるだけならまず `dbt parse`
  → `target/manifest.json` を `jq` で覗くのが速い。
- **grep の `-c`**: マッチ行数を返す。`description:` が 20 個以上あれば、ほぼ確実に各列に書いてある。
  完璧主義なら `yq` で構造的にカウントするのも可。

## 解答例

詳細は [`2-3-source-descriptions.solution.md`](2-3-source-descriptions.solution.md) を参照。
