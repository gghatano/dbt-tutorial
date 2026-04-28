# 6-2: relationships で stg_orders_100knock.customer_id の FK 契約を宣言、わざと壊す

## シナリオ

3-4 で `customer_id` に `relationships: to: ref('stg_customers_100knock'), field: customer_id`
を貼った (PASS した) 状態を出発点に、本問では **「わざと壊して FAIL を見る」** ことで
FK 契約の意味を体感する。

`relationships` test は内部で
`SELECT child.fk FROM child LEFT JOIN parent ON ... WHERE parent.pk IS NULL`
相当の SQL を生成し、「子テーブルの FK 値が、親テーブルの PK に **必ず存在する**」
という不変条件を実 SQL で検査する。これは DAG 上で
「`stg_orders_100knock` は `stg_customers_100knock` に **意味的に依存** している」
というエッジを宣言する行為でもある。

## 学べること

- `relationships` test の YAML 構文 (dbt 1.11+ の `arguments:` 形式)
- 「FK は親に必ず存在する」 不変条件の SQL 展開イメージ
- DAG が「物理的依存 (`ref()`)」 だけでなく **「参照整合の依存」** も宣言できること
- わざと壊した時の FAIL ログの読み方
- 「FAIL する状態」 を採点するときの考え方 (反転ロジック)

## 前提

- Topic ② ③ ④ ⑤ 完了 (`stg_orders_100knock` / `stg_customers_100knock` 物理化済み)
- 3-4 で `customer_id` に `relationships` test を貼っている (PASS していた状態)

## 入力データ

`raw.orders` (10,000 行) の `customer_id` は 1..1000 の範囲で生成済み。
本問では **わざと 1 行だけ存在しない値 (99999) に書き換えて FAIL 状態を作る**。

## 課題

### Step 1: schema.yml の relationships 宣言を確認

`dbt/models/100-knock/topic-3/schema.yml` の `stg_orders_100knock.customer_id`
ブロック:

```yaml
      - name: customer_id
        description: "FK → stg_customers_100knock.customer_id。"
        tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers_100knock')
                field: customer_id
```

3-4 で書いていればそのまま。`arguments:` ネスト形式が dbt 1.11+ の推奨。

### Step 2: わざと FK を壊す

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
-- 存在しない customer_id (99999) を 1 行だけ混ぜる
UPDATE raw.orders SET customer_id = 99999 WHERE order_id = 1;
SQL
```

### Step 3: dbt test を走らせ FAIL を確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select stg_orders_100knock
```

期待出力:

```
N of M FAIL 1 relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_ [FAIL 1 in 0.07s]
... 
Failure in test relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_
  Got 1 result, configured to fail if != 0
```

`dbt test` の **exit code は 1** になる (= CI でも落ちる)。本問では
「**FAIL したことを採点する**」ので、`dbt_test_passes` ではなく
`sql_assert` と `shell_command` を組み合わせて判定する。

### Step 4: 失敗行を SQL で確認 (デバッグループの体感)

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
SELECT order_id, customer_id
FROM staging.stg_orders_100knock
WHERE customer_id NOT IN (
    SELECT customer_id FROM staging.stg_customers_100knock
);
SQL
```

`order_id=1, customer_id=99999` が 1 行返れば成功 (= FK 違反が発生している)。

### Step 5: 戻して再 test (任意)

採点が終わったら raw を元に戻す (本問の **最終提出時は壊した状態** で OK):

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET customer_id = 1 WHERE order_id = 1;"
```

`dbt test --select stg_orders_100knock` で全 PASS に戻ることを確認。

## 完了条件

- [ ] `schema.yml` に `customer_id` の `relationships` test が宣言されている
- [ ] manifest に
      `test.local_analytics.relationships_stg_orders_100knock_customer_id__customer_id__ref_stg_customers_100knock_`
      が登録されている
- [ ] `staging.stg_orders_100knock` 上で「親に存在しない customer_id」 が
      **1 行以上** 存在する (= FAIL する状態を作っている)
- [ ] `dbt test --select stg_orders_100knock` を走らせると ERROR>0 で落ちる
      (採点側はこの挙動を `shell_command` の `expect_exit_code: 1` で確認)

## ヒント (詰まったら)

- **`relationships` test の SQL 展開**: dbt は内部で
  `SELECT child.fk FROM child LEFT JOIN parent ON child.fk = parent.pk WHERE parent.pk IS NULL`
  相当のクエリを生成して 0 行を期待する。1 行でも返れば FAIL。
- **`arguments:` ネスト形式**: dbt 1.11+ で推奨。古い `to:` / `field:` を
  トップレベルに書く形式も動くが warn が出る。
- **`relationships` 単体だと NULL 素通り**: `relationships` は「**値が
  あるならば** 親に存在せよ」 を検査するので、NULL 行は素通りする。
  本リポジトリの schema.yml では `not_null` + `relationships` の **二段構え**
  でこの穴を塞いでいる。
- **FAIL を採点する**: 通常 `dbt_test_passes` は PASS を求めるが、本問は
  「**わざと FAIL させた**」 状態を見るので、代わりに `sql_assert` で
  「不正行が `>= 1` 存在する」 を確認、`shell_command` で `dbt test` の
  exit code が `1` であることを確認する (採点ロジックの反転パターン)。
- **DAG への意味**: `relationships` を貼ると、`stg_orders_100knock` が
  `stg_customers_100knock` に **テストレベルでも依存** することになる。
  `dbt ls --select +stg_orders_100knock` で上流 model を見ると、
  `stg_customers_100knock` が relationships test 経由で参照されているのが
  分かる。
- **修復方針**: 本番では「raw に書き戻す」ではなく、(a) staging で
  `WHERE customer_id IN (SELECT customer_id FROM stg_customers_100knock)`
  でフィルタして失格行を切る、または (b) ETL の上流 (raw 投入) を直す、
  の 2 択。テストは「FAIL を見て初めて気付く」 ための **検知装置**。

## 解答例

詳細は [`6-2-relationships-fk.solution.md`](6-2-relationships-fk.solution.md) を参照。
