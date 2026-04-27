# 7-3: timestamp strategy で別 snapshot を作る

## シナリオ

7-1〜7-2 で `check` strategy の snapshot を作って動作確認した。`check` は
「列の値変化を全行スキャンして検知」する汎用解だが、source に **更新時刻列
(`updated_at`)** があるなら、そこの timestamp が前回 snapshot 時刻より新しい
行だけ拾えばよく、計算量が桁違いに小さくなる。これが `timestamp` strategy。

本問では `raw.products` に `updated_at` 列を追加して、`timestamp` strategy で
別 snapshot (`snap_products_ts_100knock`) を新設し、**「strategy の選択は source 側の
スキーマに依存する」** という設計判断を体に入れる。

## 学べること

- `strategy='timestamp'` + `updated_at` の宣言意味
- `check` と `timestamp` の **計算量・前提・精度差**
- 同じ source に対して複数 snapshot を並走させる運用 (戦略比較)
- raw 側にメタ列 (`updated_at`) を追加するインパクト

## 前提

- 7-1〜7-2 完了 (`snap_products_100knock` が check strategy で動いている)
- `raw.products` の DDL を変更してよい (このトピックの範囲)

## 課題

### Step 1: raw.products に updated_at を追加

`scripts/100-knock/topic-7/add_updated_at_to_products.py` を新規作成
(または psql 直叩きで OK):

```sql
ALTER TABLE raw.products ADD COLUMN updated_at TIMESTAMP DEFAULT now();
UPDATE raw.products SET updated_at = now();  -- 全行に現在時刻を埋める
```

完了の見え方:

- `\d raw.products` で 5 列目に `updated_at | timestamp` が出る
- 全 100 行で `updated_at` が NULL でない

### Step 2: sources.yml に updated_at を追記

`dbt/models/100-knock/topic-2/sources.yml` の `products` テーブル定義に
`updated_at` 列を追加:

```yaml
- name: products
  columns:
    - name: product_id
    - name: product_name
    - name: category
    - name: unit_price
    - name: updated_at         # 追加
```

### Step 3: timestamp strategy の snapshot を書く

`dbt/snapshots/100-knock/topic-7/snap_products_ts_100knock.sql` を新規作成。

要件:

- `{% snapshot snap_products_ts_100knock %}` ブロック
- config:
  - `target_schema='snapshots'`
  - `unique_key='product_id'`
  - `strategy='timestamp'`
  - `updated_at='updated_at'`
- SELECT 本体は `source('raw_100knock', 'products')` から `product_id`,
  `product_name`, `category`, `unit_price`, `updated_at` の 5 列

### Step 4: 1 回目の `dbt snapshot`

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_ts_100knock
# => SELECT 100 (1 回目なので全行 INSERT)
```

完了の見え方:

- `snapshots.snap_products_ts_100knock` が 100 行
- `dbt_valid_to is null` の行が 100 (全部最新)

### Step 5 (任意): check 版との比較

```sql
SELECT 'check' AS strategy, count(*) FROM snapshots.snap_products_100knock
UNION ALL
SELECT 'timestamp', count(*) FROM snapshots.snap_products_ts_100knock;
```

両方とも `dbt_valid_from` が打刻されていることを確認。`updated_at` を更新して
2 回目を叩くと、`timestamp` 版は `updated_at > previous` の行だけが履歴化される。

## 完了条件

- [ ] `raw.products` に `updated_at` 列が追加されている
- [ ] `sources.yml` に `updated_at` が追記されている
- [ ] `dbt/snapshots/100-knock/topic-7/snap_products_ts_100knock.sql` が存在する
- [ ] manifest に `snapshot.local_analytics.snap_products_ts_100knock` が登録される
- [ ] `dbt snapshot --select snap_products_ts_100knock` が PASS=1
- [ ] `snapshots.snap_products_ts_100knock` が 100 行

## ヒント (詰まったら)

- **`Compilation Error: snapshot ... missing required field: 'updated_at'`**:
  `strategy='timestamp'` のときは `check_cols` ではなく `updated_at='<列名>'`
  を config に書く。文字列で列名を指定する。
- **`updated_at` 列が NULL のまま**: `ALTER TABLE ... ADD COLUMN ... DEFAULT now()`
  は新規行にしか default を効かせない。既存行には別途 `UPDATE ... SET updated_at = now()`
  が要る。
- **stg_products が壊れる**: `ALTER TABLE` は CASCADE 不要だが、`stg_products`
  view が `updated_at` を参照していなければ問題なし。参照していて壊れるなら
  view 側も対応 (本問では Topic ③ の stg_products に updated_at を入れていない
  前提)。
- **2 種の snapshot が同じ schema に並ぶ**: `snapshots.snap_products_100knock`
  と `snapshots.snap_products_ts_100knock` の 2 テーブル。table 名が違うので
  衝突しない。`SELECT count(*) FROM snapshots.<table>` で別個に行数確認できる。
- **dbt 上の node 名衝突は無いか**: snapshot 名 (`{% snapshot <name> %}`) が
  別ならファイル名は同じディレクトリでも問題なし。本問は `_ts` suffix で確実に分ける。

## 解答例

詳細は [`7-3-snap-timestamp-strategy.solution.md`](7-3-snap-timestamp-strategy.solution.md) を参照。
