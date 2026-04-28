# 9-7 解答例

## ゴール再掲

- `dbt/profiles.yml` の `threads:` を `4 → 8` に変更
- threads=4 / 8 の 2 通りで `dbt build --select 100-knock` を計測
- 結果を `parallelism-analysis.md` に表 + DAG 図で記録、「並列」「シリアル」を言語化

## dbt/profiles.yml (差分)

```yaml
local_analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: "{{ env_var('DB_HOST', 'localhost') }}"
      port: "{{ env_var('DB_PORT', '5432') | int }}"
      user: "{{ env_var('DB_USER', 'dbt_user') }}"
      password: "{{ env_var('DB_PASSWORD', 'dbt_password') }}"
      dbname: "{{ env_var('DB_NAME', 'analytics') }}"
      schema: staging
      threads: 8           # ← 4 から 8 へ
      sslmode: disable
      keepalives_idle: 0
```

## 実行コマンド

```bash
set -a; source .env; set +a
cd dbt

# 一度フル build (warm-up)
../.venv/bin/dbt build --select 100-knock --profiles-dir . --no-colors >/dev/null 2>&1

# threads=4 で計測 (一旦 4 に戻して)
sed -i.bak 's/threads: 8/threads: 4/' profiles.yml
time ../.venv/bin/dbt build --select 100-knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-7-threads-4.log

# threads=8 で計測
sed -i.bak 's/threads: 4/threads: 8/' profiles.yml
time ../.venv/bin/dbt build --select 100-knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-7-threads-8.log

rm profiles.yml.bak
```

(計測前に必ず 1 回 build してから 2 回目を計測すると wal cache が効いて公平)

## docs/exercises/100-knock/topic-9-performance/parallelism-analysis.md

```markdown
# 9-7 並列度分析

実行日: 2026-04-26
対象: `dbt build --select 100-knock`
環境: docker-compose Postgres 16 / Mac M1 / 8 物理コア

## 計測結果

| 設定 | real time | user time | sys time | Concurrency log |
|---|---|---|---|---|
| threads=4 | 0m12.345s | 0m04.21s | 0m01.10s | `Concurrency: 4 threads (target='dev')` |
| threads=8 | 0m11.678s | 0m04.45s | 0m01.18s | `Concurrency: 8 threads (target='dev')` |

差は 0.67s (~5% 短縮)。**threads を 2 倍にしても線形には速くならない**。

## DAG 構造 (シリアル と 並列)

```text
[並列可能 — fan-out]                    [シリアル — fan-in]                 [並列可能 — fan-out]

source:raw_100knock.customers --> stg_customers_100knock ─┐
source:raw_100knock.products  --> stg_products_100knock  ─┤
source:raw_100knock.stores    --> stg_stores_100knock    ─┼──> int_order_details_100knock ──┐
source:raw_100knock.orders    --> stg_orders_100knock    ─┘                                 ├──> mart_customer_sales_100knock
                                                                                            ├──> mart_product_sales_100knock
                                                                                            └──> mart_daily_sales_100knock
```

- staging 4 本: **互いに独立** → threads が許す限り 4 つ同時
- intermediate 1 本: **4 staging 全部に依存** → 4 staging が完了するまで待機 (シリアル化)
- mart 3 本: **共通 int の後で互いに独立** → 3 つ同時

## 考察 — なぜ 8 threads でほぼ高速化されないか

1. **DAG の最大幅が 4** (staging 段の幅) なので、threads >= 4 の時点で staging は飽和
2. **intermediate 段が 1 model** なので並列度は意味を持たない (1 model しか走らない)
3. **mart 段の幅が 3** なので threads >= 3 で飽和
4. = 並列度の有効上限は `max(staging幅, mart幅) = 4`。threads=8 にしても 5〜8 番目のスロットは空席になる

数式で書くと: 並列度の上限 = `min(DAG 最大幅, threads, DB connection pool)` 。本 DAG は 4。

## 並列度を上げて意味があるケース

- staging が 20〜50 本ある大規模プロジェクト → 8〜16 threads が活きる
- snapshots / seeds など並列幅が大きい段がある場合
- ただし DB 側の `max_connections` を必ず超えないこと (Postgres デフォルト 100、本プロジェクトは 100)

## 結論

- 本プロジェクト規模では `threads: 4` で十分。`threads: 8` 化はオーバーキル
- 「並列度を増やせば線形に速くなる」は嘘。DAG クリティカルパス長は不変 (Amdahl の法則)
- threads は **DAG 形状を見て決める**。threads = (DAG 最大幅) で十分、それ以上は無駄
```

## 解説まとめ

### なぜ threads は宣言で抑えるのか

- threads は「**何個まで同時に DB に接続して走らせて良いか**」の宣言
- これが動的だと CI 環境差で挙動が変わる (本番 8 cores、開発 4 cores、CI 2 cores) → 必ず profiles.yml で固定
- profiles.yml はリポジトリ管理なのでチーム全員が同じ並列度で走る

### なぜ shared 依存はシリアル化されるのか — DAG クリティカルパス

- `int_order_details_100knock` が `stg_customers / stg_products / stg_stores / stg_orders` 4 本に依存している = `depends_on` で 4 本を要求
- dbt スケジューラは「**全 depends_on が完了してから**」その node を起動する
- これが **シリアル化** の正体。並列度を上げても「上流が全部終わるまで待つ」は変わらない
- 実時間 = max(各上流の完了時刻) + 自分の所要時間

### 並列度の有効上限

- **DAG 最大幅**: ある段で同時に走れる model 数
- **`threads:`**: 学習者が宣言した並列度
- **DB connection pool size**: Postgres の `max_connections` (デフォルト 100)
- **CPU cores** (実質): 物理 thread 数を超えると context switch overhead で逆効果
- 実効並列度 = `min(これら全部)`

### `time` の見方

- `real`: 壁時計時間 (人間にとって重要)
- `user`: CPU が user-mode で使った時間 (並列処理だと real より大きくなる)
- `sys`: CPU が kernel-mode で使った時間
- `user + sys > real` なら「並列に CPU を使っていた」証拠

### 採点で何を見ているか

- `file_exists` で `parallelism-analysis.md` 存在
- `shell_command` で `profiles.yml` の `threads:` が `>=8` (= 4 から増やしている) を確認
- md に「並列」「シリアル」両キーワードを grep

### 注意 — 計測の罠

- **キャッシュ効果**: 1 回目は table を CREATE するので遅い、2 回目以降は incremental の上書きや CREATE OR REPLACE で速くなる。「計測前に 1 回 warm-up」が公平
- **noise**: real time は ±10% 程度ぶれる。3 回計測の中央値を取るのが理想
- **CI vs ローカル**: GitHub Actions の runner は CPU が貧弱で計測が不安定。本問では「**数値そのものより並列/シリアルの構造を理解したか**」を採点対象にしている

### 次の問 (9-8) との接続

- 9-7 で「並列度は宣言で抑える」を学んだ後、9-8 では「**build 範囲も宣言で抑える**」(`state:modified+`) に進む
- 「**変更した model だけ build**」 + 「**並列度を最大限活用**」 = CI で「壊れたところだけ最小コストで再 build」 が完成する
