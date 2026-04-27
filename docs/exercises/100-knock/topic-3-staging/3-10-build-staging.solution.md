# 3-10 解答例

## docs/exercises/100-knock/topic-3-staging/build-log.md

```markdown
# 100-knock Topic ③ staging build ログ

実行日: 2026-04-26
実行者: 学習者
ベース: 3-1〜3-9 完了状態 (stg_*_100knock 4 model + schema.yml + dbt_project.yml の 100-knock セクション)

## 1. 実行コマンド

```bash
cd dbt
dbt build --select 100-knock.topic-3 --profiles-dir . 2>&1 | tee /tmp/topic-3-build.log
```

## 2. 出力サマリ

```
12:00:00  Found 8 models, 4 sources, 21 tests, ...
12:00:01  Concurrency: 4 threads (target='dev')

12:00:02  1 of 25 START sql view model staging_100knock.stg_customers_100knock ... [RUN]
12:00:02  2 of 25 START sql view model staging_100knock.stg_products_100knock  ... [RUN]
12:00:02  3 of 25 START sql view model staging_100knock.stg_stores_100knock    ... [RUN]
12:00:02  4 of 25 START sql view model staging_100knock.stg_orders_100knock    ... [RUN]
12:00:03  1 of 25 OK created sql view model staging_100knock.stg_customers_100knock ... [CREATE VIEW in 0.4s]
12:00:03  2 of 25 OK created sql view model staging_100knock.stg_products_100knock  ... [CREATE VIEW in 0.4s]
12:00:03  3 of 25 OK created sql view model staging_100knock.stg_stores_100knock    ... [CREATE VIEW in 0.4s]
12:00:03  4 of 25 OK created sql view model staging_100knock.stg_orders_100knock    ... [CREATE VIEW in 0.4s]

12:00:04  5 of 25 START test not_null_stg_customers_100knock_customer_id ... [RUN]
12:00:04  6 of 25 START test unique_stg_customers_100knock_customer_id   ... [RUN]
... (中略 - test 21 個が並列実行)
12:00:08 25 of 25 PASS positive_value_stg_orders_100knock_quantity ... [PASS in 0.3s]

12:00:09  Finished running 4 view models, 21 tests in 7.5s.

Done. PASS=25 WARN=0 ERROR=0 SKIP=0 TOTAL=25
```

## 3. 内訳

- **model run**: 4 (stg_customers / stg_products / stg_stores / stg_orders)
- **test**: 21
  - 4 × not_null + 4 × unique = 8 (各 PK)
  - 3 × relationships (stg_orders.customer_id / product_id / store_id)
  - 6 × not_null (FK 列 + order_date + quantity + unit_price)
  - 2 × positive_value (3-5 の自作 generic test, unit_price と quantity)
  - その他 2 (stg_products.unit_price not_null, etc.)
- **WARN/ERROR/SKIP**: 0

## 4. 学び

- `dbt build` は per-node atomic 実行。stg_customers の view 作成が PASS したら即その PK test (`not_null` / `unique`) が走る
- 4 model 並列で view 作成 → 21 test が依存順序を守りながら並列実行 → 7.5s で完了
- 失敗していたら、その node の **下流 test が SKIP される** (依存違反を伝播させない)。今回は 0 SKIP なので「依存元から末端まで契約が成立」を意味する
- このログ自体が「Topic ③ 完了の証跡」。CI で同じコマンドが PASS している限り、staging 層の契約は守られている

## 5. 失敗→修正ループの記録 (もしあれば)

(なし。1 発で通った)
```

**ポイント**:

- **`Done. PASS=N WARN=N ERROR=N SKIP=N` の 1 行サマリ**: build の結果はこの行だけ見れば判定できる。`ERROR=0 SKIP=0` で全 PASS。
- **per-node atomic の効能**: stg_customers の view 作成 → その PK test → stg_orders の view 作成 → その FK test (= stg_customers の test 後に走る) という順序が DAG から自動算出される。`dbt run` 後に `dbt test` を別フェーズで走らせる旧来運用より圧倒的に速くて局所化が利く。
- **selector の選択**: `--select 100-knock.topic-3` は `dbt_project.yml` の階層名による指定。3-8 で `models.local_analytics.100-knock.topic-3:` の形にしたから使える。物理パス `dbt/models/100-knock/topic-3` でも同じ結果。
- **build-log.md は CI で自動生成しても良い**: GitHub Actions 上で `dbt build --select 100-knock.topic-3 | tee build.log` し、PR コメントに添付する運用にすれば手動更新不要。本問は学習者が手で残す形。
- **採点が緩い理由**: build の出力ログは長くて整形しづらい。`Done. PASS=` 行のキャプチャ + コマンドが書かれていれば「実行した」証跡として十分とする。

## 実行例 (採点 shell_command 視点)

```
$ cd dbt && dbt build --select 100-knock.topic-3 --profiles-dir . 2>&1 | tail -5
12:00:09  Finished running 4 view models, 21 tests in 7.5s.

Done. PASS=25 WARN=0 ERROR=0 SKIP=0 TOTAL=25

$ cd dbt && dbt build --select 100-knock.topic-3 --profiles-dir . 2>&1 | grep -c 'ERROR=0 SKIP=0'
1
```

## 解説まとめ

- **なぜ `dbt build` を staging 単位で?**: 「staging 層の契約を 1 コマンドで検証する」ため。CI workflow に `dbt build --select 100-knock.topic-3` を 1 行入れれば、staging 層の run + test 全 PASS が継続的に保証される。
- **`dbt build` の atomic per-node**:
  1. DAG をトポロジカルソート
  2. 依存元 (上流) から順に node を取り出す
  3. node が model なら run、test なら test を実行
  4. PASS なら次の node、FAIL なら **その node の下流を全 SKIP**
  - これが「失敗の局所化」。stg_customers の test が FAIL すれば、stg_orders の test も走らない (走らせる意味がない)。
- **`dbt run + dbt test` の限界**: phase-separated 運用だと、stg_orders の test FAIL は stg_orders / stg_customers / stg_products / stg_stores 全部 run 完了後に判明する。失敗したらどこから直すか迷う。`dbt build` なら「最初に FAIL した test の node」が原因の起点。
- **レイヤー単位の build = レイヤー contract の検証**: staging 層が「raw を型 cast + 正規化 + PK/FK 契約付きで提供する view 群」というレイヤー contract を持っていることを `dbt build --select staging` 1 コマンドで CI が保証する。intermediate / mart も同じ思想で各層 build。
- **WARN との付き合い方**: `dbt source freshness` 違反 / `tests` の `severity: warn` 設定 / カスタム macro の警告などで WARN が出る。WARN は「契約違反の前段階」「目を向けるべき」のサイン。ERROR ではないので build は PASS するが、CI で WARN を ERROR に昇格させる運用 (`--warn-error`) も実務ではある。
- **ログを残す習慣**: build-log.md は将来「いつから staging が契約を守っているか」「どの commit で WARN が出始めたか」の調査の起点。git log と build-log.md を突き合わせれば原因が辿れる。
