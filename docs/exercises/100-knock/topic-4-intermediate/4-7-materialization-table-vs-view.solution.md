# 4-7 解答例

## dbt/models/100-knock/topic-4/int_orders_enriched_100knock.sql (最終 state = table 版)

```sql
{{ config(materialized='table', schema='intermediate') }}

-- Grain: 1 row = 1 order_id。int_order_details_100knock に「年月」「曜日」など
-- 派生列を追加した enriched 中継。下流 mart はここから集計を組む想定。
-- materialization: table を選択した理由 ↓
--   - 下流が複数 mart になる予定 (mart_yearly / mart_monthly / mart_dow_sales) で、
--     view にすると毎回 JOIN を再展開することになり build 時間が線形に伸びる
--   - storage コストは小さい (10,000 行 × 14 列 ≒ 数 MB)
--   - 鮮度は日次バッチで run するので table snapshot で十分
select
    order_id,
    order_date,
    extract(year from order_date)::int   as order_year,
    extract(month from order_date)::int  as order_month,
    extract(dow from order_date)::int    as order_dow,
    customer_id,
    customer_name,
    product_id,
    product_name,
    category,
    store_id,
    quantity,
    unit_price,
    sales_amount
from {{ ref('int_order_details_100knock') }}
```

**ポイント**:

- **`materialized='table'`**: 本問の主役。SQL の中身は view 版と一字一句同じだが、`CREATE TABLE AS SELECT` で物質化される結果、下流の SELECT 時に JOIN が再展開されない。
- **冒頭コメントに選択理由**: 「なぜ table を選んだか」を SQL ファイル内に書いておくのが
  実務での作法。半年後の自分や他のチームメンバーが「これ view でよくない?」と思った時に
  根拠を読み戻せる。
- **派生列 (year / month / dow)**: enriched の名前通り、下流 mart が GROUP BY しやすい
  デリバティブ列を先に展開しておく。これで下流は `group by order_year` と書くだけで済む。

## docs/exercises/100-knock/topic-4-intermediate/materialization-comparison.md

```markdown
# int_orders_enriched_100knock: view vs table の build 時間比較

実行日: 2026-04-26
実行者: 学習者
ベース: 4-1 完了 (int_order_details_100knock = view, 10,000 行)

## 1. view 版の build (1 回目)

```bash
$ time dbt build --select int_orders_enriched_100knock --profiles-dir .
04:31:00  Found 10 models, 5 sources, ...
04:31:01  1 of 1 START sql view model intermediate.int_orders_enriched_100knock [RUN]
04:31:01  1 of 1 OK created sql view model intermediate.int_orders_enriched_100knock [CREATE VIEW in 0.08s]
04:31:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

real    0m2.34s
user    0m1.10s
sys     0m0.21s
```

物理化確認:

```sql
analytics=> SELECT relname, relkind FROM pg_class
            WHERE relname = 'int_orders_enriched_100knock';
 relname                       | relkind
-------------------------------+---------
 int_orders_enriched_100knock  | v
```

`relkind = v` → Postgres の view として作成。

## 2. table 版の build (2 回目)

config を `materialized='table'` に変更後:

```bash
$ time dbt build --select int_orders_enriched_100knock --profiles-dir .
04:32:00  1 of 1 START sql table model intermediate.int_orders_enriched_100knock [RUN]
04:32:01  1 of 1 OK created sql table model intermediate.int_orders_enriched_100knock [CREATE TABLE (10000 rows, 612.0 KB) in 0.55s]
04:32:01  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1

real    0m2.81s
user    0m1.20s
sys     0m0.18s
```

物理化確認:

```sql
analytics=> SELECT relname, relkind, pg_size_pretty(pg_total_relation_size('intermediate.int_orders_enriched_100knock'))
            FROM pg_class WHERE relname = 'int_orders_enriched_100knock';
 relname                       | relkind | pg_size_pretty
-------------------------------+---------+----------------
 int_orders_enriched_100knock  | r       | 720 kB
```

`relkind = r` → ordinary table、720 KB の storage を消費。

## 3. 比較表

| 項目          | view 版           | table 版           |
|---------------|-------------------|--------------------|
| `relkind`     | `v`               | `r`                |
| build 時間    | 約 2.3 秒         | 約 2.8 秒 (+0.5s)  |
| storage       | 0 KB              | 720 KB             |
| 鮮度          | 常に上流最新      | run 時の snapshot  |
| 下流 SELECT   | JOIN を毎回展開   | table を読むだけ   |

## 4. 考察

- 本 model 単独の build 時間は **table 版が view 版より 0.5 秒遅い** (CREATE TABLE が CREATE VIEW より重いため)
- ただし下流 mart が **2 本以上** になると逆転: view 版は mart の数だけ JOIN を再展開、
  table 版は table を読むだけ。下流 mart 4 本想定なら、トータル build 時間は table 版の方が短くなる
- storage 720 KB は無視できるレベル。10 万行スケールでも数十 MB
- 鮮度: 本プロジェクトは日次バッチ前提なので、table の snapshot で十分。リアルタイム性が
  必要なら view を維持する判断もある
- **結論**: 下流 mart が 2 本以上を想定するなら table 化、単発下流なら view のまま
```

**ポイント**:

- **数値は実測値**: 学習者の環境で `time` の出力をコピペ。本サンプルは Mac M1 + Postgres 16 + ローカル接続の参考値。
- **`pg_size_pretty(pg_total_relation_size())`**: table のサイズ確認に便利。view は 0 KB。
- **比較表 + 考察 1〜2 段落** が grader の最低ライン。

## 実行例 (採点視点)

```bash
$ cd dbt && dbt build --select int_orders_enriched_100knock --profiles-dir .
... PASS=1 ...

# manifest 確認
$ python3 -c "
import json
with open('dbt/target/manifest.json') as f: m = json.load(f)
node = m['nodes']['model.local_analytics.int_orders_enriched_100knock']
print('materialized=', node['config']['materialized'])
"
materialized= table

# DB 確認
$ psql -h $DBT_HOST -U $DBT_USER -d analytics -c \
  "SELECT relkind FROM pg_class WHERE relname = 'int_orders_enriched_100knock'"
 relkind
---------
 r
```

## 解説まとめ

- **なぜ materialization 選択が重要?**: dbt は SQL を「どう物質化するか」をコード側で
  宣言する。同じ SELECT でも view にすれば storage 0 / 常に最新、table にすれば storage
  消費 / snapshot、incremental にすれば差分マージ、ephemeral にすれば物理ゼロで CTE 展開。
  **同じビジネスロジックを異なる物質化戦略で動かせる** のが dbt の核心的な強み。
- **table 化の判断基準** (実務でよく使う指針):
  1. **再利用回数 ≥ 2**: 下流が 2 本以上 ref するなら table 化を検討。`dbt ls --select <int_name>+`
     で下流ノード数をカウント
  2. **JOIN が重い**: 100 万行同士の JOIN を view にすると、下流 SELECT のたびに JOIN が走る
  3. **鮮度より速度**: BI ダッシュボードの応答速度が優先なら table、上流変化を即座に反映
     したいなら view
  4. **storage 予算**: warehouse 課金が storage 課金中心 (BigQuery の long-term storage など)
     なら view 寄り、compute 課金中心 (Snowflake) なら table 寄り
- **view と table のトレードオフ表 (覚える価値あり)**:
  | 観点         | view             | table              |
  |--------------|------------------|--------------------|
  | storage      | 0                | データサイズ       |
  | build 時間   | 速い (DDL のみ)  | 遅い (データ書込)  |
  | SELECT 速度  | 都度 JOIN 展開   | 直接 read          |
  | 鮮度         | 常に上流最新     | run 時 snapshot    |
  | 下流 N 本    | JOIN を N 回再実行 | 1 回書込で N 回読 |
- **`time` 計測の注意点**: 1 回目と 2 回目で OS / Postgres のキャッシュが効くので、ベンチマーク
  目的なら **複数回測って分布で見る**。本演習は「桁感を体感する」目的なので 1 回計測で十分。
- **materialization 切替の運用**: 本番環境で view → table 切替を行う時は `dbt run --full-refresh`
  で強制再作成 (dbt は前回の materialization と異なる場合は自動で `DROP + CREATE` するが、
  下流依存があると一瞬壊れる可能性あり)。**メンテナンス窓で実施** が安全。
- **比較ログを残す習慣**: `materialization-comparison.md` のようなドキュメントを残しておくと、
  半年後に「なぜこの int は table なんだっけ?」と疑問が湧いた時、根拠を読み戻せる。
  PR レビュー時に「table 化の根拠は?」と聞かれた時の回答にもなる。**文書化はキャッシュ**。
