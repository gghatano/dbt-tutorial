# 6-1 解答例

## dbt/models/100-knock/topic-3/schema.yml (該当ブロック)

`stg_orders_100knock` の `order_id` 列に `not_null` + `unique` の **2 件セット**:

```yaml
version: 2

models:
  # ... (stg_customers_100knock / stg_products_100knock は省略) ...

  - name: stg_orders_100knock
    description: "Type-cast staging view of raw.orders。order_date は date, unit_price は numeric(10,2)。"
    columns:
      - name: order_id
        description: "Primary key (bigint)。主キー契約: not_null + unique。"
        tests:
          - not_null
          - unique
      # ... 他列の宣言 (3-4 完成形のまま) ...
```

**ポイント**:

- **`tests:` 配下は YAML リスト**: `[not_null, unique]` のように並べるだけ。
  順序は問わない。
- **PK セットは「片方だけでは穴がある」**: `not_null` 単独 = NULL 不可だが
  重複可、`unique` 単独 = 重複不可だが NULL 複数可。両方付けて初めて
  RDB の `PRIMARY KEY` 相当の不変条件になる。
- **Postgres の `UNIQUE` 制約と NULL**: ANSI SQL は NULL を「unknown」 と
  みなし、`NULL = NULL` は unknown を返すので、UNIQUE 制約は NULL 複数行を
  許容する仕様。dbt の `unique` test も同じ挙動 (NULL 行は除外して unique を
  チェック)。
- **`description:` を書く理由**: `dbt docs generate` でカタログ化されるので、
  「この列は PK で、契約として not_null + unique」 が docs にも残る。
  契約 = 仕様書の二重メンテをやめる。

## 実行例

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
... Found 11 models, 5 sources, 75 data tests ...

$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
1 of N PASS not_null_stg_orders_100knock_order_id ........... [PASS in 0.04s]
2 of N PASS unique_stg_orders_100knock_order_id ............. [PASS in 0.05s]
3 of N PASS not_null_stg_orders_100knock_order_date ......... [PASS in 0.04s]
... 
Done. PASS=N WARN=0 ERROR=0 SKIP=0 TOTAL=N
```

## manifest 上の test node 確認

```bash
$ ../.venv/bin/dbt parse --profiles-dir .
$ python3 -c "
import json
m = json.load(open('target/manifest.json'))
for k in sorted(m['nodes']):
    if 'order_id' in k and 'stg_orders_100knock' in k:
        print(k)
"
test.local_analytics.not_null_stg_orders_100knock_order_id
test.local_analytics.unique_stg_orders_100knock_order_id
```

## わざと壊して FAIL を体感する

### NULL を混ぜる (not_null FAIL)

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET order_id = NULL WHERE order_id = 1;
SQL
```

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
N of M FAIL 1 not_null_stg_orders_100knock_order_id ........... [FAIL 1 in 0.05s]
Failure in test not_null_stg_orders_100knock_order_id (models/100-knock/topic-3/schema.yml)
  Got 1 result, configured to fail if != 0
```

### 重複を混ぜる (unique FAIL)

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET order_id = 2 WHERE order_id = 1;
SQL
```

```bash
$ ../.venv/bin/dbt test --profiles-dir . --select stg_orders_100knock
N of M FAIL 1 unique_stg_orders_100knock_order_id ............. [FAIL 1 in 0.06s]
```

戻す:

```bash
$ docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET order_id = 1 WHERE order_id = 2 AND order_date = (SELECT order_date FROM raw.orders WHERE order_id = 2 ORDER BY order_id LIMIT 1);
SQL
```

(本番環境では UPDATE で PK を壊すこと自体が事故なので、原則 raw を再生成
 `python scripts/100-knock/topic-1/generate_1_04_orders.py` し直す。)

## 解説まとめ

- **schema.yml は「データ契約の宣言面」**: SQL ファイルは「物理変換」、
  schema.yml は「不変条件 = 契約」 を担当。両方セットで staging が完成。
- **PK 契約は二段構え**: `not_null` + `unique` のセットで RDB の
  `PRIMARY KEY` 制約に相当する不変条件を YAML 上で表現する。staging が
  view materialization でも「PK である」 と宣言できるのが dbt の強み。
- **コロケートが効く理由 (3 つ)**:
  1. **レビュー粒度が 1 ファイル**: 列の意味 / 契約 / docs を同じ場所で読む
  2. **マージ可能 (dbt 1.6+)**: 同じ model 名で複数 schema.yml に書けば
     test がマージされる。MVP の `dbt/models/staging/schema.yml` を触らずに
     100-knock 側で test を増やせる
  3. **manifest 命名が一貫**: `<test_type>_<model>_<column>` の自動命名で、
     どの test が落ちたか log を読むだけで分かる
- **manifest 上での test node**:
  `test.local_analytics.not_null_stg_orders_100knock_order_id` のような
  node ID で manifest に登録される。CI / 採点はこの node ID を直接参照して
  「test が登録されているか」 を構造的に検査できる (= データ無しでも採点可能)。
- **「test = データ駆動」 という思想**: dbt の test は SQL を「**違反行を返す
  クエリ**」 として書く。0 行返れば PASS、1 行以上で FAIL。組み込み test も
  自作 test も同じ評価ルールに従う (6-4 / 6-5 で詳しく扱う)。
- **MVP との関係**: MVP の `dbt/models/staging/schema.yml` で `stg_orders.order_id`
  にも同じ `not_null` + `unique` が貼ってある。100-knock 側は完全に独立した
  並走で、MVP を触らずに同じパターンを `_100knock` 系に適用する設計。
