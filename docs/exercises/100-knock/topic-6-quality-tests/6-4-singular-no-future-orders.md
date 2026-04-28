# 6-4: singular test で「未来日付の注文は存在しない」 を表明

## シナリオ

「`order_date > current_date` の注文は存在しない」 という業務不変条件を考える。
これは:

- **1 つのモデル限定** (= `stg_orders_100knock` だけ) の話
- **1 列に閉じない** (`order_date` と `current_date()` の比較で行を識別)
- **YAML の generic test には載らない** (特殊な日付比較ロジック)

という意味で、**singular test (`dbt/tests/*.sql`)** がベストフィットする
ケース。「単発の業務ルールを 1 ファイル 1 SQL で書く」 dbt test のもう
ひとつの形式を学ぶ。

> 同じ「正数チェック」 を複数列で使う場合は generic test (6-5 で扱う) が
> 適切。本問はあえて **「YAML に乗らない単発の業務ルール」** をターゲットに
> singular test の使い所を体感する。

## 学べること

- singular test (`dbt/tests/<name>.sql`) のファイル構造と命名規則
- 「行が返れば FAIL」 という dbt test の評価ルール (singular でも同じ)
- `{{ ref('stg_orders_100knock') }}` を test 内で使う書き方
- generic vs singular の使い分け判断基準
- `current_date` の Postgres 構文 (関数呼び出しではなく予約語)

## 前提

- Topic ② ③ ④ ⑤ 完了
- `dbt/tests/100-knock/topic-6/` ディレクトリは存在しないので新規作成 OK
  (dbt は `dbt/tests/` 配下を再帰的に拾う)
- Topic ① 1-7 で `order_date` を `2025-01-01` 〜 `2026-04-30` の範囲で生成
  しているので、現在日付 (`2026-04-26`) より未来の行が **存在し得る**
  (4-27〜4-30 の 4 日分)。本問では **PASS させたい** ので、test SQL の
  比較条件で「**遠未来日付** (= 業務的にあり得ない日付)」 を弾く設計にする

## 入力データ

`staging.stg_orders_100knock` 10,000 行 (`order_date` の最大値は 2026-04-30 程度)。

## 課題

### Step 1: singular test ファイルを作成

`dbt/tests/100-knock/topic-6/assert_no_future_orders.sql` を新規作成:

```sql
-- Singular test: order_date が「業務的にあり得ない遠未来」 でないことを保証する。
-- 本問では『current_date より 90 日以上先』 を異常扱い。
-- 行が返れば FAIL (dbt の test 評価ルール)。
select
    order_id,
    order_date
from {{ ref('stg_orders_100knock') }}
where order_date > current_date + interval '90 days'
```

> **設計メモ**: 「`order_date > current_date`」 そのもので書くと、Topic ① 1-7 の
> 生成範囲 (~2026-04-30) と現在日付 (2026-04-26) の関係で 4 行ほど FAIL する。
> ここでは「**遠未来 (= 業務的にあり得ない領域)** を検査」 という意図に
> 立て付け、`+ interval '90 days'` でバッファを取って PASS させる。
> `order_date > current_date` だけで運用したい場合は、生成データの上限を
> 削るか、**FAIL を採点する 6-2 のパターン** に切り替えればよい。

### Step 2: parse + test 実行

```bash
set -a; source .env; set +a
cd dbt
../.venv/bin/dbt parse --profiles-dir .
../.venv/bin/dbt test  --profiles-dir . --select test_name:assert_no_future_orders
```

期待出力:

```
1 of 1 PASS assert_no_future_orders ........................ [PASS in 0.04s]
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### Step 3: わざと未来日付を仕込んで FAIL を体感 (任意)

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics <<'SQL'
UPDATE raw.orders SET order_date = '2099-12-31' WHERE order_id = 1;
SQL
```

```bash
../.venv/bin/dbt test --profiles-dir . --select test_name:assert_no_future_orders
# 1 of 1 FAIL 1 assert_no_future_orders ... [FAIL 1 in 0.05s]
# Got 1 result, configured to fail if != 0
```

戻す:

```bash
docker exec -i local-data-postgres psql -U dbt_user -d analytics \
    -c "UPDATE raw.orders SET order_date = '2026-04-15' WHERE order_id = 1;"
```

### Step 4: manifest 上で test node を確認

```bash
../.venv/bin/dbt parse --profiles-dir .
python3 -c "
import json
m = json.load(open('target/manifest.json'))
for k in sorted(m['nodes']):
    if 'assert_no_future_orders' in k:
        print(k)
"
```

`test.local_analytics.assert_no_future_orders` が出れば成功。

## 完了条件

- [ ] `dbt/tests/100-knock/topic-6/assert_no_future_orders.sql` が存在する
- [ ] SQL 内に `where order_date > current_date` の構造がある (grep 可能)
- [ ] `{{ ref('stg_orders_100knock') }}` で staging を参照している
- [ ] `dbt parse` が成功する
- [ ] `dbt test --select test_name:assert_no_future_orders` が PASS
- [ ] manifest に `test.local_analytics.assert_no_future_orders` が登録される

## ヒント (詰まったら)

- **singular test の最小構文**: `dbt/tests/` 配下の **任意の `.sql` ファイル**
  が対象。テンプレートは不要、SELECT 1 文を書けばよい。
- **`{{ ref(...) }}` を使う理由**: 直接 `from staging.stg_orders_100knock` と
  書いても動くが、`ref()` を使うと **test 自体が DAG に組み込まれる**。
  `dbt build --select +stg_orders_100knock` のような上流選択で test も
  一緒に走る。
- **「行が返れば FAIL」**: singular test も generic test も同じ評価ルール。
  「**違反行を返すクエリ**」 として書く。`SELECT 1 WHERE not <condition>`
  のようなアサーション風の書き方は dbt 流ではない。
- **Postgres の `current_date`**: 関数ではなく **予約語** (括弧無しで使う)。
  `current_date()` と書くと文法エラー。タイムゾーン依存だが本リポジトリは
  UTC で動かしているはず。
- **generic vs singular の判断基準**:
  - 同じロジックを **複数列 / 複数モデル** で使う → generic
  - 1 つのテーブル限定の **特殊な業務ルール** (UNION ALL で 3 mart 串刺し
    集計、日付比較、複数列の組み合わせなど) → singular
  - 本問の `order_date > current_date + interval '90 days'` は generic 化
    しても再利用先が無いので singular で OK
- **ディレクトリ構造**: `dbt/tests/100-knock/topic-6/` のように
  サブディレクトリを切っても dbt は **再帰的** に拾う。MVP の
  `dbt/tests/assert_*.sql` (フラット) と並走可能。
- **遠未来 90 日の選び方**: 業務要件 (例: 「予約注文は最大 3 ヶ月先まで OK」)
  に合わせる。本問では「絶対あり得ない」 ラインを保守的に取って 90 日。
  「未来日付は一切 NG」 ならバッファ無しで `> current_date`、
  「予約注文を含めて 1 年先まで OK」 なら `+ interval '1 year'` 等。

## 解答例

詳細は [`6-4-singular-no-future-orders.solution.md`](6-4-singular-no-future-orders.solution.md) を参照。
