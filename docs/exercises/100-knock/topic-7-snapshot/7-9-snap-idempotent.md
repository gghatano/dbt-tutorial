# 7-9: snapshot を 2 回叩いて no-op (冪等性) を確認する

## シナリオ

dbt の設計原則の 1 つに **冪等性 (idempotency)** がある: 「同じ入力に対して
何度実行しても結果が同じ」状態。snapshot もこの原則に従い、入力 (= source 側
`raw_100knock.products`) が変わっていない限り、`dbt snapshot` を何回叩いても
**新しい履歴行は 1 件も増えない** (= no-op)。

逆に冪等でないと、cron が誤って 2 回起動した時に履歴が二重化したり、
リトライのたびに `dbt_valid_to` が書き換わったりして履歴が壊れる。
本問では実際に同じ snapshot を 2 回連続で叩き、行数が **増えない** ことを
SQL で確認する。これが「snapshot の冪等性」 のエビデンス。

## 学べること

- 冪等性 (idempotency) の定義と、なぜ data pipeline で重要か
- snapshot の no-op 挙動 (= source に変化が無ければ INSERT も UPDATE も走らない)
- 「2 回目を叩いて壊れない」を **テスト可能な不変条件** として宣言する習慣
- cron 二重起動 / CI リトライ / ローカル実験 など、実務で冪等性が効く場面

## 前提

- 7-1 〜 7-8 完了 (snap_products_100knock が v1+v2 = 120 行で安定している状態)
- `dbt parse` が通る
- `set -a; source .env; set +a` 済み

## 入力データ

不要。**変えずに** snapshot を 2 回叩くのが本問の趣旨。

## 課題

### Step 1: 1 回目の dbt snapshot 直前の行数を記録

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 例: 120
```

この値を **before** として控えておく (期待: 120)。

### Step 2: dbt snapshot を 1 回目

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
cd ..
```

期待ログ: `OK snapshotted snapshots.snap_products_100knock ... [SELECT 0 in ...s]`
(= 新規 INSERT 0 行 = no-op)。

### Step 3: 行数を再確認 (mid)

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 期待: 120 (変わらない)
```

### Step 4: dbt snapshot を 2 回目

```bash
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
cd ..
```

期待ログ: 同じく `SELECT 0`。

### Step 5: 行数を最終確認 (after)

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics \
    -tAc "SELECT count(*) FROM snapshots.snap_products_100knock"
# 期待: 120 (= before と同じ)
```

before == mid == after が成立すれば冪等性 OK。

### Step 6: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-7-snapshot/7-9-snap-idempotent.grading.yaml
```

採点側でも `dbt snapshot` を **2 回** 自動実行し、その前後で行数が変わらない
ことを SQL で検証する。

## 完了条件

- [ ] `dbt snapshot --select snap_products_100knock` を **2 回連続** 叩いても
  exit 0 で完走する
- [ ] 2 回目実行後の `snapshots.snap_products_100knock` 行数が **1 回目実行後と
  同じ** (= 新規 INSERT 0 / UPDATE 0)
- [ ] 1 回目 / 2 回目とも snapshot ログに `SELECT 0` 系の no-op 表現が出る

## ヒント (詰まったら)

- **2 回目で行が増える**: 7-2 で v2 を投入した直後にこの問題を解いていないか
  確認。**raw_100knock.products が v2 のまま固定** されている前提。Step 1〜5
  の間に raw を触らない。
- **`SELECT N` (N > 0) が出る**: snapshot の `check_cols` に意図しない列が
  入っていないか確認。例えば `dbt_valid_*` や snapshot メタ列を check_cols
  に入れると、毎回「変わった」と判定されて履歴が爆発する。`check_cols` は
  source 側の業務列 (例: `unit_price`) だけ。
- **「冪等」がそもそも何か曖昧**: HTTP の `PUT` / `DELETE` と同じ概念。
  `f(x) = f(f(x)) = f(f(f(x))) = ...` を満たす関数。data pipeline では
  「同じ source 状態に対し同じ結果」 = リトライ・二重起動に強い、という意味。
- **本番運用で 2 回叩く状況とは**: cron の二重起動 (= 別ホストで同時に
  起動)、CI のリトライ、Airflow の retry policy など。冪等でないと
  「リトライが状態を破壊する」事故が起きるので、snapshot 設計者として
  常にこの性質を意識する。

## 解答例

詳細は [`7-9-snap-idempotent.solution.md`](7-9-snap-idempotent.solution.md) を参照。
