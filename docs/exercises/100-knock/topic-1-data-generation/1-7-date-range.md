# 1-7: orders.order_date を 2025-01-01 〜 2026-04-30 の範囲で分散

## シナリオ

「直近 1 年分のデータ」のような曖昧な仕様は、後続トピックで `incremental` の高水位線を
書くときに困る。実行日次第で min/max が動く CSV を相手にすると、リプレイの再現性が崩れる。

ここでは **データ範囲の境界 `[2025-01-01, 2026-04-30]` を Python 側でハードコードして宣言** し、
10000 行の `order_date` をその区間に分散させる。これにより:

- `mart_daily_sales` の最古日 / 最新日が **コードで保証される**
- 後の incremental マートで `where order_date > {{ this.max(order_date) }}` を書くときの
  「初回ロードで 16 ヶ月分入る」前提が常に同じ
- グラフを描くと約 16 ヶ月分の時系列がきれいに広がる

## 学べること

- `Faker().date_between(start_date=..., end_date=...)` あるいは
  `start_date + timedelta(rng.randint(0, total_days))` で **範囲指定** する方法
- 日付を `datetime.today()` ではなく **ハードコード** する利点 (CI 再現性)
- 「distinct な日付値が十分多い = 分散している」を検証する `awk` / Python ワンライナー
- 後続の `incremental` 戦略の前提条件を生成段階で作っておく感覚

## 前提

- 1-1 / 1-2 (customers.csv / products.csv) が既に走っていること
- 1-4 / 1-5 / 1-6 を経てすでに orders.csv が存在しているはず (この問は再度 **上書き** する)
- `requirements.txt` の `Faker` / `pandas` がインストール済み
- 1-5 の `product_id × unit_price` 決定論ロジック、1-6 の `customer_id` 1..990 縛りは
  この問では **保たなくてよい** (1-7 は時間軸だけにフォーカス)

## 入力データ

`data/100-knock/topic-1/products.csv` (100 行 + ヘッダ) を読み込み、`unit_price` を
解決するのに使う。

## 課題

### Step 1: スクリプトを書く

`scripts/100-knock/topic-1/generate_1_7_date_range.py` を作る。

要件:

- 出力: `data/100-knock/topic-1/orders.csv` を **上書き** 再生成 (10000 行 + ヘッダ)
- 列: 1-4 と同じ `order_id, order_date, customer_id, product_id, store_id, quantity, unit_price`
- `order_date` は `2025-01-01` 〜 `2026-04-30` の **閉区間** で一様分布 (= `start + randint(0, total_days)` 形)
- 区間の境界値は **モジュール先頭の定数** (`START_DATE`, `END_DATE`) で宣言
- `customer_id` は 1..1000、`product_id` は 1..100、`store_id` は 1..20、`quantity` は 1..10
- `unit_price` は `products.csv` の `product_id` キーで決定論的に取る
- ISO 形式 (`YYYY-MM-DD`) で書き出す
- **シードは 207 で固定**

### Step 2: 実行 + 確認

```bash
python3 scripts/100-knock/topic-1/generate_1_7_date_range.py
```

期待表示例:

```
Generated data/100-knock/topic-1/orders.csv: 10000 rows
order_date range: 2025-01-01 .. 2026-04-30 (distinct=486)
```

範囲を目視:

```bash
awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | head -3
awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | tail -3
awk -F, 'NR>1 {print $2}' data/100-knock/topic-1/orders.csv | sort -u | wc -l
```

### Step 3: 採点

```bash
python3 scripts/grader/grade.py --grading-file docs/exercises/100-knock/topic-1-data-generation/1-7-date-range.grading.yaml
```

## 完了条件

- [ ] `scripts/100-knock/topic-1/generate_1_7_date_range.py` が存在する
- [ ] スクリプト単体実行が exit 0
- [ ] `data/100-knock/topic-1/orders.csv` が 10000 行 + ヘッダ
- [ ] `order_date` の最小値が `2025-01-01` (± 数日以内)
- [ ] `order_date` の最大値が `2026-04-30` (± 数日以内)
- [ ] `order_date` の distinct 値数が 200 以上 (= 16 ヶ月 ≒ 486 日のうち分散している)
- [ ] `order_date` 列に NULL なし

## ヒント (詰まったら)

- `Faker().date_between(start_date=date(2025,1,1), end_date=date(2026,4,30))` は内部で
  uniform random を使うので分散は十分。ただし返り値は `datetime.date`。文字列にするなら `.isoformat()`
- 最小値 / 最大値が必ず 2025-01-01 / 2026-04-30 になる保証は uniform では弱いが、10000 行も振れば
  端まで到達する確率はほぼ 1。採点はあくまで「**± 数日以内**」のレンジで評価する
- distinct 値数は理論上 16 ヶ月 ≒ 486 日。10000 行を 486 個に振ると鳩の巣的にほぼ全日カバー
  されるが、採点は「**>= 200**」と緩く取って学習者ミスを区別する
- `awk -F, 'NR>1 {print $2}' ... | sort -u | wc -l` のワンライナーは UNIX 流の distinct count。
  Python ワンライナーで書いてもよい

## 解答例

詳細は [`1-7-date-range.solution.md`](1-7-date-range.solution.md) を参照。
