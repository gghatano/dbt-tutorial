# 6-10: dbt_project.yml の data_tests: で staging だけに +store_failures: true を付与

## シナリオ

6-9 で `store_failures: true` を **test 1 つずつ** に貼ることを学んだ。だが
プロジェクトに 100 個 test があれば 100 箇所書く羽目になり、また「mart の test
には付けない」 「staging だけ付ける」 のような **layer ごとの運用ポリシー** を
test 単位の宣言で散らばらせると、レビューで全体像が見えない。

dbt_project.yml の **`data_tests:` セクション** で、`+store_failures` /
`+severity` / `+enabled` などの設定を **モデル階層 (`staging:` / `marts:`) ごとに
継承宣言** できる。「staging 配下の全 test には store_failures: true を継承、
marts には付けない」 のような **テスト運用ポリシー** が dbt_project.yml 上に
1 ヶ所に集約される。

学習者は dbt_project.yml を編集して `data_tests:` セクションを追加し、
parse + manifest 上で「staging の test に store_failures が継承されている」
「marts の test には継承されていない」 ことを確認する。**最後に Step 5 で
ロールバック** する (本問は学習目的の編集なので、他 100-knock との
非干渉を保つため)。

## 学べること

- `dbt_project.yml` の `data_tests:` 階層宣言の構文
- `+store_failures` / `+severity` のような **+prefix** 付き継承設定の仕組み
- 「test ごとの宣言 (6-9)」 と「layer ごとの宣言 (6-10)」 の **使い分け軸**
- なぜテスト運用ポリシーをコードで宣言するのか (= 属人化排除)
- 設定の **優先順位**: 個別 schema.yml > dbt_project.yml の階層 > プロジェクト全体

## 前提

- Topic ② ③ ④ ⑤ + Topic ⑥ 6-1〜6-9 完了
- `dbt/dbt_project.yml` の `models:` セクションに staging / intermediate / marts
  が階層宣言されている (本リポジトリ初期状態のまま)
- 6-9 までで `staging` / `marts` 配下に test がいくつか宣言済み

## 入力データ

不要。dbt_project.yml の編集と manifest 確認のみ。

## 課題

### Step 1: dbt_project.yml に data_tests: セクションを追加

`dbt/dbt_project.yml` の末尾 (または `models:` の下) に追加:

```yaml
data_tests:
  local_analytics:
    staging:
      +store_failures: true
    # marts: には何も書かない (= store_failures は継承されない)
```

要件:

- `data_tests:` ルートキー (dbt 1.8+ の正式名。1.7 以前は `tests:`)
- 配下に `<project_name>:` (本リポジトリは `local_analytics`)
- `staging:` ブロックに `+store_failures: true` (前置きの `+` を忘れない)
- `marts:` ブロックは追加しない or 追加しても `+store_failures: false` を明示

### Step 2: parse して manifest を確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
```

manifest 上で確認:

```bash
python3 -c "
import json
m = json.load(open('target/manifest.json'))

# staging 配下の test の store_failures
staging_tests = [n for k, n in m['nodes'].items()
                 if n.get('resource_type') == 'test'
                 and 'staging' in n.get('fqn', [])]
print('staging tests sample (store_failures):')
for t in staging_tests[:3]:
    print(f\"  {t['name'][:60]:60s} | store_failures={t['config'].get('store_failures')}\")

# marts 配下の test の store_failures
marts_tests = [n for k, n in m['nodes'].items()
               if n.get('resource_type') == 'test'
               and 'marts' in n.get('fqn', [])]
print('marts tests sample (store_failures):')
for t in marts_tests[:3]:
    print(f\"  {t['name'][:60]:60s} | store_failures={t['config'].get('store_failures')}\")
"
```

期待: staging 配下の test は `store_failures=True`、marts 配下は
`store_failures=False` (or `None`) になる。

### Step 3: dbt test で実際に failure 保存挙動を確認 (任意)

stg_products_100knock の category に違反データを混ぜて (6-9 と同様):

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.products SET category = 'unknown' WHERE product_id = 1;"

../.venv/bin/dbt test --profiles-dir . --select stg_products_100knock
# FAIL し、dbt_test__audit に table ができる (project.yml 経由で継承された)
```

戻す: `UPDATE raw.products SET category = 'food' WHERE product_id = 1;`

### Step 4: marts 側に「継承されていないこと」 を確認

mart 側の test (例: `not_null_mart_daily_sales_100knock_total_sales_amount`) を
わざと FAIL させても、`dbt_test__audit.<test>` table は **作られない** ことを
確認する (省略可、manifest 確認で十分)。

### Step 5: ロールバック (重要)

本問は **dbt_project.yml を編集** したので、他 100-knock との干渉を避けるため
**最後に必ず元に戻す**:

```bash
cd /Users/hatanotakuma/works/dbt-tutorial/gitworktree/feature-100-knock-topic-6-7
git diff dbt/dbt_project.yml         # 何を追加したか確認
git checkout -- dbt/dbt_project.yml  # 戻す
```

または、`data_tests:` セクションだけを手で削除。

> **注**: 採点 (grading) は dbt_project.yml を編集**したまま** 走らせる。
> ロールバックは「100-knock 全体の通し演習に戻る時」 に行う運用判断。

## 完了条件

- [ ] `dbt/dbt_project.yml` に `data_tests:` ブロックがある
- [ ] `data_tests.local_analytics.staging.+store_failures` が `true` になっている
- [ ] `dbt parse` が成功する
- [ ] manifest 上で staging 配下の test の `config.store_failures` が `true` で
      継承されている (1 個でも確認できれば OK)
- [ ] manifest 上で marts 配下の test の `config.store_failures` が `true` で
      **ない** (= 継承されていない)

## ヒント (詰まったら)

- **`tests:` vs `data_tests:`**: dbt 1.8+ で `tests:` が deprecated、
  `data_tests:` が正式名。本リポジトリの dbt-core 1.11 では両方動くが、
  新規宣言は `data_tests:` を使う。
- **`+` prefix の意味**: `+store_failures: true` の `+` は dbt 設定階層で
  「この階層配下の全ノードに継承される」 マーカー。`+` を忘れると単なる
  ディレクトリ名扱いになり、効かない。
- **`local_analytics:` 直下が project 名**: `dbt_project.yml` 冒頭の
  `name: 'local_analytics'` と一致させる。違うとサイレントに無効化されて
  「効いていないのに parse は通る」 状態になる (= 罠)。
- **layer 階層は `models:` セクションと同じ命名**: `models/staging/` 配下の
  ファイルが `staging:` ブロックで継承を受ける。`models/100-knock/topic-3/` は
  本リポジトリでは `models:` の `local_analytics:` 直下に書かれていないので、
  実際の継承挙動を確認する場合は本問の test 対象が `models/staging/` 配下に
  あるか、`models/100-knock/topic-3/` 配下にあるかで挙動が分かれる点に注意。
- **継承の優先順位** (高い → 低い):
  1. **schema.yml 内の test 個別 `config:` 宣言** (= 6-9 で書いた方法)
  2. **dbt_project.yml の `data_tests:` 階層宣言** (= 本問)
  3. **dbt-core 内のデフォルト** (`store_failures: false`)
  → 個別宣言は階層宣言を上書きする (Python の MRO に近い感覚)。
- **本リポジトリ models 階層の確認**:
  `dbt/dbt_project.yml` の `models:` ブロックで `staging:`/`intermediate:`/`marts:` が
  どう定義されているかを確認。本問の `data_tests:` も同じ階層名で書く。

## 解答例

詳細は [`6-10-data-tests-policy.solution.md`](6-10-data-tests-policy.solution.md) を参照。
