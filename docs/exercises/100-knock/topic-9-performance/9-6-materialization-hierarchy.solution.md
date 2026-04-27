# 9-6 解答例

## ゴール再掲

- `dbt_project.yml` の `100-knock:` セクションに 3 レイヤーの `+materialized:` を宣言
  - `topic-3: +materialized: view`
  - `topic-4: +materialized: ephemeral`
  - `topic-5: +materialized: table`
- `mart_orders_incremental_100knock.sql` の `config()` で `materialized='incremental'` を宣言、
  プロジェクト config を override
- manifest で 4 model の materialized 値を確認

## dbt/dbt_project.yml (差分)

```yaml
models:
  local_analytics:
    staging:        # MVP - 触らない
      +materialized: view
      +schema: staging
    intermediate:   # MVP - 触らない
      +materialized: view
      +schema: intermediate
    marts:          # MVP - 触らない
      +materialized: table
      +schema: marts
    100-knock:
      topic-3:
        +materialized: view
        +schema: staging_100knock
      topic-4:                       # ← 9-6 で追加
        +materialized: ephemeral
        +schema: intermediate_100knock
      topic-5:                       # ← 9-6 で追加
        +materialized: table
        +schema: marts_100knock
```

## dbt/models/100-knock/topic-5/mart_orders_incremental_100knock.sql (冒頭)

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    on_schema_change='fail'
) }}

select
    order_id,
    order_date,
    customer_id,
    product_id,
    store_id,
    quantity,
    unit_price,
    quantity * unit_price as line_amount,
    loaded_at
from {{ ref('stg_orders_100knock') }}

{% if is_incremental() %}
where loaded_at > (select coalesce(max(loaded_at), '1970-01-01'::timestamp) from {{ this }})
{% endif %}
```

(本体 SQL は 9-2 で書いたものをそのまま再利用。本問は冒頭 `config()` の宣言ががポイント)

## 確認手順

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .

../.venv/bin/python -c "
import json
with open('target/manifest.json') as f:
    m = json.load(f)
for name in [
    'model.local_analytics.stg_orders_100knock',
    'model.local_analytics.int_order_details_100knock',
    'model.local_analytics.mart_customer_sales_100knock',
    'model.local_analytics.mart_orders_incremental_100knock',
]:
    n = m['nodes'].get(name)
    if n:
        cfg = n['config']
        print(f\"{name.split('.')[-1]:42s} materialized={cfg['materialized']:12s} schema={cfg['schema']}\")
"
```

期待出力:

```text
stg_orders_100knock                        materialized=view         schema=staging_100knock
int_order_details_100knock                 materialized=ephemeral    schema=intermediate_100knock
mart_customer_sales_100knock               materialized=table        schema=marts_100knock
mart_orders_incremental_100knock           materialized=incremental  schema=marts_100knock
```

`mart_orders_incremental_100knock` だけが `incremental` になっており、他の `mart_*_100knock` は `table` のまま。これが「プロジェクト規約 → 個別 override」の precedence。

## 解説まとめ

### なぜ materialization をプロジェクト config に巻き上げるのか

- **DRY**: N 個の SQL に同じ `{{ config(materialized='view') }}` を書くのは保守不能。staging を全部 incremental に変えたい時に N ファイル書き換えになる
- **規約の見える化**: `dbt_project.yml` を見れば「このプロジェクトはレイヤーごとにこの materialization」と一目で分かる。チームに新しい人が来た時の onboarding コストが下がる
- **レイヤー contract**: 「staging は view」は単なる物理選択ではなく **「staging は常に最新を返す論理レイヤー」** という契約の表明。`dbt_project.yml` がその契約の場所

### なぜ ephemeral を中間層に選ぶのか

- ephemeral は **DB に table / view を作らない**。下流 model が `ref('int_order_details_100knock')` した時、dbt が **CTE として展開** する
- メリット: 中間層のストレージが 0、`intermediate_100knock` schema に何も漏れ出さず BI 部門が誤って参照することもない
- デメリット: 中間層単体では SELECT できない (`dbt show --select int_*_100knock` でしか確認できない)、複雑な intermediate を ephemeral にすると下流 SQL が肥大化して explain plan が読みにくくなる
- 実務では「**よく使う / 重い中間層は table**、**1〜2 model でしか参照しない軽い中間層は ephemeral**」と使い分ける

### なぜ個別 model で override できるのか — precedence の正体

dbt の config 解決順 (左ほど強い):

```
SQL 内 {{ config(...) }}  >  dbt_project.yml の末端  >  dbt_project.yml の親  >  default
```

- これにより「**規約はプロジェクトで宣言、例外は SQL で宣言**」が成立
- `mart_orders_incremental_100knock` だけ `incremental` にしたいのは **incremental は他の mart と更新性質が違う** から (差分 merge する mart)。例外として SQL 側で明示する方が「この model は普通と違う」という意図が伝わる
- 逆に「全 mart を table に統一しているが 1 本だけ incremental」を SQL 側でなくプロジェクト config の `topic-5: marts.mart_orders_incremental_100knock: +materialized: incremental` のような fully-qualified path で書くこともできる。だが「例外は SQL で」の方が読み手に親切

### 階層宣言の落とし穴

- **`+` プレフィックス必須**: `materialized: view` (プレフィックスなし) は dbt が **設定として認識しない** (子ディレクトリの folder name と解釈される)。必ず `+materialized:` と書く
- **`100-knock` キーは数字始まり**: YAML 仕様としては OK だが、Python 辞書アクセスは `cfg['models']['local_analytics']['100-knock']` の形で文字列キー必須
- **`+schema:` の効き方**: `+schema: staging_100knock` を宣言すると、dbt の generate_schema_name マクロを上書きしない限り `<target_schema>_staging_100knock` が物理 schema 名になる。詳細は dbt の [Custom schemas](https://docs.getdbt.com/docs/build/custom-schemas) 参照
- **MVP セクションを誤って消す**: 本問の唯一のリスク。`git diff dbt/dbt_project.yml` で MVP 行が削除されていないことをコミット前に必ず確認

### 採点で何を見ているか

- `shell_command` で `dbt_project.yml` の YAML を `yaml.safe_load` し、`100-knock.topic-3 / topic-4 / topic-5` の `+materialized` キーが期待値か確認
- `manifest_config` で `mart_orders_incremental_100knock` の `materialized: incremental` を直接確認 — これが override の証拠
- MVP セクション無傷チェックを別 check で残す (3-8 と同じ防御)

### 次の問 (9-7) との接続

- 9-7 では `profiles.yml` の `threads` を変えて並列度を測る。9-6 で「materialization は宣言で抑える」を学んだ後、9-7 では「**並列性も宣言で抑える**」という流れ
- 「物理コストを宣言で抑える」という Topic ⑨ の貫通テーマがここで完成に向かう
