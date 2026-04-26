# ADR 0009: プロジェクト完了サマリ

- 日付: 2026-04-26
- ステータス: Accepted
- コンテキスト: phase-06/task-003 (FINAL)
- 関連: spec §13, §14, ADR-0001 〜 0008

## 概要

`local-data-platform` (dbt-tutorial) の MVP（spec §1〜§13）が完了した。
本 ADR ではプロジェクト全体の到達点・spec §13 完了条件の最終 verification 結果・
開発を通じて得た教訓・次フェーズ候補を一括で記録する。

## 1. 全 phase の到達点（commit hash 付き）

| Phase | 完了内容 | 主要 commit |
|---|---|---|
| phase-01 | docker-compose.yml + .env.example、Colima 上で Postgres healthy | `a1eb0e7` |
| phase-02 | Terraform で 4 schema (`raw`/`staging`/`intermediate`/`marts`) と 2 role (`dbt_user`/`readonly_user`) を構築 | `e765f16` |
| phase-03 | requirements.txt + uv venv (3.12) + Faker dummy 生成 + psycopg3 で raw COPY 投入（DROP→CREATE→COPY、冪等） | `8f63a61`, `40f8c5f`, `b6207cb` |
| phase-04 | dbt project (local_analytics) + sources.yml + staging 4 model + built-in tests + `generate_schema_name` macro override | `7cbf1a2` |
| phase-05 | `int_order_details` (intermediate, INNER JOIN) + mart 3 本 (daily/customer/product sales, materialized=table) | `1e2dd03` |
| phase-06 | custom singular test 4 本（sales_amount/quantity 正値、mart 非空、mart 合計非負）+ `scripts/smoke_test.py` + 本タスクで README/ADR 仕上げ | `10aa4e8`, `e57a4f1` |

最終ブランチ: `feature-phase-06-task-003-completion` (本タスクで main にマージ予定)。

## 2. spec §13 完了条件と verification 結果

end-to-end 再検証は本ブランチ上で手動実行。`set -a; source ../.env; set +a` を
`dbt` 配下で実行する前に必ず行う。

| § | 完了条件 | 検証コマンド | 結果 |
|---|---|---|---|
| §13 | docker compose up で Postgres 起動 | `docker ps --filter name=local-data-postgres --format '{{.Status}}'` | `Up 3 hours (healthy)` ✅ |
| §13 | Terraform で schema/role 作成済 | `\dn` / `SELECT rolname FROM pg_roles ...` | 4 schema (owner=dbt_user) + 2 role 確認 ✅ |
| §13 | ダミーデータ CSV 生成 | `.venv/bin/python scripts/generate_dummy_data.py` + `wc -l` | `1001/101/21/10001` (header 込) ✅ |
| §13 | raw 投入 | `.venv/bin/python scripts/load_raw_data.py` | `customers 1,000 / products 100 / stores 20 / orders 10,000` ✅ |
| §13 | dbt run 成功 | `dbt run --profiles-dir .` | `Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8` ✅ |
| §13 | dbt test 成功 | `dbt test --profiles-dir .` | `Done. PASS=61 WARN=0 ERROR=0 SKIP=0 TOTAL=61` ✅ |
| §13 | marts schema に 3 mart | `\dt marts.*` | `mart_customer_sales / mart_daily_sales / mart_product_sales` (table) ✅ |
| §13 | dbt docs generate 成功 | `dbt docs generate --profiles-dir .` | `target/manifest.json` + `target/catalog.json` 生成 ✅ |
| §13 | README に手順・トラブルシュート | `README.md` 確認 | クイックスタート / ディレクトリ構成 / トラブルシュート / 完了状況の各セクションあり ✅ |

補助: `scripts/smoke_test.py` → `[PASS] all smoke checks passed (raw.orders=10000, marts.mart_daily_sales=365)` exit 0。

## 3. 開発を通じて得た教訓

### 3.1 環境系

- **Docker `credsStore=desktop` の罠**: Docker Desktop が無いマシンに credsStore=desktop の
  `~/.docker/config.json` が残ると、`docker pull` が `docker-credential-desktop` ヘルパを
  待ち続けて無言ハングする (exit 144)。Colima 移行時の典型的な落とし穴。詳細は ADR-0002。
- **Colima の VM ボリューム**: `docker compose down -v` が VM 内のボリュームを消すため、
  raw 層の再ロードが必要になる。worktree 切替で見落とすと夕方以降のハマりが長くなる。

### 3.2 IaC / DB 系

- **raw 層に FK / 制約を入れない**: spec §4 の「raw は CSV をそのまま投入」原則を厳守。
  整合性は staging の `relationships` テストで担保し、raw は「上流由来のゴミも含めて
  そのまま受け取れる」価値を保つ。FK を入れると将来のテスト網羅性が下がる（ADR-0004）。
- **接続ロールは `dbt_user` 一本**: スーパーユーザー (`analytics_user`) は使わず、
  最小権限。dbt も raw ロードも同じ schema 所有者で動くのでシームレス。

### 3.3 dbt 系

- **`generate_schema_name` macro override パターン**: dbt-postgres デフォルトでは
  `+schema: marts` が `<target_schema>_marts` という prefix 命名になる。Terraform で
  作った素の `marts` schema を使うため、macro を override して `custom_schema_name`
  をそのまま返す（ADR-0005）。spec §4 と Terraform の schema 命名を 1:1 に保つために必須。
- **`relationships` テストの `arguments:` ネスト**: dbt 1.11 から `to:` / `field:` は
  `arguments:` 配下に置くのが推奨。旧形式は `MissingArgumentsPropertyInGenericTestDeprecation`
  warning を出す（ADR-0005 末尾）。
- **dbt_utils を入れない最小構成**: `expression_is_true` / `accepted_range` は便利だが、
  spec §9 は built-in + singular test だけで網羅可能。学習用最小構成では依存追加コストの
  方が大きい（ADR-0005）。
- **`accepted_values` の置き場所**: 静的列挙が存在するカラムでないと拡張コストが上がる。
  `mart_product_sales.category` は `generate_dummy_data.py` 側で固定列挙されており、
  `stg_stores.prefecture`（生成は 20/47 都道府県）よりテスト lock 先として自然（ADR-0006）。
- **mart は table、staging/intermediate は view**: 行数小（≤10k）かつ参照集中で再計算
  コストの方が高いため、mart は `materialized: table`（ADR-0006）。

### 3.4 テスト戦略

- **singular test の SELECT 戦略**: `tests/assert_*.sql` は「失敗行を返す SELECT」を書く。
  正例（spec §9.2）: `select * from {{ ref('mart_xxx') }} where total_sales_amount < 0`。
  「テスト名をそのまま読めば落ちる条件が分かる」命名にする（assert_positive_*, assert_*_non_empty）。
- **smoke と test の分離**: smoke (`scripts/smoke_test.py`) の strict 範囲は spec §11.3 の
  3 項目だけに厳密に絞り、staging/intermediate は warn-level に留める。「成功」の定義を
  勝手に強化しない（ADR-0008）。

### 3.5 進め方

- **worktree + phase 単位の linear merge**: 各 phase は独立 worktree で開発し main にマージ。
  ローカル `terraform.tfstate` は worktree ごとに別になるが、Postgres 上の実 schema/role は
  共有されているので、新 worktree で `terraform apply` を再実行する必要は無い（schema は
  既に存在）。
- **判断ログを ADR で逃さない**: コミットメッセージに収まらない設計判断（INNER vs OUTER、
  table vs view、accepted_values の置き場所）は ADR に書き残す。後で「なぜこう書いたか」を
  辿れる。

## 4. 次フェーズ候補（spec §14）

spec §14 は MVP 完了後の拡張候補を「Airflow / クラウド DWH / CI/CD / BI」とだけ記載。
本 MVP の構成を出発点に、それぞれ次のような取り組みが考えられる:

| 領域 | 候補 | 想定スコープ |
|---|---|---|
| スケジューラ | Airflow / Dagster | `generate_dummy_data` → `load_raw_data` → `dbt build` を DAG 化。Postgres は引き続きローカル。 |
| クラウド DWH | BigQuery / Snowflake / Redshift | dbt-postgres → dbt-bigquery 等に adapter 切替。`profiles.yml` に dev/prod target を追加。`generate_schema_name` macro はそのまま使える。 |
| CI/CD | GitHub Actions | PR 時に `dbt build --target ci` + `smoke_test.py`。Postgres は service container で起動。 |
| BI | Metabase / Superset | mart 3 本にダッシュボードを 1〜2 本付ける。`marts` schema を read-only ロールで参照（`readonly_user` を活用）。 |
| データ品質 | Great Expectations / Soda | dbt test の外側でプロファイリング・分布監視を追加。 |

優先順は学習目的次第だが、CI/CD → スケジューラ → クラウド DWH の順が現実的（ローカル開発の
延長で運用に近づける）。

## 5. 再現性ドリル（本タスクではスキップ）

phase-06/task-003 の元の受入条件には `docker compose down -v && colima stop` 後の
再構築手順検証が含まれていたが、本タスクでは以下の理由でスキップ:

- destructive な `down -v` / `terraform destroy` / `colima delete` は前 phase の
  実行済み状態（Postgres ボリューム + Terraform state）を消すため、本ターンで実施すると
  即座のロールバック手段が無い。
- spec §13 の 9 項目に「再構築」は含まれない。再構築は受入条件の外。
- 同等の保証は (1) `load_raw_data.py` の DROP→CREATE→COPY による idempotency と
  (2) `dbt run` の view/table 再生成で代替できる（実際、本タスク内で 2 回目の実行を
  通している）。

ユーザーが将来再現性ドリルを実施する場合の手順:

```bash
# 1. 既存環境を破棄（破壊的）
cd dbt && rm -rf target logs
cd ../infra/terraform && terraform destroy -auto-approve
cd ../../ && docker compose down -v
colima stop

# 2. README "クイックスタート" の手順を頭から再実行
colima start --cpu 4 --memory 8 --disk 20
docker compose up -d
cd infra/terraform && terraform init && terraform apply -auto-approve
cd ../../ && uv venv --python 3.12 && uv pip install -r requirements.txt
.venv/bin/python scripts/generate_dummy_data.py
.venv/bin/python scripts/load_raw_data.py
set -a; source .env; set +a
cd dbt && ../.venv/bin/dbt run --profiles-dir . && ../.venv/bin/dbt test --profiles-dir .

# 3. smoke で確認
cd .. && .venv/bin/python scripts/smoke_test.py  # exit 0 を期待
```

## 結果

spec §13 の全 9 項目で ✅。MVP は完了とみなす。
本 ADR を最後に、`docs/decisions/` の追記は次フェーズ着手時まで停止する。
