# 7-5 解答例

## dbt/snapshots/100-knock/topic-7/schema.yml

```yaml
version: 2

# 100-knock Topic ⑦ Q5 — snapshot 自身の schema 契約。
# snapshot は dbt が自動生成した SCD Type-2 構造を持つが、メタ列が壊れていない
# ことを **明示契約** で保証する。これが運用上の安全網になる。
snapshots:
  - name: snap_products_100knock
    description: |
      products の価格履歴 (SCD Type-2, check strategy on unit_price).
      Topic ⑦ 7-1 で定義された snapshot に対する schema 契約。
    columns:
      - name: dbt_scd_id
        description: |
          dbt が自動生成する SCD 物理 PK (unique_key + dbt_valid_from の hash).
          snapshot 行の絶対同一性を保証する列。
        tests:
          - not_null
          - unique

      - name: product_id
        description: |
          論理同一性のキー (snapshot config の unique_key).
          履歴版が複数あるので unique 不可。NULL は不変条件として禁止。
        tests:
          - not_null

      - name: dbt_valid_from
        description: |
          この snapshot 行が有効になった時点 (= snapshot 実行時刻、または timestamp
          strategy なら updated_at). NULL は不変条件として禁止。
        tests:
          - not_null

      - name: dbt_valid_to
        description: |
          この snapshot 行が無効化された時点。NULL は「最新行」を意味する規約なので
          test は貼らない (NULL を許す)。

      - name: unit_price
        description: "snapshot 時点の単価 (NUMERIC). 0 以下は raw 側で禁止されている。"
```

**ポイント**:

- **`snapshots:` トップレベルキー**: `models:` ではない。dbt 1.x 以降、snapshot 用の
  schema 契約はこの専用キーで宣言する。中身の構造 (`name:` / `description:` /
  `columns:`) は models と同じ。
- **`dbt_scd_id` への `not_null` + `unique`**: snapshot 行の **物理 PK 契約**。
  この 2 件が PASS する限り、snapshot 内の行同士で SCD ID 衝突 / NULL は無いと
  機械的に保証される。
- **`product_id` には `not_null` のみ**: 同じ product_id の履歴複数行があるので
  `unique` は不可。NULL は raw 側で禁止されている (Topic ② で `BIGINT PRIMARY KEY`)
  ので snapshot 側でも NULL は来ないはずだが、契約として明示。
- **`dbt_valid_from` への `not_null`**: snapshot は実行時に必ず `now()` を入れる
  仕様なので NULL になることは無い (はず)。「無いはず」を test で保証するのが
  schema 契約の本質。
- **`dbt_valid_to` には test を貼らない**: 最新行は NULL なので、`not_null` を
  貼ると常に FAIL する。代わりに「同一 unique_key で `dbt_valid_to is null` の
  行は **必ず 1 行**」を検証する singular test を書くのが本格派 (発展課題、
  下記補足参照)。

## 実行ログ例

```text
$ ../.venv/bin/dbt test --profiles-dir . --select snap_products_100knock
15:10:01  Running with dbt=1.11.x
15:10:01  Found 3 snapshots, ... 8 data tests, ...

15:10:02  1 of 4 START test not_null_snap_products_100knock_dbt_scd_id .... [RUN]
15:10:02  1 of 4 PASS  not_null_snap_products_100knock_dbt_scd_id ........... [PASS]
15:10:02  2 of 4 START test unique_snap_products_100knock_dbt_scd_id ...... [RUN]
15:10:02  2 of 4 PASS  unique_snap_products_100knock_dbt_scd_id ............. [PASS]
15:10:02  3 of 4 START test not_null_snap_products_100knock_product_id .... [RUN]
15:10:02  3 of 4 PASS  not_null_snap_products_100knock_product_id ........... [PASS]
15:10:02  4 of 4 START test not_null_snap_products_100knock_dbt_valid_from  [RUN]
15:10:02  4 of 4 PASS  not_null_snap_products_100knock_dbt_valid_from ........ [PASS]

15:10:02  Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

## 補足: 発展課題 — 「unique_key ごとに最新行は 1 行」 singular test

`dbt/tests/100-knock/topic-7/snap_one_active_per_key.sql`:

```sql
-- 失敗行 (= 同一 product_id で dbt_valid_to is null が 2 行以上) を返すクエリ
select
    product_id,
    count(*) as active_rows
from {{ ref('snap_products_100knock') }}
where dbt_valid_to is null
group by product_id
having count(*) > 1
```

dbt の singular test 規約: **「行が返ったら FAIL、空行なら PASS」**。
snapshot の不変条件として「最新行はキーごとに必ず 1 行」を機械的に保証できる。
本問の必須範囲ではないが、Topic ⑥ の Singular test と組み合わせて運用に進化させる
ステップ。

## 解説まとめ

- **machine-generated でも壊れる**: snapshot は dbt が自動生成するので人間が
  直接 INSERT することは少ないが、運用上は (a) 同一秒の race、(b) 手動 SQL での
  事故、(c) 上流 source の制約緩和 (PK 削除) などで壊れる余地がある。
  **「壊れない前提」を契約で機械化** するのが schema test の本質。
- **`dbt_scd_id` の unique が最重要**: SCD Type-2 の物理 PK が壊れたら、すべての
  point-in-time クエリが意味を失う。最初に貼るべき contract はこの 1 点。
- **「最新行は 1 行」契約**: 厳密にはこれが SCD Type-2 の本質的不変条件。Generic
  test では表現しきれないので singular test に切り出す (発展課題)。
- **snapshot にも description を**: `dbt docs generate` で snapshot もカタログに
  載る。「この snapshot は何の歴史か / どの strategy か / どの列を check するか」を
  description に書いておけば、後から見た人が理解できる。
- **MVP 側との並走**: 本リポジトリの MVP は `dbt/snapshots/snap_products.sql`
  (Ex.04) を持つが、そちらに schema.yml は無い。100-knock 側で schema test の
  習慣を先に身につけ、後から MVP に逆輸入するのも良い学び。
- **次の問への接続**: 7-6 では「snapshot を point-in-time クエリで使う」、
  7-7 では「snapshot を ref して下流モデルに組み込む」。schema test を貼った
  snapshot は **下流から信頼して ref できる** 存在になる、という流れに繋がる。
