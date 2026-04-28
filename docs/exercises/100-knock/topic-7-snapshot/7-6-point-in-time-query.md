# 7-6: 過去のある時点を SQL 1 本で再現する (point-in-time クエリ)

## シナリオ

7-1〜7-5 で `snapshots.snap_products_100knock` を作り、v1 (初期 100 行) → v2
(20 商品の `unit_price` 改定) の **2 世代** の履歴を持たせた。
履歴を持っただけでは情報量が増えただけで、それを **取り出す** 手段が無いと
意味が無い。snapshot の本質的な価値は「**任意の時刻 `as_of` を指定したら、
その時刻に有効だった行が一意に決まる**」こと。これが point-in-time クエリ。

具体的には `dbt_valid_from <= as_of < coalesce(dbt_valid_to, '9999-12-31')`
の半開区間を where 句で書く。本問では `as_of = '2026-04-15'` 時点の
**全 product 価格表 (100 行)** を SQL 1 本で再現し、結果を md に記録する。

## 学べること

- snapshot の本質: 「履歴を持つ」ではなく「**過去の任意時点を再現できる**」こと
- `dbt_valid_from` / `dbt_valid_to` の **半開区間** `[from, to)` 規約と、
  `dbt_valid_to IS NULL` を「+∞」として扱う `coalesce` パターン
- `as_of` をパラメータ化すれば、**監査** (例: 4/15 時点の単価で再計算) や
  **障害調査** (例: ある日の集計値を再現) に直結
- 結果を md に残す = レビュー / 振り返り可能なエビデンスにする

## 前提

- 7-1 〜 7-5 完了 (`snapshots.snap_products_100knock` が **120 行** 持っている:
  v1 100 行のうち 20 行が expired、v2 で 20 行追加された状態)
- `psql` が `analytics` DB に接続できる
- 学習者が **2026-04-15** が「v1 が有効、v2 はまだ来ていない」時点だと
  認識している (= 7-2 の v2 投入は今日 = 2026-04-26 想定)

## 入力データ

不要。`snapshots.snap_products_100knock` を直接 SELECT する。

## 課題

### Step 1: point-in-time クエリを書いて実行

```bash
docker exec -i local-data-postgres psql -U analytics_user -d analytics <<'SQL'
SELECT
    product_id,
    product_name,
    category,
    unit_price,
    dbt_valid_from,
    dbt_valid_to
FROM snapshots.snap_products_100knock
WHERE dbt_valid_from <= '2026-04-15'
  AND ('2026-04-15' < dbt_valid_to OR dbt_valid_to IS NULL)
ORDER BY product_id;
SQL
```

期待: **100 行**ちょうど (= 全 product を、`as_of='2026-04-15'` 時点の
有効 1 行に絞り込んだ結果)。

### Step 2: 結果を md に記録

`docs/exercises/100-knock/topic-7-snapshot/point-in-time-result.md` を新規作成し、
以下を含める:

- 上の SQL (そのまま貼る)
- 実行結果の **行数** と **抜粋** (最初の 5 行と最後の 1 行など)
- 「なぜ 100 行 ぴったりになるのか」の 1〜2 行解説
  (= 全 product につき `as_of` 時点の有効版が 1 行ずつ出るから)

形式自由、30〜60 行を目安。

### Step 3: 採点

```bash
python3 scripts/grader/grade.py \
    --grading-file docs/exercises/100-knock/topic-7-snapshot/7-6-point-in-time-query.grading.yaml
```

## 完了条件

- [ ] `point-in-time-result.md` が存在し、上記 SQL とその結果が記録されている
- [ ] 採点で同じ SQL を直接 DB に投げて 100 行返ることが確認できる

## ヒント (詰まったら)

- **行数が 100 にならない**: 半開区間の不等号を間違えていないか確認。
  `dbt_valid_from <= as_of` (= or <)、 `as_of < dbt_valid_to` (or NULL) が正解。
  両方 `<=` にすると境界値で 2 行返る瞬間がある。
- **`as_of` の型**: snapshot のメタ列は timestamp (with timezone) なので、
  `'2026-04-15'` は date リテラルとして暗黙キャストされる。厳密に書くなら
  `'2026-04-15 00:00:00+00'::timestamptz`。
- **v2 で更新された 20 商品の挙動**: 4/15 時点では v2 はまだ存在しない
  (v2 投入は 7-2 で今日 = 4/26 想定)。よって v1 の expired 行
  (`dbt_valid_to` が今日のもの) が `4/15 < dbt_valid_to` を満たし、有効と判定される。
- **「+∞ の表現」を `9999-12-31` で書きたい**: `coalesce(dbt_valid_to, '9999-12-31')`
  でも同じ。本問は `OR dbt_valid_to IS NULL` 形を採用したが好み。

## 解答例

詳細は [`7-6-point-in-time-query.solution.md`](7-6-point-in-time-query.solution.md) を参照。
