# 5-7 解答例

## ゴール再掲

- `dbt/models/100-knock/topic-5/_groups.yml` で `marts_finance` group を定義
- `dbt/models/100-knock/topic-5/mart_customer_lifetime_value_100knock.sql` を新規作成し、`config(group='marts_finance', access='private')` で finance グループに所属させる
- `dbt build --select mart_customer_lifetime_value_100knock` で table が作られることを確認
- manifest にも group / access が記録されていることを確認

## Step 1: `_groups.yml`

`dbt/models/100-knock/topic-5/_groups.yml`:

```yaml
version: 2

# 100-knock Topic ⑤ 5-7: model のオーナーシップと公開範囲を宣言する
# - groups: の owner: は dbt docs に表示される
# - 同一 group 内の model 同士のみ private node を ref() できる
groups:
  - name: marts_finance
    owner:
      name: Finance Team
      email: finance@example.com
      slack: "#mart-finance"
```

## Step 2: `mart_customer_lifetime_value_100knock.sql`

`dbt/models/100-knock/topic-5/mart_customer_lifetime_value_100knock.sql`:

```sql
{{ config(
    materialized='table',
    schema='marts',
    group='marts_finance',
    access='private'
) }}

-- mart_customer_lifetime_value_100knock
-- ----------------------------------------------------------------------
-- Grain: 1 customer = 1 row.
-- Owner: marts_finance group (see _groups.yml).
-- Access: private — only models inside marts_finance group may ref() this.
--
-- Business rule:
--   - lifetime_sales_amount = sum(quantity * unit_price) over all orders
--   - tenure_days = last_order_date - first_order_date
--   - 注文 0 件の顧客は表示しない (INNER JOIN で自動的に除外)
-- ----------------------------------------------------------------------

with order_agg as (
    select
        o.customer_id,
        count(*)                              as lifetime_order_count,
        sum(o.quantity * o.unit_price)::numeric(18, 2) as lifetime_sales_amount,
        min(o.order_date)                     as first_order_date,
        max(o.order_date)                     as last_order_date
    from {{ ref('stg_orders_100knock') }} as o
    group by o.customer_id
)

select
    c.customer_id,
    c.customer_name,
    a.lifetime_order_count,
    a.lifetime_sales_amount,
    a.first_order_date,
    a.last_order_date,
    (a.last_order_date - a.first_order_date) as tenure_days
from {{ ref('stg_customers_100knock') }} as c
inner join order_agg as a on a.customer_id = c.customer_id
order by a.lifetime_sales_amount desc
```

> `int_order_details_100knock` が Topic ④ で完成している場合は `{{ ref('int_order_details_100knock') }}` を直接 `from` 句に使ってもよい (集計の起点が揃って読みやすい)。本解答は最小依存で書いた版。

## Step 3: parse / build

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
# 22:10:01  Found 12 models, 4 sources, ...

../.venv/bin/dbt build --select mart_customer_lifetime_value_100knock --profiles-dir .
# 22:10:11  1 of 1 START sql table model marts.mart_customer_lifetime_value_100knock ... [RUN]
# 22:10:11  1 of 1 OK created sql table model marts.mart_customer_lifetime_value_100knock ... [SELECT 100 in 0.30s]
# Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=1
```

## Step 4: manifest 確認

```bash
../.venv/bin/python -c "
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.mart_customer_lifetime_value_100knock']
print('group =', node['config'].get('group'))
print('access =', node.get('access'))
"
# group = marts_finance
# access = private
```

`groups` トップレベルにも:

```bash
../.venv/bin/python -c "
import json
m = json.load(open('target/manifest.json'))
print(list(m['groups'].keys()))
print(m['groups']['group.local_analytics.marts_finance']['owner'])
"
# ['group.local_analytics.marts_finance']
# {'email': 'finance@example.com', 'name': 'Finance Team', 'slack': '#mart-finance'}
```

## Step 5 (任意): `private` の効果を確認

`dbt/models/100-knock/topic-5/_test_violation.sql` (一時的):

```sql
{{ config(materialized='view', schema='marts') }}
select * from {{ ref('mart_customer_lifetime_value_100knock') }}
```

`dbt parse`:

```
Compilation Error in model _test_violation
  Node model.local_analytics._test_violation attempted to reference
  node model.local_analytics.mart_customer_lifetime_value_100knock,
  which is not allowed because the referenced node is private to the marts_finance group.
```

エラーを確認したらファイルを削除:

```bash
rm dbt/models/100-knock/topic-5/_test_violation.sql
```

(逆に `_test_violation.sql` の冒頭にも `config(group='marts_finance')` を足すと、parse は通る = 同 group なら private mart も `ref()` 可。)

## Step 6: 採点

```bash
python3 scripts/grader/grade.py \
  --grading-file docs/exercises/100-knock/topic-5-mart/5-7-mart-groups-access.grading.yaml
```

期待:

```
## Grading Result: OK (100%)
| OK | groups-yml-exists                  | 10/10 |
| OK | mart-sql-exists                    | 15/15 |
| OK | dbt-parse-success                  | 15/15 |
| OK | manifest-node-exists               | 15/15 |
| OK | manifest-config-group-private      | 25/25 |
| OK | dbt-build-mart-success             | 20/20 |
```

## ポイント

- **groups は「責任の宣言」**: model 1 つ 1 つに owner を書くと冗長になる。`group:` で 1 段階抽象化し、group に owner を持たせる設計。`schema.yml` での重複が減り、チーム異動で owner が変わっても 1 ファイル変更で済む。
- **`access: private` の build 時保証**: `private` model を別 group が `ref()` した瞬間、`dbt parse` (= compile 段階) で fail する。実行時ではなく **コードを書いた瞬間に検出** されるのが宣言ファーストの強み。
- **`access: public` は dbt mesh 用**: 単一 project では `protected` と機能的に同じ。dbt 1.6+ の cross-project ref では `public` model だけが他 project から参照可能。「将来的に他 project から使われる予定の mart は `public`、内部実装は `private` / `protected`」という設計が将来の mesh 化を楽にする。
- **`config(group=...)` vs `schema.yml` での宣言**: SQL の `config()` ブロックに書く方が「model 自体の属性」感が出て読みやすい。`schema.yml` に書くとテストや description と一緒に俯瞰できる利点がある。本解答は SQL 内方式。
- **`dbt_project.yml` の path-based group**: `models.local_analytics.100-knock.topic-5: { +group: marts_finance }` と書けば配下全 model に group が継承される。本問は 1 model だけなので個別宣言にしたが、Topic ⑤ の mart 全部を `marts_finance` にしたいならこの方式が短い。
- **`marts_finance` という命名**: domain (finance / marketing / product) を group 名にするのが業界慣習。`mart_*` か `int_*` かでは分けない (それは layer であって ownership ではない)。

## 実行例 (採点 shell_command 視点)

```bash
$ test -f dbt/models/100-knock/topic-5/_groups.yml && echo OK
OK
$ test -f dbt/models/100-knock/topic-5/mart_customer_lifetime_value_100knock.sql && echo OK
OK
$ cd dbt && dbt parse --profiles-dir . 2>&1 | tail -3
22:10:01  Found 12 models, 4 sources, 25 tests, ...
$ python3 -c "import json; m=json.load(open('target/manifest.json')); n=m['nodes']['model.local_analytics.mart_customer_lifetime_value_100knock']; print(n['config']['group'], n['access'])"
marts_finance private
```

## 解説まとめ

- **なぜ `groups:` / `access:` で公開範囲を宣言？**: mart 数が増えると「うっかり他チームの内部 mart を `ref()` してしまう」事故が発生する。それを **コードレビューと build 前** に止めるのが `private`。「壊しちゃいけないものは型で守る」プログラミング言語の発想を dbt に持ち込んだ機能。
- **dbt 1.5+ の宣言群の 4 点セット**:
  1. `contract: enforced` (5-3) — 列の型を契約として宣言
  2. `+grants:` (5-6) — 誰が SELECT できるかを宣言
  3. `groups:` + `access:` (本問) — 誰がオーナーで誰が参照できるかを宣言
  4. `meta:` (5-8) — 運用 SLA / Slack 連絡先を宣言
  - これら全部「mart は対外契約の塊」という Topic ⑤ Intro の考えを実装する機構。手続き (hook / 命名規則) ではなく **宣言 + build 時 fail** で守るのが共通設計。
- **group のスコープ**: 1 group 内なら private model も `ref()` 可。group 外からは `protected` 以上が要る。group は「コードベースの中の小さなチーム」と思うと感覚が合う。
- **将来の dbt mesh への足がかり**: `public` を意識的に使い分けると、「この project のうち、外に公開するのはどの mart？」が `dbt ls --select 'config.access:public'` で抽出できる。後で project 分割するときの境界候補が機械的に決まる。
- **owner が必須ではない**: `groups:` の `owner:` は省略可能だが、書かないと意味が半減する。group の存在意義は「責任主体を明示する」ことなので、必ず `email` か `slack` のどちらかは入れる。

## 拡張アイデア

- **複数 group**: `marts_marketing` group も追加し、`mart_top_rated_products_100knock` (5-1) を `marts_marketing` に所属させる。両 group の境界を `dbt ls --select 'group:marts_finance'` で確認
- **CI で「group が宣言されていない model を検出」**: `dbt ls --resource-type model --output json | jq '.[] | select(.config.group == null)'` を CI に組み込み、新 mart が group 未宣言で merge されないようにする
- **`access: public` で cross-project ref**: 別の dbt project (`dbt-project.yml` を分けた小 project) を作り、本 project の `public` mart を `ref()` してみる (dbt mesh 1.6+)
- **`exposure:` との連携**: 5-5 で書いた `exposures.yml` の `depends_on:` に private mart を入れると warn / error になるか試す (BI は project 外の依存先と見なされるため)
