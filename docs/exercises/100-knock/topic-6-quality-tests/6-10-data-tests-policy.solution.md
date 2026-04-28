# 6-10 解答例

## dbt/dbt_project.yml (data_tests: セクション追加後)

```yaml
name: 'local_analytics'
version: '1.0.0'
config-version: 2

profile: 'local_analytics'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  local_analytics:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts

# ----------------------------------------------------------------------------
# data_tests: テスト運用ポリシーの宣言
# ----------------------------------------------------------------------------
# - staging 配下の全 test に store_failures: true を継承
#   → 失敗行を dbt_test__audit に永続化、デバッグループが SQL で完結
# - marts には何も継承させない (mart のテストは contract / not_null など
#   破壊力の高いものが多く、失敗行を残す価値は staging より低い)
# - 6-9 で個別 test に書いた store_failures: true は本宣言と冗長になるが、
#   個別宣言は親宣言を上書きする (= 同値) ため矛盾は起きない。
# ----------------------------------------------------------------------------
data_tests:
  local_analytics:
    staging:
      +store_failures: true
    # marts: 配下は宣言しない (= 継承されない)
    # 必要なら +store_failures: false を明示
```

**ポイント**:

- **`data_tests:` ルートキー**: dbt 1.8+ の正式名。`tests:` (旧名) も
  後方互換で動くが、本リポジトリ (dbt-core 1.11) では新名を使う。
- **`local_analytics:` は project 名と一致**: `name: 'local_analytics'` と
  揃えないとサイレントに無効化される (= parse は通るのに継承されない最悪の罠)。
- **`+store_failures: true`**: `+` 前置きが「**この階層配下の全 test に継承**」
  の意味。`+` を忘れるとディレクトリ名として解釈されて効かない。
- **marts に書かない選択**: 「明示的に false を書く」 と「何も書かない」 は
  同じ効果 (デフォルト false)。本問は読み手に「marts には意図的に貼らない」 ことを
  伝えるため **コメントで宣言** している。

## manifest で継承を確認

```bash
$ ../.venv/bin/dbt parse --profiles-dir .

$ python3 -c "
import json
m = json.load(open('target/manifest.json'))

# staging 配下の test
staging_tests = [n for k, n in m['nodes'].items()
                 if n.get('resource_type') == 'test'
                 and 'staging' in n.get('fqn', [])]
print('=== staging tests (sample 3) ===')
for t in staging_tests[:3]:
    print(f\"  {t['name'][:60]:60s} | store_failures={t['config'].get('store_failures')}\")

# marts 配下の test
marts_tests = [n for k, n in m['nodes'].items()
               if n.get('resource_type') == 'test'
               and 'marts' in n.get('fqn', [])]
print('=== marts tests (sample 3) ===')
for t in marts_tests[:3]:
    print(f\"  {t['name'][:60]:60s} | store_failures={t['config'].get('store_failures')}\")
"
=== staging tests (sample 3) ===
  not_null_stg_customers_100knock_customer_id                  | store_failures=True
  unique_stg_customers_100knock_customer_id                    | store_failures=True
  not_null_stg_customers_100knock_email                        | store_failures=True
=== marts tests (sample 3) ===
  not_null_mart_daily_sales_100knock_order_date                | store_failures=False
  unique_mart_daily_sales_100knock_order_date                  | store_failures=False
  not_null_mart_daily_sales_100knock_order_count               | store_failures=False
```

**staging は True、marts は False** と継承が効いている。

## 動作確認 (任意): staging で failure が永続化される

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'unknown' WHERE product_id = 1;"

$ ../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
... FAIL ... 
... See test failures: SELECT * FROM dbt_test__audit.accepted_values_...

$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "\dt dbt_test__audit.*"
              List of relations
      Schema      |    Name             | Type
------------------+---------------------+-------
 dbt_test__audit  | accepted_values_... | table
```

戻す:

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'food' WHERE product_id = 1;"
```

## ロールバック手順

```bash
$ cd /Users/hatanotakuma/works/dbt-tutorial/gitworktree/feature-100-knock-topic-6-7
$ git diff dbt/dbt_project.yml
+++ b/dbt/dbt_project.yml
@@ -28,2 +28,7 @@
       +materialized: table
       +schema: marts
+
+data_tests:
+  local_analytics:
+    staging:
+      +store_failures: true

$ git checkout -- dbt/dbt_project.yml   # 元に戻す
$ ../.venv/bin/dbt parse --profiles-dir .
$ python3 -c "..."   # staging tests も store_failures=False に戻ることを確認
```

> **本問の grading は dbt_project.yml を編集した状態** で実行する。ロールバックは
> 100-knock 全体の通し演習に戻る時に行う運用判断。本問の学習目的を達成したら
> 戻して構わない。

## 解説まとめ

- **なぜテスト運用ポリシーを dbt_project.yml で宣言するか**:
  - **属人化排除**: test ごとに `store_failures: true` を貼る運用は、新人が
    新規 test を書いた時に「貼り忘れる」 → ポリシーが守られない、という
    ヒューマンエラーが起きる。階層宣言なら **「staging に書いた test は
    自動で継承される」** ため、貼り忘れない。
  - **コードレビュー対象になる**: 「staging には store_failures、marts には
    contract: enforced」 のような **層別ポリシー** が dbt_project.yml 1 ファイルで
    一望できる → PR レビュアーが読むべき場所が明確化。
  - **変更が一括で効く**: 「staging の test 全部に severity: warn を一時的に
    付けたい」 みたいな運用判断が、dbt_project.yml の 1 行追加で実現できる。
- **設定の優先順位 (上位ほど強い)**:
  1. schema.yml の `tests:` 配下の `config:` 個別宣言
  2. dbt_project.yml の `data_tests:` 階層宣言 (本問)
  3. dbt-core デフォルト (= store_failures: false 等)
  → 個別宣言で例外を書ける。「全 staging で store_failures: true、ただしこの
  test だけ false」 のような微調整が可能。
- **`+` prefix の動作仕様**:
  - `+store_failures: true` → この階層配下に継承
  - `store_failures: true` (+ なし) → ディレクトリ名と解釈、無効
  - `+severity: warn` → 同様に severity を継承
  - dbt の **設定継承メカニズム** は YAML 階層 + `+` 接頭辞で表現されている。
- **「設定もコード」 = レビュー対象になる効能**:
  - 運用エンジニアが「失敗行を残したい」 と判断 → schema.yml に `store_failures: true`
    を貼る → PR レビュー → マージ。
  - dbt_project.yml で **layer 単位** に変えるなら、レビュアーは「staging 全 test
    の挙動が変わる」 という影響範囲を意識して見られる。
  - **GUI ツールで設定変更 = 履歴が残らない / レビューされない / 属人化** の
    アンチテーゼとしてのコード化。
- **6-9 (個別宣言) との使い分け軸**:
  - **「全 staging 一律」 のような **横断ポリシー** → dbt_project.yml**
  - **「この test だけ特別扱い」 のような **個別判断** → schema.yml の config:**
  - **両方使ってよい**: 階層宣言で大方針、個別宣言で例外、という二段構え。
- **「test ポリシーをコードで宣言する」 が変えるのは何か**:
  - test の **量** が増えても、運用ルールが **属人化しない**。
  - 「データ品質 SLO は、コードで読み書きできる契約」 という Topic ⑥ 全体の
    最終形を、dbt_project.yml 上に **明文化** することで体現する。
  - test は **「実行されるたびに緑/赤を吐く動的なもの」** ではなく、**「ポリシーが
    宣言され、結果が観測される、運用される対象」** へと格上げされる。
- **ロールバック前提で書く理由**:
  - 本問は dbt_project.yml の **共有設定ファイル** を編集する。100-knock 他問題で
    `staging` 配下に追加された test が、本問の継承で予期せず `store_failures: true`
    になる可能性がある。
  - 学習目的の達成後はロールバックして、他問題への影響を切り離す。
  - 本番運用では「ロールバックなし、ポリシーを残す」 が正しい振る舞い。
    学習環境では「ポリシー学習 → 戻す」 が安全。
