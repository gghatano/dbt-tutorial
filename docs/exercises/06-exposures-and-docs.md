# Exercise 06: BI ダッシュボードを dbt の lineage に組み込む

## シナリオ

`docs/dashboard.md` の手順で Metabase を立ち上げ、`Sales Overview` ダッシュボードが `marts.*` を参照するようになった。一方、dbt 側からは「どの mart が BI で使われているか」が見えない。`mart_customer_sales` を間違って削除しても、それが BI に影響するかを `dbt docs` の lineage graph 上で判別できない。

そこで dbt の `exposures` 機能を使い、Metabase ダッシュボードを **dbt DAG の終端ノード** として宣言する。`dbt docs generate` の lineage 上で `mart_*` → `Sales Overview` のエッジが描かれるようになる。

## 学べること

- `exposure:` の YAML 宣言フォーマット
- `depends_on: [ref('mart_*')]` で dbt DAG に組み込む
- `dbt docs generate` / `dbt docs serve` で lineage graph を可視化
- `dbt ls --select +exposure:sales_overview` で exposure 起点の依存解析

## 前提

- main HEAD 完了状態（`marts.mart_daily_sales` 等が存在する）
- `docs/dashboard.md` の手順で Metabase が起動済み（自動 bootstrap で `Sales Overview` ダッシュボードが作られている）
- 他 Exercise との依存なし

## 入力データ

不要。既存の mart を参照するだけ。

## 課題

### Step 1: exposure 用ディレクトリと YAML を作る

`dbt/models/exposures/exposures.yml` を新規作成。

要件:

- `version: 2` ヘッダ
- 1 つの exposure を宣言:
  - 名前: `sales_overview`
  - タイプ: `dashboard`
  - URL: `http://localhost:3000/dashboard/2`（自分の環境の dashboard URL に合わせる、`scripts/metabase_bootstrap.py` 完了時に出力される）
  - オーナー (`owner`): メールアドレスと氏名
  - `depends_on`: 3 つの mart を `ref()` で列挙
  - `description`: 何を可視化しているかの 1〜2 行説明
  - `maturity`: `medium` か `high`

dbt 公式: [Add Exposures to your DAG](https://docs.getdbt.com/docs/build/exposures)

### Step 2: parse して構文確認

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
```

エラーが出ないこと。`target/manifest.json` に `"exposure.local_analytics.sales_overview"` が現れる。

### Step 3: lineage を生成して確認

```bash
../.venv/bin/dbt docs generate --profiles-dir .
../.venv/bin/dbt docs serve --profiles-dir .
```

ブラウザで <http://localhost:8080> を開き、左上の lineage graph アイコンから DAG を表示。`sales_overview` exposure ノードが下流側に描かれ、3 つの `mart_*` から矢印が伸びていれば成功。

### Step 4: exposure を起点とした selector を試す

```bash
../.venv/bin/dbt ls --profiles-dir . --select +exposure:sales_overview
```

`sales_overview` が依存する全 model（mart 3 + intermediate 1 + staging 4 + sources）が列挙される。これで「BI に影響する model だけを再 build する」ような選択ができるようになる。

```bash
../.venv/bin/dbt run --profiles-dir . --select +exposure:sales_overview
```

すべての上流 model が再 build される（marts 3 本 + intermediate 1 + staging 4）。

## 完了条件

- [ ] `dbt parse` が成功する
- [ ] `target/manifest.json` を grep して `"exposure.local_analytics.sales_overview"` が見つかる
- [ ] `dbt docs serve` の lineage graph で `sales_overview` ノードと 3 mart からのエッジが見える
- [ ] `dbt ls --select +exposure:sales_overview` で 8 ノード以上が列挙される

## ヒント（詰まったら）

- **exposure はモデルではない**: `exposures.yml` は `dbt run` の対象にはならない。あくまで「DAG 上の終端メタデータ」。`dbt build` の流れに組み込まれない代わりに、`dbt docs` と `dbt ls` で恩恵を受ける。
- **`depends_on` の書き方**: `ref('mart_daily_sales')` のように Jinja を YAML 内に書く。`source('...')` も使える。文字列の中に Jinja を書くので、リテラルの ref 参照とは違ってクオートで囲う点に注意。
- **`maturity` の意味**: `low` / `medium` / `high`。`high` の exposure を支える model を破壊的に変更しようとすると、CI で警告を出すような運用が組める（dbt-checkpoint や独自スクリプトで判定）。学習用なら `medium` で十分。
- **URL を正確に貼る理由**: lineage UI 上で exposure をクリックすると URL が表示される。BI 側からも dbt docs に逆リンクを張る運用にすると、dbt と BI の往復が早くなる。
- **`models/` 配下に置く理由**: `dbt_project.yml` の `models:` config に対応するため、`dbt/models/exposures/` 配下が無難。`dbt/exposures/` でも parse はされる（ファイルの位置よりも YAML 構文が支配的）。
- **`sales_overview` が起点で `+exposure:` セレクタが効かない**: dbt 1.x では `+exposure:` プレフィックスが必要（ハイフンではなくコロン）。`dbt ls --select +exposure:sales_overview` の `+` は「上流すべて」の意味。

## 解答例

詳細は [`solutions/06-exposures-and-docs.solution.md`](solutions/06-exposures-and-docs.solution.md) を参照。
