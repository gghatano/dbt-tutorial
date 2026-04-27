# 5-3: mart_daily_sales_100knock に contract: enforced + data_type を宣言

## シナリオ

`mart_daily_sales` は MVP 側で動いているが、Metabase / CSV エクスポート /
ML 特徴量パイプラインなど **下流が増えてきた**。誰かが SQL を変えて列を
1 つ消すと、明日朝の経営会議資料が出ない。

そこで dbt 1.5+ の **`contract: enforced`** を使って、mart の「列名 + 列型」を
**build 時に検証される対外契約**にする。`schema.yml` で宣言した列構成と
SQL が返す列構成が一致しないと、`dbt run` 自体が `Contract Error` で fail する。
これが「mart は BI と契約している」という Topic ⑤ の核心。

本問では `mart_daily_sales_100knock` を新規に作り (MVP の `mart_daily_sales` と
ロジックは同じ)、**contract と data_type を最初から付けた状態で立ち上げる**。
次の 5-4 で「わざと型を壊す」体験につなげる。

## 学べること

- `config(contract={'enforced': true})` の意味と効果
- 各列に `data_type:` を宣言する書き方 (Postgres 型を正確に書く)
- `dbt run` 時に schema diff で fail する挙動
- なぜ contract は test ではなく build 時に必要か (BI 影響事前検知)
- intermediate / staging には不要、mart に集中させる理由

## 前提

- dbt **1.5 以上** (`dbt --version` で確認)
- Topic ② ③ ④ 完了:
  - `dbt/models/100-knock/topic-4/int_order_details_100knock.sql` (またはまだ
    なら MVP の `int_order_details` を ref する)
- main HEAD の MVP `mart_daily_sales` が動いている (列構成のリファレンスとして)

## 入力データ

新規データなし。既存の `int_order_details_100knock` (or MVP) を集計するだけ。

## 課題

### Step 1: SQL を書く

`dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql` を新規作成。

要件:

- `int_order_details_100knock` (or MVP) から日次集計
- 列: `order_date` (date), `order_count` (bigint), `customer_count` (bigint),
  `total_quantity` (bigint), `total_sales_amount` (numeric(18,2))
- 各 SQL 列に **明示 cast** を書いて schema.yml の `data_type:` と一致させる
- materialization は `table`、`schema='marts'` 明示
- `config(contract={'enforced': true})` を必ず付ける

### Step 2: schema.yml に contract 宣言を書く

`dbt/models/100-knock/topic-5/schema.yml` に追加:

```yaml
  - name: mart_daily_sales_100knock
    config:
      contract:
        enforced: true
    description: |
      Daily sales mart with enforced column contract.
      One row per order_date.
    columns:
      - name: order_date
        data_type: date
        description: "Calendar date of orders. PK."
        tests:
          - not_null
          - unique
      - name: order_count
        data_type: bigint
        # ... 以下同様に全列に data_type と tests を書く
```

**全列に `data_type:` を書く** ことが必須。1 列でも欠けると contract が
完全には enforce されない。

### Step 3: 実行

```bash
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt run  --profiles-dir . --select mart_daily_sales_100knock
../.venv/bin/dbt test --profiles-dir . --select mart_daily_sales_100knock
```

`dbt run` の log に **`unverified contract`** の WARN が出ていないこと。
SQL の列型と schema.yml の `data_type:` が完全一致したときのみ contract が
enforced と判定される。

### Step 4: contract が効いていることの確認

`target/manifest.json` を inspect:

```bash
../.venv/bin/dbt parse --profiles-dir .
python3 -c "
import json
m = json.load(open('target/manifest.json'))
node = m['nodes']['model.local_analytics.mart_daily_sales_100knock']
print('contract:', node['config'].get('contract'))
"
```

`contract: {'enforced': True, 'alias_types': True, 'checksum': '...'}` と
出れば成功。

## 完了条件

- [ ] `dbt/models/100-knock/topic-5/mart_daily_sales_100knock.sql` が存在
- [ ] manifest の `model.local_analytics.mart_daily_sales_100knock` の
      `config.contract.enforced` が `true`
- [ ] schema.yml で全 5 列に `data_type:` が宣言されている
- [ ] `dbt run --select mart_daily_sales_100knock` が成功する

## ヒント (詰まったら)

- **Postgres の型表記**: `numeric(18, 2)` は `numeric(18,2)` (空白なし) でも
  OK だが、SQL 側 (`::numeric(18, 2)`) と schema.yml 側 (`numeric(18,2)`) の
  片方が空白付き、もう片方が空白なしだと dbt は同じと判定する。`bigint` は
  `int8` でも OK (Postgres alias)。
- **`integer` vs `bigint`**: `count(*)` は Postgres では `bigint` を返す。
  `data_type: integer` と書くと型不一致で contract error になる。
- **`numeric(18, 2)` の右辺キャスト**: `sum(sales_amount)::numeric(18,2)` を
  忘れると dbt が推定した型 (`numeric` だけ、precision なし) になり、
  `data_type: numeric(18,2)` と一致せず WARN になる。
- **`alias_types: true` がデフォルト**: 1.6+ では `int8` ↔ `bigint` のような
  alias は自動で同一視してくれる。1.5 だと厳密マッチが必要なので注意。
- **どこに contract を付けるか**: staging / intermediate には付けない。
  内部表現が変わるたびに型を YAML で同期するコストが学習ペースに見合わない。
  **mart にだけ** 付けるのが Topic ⑤ の方針。

## 解答例

詳細は [`5-3-mart-contract-enforced.solution.md`](5-3-mart-contract-enforced.solution.md) を参照。
