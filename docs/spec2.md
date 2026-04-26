以下を `spec.md` としてそのまま使えます。バージョンは固定し、dbtは `dbt-core 1.11.8`、`dbt-postgres 1.10.0` を前提にしています。dbt CoreはPyPI上で2026-04-08時点の最新版です。([PyPI][1])

````md
# local-data-platform spec

## 1. 目的

ローカル環境で、IaC・DWH・dbt・データマート・ELT・テスト・ドキュメント生成を一通り練習できる最小構成を作成する。

本環境では、Docker ComposeでPostgreSQLを起動し、TerraformでDB内のスキーマ・ロールを構築し、ダミーデータをraw層に投入したうえで、dbtによりstaging層・intermediate層・mart層を作成する。

## 2. 採用技術・バージョン

| 区分 | 技術 | バージョン |
|---|---|---|
| コンテナ実行 | Docker Compose | Docker Compose v2系 |
| IaC | Terraform | 1.14.9 |
| DWH代替 | PostgreSQL | 17-alpine |
| Python | Python | 3.12 |
| パッケージ管理 | uv | 0.6系以上 |
| dbt Core | dbt-core | 1.11.8 |
| dbt Adapter | dbt-postgres | 1.10.0 |
| DB接続 | psycopg | 3.2系 |
| データ生成 | Faker | 33系 |
| データ処理 | pandas | 2.2系 |

## 3. ディレクトリ構成

```text
local-data-platform/
├── README.md
├── spec.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── versions.tf
├── scripts/
│   ├── generate_dummy_data.py
│   ├── load_raw_data.py
│   └── smoke_test.py
├── data/
│   └── raw/
│       ├── customers.csv
│       ├── products.csv
│       ├── stores.csv
│       └── orders.csv
└── dbt/
    ├── dbt_project.yml
    ├── profiles.yml
    ├── packages.yml
    ├── models/
    │   ├── sources.yml
    │   ├── staging/
    │   │   ├── stg_customers.sql
    │   │   ├── stg_products.sql
    │   │   ├── stg_stores.sql
    │   │   └── stg_orders.sql
    │   ├── intermediate/
    │   │   └── int_order_details.sql
    │   └── marts/
    │       ├── mart_daily_sales.sql
    │       ├── mart_customer_sales.sql
    │       └── mart_product_sales.sql
    └── tests/
        └── assert_positive_sales_amount.sql
````

## 4. データ層の設計

| 層            | schema       | 役割               |
| ------------ | ------------ | ---------------- |
| raw          | raw          | CSVをそのまま投入する層    |
| staging      | staging      | 型変換、列名統一、軽微な正規化  |
| intermediate | intermediate | 結合・中間集計・業務ロジック整理 |
| marts        | marts        | 分析・BI向けのデータマート   |

## 5. サンプルデータ

以下の4種類のCSVを生成する。

| ファイル          |     件数 | 内容         |
| ------------- | -----: | ---------- |
| customers.csv |  1,000 | 顧客マスタ      |
| products.csv  |    100 | 商品マスタ      |
| stores.csv    |     20 | 店舗マスタ      |
| orders.csv    | 10,000 | 注文トランザクション |

## 6. Docker Compose要件

`docker-compose.yml` で以下を定義する。

* PostgreSQL 17-alpine
* database: `analytics`
* user: `analytics_user`
* password: `analytics_password`
* port: `5432`
* volume: `postgres_data`

## 7. Terraform要件

Terraformで以下を作成する。

* schema `raw`
* schema `staging`
* schema `intermediate`
* schema `marts`
* role `dbt_user`
* role `readonly_user`
* 必要な権限付与

Terraform providerは `cyrilgdn/postgresql` を使用する。

## 8. dbt要件

dbt project名は `local_analytics` とする。

### 8.1 source定義

`raw` schemaの以下テーブルをsourceとして定義する。

* raw.customers
* raw.products
* raw.stores
* raw.orders

### 8.2 staging models

以下を作成する。

* `stg_customers`
* `stg_products`
* `stg_stores`
* `stg_orders`

要件：

* 主キーをnot_null, uniqueでテストする
* 外部キー相当の列にrelationshipsテストを設定する
* 日付・数値型を明示的に変換する
* 金額・数量が負数にならないことを確認する

### 8.3 intermediate model

`int_order_details` を作成する。

要件：

* 注文、顧客、商品、店舗を結合する
* `sales_amount = quantity * unit_price` を算出する
* `order_date`, `customer_id`, `product_id`, `store_id`, `sales_amount` を含める

### 8.4 mart models

以下を作成する。

#### mart_daily_sales

日次売上マート。

主な列：

* order_date
* order_count
* customer_count
* total_quantity
* total_sales_amount

#### mart_customer_sales

顧客別売上マート。

主な列：

* customer_id
* customer_name
* order_count
* total_sales_amount
* first_order_date
* last_order_date

#### mart_product_sales

商品別売上マート。

主な列：

* product_id
* product_name
* category
* order_count
* total_quantity
* total_sales_amount

## 9. テスト要件

以下のテストを実装する。

### 9.1 dbt built-in tests

* not_null
* unique
* relationships
* accepted_values

### 9.2 custom generic / singular tests

以下を確認する。

* `sales_amount >= 0`
* `quantity > 0`
* `total_sales_amount >= 0`
* martの日次売上件数が0件でないこと

## 10. 実行コマンド

READMEに以下のコマンドを記載する。

```bash
docker compose up -d

cd infra/terraform
terraform init
terraform apply -auto-approve

cd ../../
uv venv
uv pip install -r requirements.txt

python scripts/generate_dummy_data.py
python scripts/load_raw_data.py

cd dbt
dbt debug --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
dbt docs generate --profiles-dir .
dbt docs serve --profiles-dir .
```

## 11. Pythonスクリプト要件

### 11.1 generate_dummy_data.py

以下を実装する。

* Fakerで顧客、商品、店舗、注文データを生成する
* seedを固定し、毎回同じデータが生成されるようにする
* `data/raw/*.csv` に出力する

### 11.2 load_raw_data.py

以下を実装する。

* PostgreSQLに接続する
* raw schemaに以下テーブルを作成する

  * customers
  * products
  * stores
  * orders
* CSVを投入する
* 冪等に実行できるように、ロード前に対象テーブルをtruncateまたは再作成する

### 11.3 smoke_test.py

以下を確認する。

* PostgreSQLに接続できる
* raw.ordersに1件以上存在する
* dbt mart作成後、marts.mart_daily_salesに1件以上存在する

## 12. requirements.txt

以下を作成する。

```txt
dbt-core==1.11.8
dbt-postgres==1.10.0
psycopg[binary]==3.2.3
pandas==2.2.3
Faker==33.3.1
python-dotenv==1.0.1
```

## 13. 完了条件

以下をすべて満たすこと。

* `docker compose up -d` でPostgreSQLが起動する
* Terraformでschemaとroleが作成される
* ダミーデータCSVが生成される
* raw schemaにCSVが投入される
* `dbt run` が成功する
* `dbt test` が成功する
* marts schemaに以下が作成される

  * mart_daily_sales
  * mart_customer_sales
  * mart_product_sales
* `dbt docs generate` が成功する
* READMEに環境構築手順、実行手順、トラブルシュートが記載されている

## 14. 実装方針

最初からAirflowやクラウドDWHは入れない。

今回の目的は、以下の基本動作を明確に理解することである。

1. IaCでデータ基盤の構成を定義する
2. raw層にデータを投入する
3. dbtで変換処理を管理する
4. データマートを作成する
5. テストとドキュメント生成を行う

スケジューラ、BI、クラウドDWH、CI/CDは次フェーズで追加する。

```

補足すると、Terraformは `1.15.0-rc3` が出ていますがRC版なので、練習環境では安定版の `1.14.9` 固定が妥当です。Terraform 1.14.9は2026-04-20時点の1.14系最新として確認できます。:contentReference[oaicite:1]{index=1}
::contentReference[oaicite:2]{index=2}
```

[1]: https://pypi.org/project/dbt-core/?utm_source=chatgpt.com "dbt-core"

