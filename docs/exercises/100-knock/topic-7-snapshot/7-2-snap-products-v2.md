# 7-2: v2 を流し込んで履歴 v1+v2 を確認

## シナリオ

7-1 で `snap_products_100knock` を 1 回目実行し、`snapshots.snap_products_100knock` に
全 100 行を「最新行」として記録できた。今度はマーチャンダイザが **20 商品の
`unit_price` を改定** したことを想定して、raw 側を v2 に差し替え、2 回目の
`dbt snapshot` を実行する。

期待挙動: 旧 20 行に `dbt_valid_to` が埋まり、新 20 行が `dbt_valid_to is null` で
追記される。結果として `snapshots.snap_products_100knock` の総行数は **120 行
(v1 100 + v2 20)** になる。これが SCD Type-2 の本体動作。

## 学べること

- raw 側の **「上書き」を「履歴行の追加」に変換する** dbt snapshot の挙動
- `dbt_valid_to is null` が「最新行」を表すフィルタ規約
- 2 回目以降の `dbt snapshot` のログ (`SELECT 20` = 変化検知 20 行)
- raw を物理的に差し替える運用 (DROP + CREATE + COPY) と stg view の rebind

## 前提

- 7-1 完了: `snap_products_100knock.sql` がコミット済み、1 回目実行済みで
  `snapshots.snap_products_100knock` が 100 行
- `data/exercises/inbox/products_v2.csv` が手元にある
  (Ex.04 用の `scripts/exercises/generate_04_price_update.py` を流用すれば作れる)
  - 100-knock 用に新規生成スクリプトを作っても良い (ファイル末尾参照)

## 入力データ

`products_v2.csv` の作り方:

```bash
# Ex.04 用のジェネレータを流用 (data/raw/products.csv を v1 とみなして 20 行差し替え)
.venv/bin/python scripts/exercises/generate_04_price_update.py
# => data/exercises/inbox/products_v2.csv (100 行 / うち 20 行の unit_price が変化)
```

> **100-knock 派生**: 純粋に 100-knock データから作りたい場合は、
> `data/100-knock/topic-1/products.csv` を入力にする派生スクリプトを書く
> (解答例参照)。

## 課題

### Step 1: v2 ロード script を書く

`scripts/100-knock/topic-7/load_products_v2.py` を新規作成。

要件:

- `.env` から DB 接続情報を読み込む (`dotenv` 利用)
- `raw.products` を `DROP TABLE ... CASCADE` してから `CREATE TABLE` し直す
  (DDL は Topic ② 2-1 と同じ `BIGINT PK` + `NUMERIC(12,2)`)
- `data/exercises/inbox/products_v2.csv` を `COPY ... FROM STDIN` で投入
- 投入後の行数を print して確認

### Step 2: v2 を投入

```bash
.venv/bin/python scripts/100-knock/topic-7/load_products_v2.py
# raw.products refreshed: 100 rows
```

完了の見え方:

- `SELECT count(*) FROM raw.products;` が 100 のまま
- `SELECT count(DISTINCT unit_price) FROM raw.products;` が増減 (v1 と差分が出る)

### Step 3: 2 回目の `dbt snapshot`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_100knock
# => SELECT 20 と表示される (変化検知 20 行を新規 INSERT)
```

完了の見え方:

- `snapshots.snap_products_100knock` が `count(*) = 120`
- `dbt_valid_to is null` の行が **100** (最新行 = 変わらない 80 + 新版 20)
- `dbt_valid_to is not null` の行が **20** (旧版 20)

### Step 4: 履歴を確認

```sql
SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to
FROM snapshots.snap_products_100knock
WHERE product_id IN (
    SELECT product_id
    FROM snapshots.snap_products_100knock
    GROUP BY product_id
    HAVING count(*) > 1
)
ORDER BY product_id, dbt_valid_from
LIMIT 6;
```

20 商品が 2 行ずつ (v1 + v2) で出れば成功。

## 完了条件

- [ ] `scripts/100-knock/topic-7/load_products_v2.py` が存在する
- [ ] `raw.products` が v2 に差し替わっている (20 行の unit_price が v1 と異なる)
- [ ] 2 回目の `dbt snapshot` が PASS=1 で完了
- [ ] `snapshots.snap_products_100knock` が **120 行**
- [ ] `dbt_valid_to is null` の行が **100**
- [ ] `dbt_valid_to is not null` の行が **20**

## ヒント (詰まったら)

- **2 回目で行数が増えない**: raw が変わっていないと snapshot は no-op。
  Step 1〜2 で v2 を本当に流し込めたか psql で確認 (`SELECT count(DISTINCT unit_price)`)。
- **2 回目で 100 行全部に新版**: `check_cols` に **常に変わる列** (e.g. 自動採番)
  を入れている可能性。`unit_price` だけにする。
- **`SELECT 0` と表示される**: source 側に変化が無い扱い。`raw.products` が
  v1 のままか、または v2 と完全一致している。`generate_04_price_update.py` の
  seed (`SEED=104`) は v1 と必ず 20 行差分が出るよう設計済み。
- **`stg_products` (Topic ③) が壊れる**: `DROP TABLE ... CASCADE` で `stg_products`
  view が一旦無効化される。次の `dbt run --select stg_products+` で復活する。
  並走中の MVP build 中は避ける。
- **2 回目の `dbt snapshot` が `permission denied`**: snapshot table の owner が
  正しく dbt_user になっているか確認。Step 0 で `AUTHORIZATION dbt_user` を
  忘れると 1 回目はギリ動いて 2 回目で UPDATE 権限不足で落ちることがある。

## 解答例

詳細は [`7-2-snap-products-v2.solution.md`](7-2-snap-products-v2.solution.md) を参照。
