# アーキテクチャ

## レイヤー構造

```text
   CSV (Faker)
        │
        ▼  COPY (psycopg3)
 ┌────────────┐
 │  raw       │   ← Terraform で schema / role 構築
 └────────────┘
        │
        ▼  dbt (view)
 ┌────────────┐
 │  staging   │   ← 型変換・列名統一・PK/FK テスト
 └────────────┘
        │
        ▼  dbt (view)
 ┌────────────┐
 │ intermediate│  ← 注文 × 顧客 × 商品 × 店舗 結合 + sales_amount
 └────────────┘
        │
        ▼  dbt (table)
 ┌────────────┐
 │  marts     │   ← daily / customer / product sales
 └────────────┘
        │
        ▼  SELECT (readonly_user)
 ┌────────────┐
 │  Metabase  │   ← BI（任意）
 └────────────┘
```

各層の責務は [spec.md §4](spec.md) に詳述。要点だけまとめると:

| 層 | 責務 | 物質化 | 触ってよい人 |
|---|---|---|---|
| raw | CSV をそのまま受ける | table (psycopg COPY) | ロード処理のみ |
| staging | 型変換・列名統一・1:1 の薄い変換 | view | dbt |
| intermediate | 結合・派生カラム | view | dbt |
| marts | KPI 集計 (daily / customer / product) | table | dbt → BI 公開 |

## ロール分離 (dbt_user / readonly_user)

- **dbt_user**: 4 schema (raw / staging / intermediate / marts) のオーナー。raw ロード〜`dbt run` まで担当。
- **readonly_user**: `marts.*` の SELECT のみ。BI ツール (Metabase) やアナリストが触る想定。誤って DELETE / UPDATE が走っても拒否される保険。

「dbt が書く側」「人間 / BI が読む側」を最初から分離しておくと、クラウド DWH に載せ替えるときも同じ思想が流用できる。

## ディレクトリ構成

```text
.
├── README.md
├── docker-compose.yml         # PostgreSQL 17-alpine + Metabase
├── .env.example               # 接続情報の雛形（実体は .env で gitignored）
├── requirements.txt           # Python 依存（dbt-core, psycopg, Faker, ...）
├── infra/terraform/           # schema / role / grant の IaC
├── scripts/                   # ダミーデータ生成・raw ロード・smoke・metabase bootstrap
│   └── exercises/             # 練習問題用の追加データ生成
├── data/                      # 生成 CSV (gitignored)
│   ├── raw/                   # MVP 用
│   └── exercises/inbox/       # 練習問題用
├── dbt/                       # dbt project (local_analytics)
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   ├── models/
│   │   ├── sources.yml        # raw を source 宣言
│   │   ├── staging/           # stg_* (view)
│   │   ├── intermediate/      # int_* (view)
│   │   └── marts/             # mart_* (table)
│   ├── macros/
│   │   └── get_custom_schema.sql  # generate_schema_name override
│   └── tests/                 # singular tests (custom 4 本)
└── docs/
    ├── setup.md               # セットアップ詳細手順
    ├── architecture.md        # 本ファイル
    ├── troubleshooting.md     # 既知の罠
    ├── spec.md                # プロジェクト仕様（権威）
    ├── dashboard.md           # Metabase 起動手順
    ├── exercises/             # 練習問題セット (10 問)
    ├── tasks/                 # phase-NN/task-MMM.md
    ├── decisions/             # ADR
    └── reviews/               # コードレビュー記録
```

`.gitkeep` は CSV 生成前のディレクトリ存在保証用。中身（`*.csv`）は `.gitignore` 済み。

## 主要マクロ: `generate_schema_name` の override

`dbt/macros/get_custom_schema.sql` は dbt-postgres デフォルトの「`<target_schema>_<custom_schema>`」prefix 命名を打ち消し、`+schema: marts` を文字どおり `marts` schema にマップする。これを外すと `staging_marts` のような prefix 付き schema が作られ、Terraform が用意した schema と一致しなくなる。詳細は [ADR-0005](decisions/0005-dbt-config.md)。

## materialization の使い分け

| materialization | 再計算 | 速度（参照） | ストレージ | 使い所 |
|---|---|---|---|---|
| view | 参照のたび | 遅い | ほぼ 0 | 軽い変換、staging |
| table | dbt run のたび full | 速い | 行数分 | mart、頻繁に参照される集計 |
| incremental | 差分のみ追加 | 速い | 行数分 | 大規模 fact、毎日追記 |
| ephemeral | 物質化しない（CTE 化） | 中 | 0 | プライベート中間 SQL |

## テストの 2 系統

- **generic test** (`schema.yml` に YAML で書く): `not_null` / `unique` / `relationships` / `accepted_values` などのビルトイン。複数列で再利用される定型チェック。
- **singular test** (`tests/*.sql` に SQL を書く): 「失敗行を返す SELECT 文」を書くだけ。1 行でも返ったら fail。`assert_positive_sales_amount.sql` は `WHERE sales_amount < 0` で違反行を返している。

両者を組み合わせて MVP では 61 件のテストを構成している。
