# 7-8 解答例

## ゴール再掲

- `dbt build --select +int_orders_with_historical_price_100knock` を実行
- ログに **snapshot ステップ → model ステップ → test ステップ** が
  順に出ることを確認
- ログを `docs/exercises/100-knock/topic-7-snapshot/build-log.md` に保存

## 実行コマンド

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt build --profiles-dir . \
    --select +int_orders_with_historical_price_100knock \
    --no-colors \
    2>&1 | tee /tmp/build-7-8.log
cd ..
```

`--no-colors` は md に貼ったときに ANSI escape が混じらないようにするため
(任意)。`tee` で標準出力に流しつつファイルにも残す。

## 期待ログ (要約)

```text
06:00:00  Running with dbt=1.11.0
06:00:00  Registered adapter: postgres=...
06:00:00  Found N models, M snapshots, K tests, ...

06:00:01  Concurrency: 4 threads
06:00:01
06:00:01  1 of 9 START sql view model staging.stg_products_100knock ........... [RUN]
06:00:01  1 of 9 OK   created sql view model staging.stg_products_100knock ... [CREATE VIEW in 0.10s]
06:00:01  2 of 9 START sql view model staging.stg_orders_100knock ............. [RUN]
06:00:01  2 of 9 OK   created sql view model staging.stg_orders_100knock ..... [CREATE VIEW in 0.09s]
...
06:00:02  4 of 9 START snapshot snapshots.snap_products_100knock .............. [RUN]
06:00:02  4 of 9 OK   snapshotted snapshots.snap_products_100knock ........... [SELECT 0 in 0.20s]
...
06:00:02  6 of 9 START sql view model intermediate.int_order_details_100knock . [RUN]
06:00:02  6 of 9 OK   created sql view model intermediate.int_order_details_100knock [CREATE VIEW in 0.11s]
06:00:02  7 of 9 START sql view model intermediate.int_orders_with_historical_price_100knock [RUN]
06:00:02  7 of 9 OK   created sql view model intermediate.int_orders_with_historical_price_100knock [CREATE VIEW in 0.13s]
06:00:03  8 of 9 START test not_null_int_orders_with_historical_price_100knock_unit_price [RUN]
06:00:03  8 of 9 PASS  not_null_int_orders_with_historical_price_100knock_unit_price [PASS in 0.05s]
06:00:03  9 of 9 START test unique_int_orders_with_historical_price_100knock_order_id [RUN]
06:00:03  9 of 9 PASS  unique_int_orders_with_historical_price_100knock_order_id [PASS in 0.05s]

06:00:03  Done. PASS=9 WARN=0 ERROR=0 SKIP=0 TOTAL=9
```

実順序のポイント:

- **snapshot → model**: snapshot を ref している model は `depends_on` で
  snapshot に紐づくので、snapshot が先に走らないと model 側が古い snapshot
  を読むことになる。dbt のスケジューラがこれをトポロジカル順に解決する。
- **model → test**: 物理化されていないと test は実行できないので、必ず
  model の後ろ。
- `SELECT 0` の意味: 「既存 snapshot に対して INSERT すべき新行が 0 件」
  = 入力 raw.products に変化が無かった (= 冪等。詳細 7-9)。

## build-log.md (例)

`docs/exercises/100-knock/topic-7-snapshot/build-log.md`:

```markdown
# 7-8 build-log

## 実行コマンド

\`\`\`bash
cd dbt
../.venv/bin/dbt build --profiles-dir . \
    --select +int_orders_with_historical_price_100knock \
    --no-colors
\`\`\`

## 結果サマリ

`Done. PASS=9 WARN=0 ERROR=0 SKIP=0 TOTAL=9`

## 抜粋ログ (snapshot / model / test の順序が見える部分)

\`\`\`text
06:00:02  4 of 9 START snapshot snapshots.snap_products_100knock .............. [RUN]
06:00:02  4 of 9 OK   snapshotted snapshots.snap_products_100knock ........... [SELECT 0 in 0.20s]
06:00:02  7 of 9 START sql view model intermediate.int_orders_with_historical_price_100knock [RUN]
06:00:02  7 of 9 OK   created sql view model intermediate.int_orders_with_historical_price_100knock [CREATE VIEW in 0.13s]
06:00:03  8 of 9 PASS  not_null_int_orders_with_historical_price_100knock_unit_price [PASS in 0.05s]
06:00:03  9 of 9 PASS  unique_int_orders_with_historical_price_100knock_order_id [PASS in 0.05s]
\`\`\`

snapshot が **先** に走り (4 of 9)、それを ref している model
(7 of 9) → 上に張った test (8〜9 of 9) という順で完走している。

## なぜ `dbt run` だけではダメか

`dbt run` は snapshot を **走らせない**。仮に raw.products が更新されている
状況で `dbt run` だけ叩くと、snap_products_100knock は古いまま、
`int_orders_with_historical_price_100knock` が引き当てる「注文時点の単価」も
古いまま、という整合性ズレが起きる。`dbt build` は snapshot / model / test
を 1 本で順序保証付きで動かす総合コマンドで、CI / 本番 cron はこの形が原則。
```

形式は自由、行数は 30〜100 行を目安。

## 解説まとめ

1. **`dbt build` は総合コマンド**: `seed` + `run` + `snapshot` + `test` を
   トポロジカル順に直列で実行する。本番運用 / CI で「全部更新」に使う 1 本。
   `dbt run` / `dbt snapshot` / `dbt test` は **個別 stage を走らせたい時の
   下位コマンド**。普段は `dbt build` で良い。
2. **`+<node>` セレクタの威力**: 「この node を更新するために必要な上流すべて
   + 自分」を 1 文字で表現できる。これがあるので「snap → model → test の
   1 系統だけ」を局所的に再ビルドできる。`<node>+` (下流) と組み合わせると
   `+<node>+` (上下流すべて) になり、影響範囲全体を再ビルドできる。
3. **トポロジカル順序の保証**: dbt スケジューラは manifest の DAG から
   実行順を決める。snapshot を ref している model は **必ず snapshot の後**
   に走る = 「snap の最新 v が model に乗る」 整合性が常に保たれる。
4. **ログを成果物として残す習慣**: build ログは「あの時点で DAG は通って
   いたか」の **エビデンス**。本番運用では artifact として S3 や Actions
   summary に残す。本演習では md に保存することで PR レビュー時にも参照可能。
5. **次の問 (7-9)**: 同じ `dbt snapshot` を 2 回叩いて **何も起きない**
   (= no-op = 冪等) ことを確認する。冪等性は dbt 全体の設計原則であり、
   snapshot もこの原則に従う。
