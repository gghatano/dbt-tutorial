# 9-8 解答例

## ゴール再掲

- 前回 manifest を `prev-manifest/manifest.json` に保存
- `stg_orders_100knock.sql` に 1 列追加
- `dbt run --select state:modified+ --state ./prev-manifest/` で「自分と下流」のみ build
- 結果を `state-modified.md` に記録

## ベースライン取得 (Step 1)

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
mkdir -p prev-manifest
cp target/manifest.json prev-manifest/manifest.json
```

## 変更 (Step 2): stg_orders_100knock.sql に列追加

差分:

```diff
 select
     order_id::bigint               as order_id,
     order_date::date               as order_date,
     customer_id::bigint            as customer_id,
     product_id::bigint             as product_id,
     store_id::bigint               as store_id,
     quantity::int                  as quantity,
     unit_price::numeric            as unit_price,
+    (quantity * unit_price)::numeric as line_amount
 from {{ source('raw_100knock', 'orders') }}
```

## 差分 run (Step 3)

```bash
../.venv/bin/dbt parse --profiles-dir .   # 現在 manifest を更新
../.venv/bin/dbt run \
    --select state:modified+ \
    --state ./prev-manifest/ \
    --profiles-dir . \
    --no-colors 2>&1 | tee /tmp/9-8-state-modified.log
```

期待ログ:

```text
06:00:00  Running with dbt=1.11.0
06:00:00  Found 12 models, 4 sources, 21 tests, ...
06:00:00  Concurrency: 4 threads (target='dev')
06:00:00
06:00:00  1 of 4 START sql view model staging_100knock.stg_orders_100knock ............ [RUN]
06:00:00  1 of 4 OK   created sql view model staging_100knock.stg_orders_100knock ..... [CREATE VIEW in 0.10s]
06:00:00  2 of 4 START sql view model intermediate_100knock.int_order_details_100knock . [RUN]
06:00:00  2 of 4 OK   created sql view model intermediate_100knock.int_order_details_100knock [CREATE VIEW in 0.12s]
06:00:01  3 of 4 START sql table model marts_100knock.mart_customer_sales_100knock .... [RUN]
06:00:01  3 of 4 OK   created sql table model marts_100knock.mart_customer_sales_100knock [CREATE TABLE in 0.20s]
06:00:01  4 of 4 START sql table model marts_100knock.mart_product_sales_100knock ..... [RUN]
06:00:01  4 of 4 OK   created sql table model marts_100knock.mart_product_sales_100knock [CREATE TABLE in 0.18s]

06:00:01  Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

ポイント:

- `1 of 4` から `4 of 4` まで、変更した `stg_orders_100knock` + その下流 3 model だけが build
- `stg_customers_100knock` / `stg_products_100knock` / `stg_stores_100knock` は **対象外** (含まれない)
- `Found 12 models` のうち 4 model しか走っていない = **差分 build が機能している証拠**

## docs/exercises/100-knock/topic-9-performance/state-modified.md (例)

```markdown
# 9-8 state:modified+ で差分 build

実行日: 2026-04-26
対象: `stg_orders_100knock` の SELECT 句に `line_amount` 列追加

## 1. ベースライン manifest

\`\`\`bash
mkdir -p prev-manifest
cp target/manifest.json prev-manifest/manifest.json
\`\`\`

## 2. 変更内容

`dbt/models/100-knock/topic-3/stg_orders_100knock.sql` の SELECT 句に列 `line_amount` を 1 列追加。
`(quantity * unit_price)::numeric as line_amount`

## 3. 差分 run コマンド

\`\`\`bash
dbt parse --profiles-dir .   # 現 manifest を再生成
dbt run --select state:modified+ --state ./prev-manifest/ --profiles-dir .
\`\`\`

## 4. 結果ログ抜粋

\`\`\`text
1 of 4 OK   created sql view model staging_100knock.stg_orders_100knock           [CREATE VIEW in 0.10s]
2 of 4 OK   created sql view model intermediate_100knock.int_order_details_100knock [CREATE VIEW in 0.12s]
3 of 4 OK   created sql table model marts_100knock.mart_customer_sales_100knock   [CREATE TABLE in 0.20s]
4 of 4 OK   created sql table model marts_100knock.mart_product_sales_100knock    [CREATE TABLE in 0.18s]

Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
\`\`\`

## 5. 観察

- 変更した `stg_orders_100knock` 自身が含まれた
- 下流 3 model (`int_order_details_100knock`, `mart_customer_sales_100knock`, `mart_product_sales_100knock`) も build
- 変更していない 3 staging (`stg_customers_100knock` 等) は **対象外** (合計 12 model 中 4 model のみ)
- フル build なら 12 model、`state:modified+` で 4 model = 約 1/3 のコストに圧縮

## なぜ `+` を後ろに付けるか

- `state:modified` のみ → 自身 1 model のみ。下流が古いまま
- `state:modified+` → 自身 + 下流すべて。PR 影響範囲を網羅 (王道)
- `+state:modified` → 上流 + 自身。上流は変わっていないので意味薄
```

## 解説まとめ

### なぜ state:modified+ が「dbt の核心」なのか

- dbt の本質は **DAG (model 間の依存関係グラフ)**。manifest.json はその DAG の凍結版
- 「**前回 manifest と今 manifest を比較すれば、差分 model が分かる**」という発想は dbt の設計から自然に出てくる
- これがあるから「**全 model 再 build (= 数百〜数千 model)**」せずに「**変更したものだけ + 下流**」で済む
- 大規模プロジェクトほど威力が出る (1000 model のうち 5 model しか変えなかった PR を 5 model + 下流 30 model = 35 model だけで build)

### 変更検出の粒度

dbt は次のいずれかが変わると `state:modified` 扱い:

1. **SQL 本体の文字列** (空白も含む。差分は hash で検出)
2. **依存 macro の SQL** (使っている macro の中身が変われば下流とみなす)
3. **config の変更** (`materialized`, `unique_key` など)
4. **column-level metadata** (schema.yml の `columns:` を変えた場合)
5. **persist_docs** (description を変えた場合)

逆に `state:modified.body` / `.configs` / `.relation` / `.persisted_descriptions` / `.macros` で個別に絞ることもできる。

### `--state` の典型的な置き場所

| 環境 | `--state` の中身 |
|---|---|
| ローカル | 直前 build の `target/manifest.json` を `prev-manifest/` にコピー |
| CI | main ブランチの本番 manifest を artifact として download し `./prod-manifest/` に展開 |
| `--defer` 併用 | 本番 manifest を渡し、未変更 model は本番 schema を参照させる (上級) |

### CI における典型パターン

```bash
# main ブランチの最新 manifest を取得
gh run download <main-build-id> -n manifest -D ./prod-manifest

# PR で変わった model + 下流だけ build & test
dbt build --select state:modified+ --state ./prod-manifest --defer
```

これで「PR で 1 model 触ったら 1 model + 下流のみ build、上流は本番 schema を参照」という最小コスト CI が完成する。

### 採点で何を見ているか

- `file_exists` で `state-modified.md` 存在
- `shell_command` で `dbt run --select state:modified+ --state ./prev-manifest/` を実行 (= 学習者の prev-manifest が正しく置けているか)
- md に「変更 model + 下流 model」両方の名前を grep
- (ベースライン manifest が無いと grader は失敗する。学習者は事前に `prev-manifest/manifest.json` を必ず作っておく)

### 注意 — `prev-manifest/` の git 扱い

- `prev-manifest/manifest.json` は学習者が **自分の手元** で作るものなので git にコミットしない方が良い (.gitignore 推奨)
- だが採点 CI は `prev-manifest/` を生成するステップが必要 (採点 yaml 内の shell_command で `mkdir + cp` を含めるか、学習者にコミットさせるかの判断)
- 本問の grading では「学習者の手で事前に `prev-manifest/` を作っておく」前提で grader が `--state ./prev-manifest/` を読みに行く。`prev-manifest/manifest.json` 不在なら採点失敗 → ヒントで気づく

### 次の問 (9-9) との接続

- 9-8 で「**範囲を絞って build**」を学んだ後、9-9 では「**build 中に test が失敗したら下流を SKIP する依存ガード**」に進む
- 「**最小範囲を build → test 失敗で下流を止める**」 = CI で「壊れたところだけ build、壊れたら下流を即停止」が完成
