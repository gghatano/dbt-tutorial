# 9-7: `profiles.yml` の threads を 4 → 8 に変えて build 時間を測定、シリアル/並列の DAG を分析する

> ⚠️ **本問は `dbt/profiles.yml` を学習者が編集する**。MVP で動いている `threads: 4` の状態に戻せるよう Step 5 にロールバック手順あり。

## シナリオ

dbt はデフォルトで複数 model を並列に build する。並列度を決めるのが `profiles.yml` の `threads:` 設定。`threads: 4` なら同時に 4 model まで走る。だが **どれだけ threads を増やしても並列にできない箇所** がある — それが「上流が共通の単一 model に集約されている」ような **シリアル依存** の部分。

例えば `stg_customers_100knock` / `stg_products_100knock` / `stg_stores_100knock` / `stg_orders_100knock` の 4 staging は互いに独立なので、threads が許せば 4 つ同時に走れる。だが `int_order_details_100knock` は 4 staging すべてに依存するので、4 staging 全部が終わるまで待たねばならない (= シリアル化される)。

本問では `threads: 4` と `threads: 8` で `dbt build --select 100-knock` を計測し、**並列にできる範囲とシリアル化される範囲を DAG 図で描く**。結果を `parallelism-analysis.md` に残し、「**並列度の宣言 ↔ DAG 形状の関係**」を自分の言葉で書く。

## 学べること

- `profiles.yml` の `threads:` で並列度を宣言
- `time dbt build` で実時間を計測する習慣
- DAG の **fan-out** (= 並列可能) と **shared 依存** (= シリアル化) の見分け方
- 「threads を増やせば線形に速くなる」が成立しない理由 (= DAG のクリティカルパス長は変わらない)
- 並列度の上限が「DAG の最大幅」と「DB connection pool size」の min で決まること

## 前提

- Topic ② 〜 ⑦ + ⑧ + 9-1〜9-5 + 9-6 完了
- `dbt/models/100-knock/topic-3/stg_*_100knock.sql` 4 本以上
- `dbt/models/100-knock/topic-4/int_*_100knock.sql` 1 本以上
- `dbt/models/100-knock/topic-5/mart_*_100knock.sql` 1 本以上
- `dbt parse` が通る
- `git status` がクリーン

## 入力データ

不要。学習者は `profiles.yml` を編集 + 計測スクリプトを叩くのみ。

## 課題

### Step 1: 現状の threads を確認

```bash
grep -E '^\s*threads:' dbt/profiles.yml
# threads: 4
```

### Step 2: threads=4 で計測 (ベースライン)

```bash
set -a; source .env; set +a
cd dbt
# 一度フル build して target/ をクリーンに
../.venv/bin/dbt build --select 100-knock --profiles-dir . >/dev/null 2>&1 || true

# 計測 1: threads=4
time ../.venv/bin/dbt build --select 100-knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-7-threads-4.log
```

実時間 (`real`) をメモ。例: `real 0m12.345s`。

### Step 3: threads=8 に変更 → 計測

`dbt/profiles.yml` の `threads: 4` を `threads: 8` に書き換え:

```yaml
local_analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      # ...
      threads: 8     # ← 4 から 8 へ
      sslmode: disable
```

```bash
# 計測 2: threads=8
time ../.venv/bin/dbt build --select 100-knock --profiles-dir . --no-colors 2>&1 | tee /tmp/9-7-threads-8.log
```

実時間をメモ。

### Step 4: parallelism-analysis.md に記録

`docs/exercises/100-knock/topic-9-performance/parallelism-analysis.md` を新規作成。以下を含める:

```markdown
# 9-7 並列度分析

## 計測結果

| 設定 | real time | Concurrency log |
|---|---|---|
| threads=4 | 0m12.345s | `Concurrency: 4 threads (target='dev')` |
| threads=8 | 0m11.678s | `Concurrency: 8 threads (target='dev')` |

(差が小さい場合は「シリアル依存があるため線形には速くならない」と書く)

## DAG 構造 (シリアル と 並列)

```text
[並列可能: 4 threads で同時に走る]
source:raw_100knock.customers --> stg_customers_100knock ─┐
source:raw_100knock.products  --> stg_products_100knock  ─┤
source:raw_100knock.stores    --> stg_stores_100knock    ─┼──> int_order_details_100knock
source:raw_100knock.orders    --> stg_orders_100knock    ─┘    [シリアル: 4 staging 全部が終わってから 1 個が走る]
                                                               │
                                                               v
                                                      mart_customer_sales_100knock
                                                      mart_product_sales_100knock     [並列可能: int の後で同時]
```

## 考察

- 「**並列**」化されているのは: 4 staging (互いに独立) と 複数 mart (共通 int の後で互いに独立)
- 「**シリアル**」になっているのは: source → staging → intermediate → mart のレイヤー間 (depends_on で順序がある)
- threads=8 にしても **並列幅が 4 を超えない** 部分 (4 staging が同時) ではほぼ高速化されない
- 並列度の上限は **min(DAG 最大幅, threads, DB connection pool size)** で決まる
```

### Step 5: ロールバック手順

```bash
git checkout HEAD -- dbt/profiles.yml
# または手で threads: 8 → 4 に戻す
```

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-9-performance/9-7-parallelism-threads.grading.yaml
```

## 完了条件

- [ ] `dbt/profiles.yml` の `threads:` が 8 になっている (または学習者が選んだ別値)
- [ ] `docs/exercises/100-knock/topic-9-performance/parallelism-analysis.md` が存在
- [ ] md に「並列」「シリアル」両キーワードがあり、DAG 構造の図 (text 図 or mermaid) がある
- [ ] threads=4 と threads=8 の計測結果が表として記録されている

## ヒント (詰まったら)

- **`Concurrency: N threads` ログ**: `dbt build` の冒頭ログに `Concurrency: 4 threads (target='dev')` のような行が出る。これが実際に dbt が使った並列度の証拠
- **threads を増やしても速くならない**: それが本問の主旨。DAG にシリアル依存があるとクリティカルパス長は変わらない (Amdahl の法則)。むしろ DB の connection pool が枯渇して逆効果になることもある
- **build がエラーで止まる**: 並列度を増やすと race condition が露呈する場合がある (e.g. seed が同時に CREATE TABLE を発行して競合)。本問では既存 model だけ build すれば問題は出ないはず
- **`time` が複数行に分かれる**: zsh / bash で `time` の出力フォーマットが違う。`real` 行の数値が壁時計時間
- **threads は connection pool より小さくする**: Postgres の `max_connections` (デフォルト 100) を超える threads を指定すると接続エラー。docker-compose の Postgres は 100 なので 8 threads は問題ないが 1000 threads は不可
- **DAG 図を Mermaid で描く** (任意): GitHub の Markdown は Mermaid をレンダリングする。`graph LR` で fan-out / fan-in を視覚化できる

## 解答例

詳細は [`9-7-parallelism-threads.solution.md`](9-7-parallelism-threads.solution.md) を参照。
