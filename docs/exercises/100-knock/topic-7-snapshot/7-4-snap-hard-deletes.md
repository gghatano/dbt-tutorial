# 7-4: hard_deletes で物理削除も履歴に残す

## シナリオ

7-1〜7-3 で「列の値変化」を SCD Type-2 で履歴化する仕組みを身につけた。
しかし実運用ではもうひとつの **時間軸イベント** がある: source 行の **物理削除**
(SKU 廃番、退会、店舗閉店など)。

標準の dbt snapshot は raw から消えた行を **そのまま放置** (旧行の `valid_to` を
更新しない) する設計。「source からも snapshot からも未来永劫 valid_to が NULL の
ままで、いつ消えたか分からない」状態が残る。dbt 1.9+ で導入された
**`hard_deletes: new_record`** 設定を使うと、source から消えた瞬間に snapshot 側に
**「削除イベント」行** を追加し、`dbt_is_deleted=true` のメタ列で削除を歴史として
記録できる。

本問は raw から 5 行物理削除して `hard_deletes: new_record` を有効化した snapshot
で、削除も履歴に残ることを確認する。

## 学べること

- `hard_deletes: new_record` の宣言意味 (dbt 1.9+)
- `dbt_is_deleted` メタ列の挙動
- 「物理削除イベント」を時間軸の事実として宣言する設計判断
- snapshot のメタ列拡張ファミリ (`dbt_valid_from` / `dbt_valid_to` / `dbt_scd_id` /
  `dbt_is_deleted`)

## 前提

- 7-1〜7-2 完了 (`snap_products_100knock` が check 版で動き、120 行ある)
- dbt-core 1.9+ で実行 (本リポジトリは dbt-core 1.11、動作する想定)
- raw.products から 5 行を物理削除して良い

> **動かない場合の保険**: dbt-core が古い / hard_deletes が未対応の場合は、
> 解答例の **「ヒント代替案」** に従って `dbt_is_deleted` を SELECT で
> 手動エミュレートする方針に切り替える。本問の grading は **「snapshot ファイルに
> hard_deletes の記述がある」** + **「削除後に snapshot を実行できる」** までを
> 必須とし、`dbt_is_deleted` の物理出現は加点扱いとする。

## 課題

### Step 1: snapshot に hard_deletes を追加

7-1 で作った `dbt/snapshots/100-knock/topic-7/snap_products_100knock.sql` を編集
**するのではなく**、新しいファイル
`dbt/snapshots/100-knock/topic-7/snap_products_hd_100knock.sql` を作る
(7-1 の状態を保つため、独立 snapshot として並走させる)。

要件:

- `{% snapshot snap_products_hd_100knock %}` ブロック
- config に `hard_deletes='new_record'` を追加
- それ以外は 7-1 と同じ (check strategy / unit_price / unique_key=product_id /
  target_schema=snapshots)

### Step 2: 1 回目の snapshot

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_hd_100knock
# => SELECT 100 (raw.products は v2 状態の 100 行)
```

完了の見え方:

- `snapshots.snap_products_hd_100knock` が 100 行
- 全行 `dbt_is_deleted = false` (もしくは NULL)、`dbt_valid_to is null`

### Step 3: raw.products から 5 行物理削除

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
DELETE FROM raw.products WHERE product_id IN (1, 2, 3, 4, 5);
SQL
```

完了の見え方:

- `SELECT count(*) FROM raw.products;` が 95
- product_id 1〜5 が消えている

### Step 4: 2 回目の snapshot (削除イベントを履歴化)

```bash
../.venv/bin/dbt snapshot --profiles-dir . --select snap_products_hd_100knock
```

完了の見え方:

- `snapshots.snap_products_hd_100knock` が **105 行** (元の 100 + 削除イベント 5)
- 元の 5 行の `dbt_valid_to` が UPDATE される
- 新規 5 行が `dbt_is_deleted = true` で INSERT される

### Step 5: 削除履歴を確認

```sql
SELECT product_id, unit_price, dbt_valid_from, dbt_valid_to, dbt_is_deleted
FROM snapshots.snap_products_hd_100knock
WHERE product_id IN (1, 2, 3, 4, 5)
ORDER BY product_id, dbt_valid_from;
```

各 product_id に対して 2 行が出る:

- v1: `dbt_valid_to` 埋まり、`dbt_is_deleted=false`
- 削除イベント行: `dbt_is_deleted=true`、`dbt_valid_to is null`

## 完了条件

- [ ] `dbt/snapshots/100-knock/topic-7/snap_products_hd_100knock.sql` が存在する
- [ ] snapshot ファイルに `hard_deletes:` の記述がある (`new_record` / `'new_record'`)
- [ ] 1 回目 snapshot 後に `snapshots.snap_products_hd_100knock` が 100 行
- [ ] 5 行物理削除後の 2 回目 snapshot 実行が成功する
- [ ] (加点) 2 回目 snapshot 後に `dbt_is_deleted=true` の行が 5 ある

## ヒント (詰まったら)

- **`hard_deletes: new_record` が `Compilation Error` で落ちる**: dbt-core が
  1.9 未満。`pip show dbt-core` で確認。本リポジトリは 1.11 を想定。
  動かなければヒント代替案 (`dbt_is_deleted` を SELECT 側で手動エミュレート) に切替。
- **2 回目で削除イベント行が出ない**: `hard_deletes='ignore'` (default) になっている
  か、`hard_deletes` の文字列値タイポ (`new-record` / `new_records`)。`new_record`
  (アンダースコア区切り、単数) が正解。
- **`dbt_is_deleted` 列が無い**: dbt-core 1.9 でもデフォルトでは付かない。
  `hard_deletes='new_record'` で snapshot を **初回作成** するか、既存 snapshot を
  drop して作り直すと付く。後付けは ALTER で手動追加が要る場合がある。
- **MVP の Ex.04 snapshot に影響が出る**: 本問は **新規 snapshot ファイル**
  (`snap_products_hd_100knock`) を作る方針。7-1 の `snap_products_100knock` も
  独立して残るので、Ex.04 や 7-1〜7-3 の状態は壊れない。
- **DELETE で stg_products が壊れる**: `DELETE` は `DROP TABLE` と違って
  view を巻き込まない。stg_products は 95 行返す状態になるだけで、
  schema は壊れない。

## 解答例

詳細は [`7-4-snap-hard-deletes.solution.md`](7-4-snap-hard-deletes.solution.md) を参照。
