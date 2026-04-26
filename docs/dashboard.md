# Dashboard (Metabase)

dbt が作った marts を **Metabase** から可視化する手順。

## 起動

```bash
docker compose up -d metabase
```

初回は Metabase 内蔵 H2 DB の初期化と JAR の展開で **60〜120 秒**ほどかかる（Apple Silicon は amd64 エミュレーションのため、起動時に CPU を使う）。

ヘルスチェック確認:

```bash
docker inspect --format '{{.State.Health.Status}}' local-data-metabase
# healthy が返るまで待つ
```

ヘルシーになったらブラウザで <http://localhost:3000> を開く。

## 自動セットアップ（推奨）

`docker compose up -d metabase` 後、`scripts/metabase_bootstrap.py` を実行すると以下が一発で揃う:

- 管理者アカウント作成（`.env` の `METABASE_ADMIN_*`）
- Postgres を `local-analytics` として登録（接続ユーザは `readonly_user`）
- Collection `Sales Marts` 作成
- 3 つの Card 作成（Daily Sales / Top 20 Customers / Sales by Category）
- Dashboard `Sales Overview` 作成 + Card 配置（grid 12 列、上段に Daily Sales / 下段に他 2 枚）

実行:

```bash
# 1) 仮想環境の用意（既にあればスキップ）
uv venv --python 3.12
uv pip install -r requirements.txt

# 2) .env に METABASE_* 変数を記述（.env.example 参照）

# 3) bootstrap 実行
.venv/bin/python scripts/metabase_bootstrap.py
```

完了すると最後に Dashboard URL が出力される（例: `http://localhost:3000/dashboard/2`）。

### 冪等性

- 名前 (`Sales Marts` collection / 3 Card / `Sales Overview` dashboard) で upsert するため、
  何度再実行しても重複作成されない。Card は SQL / 可視化設定が常に最新版に**更新**される。
- 「Metabase 既にセットアップ済み」かどうかは `/api/session/properties` の
  `has-user-setup` で判定する（`setup-token` はセットアップ完了後も値が残るため
  単独では判定に使えない、というのが Metabase API のクセ）。
- 既に管理者が居る環境では、`.env` の admin 認証情報でログインして DB / collection /
  card / dashboard を ensure するフォールバックパスに入る。

### パスワード方針

`.env` の `METABASE_ADMIN_PASSWORD` は学習用デフォルトとして
`Local-data-1` を採用（Metabase の要件 = 6 文字以上 + 大文字 + 小文字 + 数字 + 記号 を満たす）。
本番想定では各自書き換えてから初回 bootstrap を実行する。

## マニュアル操作（リファレンス）

> ※ 以下は API 自動化を使わず、ブラウザで全部やる場合の手順。
> 通常は上の「自動セットアップ」で十分。

### 初回セットアップ（ブラウザ操作）

1. 「ようこそ」画面 → 言語選択（日本語可）
2. 管理者アカウント作成（メールアドレスは何でもよい。学習用なので `admin@local.test` 等）
3. **データソース追加** で以下を入力:
   - データベースタイプ: **PostgreSQL**
   - 表示名: `local-analytics`（任意）
   - **ホスト**: `postgres`（**`localhost` ではない**。Metabase コンテナから見た Postgres コンテナのホスト名 = compose サービス名）
   - ポート: `5432`
   - データベース名: `analytics`
   - ユーザー名: `readonly_user`（**dbt_user ではない**。BI は読み取り専用ロールで接続）
   - パスワード: `readonly_password`
   - スキーマ: 空欄（全 schema を見せる）
4. 接続成功後、利用統計の収集設定 → 完了

### 推奨ダッシュボード

ログイン後、以下のクエリで「最初の 1 枚」を作ってみる
（`scripts/metabase_bootstrap.py` でも同じクエリが自動投入される）。

#### 日次売上推移（折れ線）

```sql
select order_date, total_sales_amount
from marts.mart_daily_sales
order by order_date
```

→ 「グラフタイプ：折れ線」「X 軸：order_date / Y 軸：total_sales_amount」。

#### 顧客別売上 TOP20（棒）

```sql
select customer_name, total_sales_amount
from marts.mart_customer_sales
order by total_sales_amount desc
limit 20
```

→ 「棒グラフ」「X 軸：customer_name / Y 軸：total_sales_amount」。

#### 商品カテゴリ別売上（円グラフ）

```sql
select category, sum(total_sales_amount) as total
from marts.mart_product_sales
group by category
order by total desc
```

→ 「円グラフ」「ディメンション：category / メトリクス：total」。

3 つのクエリを保存して同じダッシュボードに並べると「日次売上 / 顧客 TOP / カテゴリ構成」が一画面で確認できる。

## 接続権限についての補足

| 用途 | DB ユーザ | 権限 |
|---|---|---|
| dbt の実行 | `dbt_user` | 全 schema の OWNER + 各種 grant |
| **BI の閲覧** | **`readonly_user`** | `marts.*` のみ SELECT（Terraform で grant 済み） |

Metabase からは **readonly_user** で接続することを推奨。理由:

- マート以外のレイヤ（raw / staging / intermediate）は中間生成物なので BI から見せたくない（混乱や誤集計の元）
- 万一 Metabase 経由で `DELETE` / `UPDATE` 文を叩いても、readonly では拒否される（保険）
- 詳細は `infra/terraform/main.tf` の `readonly_user` grant 定義を参照

`readonly_user` で `marts.*` だけを見せることで、Metabase の「データ参照」UI に**余計な schema が出ない**シンプルな BI 画面になる。

## トラブルシュート

### Metabase が起動しない / 504

- `docker logs local-data-metabase --tail 50` で確認
- 60 秒以上経っても healthy にならない場合は CPU/RAM 不足が疑わしい。Colima のリソースを増やす:
  ```bash
  colima stop
  colima start --cpu 4 --memory 8 --disk 20  # spec §15.2 推奨
  docker compose up -d
  ```

### postgres ホスト名が解決しない

Metabase 設定でホスト名に `localhost` を入れていないか確認。**コンテナ間通信ではサービス名 `postgres` を使う**（spec §15.5）。

### 接続テストで permission denied

`readonly_user` のパスワード（`readonly_password`）は Terraform の `variables.tf` の default 値。`.env` で上書きしている場合はそれを参照。

### marts schema が見えない

- `terraform apply` で `readonly_user` への grant が走っているか確認
- `docker exec -i local-data-postgres psql -U analytics_user -d analytics -c '\dp marts.*'` で `readonly_user=r/dbt_user` の表示があれば SELECT 権限あり

## 停止 / 再起動

```bash
docker compose stop metabase   # Metabase だけ止める（Postgres は維持）
docker compose start metabase  # 再開
```

完全に消したい場合（Metabase の設定・ダッシュボードもすべて消える）:

```bash
docker compose rm -sf metabase
docker volume rm dbt-tutorial_metabase_data  # ボリューム名は環境により異なる
```

`postgres_data` ボリュームは消さないこと（dbt の出力含めて全データが消える）。
